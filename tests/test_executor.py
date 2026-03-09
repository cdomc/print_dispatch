from __future__ import annotations

import pytest

from print_dispatch.config import ExecutionMode
from print_dispatch.domain.models import Group, Manifest, PrintablePage
from print_dispatch.execute.dry_run import DryRunSubmitter
from print_dispatch.execute.executor import commit_print


def _base_manifest(tmp_path) -> Manifest:
    return Manifest(
        order_id="ord-exec-1",
        received_time="2026-03-06 11:00:00",
        source_type="MANUAL",
        source_paths=[str(tmp_path / "in")],
        source_ref="manual:20260306110000",
        person="Test",
        topic="Exec",
        copies_default=1,
        persistent_dir=str(tmp_path / "persistent"),
        temp_dir=str(tmp_path / "temp"),
    )


def test_commit_print_logs_file_and_page_for_multi_page_only(tmp_path):
    manifest = _base_manifest(tmp_path)
    manifest.printable_pages = [
        PrintablePage(
            file_original_name="multi.pdf",
            file_original_path="C:/in/multi.pdf",
            page_number=1,
            width_key=297,
            profile_id="P297_A3_STD",
            target_queue="Ploter_A_297mm",
            copies=2,
        ),
        PrintablePage(
            file_original_name="multi.pdf",
            file_original_path="C:/in/multi.pdf",
            page_number=2,
            width_key=297,
            profile_id="P297_A3_STD",
            target_queue="Ploter_A_297mm",
            copies=2,
        ),
        PrintablePage(
            file_original_name="single.pdf",
            file_original_path="C:/in/single.pdf",
            page_number=1,
            width_key=420,
            profile_id="P420_A2_LONG_3000_TRIM",
            target_queue="Ploter_B_420mm",
            copies=1,
        ),
    ]
    manifest.groups = [
        Group(
            group_id="g-std-a",
            target_queue="Ploter_A_297mm",
            profile_id="P297_A3_STD",
            item_refs=[0, 1],
            status="READY",
        ),
        Group(
            group_id="g-420",
            target_queue="Ploter_B_420mm",
            profile_id="P420_A2_LONG_3000_TRIM",
            item_refs=[2],
            status="READY",
        ),
    ]

    commit_print(manifest)

    log_path = tmp_path / "persistent" / "dispatch.log"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()

    assert len(lines) == 3
    assert "FILE=multi.pdf | PAGE=1" in lines[0]
    assert "FILE=multi.pdf | PAGE=2" in lines[1]
    assert "FILE=single.pdf" in lines[2]
    assert "PAGE=" not in lines[2]

    assert manifest.state == "W_TRAKCIE"
    assert all(g.status == "COMPLETED" for g in manifest.groups)
    assert all(p.status == "SUBMITTED" for p in manifest.printable_pages)


def test_commit_print_allows_retry_after_failure(tmp_path):
    manifest = _base_manifest(tmp_path)
    manifest.printable_pages = [
        PrintablePage(
            file_original_name="retry.pdf",
            file_original_path="C:/in/retry.pdf",
            page_number=1,
            width_key=297,
            profile_id="P297_A3_STD",
            target_queue="Ploter_A_297mm",
            copies=1,
        )
    ]
    manifest.groups = [
        Group(
            group_id="g-retry",
            target_queue="Ploter_A_297mm",
            profile_id="P297_A3_STD",
            item_refs=[0],
            status="READY",
        )
    ]

    submitter = DryRunSubmitter(
        fail_once_keys={("retry.pdf", 1, "Ploter_A_297mm")}
    )

    commit_print(manifest, submitter=submitter)
    assert manifest.groups[0].status == "FAILED"
    assert manifest.printable_pages[0].status == "FAILED"

    commit_print(manifest, submitter=submitter)
    assert manifest.groups[0].status == "COMPLETED"
    assert manifest.printable_pages[0].status == "SUBMITTED"


def test_commit_print_real_requires_temp_dir(tmp_path):
    manifest = _base_manifest(tmp_path)
    manifest.temp_dir = None
    manifest.printable_pages = [
        PrintablePage(
            file_original_name="r.pdf",
            file_original_path="C:/in/r.pdf",
            page_number=1,
            width_key=297,
            profile_id="P297_A3_STD",
            target_queue="Ploter_A_297mm",
            copies=1,
        )
    ]
    manifest.groups = [
        Group(
            group_id="g-real",
            target_queue="Ploter_A_297mm",
            profile_id="P297_A3_STD",
            item_refs=[0],
            status="READY",
        )
    ]

    with pytest.raises(ValueError):
        commit_print(manifest, execution_mode=ExecutionMode.REAL)


def test_commit_print_real_with_injected_submitter(tmp_path):
    class FakeRealSubmitter:
        def __init__(self):
            self.calls = 0

        def submit_page(self, _page):
            self.calls += 1

    manifest = _base_manifest(tmp_path)
    manifest.printable_pages = [
        PrintablePage(
            file_original_name="r.pdf",
            file_original_path="C:/in/r.pdf",
            page_number=1,
            width_key=297,
            profile_id="P297_A3_STD",
            target_queue="Ploter_A_297mm",
            copies=1,
        )
    ]
    manifest.groups = [
        Group(
            group_id="g-real",
            target_queue="Ploter_A_297mm",
            profile_id="P297_A3_STD",
            item_refs=[0],
            status="READY",
        )
    ]

    fake = FakeRealSubmitter()
    commit_print(manifest, execution_mode=ExecutionMode.REAL, submitter=fake)

    assert fake.calls == 1
    assert manifest.groups[0].status == "COMPLETED"


def test_commit_print_error_without_message_uses_exception_name(tmp_path):
    class SilentFailSubmitter:
        def submit_page(self, _page):
            raise RuntimeError()

    manifest = _base_manifest(tmp_path)
    manifest.printable_pages = [
        PrintablePage(
            file_original_name="silent.pdf",
            file_original_path="C:/in/silent.pdf",
            page_number=1,
            width_key=297,
            profile_id="P297_A3_STD",
            target_queue="Ploter_A_297mm",
            copies=1,
        )
    ]
    manifest.groups = [
        Group(
            group_id="g-silent",
            target_queue="Ploter_A_297mm",
            profile_id="P297_A3_STD",
            item_refs=[0],
            status="READY",
        )
    ]

    commit_print(manifest, submitter=SilentFailSubmitter())

    assert manifest.groups[0].status == "FAILED"
    assert manifest.groups[0].last_error == "RuntimeError"
