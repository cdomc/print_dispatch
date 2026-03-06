from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pypdf import PdfWriter

from print_dispatch.ingest.outlook_ingest import ingest_outlook_orders, parse_email_body, parse_paths_field


def _mm_to_pt(value_mm: float) -> float:
    return value_mm * 72.0 / 25.4


def _make_pdf(path: Path, width_mm: float = 297, height_mm: float = 420) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=_mm_to_pt(width_mm), height=_mm_to_pt(height_mm))
    with path.open("wb") as f:
        writer.write(f)


class FakeCategory:
    def __init__(self, name: str):
        self.Name = name


class FakeCategories(list):
    def Add(self, name: str) -> None:
        self.append(FakeCategory(name))


class FakeSession:
    def __init__(self):
        self.Categories = FakeCategories()


class FakeApplication:
    def __init__(self):
        self.Session = FakeSession()


class FakeMessage:
    def __init__(self, *, subject: str, body: str, entry_id: str, received_time: datetime):
        self.Subject = subject
        self.Body = body
        self.EntryID = entry_id
        self.ReceivedTime = received_time
        self.Categories = ""
        self.UnRead = True
        self._saved = False

    def Save(self) -> None:
        self._saved = True


class FakeItems(list):
    def Sort(self, *_args, **_kwargs):
        self.sort(key=lambda item: item.ReceivedTime, reverse=True)


class FakeFolderCollection(dict):
    def __call__(self, name: str):
        return self[name]


class FakeInbox:
    def __init__(self, items):
        self.Items = FakeItems(items)


class FakeStore:
    def __init__(self, name: str, inbox: FakeInbox):
        self.Name = name
        self._folders = FakeFolderCollection({"Inbox": inbox, "Skrzynka odbiorcza": inbox})

    def Folders(self, name: str):
        return self._folders[name]


class FakeNamespace:
    def __init__(self, stores):
        self.Folders = stores
        self.Application = FakeApplication()


def test_parse_paths_field_supports_bracketed_and_multiline():
    assert parse_paths_field("['C:/a';'C:/b']") == ["C:/a", "C:/b"]
    assert parse_paths_field("C:/a\nC:/b") == ["C:/a", "C:/b"]


def test_parse_email_body_extracts_expected_fields():
    body = """
    Nazwa tematu [Temat ABC]
    Rodzaj drukowanego dokumentu [Plan]
    osoba zlecająca i odpowiedzialna [Jan Kowalski]
    ilość egzemplarzy [3]
    ścieżka zawierająca folder z pdf ['C:/pdf/in_1';'C:/pdf/in_2']
    """

    parsed = parse_email_body(body)

    assert parsed["topic_name"] == "Temat ABC"
    assert parsed["doc_type"] == "Plan"
    assert parsed["person"] == "Jan Kowalski"
    assert parsed["copies"] == "3"
    assert parsed["paths"] == ["C:/pdf/in_1", "C:/pdf/in_2"]


def test_ingest_outlook_orders_smoke_with_fake_namespace(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)
    _make_pdf(source_dir / "doc.pdf")

    body = (
        "Nazwa tematu [Outlook temat]\n"
        "Rodzaj drukowanego dokumentu [Plan]\n"
        "osoba zlecająca i odpowiedzialna [Anna]\n"
        "ilość egzemplarzy [2]\n"
        f"ścieżka zawierająca folder z pdf ['{source_dir}']\n"
    )

    message = FakeMessage(
        subject="Nowe_Zlecenie_Wydruku_123 - test",
        body=body,
        entry_id="entry-1",
        received_time=datetime(2026, 3, 6, 9, 30, 0),
    )
    store = FakeStore("ploterownia@value-eng.pl", FakeInbox([message]))
    namespace = FakeNamespace([store])

    orders_root = tmp_path / "orders"
    processed_ids_file = tmp_path / "processed_ids.json"

    manifests = ingest_outlook_orders(
        orders_root=orders_root,
        processed_ids_file=processed_ids_file,
        namespace=namespace,
    )

    assert len(manifests) == 1
    manifest = manifests[0]
    assert manifest.source_type == "OUTLOOK"
    assert manifest.source_ref == "entry-1"
    assert manifest.source_paths == [str(source_dir)]
    assert manifest.copies_default == 2

    manifest_path = orders_root / manifest.order_id / "manifest.json"
    assert manifest_path.exists()
    assert (orders_root / manifest.order_id / "persistent" / "A4_REVIEW").exists()
    assert (orders_root / manifest.order_id / "persistent" / "CUSTOM_REVIEW").exists()

    assert "Processed" in message.Categories
    assert message.UnRead is False
    assert message._saved is True

    processed_ids = json.loads(processed_ids_file.read_text(encoding="utf-8"))
    assert "entry-1" in processed_ids

    # Dedup on second run.
    manifests_second = ingest_outlook_orders(
        orders_root=orders_root,
        processed_ids_file=processed_ids_file,
        namespace=namespace,
    )
    assert manifests_second == []
