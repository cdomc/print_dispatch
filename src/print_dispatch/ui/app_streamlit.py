"""Streamlit UI for print-dispatch, aligned with ui_contract_v1."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

import streamlit as st

# Allow running via `streamlit run src/print_dispatch/ui/app_streamlit.py`.
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from print_dispatch.dispatch.build_groups import build_groups
from print_dispatch.dispatch.queue_depth import FakeQueueDepth
from print_dispatch.domain.models import Manifest
from print_dispatch.execute.executor import commit_print
from print_dispatch.ingest.outlook_ingest import ingest_outlook_orders
from print_dispatch.manifest_io import load_manifest, save_manifest
from print_dispatch.prepare.materialize_order import materialize_order

APP_DATA_DIR = Path("data/orders")
STATE_ORDER = ["ZLECONE", "W_TRAKCIE", "WYDRUKOWANE", "ZAKONCZONE"]
STATE_LABELS = {
    "ZLECONE": "Zlecone",
    "W_TRAKCIE": "W trakcie",
    "WYDRUKOWANE": "Wydrukowane",
    "ZAKONCZONE": "Zakończone",
}


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _order_dir(order_id: str) -> Path:
    return APP_DATA_DIR / order_id


def _manifest_path(order_id: str) -> Path:
    return _order_dir(order_id) / "manifest.json"


def _init_state() -> None:
    if "selected_order_id" not in st.session_state:
        st.session_state.selected_order_id = None
    if "confirm_delete_temp_for" not in st.session_state:
        st.session_state.confirm_delete_temp_for = None
    if "show_manual_form" not in st.session_state:
        st.session_state.show_manual_form = False
    if "confirm_delete_order_for" not in st.session_state:
        st.session_state.confirm_delete_order_for = None


def _load_all_manifests() -> list[Manifest]:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifests: list[Manifest] = []
    for manifest_file in sorted(APP_DATA_DIR.glob("*/manifest.json")):
        try:
            manifests.append(load_manifest(manifest_file))
        except Exception:
            continue
    return sorted(manifests, key=lambda m: m.received_time, reverse=True)


def _persist_manifest(manifest: Manifest) -> None:
    save_manifest(_manifest_path(manifest.order_id), manifest)


def _is_multi_source_file(manifest: Manifest, page_index: int) -> bool:
    target = manifest.printable_pages[page_index]
    count = 0
    for page in manifest.printable_pages:
        if page.file_original_name == target.file_original_name and page.file_original_path == target.file_original_path:
            count += 1
    return count > 1


def _page_line(manifest: Manifest, page_index: int) -> str:
    page = manifest.printable_pages[page_index]
    page_suffix = f" | PAGE={page.page_number}" if _is_multi_source_file(manifest, page_index) else ""
    return f"FILE={page.file_original_name}{page_suffix} | COPIES={page.copies}"


def _auto_counters(manifest: Manifest) -> dict[str, int]:
    counters = Counter()
    for page in manifest.printable_pages:
        if page.profile_id == "P297_A3_STD":
            counters["Auto 297 A3"] += 1
        elif page.profile_id == "P297_A3_LONG_3000_TRIM":
            counters["Auto 297 A3Long"] += 1
        elif page.profile_id == "P420_A2_LONG_3000_TRIM":
            counters["Auto 420 Long"] += 1
        elif page.profile_id == "P594_A1_LONG_3000_TRIM":
            counters["Auto 594 Long"] += 1
        elif page.profile_id == "P841_A0_LONG_3000_TRIM":
            counters["Auto 841 Long"] += 1
    return counters


def _count_review(manifest: Manifest, bucket: str) -> int:
    return sum(1 for item in manifest.review_items if item.bucket == bucket)


def _all_groups_completed(manifest: Manifest) -> bool:
    return bool(manifest.groups) and all(g.status == "COMPLETED" for g in manifest.groups)


def _run_dispatch(manifest: Manifest) -> None:
    build_groups(manifest, FakeQueueDepth({"Ploter_A_297mm": 0, "Ploter_E_297mm": 0}))
    commit_print(manifest)
    if _all_groups_completed(manifest):
        manifest.state = "WYDRUKOWANE"
        manifest.state_timestamps["WYDRUKOWANE"] = _now_str()
    _persist_manifest(manifest)


def _delete_order(manifest: Manifest) -> None:
    shutil.rmtree(_order_dir(manifest.order_id), ignore_errors=True)
    if st.session_state.selected_order_id == manifest.order_id:
        st.session_state.selected_order_id = None


def _open_path(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        st.info(f"Ścieżka: {path}")


def _resolve_user_source_path(raw_path: str) -> tuple[Path | None, str]:
    cleaned = raw_path.strip().strip('"').strip("'")
    cleaned = os.path.expanduser(os.path.expandvars(cleaned))
    if not cleaned:
        return None, ""

    candidates: list[Path] = [Path(cleaned)]
    # When app runs in Linux/WSL and user pastes Windows path.
    if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", cleaned):
        drive = cleaned[0].lower()
        tail = cleaned[2:].replace("\\", "/").lstrip("/")
        candidates.append(Path(f"/mnt/{drive}/{tail}"))

    for candidate in candidates:
        if candidate.exists():
            return candidate, cleaned

    return None, cleaned


def _create_manual_order(
    source_path: str,
    copies: int,
    person: str,
    topic: str,
    sposob_opracowania: str | None,
    auto_print: bool,
) -> None:
    order_id = f"ord-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    persistent_dir = _order_dir(order_id) / "persistent"
    temp_dir = _order_dir(order_id) / "temp"

    manifest = Manifest(
        order_id=order_id,
        received_time=_now_str(),
        source_type="MANUAL",
        source_paths=[source_path],
        source_ref=f"manual:{datetime.now().strftime('%Y%m%d%H%M%S')}",
        person=person or "Ręczne",
        topic=topic or "Ręczne",
        copies_default=max(1, copies),
        sposob_opracowania=sposob_opracowania,
        persistent_dir=str(persistent_dir),
        temp_dir=str(temp_dir),
        state="ZLECONE",
        state_timestamps={"ZLECONE": _now_str()},
    )

    materialize_order(manifest, manifest_path=_manifest_path(order_id))
    if auto_print and manifest.printable_pages:
        _run_dispatch(manifest)
    else:
        _persist_manifest(manifest)

    st.session_state.selected_order_id = order_id


def _check_outlook() -> list[Manifest]:
    processed_ids_file = APP_DATA_DIR.parent / "processed_ids.json"
    manifests = ingest_outlook_orders(
        orders_root=APP_DATA_DIR,
        processed_ids_file=processed_ids_file,
    )
    if manifests:
        st.session_state.selected_order_id = manifests[0].order_id
    return manifests


def _render_header_actions() -> None:
    col_manual, col_outlook = st.columns([1, 1])
    if col_manual.button("Nowe zlecenie ręczne", use_container_width=True):
        st.session_state.show_manual_form = not st.session_state.show_manual_form
    if col_outlook.button("Sprawdź Outlook", use_container_width=True):
        created = _check_outlook()
        if created:
            st.success(f"Dodano z Outlook: {len(created)}")
        else:
            st.info("Brak nowych zleceń Outlook.")
        st.rerun()


def _render_manual_intake() -> None:
    if not st.session_state.show_manual_form:
        return

    with st.container(border=True):
        st.markdown("### Formularz ręczny")
        with st.form("manual_intake"):
            source_path = st.text_input("Ścieżka (plik/folder)")
            copies = st.number_input("Kopie", min_value=1, value=1, step=1)
            person = st.text_input("Osoba", value="Ręczne")
            topic = st.text_input("Temat", value="Ręczne")
            sposob_choice = st.selectbox("Sposób opracowania", options=["(brak)", "Zeszyt", "Teczka"])
            col_a, col_b = st.columns(2)
            create_clicked = col_a.form_submit_button("Utwórz zlecenie")
            create_print_clicked = col_b.form_submit_button("Utwórz i drukuj automatyczne")

    if create_clicked or create_print_clicked:
        if not source_path.strip():
            st.error("Ścieżka jest wymagana.")
            return
        source, normalized = _resolve_user_source_path(source_path)
        if source is None:
            st.error(f"Ścieżka nie istnieje: {normalized}")
            if os.name != "nt":
                st.caption("Jeśli podajesz ścieżkę Windows (np. C:\\...), uruchom aplikację natywnie na Windows albo użyj /mnt/<dysk>/...")
            return
        sposob = None if sposob_choice == "(brak)" else sposob_choice
        _create_manual_order(
            source_path=str(source),
            copies=int(copies),
            person=person,
            topic=topic,
            sposob_opracowania=sposob,
            auto_print=bool(create_print_clicked),
        )
        st.success("Utworzono zlecenie.")
        st.rerun()


def _render_order_card(manifest: Manifest) -> None:
    auto_counts = _auto_counters(manifest)
    a4_count = _count_review(manifest, "A4_REVIEW")
    custom_count = _count_review(manifest, "CUSTOM_REVIEW")

    with st.container(border=True):
        st.markdown(f"**{manifest.person}**")
        st.write(f"Temat: {manifest.topic}")
        st.write(f"Kopie: {manifest.copies_default}")
        st.write(f"Sposób opracowania: {manifest.sposob_opracowania or '(brak)'}")
        st.caption(
            " | ".join(
                [
                    f"A4_REVIEW: {a4_count}",
                    f"CUSTOM_REVIEW: {custom_count}",
                    f"Auto 297 A3: {auto_counts.get('Auto 297 A3', 0)}",
                    f"Auto 297 A3Long: {auto_counts.get('Auto 297 A3Long', 0)}",
                    f"Auto 420 Long: {auto_counts.get('Auto 420 Long', 0)}",
                    f"Auto 594 Long: {auto_counts.get('Auto 594 Long', 0)}",
                    f"Auto 841 Long: {auto_counts.get('Auto 841 Long', 0)}",
                ]
            )
        )

        if manifest.state in {"ZLECONE", "W_TRAKCIE"} and manifest.printable_pages:
            if st.button("Drukuj automatyczne", key=f"print-{manifest.order_id}"):
                _run_dispatch(manifest)
                st.success("Wykonano plan automatyczny.")
                st.rerun()

        if a4_count > 0:
            if st.button("Otwórz A4_REVIEW", key=f"open-a4-{manifest.order_id}"):
                _open_path(Path(manifest.persistent_dir) / "A4_REVIEW")
        if custom_count > 0:
            if st.button("Otwórz CUSTOM_REVIEW", key=f"open-custom-{manifest.order_id}"):
                _open_path(Path(manifest.persistent_dir) / "CUSTOM_REVIEW")

        if manifest.state == "WYDRUKOWANE":
            disabled = manifest.sposob_opracowania is None
            if st.button(
                "Potwierdź zakończenie",
                key=f"finish-{manifest.order_id}",
                disabled=disabled,
                help="Uzupełnij sposób opracowania, aby zakończyć." if disabled else None,
            ):
                manifest.state = "ZAKONCZONE"
                manifest.state_timestamps["ZAKONCZONE"] = _now_str()
                _persist_manifest(manifest)
                st.rerun()

        if manifest.state == "ZAKONCZONE":
            if st.session_state.confirm_delete_temp_for == manifest.order_id:
                st.warning("Potwierdź usunięcie TEMP")
                col1, col2 = st.columns(2)
                if col1.button("Tak, usuń TEMP", key=f"delete-temp-confirm-{manifest.order_id}"):
                    if manifest.temp_dir:
                        shutil.rmtree(manifest.temp_dir, ignore_errors=True)
                    st.session_state.confirm_delete_temp_for = None
                    st.success("Usunięto TEMP.")
                    st.rerun()
                if col2.button("Anuluj", key=f"delete-temp-cancel-{manifest.order_id}"):
                    st.session_state.confirm_delete_temp_for = None
                    st.rerun()
            else:
                if st.button("Usuń TEMP", key=f"delete-temp-{manifest.order_id}"):
                    st.session_state.confirm_delete_temp_for = manifest.order_id
                    st.rerun()

        if st.session_state.confirm_delete_order_for == manifest.order_id:
            st.warning("Potwierdź usunięcie zlecenia")
            col_del1, col_del2 = st.columns(2)
            if col_del1.button("Tak, usuń zlecenie", key=f"delete-order-confirm-{manifest.order_id}"):
                _delete_order(manifest)
                st.session_state.confirm_delete_order_for = None
                st.success("Usunięto zlecenie.")
                st.rerun()
            if col_del2.button("Anuluj", key=f"delete-order-cancel-{manifest.order_id}"):
                st.session_state.confirm_delete_order_for = None
                st.rerun()
        else:
            if st.button("Usuń zlecenie", key=f"delete-order-{manifest.order_id}"):
                st.session_state.confirm_delete_order_for = manifest.order_id
                st.rerun()

        if st.button("Szczegóły", key=f"details-{manifest.order_id}"):
            st.session_state.selected_order_id = manifest.order_id
            st.rerun()


def _render_kanban(manifests: list[Manifest]) -> None:
    columns = st.columns(4)
    for idx, state in enumerate(STATE_ORDER):
        with columns[idx]:
            st.subheader(STATE_LABELS[state])
            state_orders = [m for m in manifests if m.state == state]
            if not state_orders:
                st.caption("Brak zleceń")
            for manifest in state_orders:
                _render_order_card(manifest)


def _render_review_details(manifest: Manifest) -> None:
    st.markdown("### Review (manual)")
    a4 = [item for item in manifest.review_items if item.bucket == "A4_REVIEW"]
    custom = [item for item in manifest.review_items if item.bucket == "CUSTOM_REVIEW"]

    st.write("A4_REVIEW")
    if not a4:
        st.caption("Brak")
    for item in a4:
        st.write(f"- {item.file_original_name} ({item.reason})")

    st.write("CUSTOM_REVIEW")
    if not custom:
        st.caption("Brak")
    for item in custom:
        st.write(f"- {item.file_original_name} ({item.reason})")


def _render_groups_details(manifest: Manifest) -> None:
    st.markdown("### Automat - grupy druku")
    if not manifest.groups:
        st.caption("Brak grup")
        return

    for group in manifest.groups:
        with st.expander(
            f"{group.group_id} | queue={group.target_queue} | profile={group.profile_id} | "
            f"items={len(group.item_refs)} | status={group.status}",
            expanded=False,
        ):
            for ref in group.item_refs:
                st.write(f"- {_page_line(manifest, ref)}")


def _render_batch_297_details(manifest: Manifest) -> None:
    st.markdown("### Plan 297 (paczki)")
    plan = manifest.batch_plan_297
    if plan is None:
        st.caption("Brak planu 297")
        return

    st.write(f"qA={plan.qA} | qE={plan.qE} | start={plan.start_printer} | K={plan.K}")
    for batch in plan.batches:
        with st.expander(
            f"Batch {batch.batch_index} | queue={batch.target_queue} | status={batch.status}",
            expanded=False,
        ):
            for ref in batch.item_refs:
                st.write(f"- {_page_line(manifest, ref)}")


def _render_details_panel(manifests: list[Manifest]) -> None:
    selected_id = st.session_state.selected_order_id
    selected = next((m for m in manifests if m.order_id == selected_id), None)
    st.divider()
    st.subheader("Szczegóły")

    if selected is None:
        st.caption("Wybierz zlecenie: kliknij 'Szczegóły' na kafelku.")
        return

    st.write(f"Order ID: {selected.order_id}")
    st.write(f"Stan: {selected.state}")
    st.write(f"Persistent dir: {selected.persistent_dir}")
    st.write(f"Temp dir: {selected.temp_dir}")

    _render_review_details(selected)
    _render_groups_details(selected)
    _render_batch_297_details(selected)


def main() -> None:
    st.set_page_config(page_title="Print Dispatch", layout="wide")
    _init_state()

    st.title("Print Dispatch")
    _render_header_actions()
    _render_manual_intake()

    manifests = _load_all_manifests()
    _render_kanban(manifests)
    _render_details_panel(manifests)


if __name__ == "__main__":
    main()
