"""Ingest orders from Outlook mailbox into manifest pipeline."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ..domain.models import Manifest
from ..manifest_io import save_manifest
from ..prepare.materialize_order import materialize_order

TARGET_ACCOUNT = "ploterownia@value-eng.pl"
SUBJECT_KEYWORD = "Nowe_Zlecenie_Wydruku_123"
PROCESSED_CATEGORY = "Processed"

DEFAULT_ORDERS_ROOT = Path("data/orders")
DEFAULT_PROCESSED_IDS_FILE = Path("data/processed_ids.json")


def load_processed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_processed_ids(ids_set: set[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(ids_set), ensure_ascii=False, indent=2), encoding="utf-8")


def parse_paths_field(raw: str | None) -> list[str]:
    def _clean(value: str) -> str:
        return value.strip().strip('"').strip("'").strip()

    s = (raw or "").strip()
    if not s:
        return []
    if s.startswith("[") and s.endswith("]"):
        quoted = re.findall(r"[\"']([^\"']+)[\"']", s)
        if quoted:
            return [_clean(p) for p in quoted if _clean(p)]
        return [_clean(p) for p in s[1:-1].split(";") if _clean(p)]
    return [_clean(p) for p in re.split(r"[;\n\r]+", s) if _clean(p)]


def parse_email_body(body: str) -> dict[str, Any]:
    patterns = {
        "topic_name": r"Nazwa tematu.*?\[([^\]]+)\]",
        "doc_type": r"Rodzaj drukowanego dokumentu.*?\[([^\]]+)\]",
        "person": r"osoba zlecająca i odpowiedzialna.*?\[([^\]]+)\]",
        "copies": r"ilość egzemplarzy.*?\[([^\]]+)\]",
    }
    result = {
        key: (match.group(1).strip() if (match := re.search(pattern, body, re.IGNORECASE | re.DOTALL)) else None)
        for key, pattern in patterns.items()
    }
    path_match = re.search(r"ścieżka zawierająca folder z pdf.*?\[([^\]]+)\]", body, re.IGNORECASE | re.DOTALL)
    result["paths"] = parse_paths_field(path_match.group(1).strip() if path_match else None)
    return result


def _to_int_copies(value: str | None) -> int:
    if value is None:
        return 1
    match = re.search(r"\d+", value)
    if not match:
        return 1
    return max(1, int(match.group(0)))


def _get_namespace(namespace: Any | None) -> Any | None:
    if namespace is not None:
        return namespace
    try:
        import win32com.client  # type: ignore[import-not-found]

        return win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    except Exception:
        return None


def _find_store(namespace: Any, account_email: str) -> Any | None:
    for store in getattr(namespace, "Folders", []):
        if account_email.lower() in str(getattr(store, "Name", "")).lower():
            return store
    return None


def _find_inbox(store: Any) -> Any | None:
    for name in ("Inbox", "Skrzynka odbiorcza"):
        try:
            return store.Folders(name)
        except Exception:
            continue
    return None


def _iter_messages(inbox: Any) -> list[Any]:
    items = inbox.Items
    try:
        items.Sort("[ReceivedTime]", True)
    except Exception:
        pass
    return list(items)


def _ensure_category(namespace: Any, name: str = PROCESSED_CATEGORY) -> None:
    try:
        categories = namespace.Application.Session.Categories
        if not any(cat.Name == name for cat in categories):
            categories.Add(name)
    except Exception:
        return


def mark_processed(message: Any, namespace: Any) -> bool:
    try:
        _ensure_category(namespace, PROCESSED_CATEGORY)
        categories = (getattr(message, "Categories", "") or "").split(";")
        categories = [c.strip() for c in categories if c.strip()]
        if PROCESSED_CATEGORY not in categories:
            categories.append(PROCESSED_CATEGORY)
        message.Categories = ";".join(categories)
        message.UnRead = False
        message.Save()
        return True
    except Exception:
        return False


def _is_processed_message(entry_id: str, message: Any, processed_ids: set[str]) -> bool:
    if entry_id in processed_ids:
        return True
    categories = (getattr(message, "Categories", "") or "").split(";")
    return any(c.strip() == PROCESSED_CATEGORY for c in categories)


def _build_outlook_manifest(data: dict[str, Any], orders_root: Path) -> Manifest:
    order_id = f"outlook-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    order_dir = orders_root / order_id
    received = data["received"]
    topic = data.get("topic_name") or "Ręczne"
    person = data.get("person") or "Ręczne"

    return Manifest(
        order_id=order_id,
        received_time=received,
        source_type="OUTLOOK",
        source_paths=list(data.get("paths") or []),
        source_ref=data["entry_id"],
        person=person,
        topic=topic,
        copies_default=_to_int_copies(data.get("copies")),
        persistent_dir=str(order_dir / "persistent"),
        temp_dir=str(order_dir / "temp"),
        state="ZLECONE",
        state_timestamps={"ZLECONE": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
    )


def ingest_outlook_orders(
    *,
    orders_root: Path = DEFAULT_ORDERS_ROOT,
    processed_ids_file: Path = DEFAULT_PROCESSED_IDS_FILE,
    namespace: Any | None = None,
) -> list[Manifest]:
    ns = _get_namespace(namespace)
    if ns is None:
        return []

    store = _find_store(ns, TARGET_ACCOUNT)
    if store is None:
        return []

    inbox = _find_inbox(store)
    if inbox is None:
        return []

    processed_ids = load_processed_ids(processed_ids_file)
    created: list[Manifest] = []

    for message in _iter_messages(inbox):
        subject = str(getattr(message, "Subject", "") or "")
        if SUBJECT_KEYWORD.lower() not in subject.lower():
            continue

        entry_id = str(getattr(message, "EntryID", "") or "")
        if not entry_id:
            continue

        if _is_processed_message(entry_id, message, processed_ids):
            continue

        try:
            received_obj = getattr(message, "ReceivedTime", datetime.now())
            received = received_obj.strftime("%Y-%m-%d %H:%M:%S")
            parsed = parse_email_body(str(getattr(message, "Body", "") or ""))
            parsed.update({"received": received, "entry_id": entry_id})

            manifest = _build_outlook_manifest(parsed, orders_root)
            manifest_path = orders_root / manifest.order_id / "manifest.json"
            materialize_order(manifest, manifest_path=manifest_path)

            # Ensure manifest exists even if materialize path handling changes later.
            save_manifest(manifest_path, manifest)

            if mark_processed(message, ns):
                processed_ids.add(entry_id)
            created.append(manifest)
        except Exception:
            continue

    save_processed_ids(processed_ids, processed_ids_file)
    return created
