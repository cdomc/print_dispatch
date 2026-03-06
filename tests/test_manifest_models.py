from __future__ import annotations

from dataclasses import asdict

from print_dispatch.domain.models import (
    Batch297,
    BatchPlan297,
    ExecutionAttempt,
    Group,
    Manifest,
    PrintablePage,
    ReviewItem,
)
from print_dispatch.manifest_io import load_manifest, save_manifest


def test_manifest_defaults():
    manifest = Manifest(
        order_id="ord-1",
        received_time="2026-03-05 12:00:00",
        source_type="MANUAL",
        source_paths=["C:/in/a.pdf"],
        source_ref="manual:20260305120000",
        person="Jan",
        topic="Test",
        copies_default=1,
        persistent_dir="C:/persistent/ord-1",
    )

    assert manifest.state == "ZLECONE"
    assert manifest.review_items == []
    assert manifest.printable_pages == []
    assert manifest.groups == []


def test_manifest_roundtrip_preserves_all_fields(tmp_path):
    manifest = Manifest(
        order_id="order-20260305-001",
        received_time="2026-03-05 14:10:00",
        source_type="OUTLOOK",
        source_paths=["C:/drop/a.pdf", "C:/drop/b.pdf"],
        source_ref="outlook:entry-123",
        person="Kowalski",
        topic="Temat",
        copies_default=2,
        persistent_dir="C:/persistent/order-20260305-001",
        sposob_opracowania="Zeszyt",
        state="W_TRAKCIE",
        state_timestamps={
            "ZLECONE": "2026-03-05 14:10:00",
            "W_TRAKCIE": "2026-03-05 14:11:00",
        },
        temp_dir="C:/temp/order-20260305-001",
        review_items=[
            ReviewItem(
                bucket="A4_REVIEW",
                file_original_name="a4.pdf",
                file_original_path="C:/drop/a4.pdf",
                reason="CONTAINS_A4",
            ),
            ReviewItem(
                bucket="CUSTOM_REVIEW",
                file_original_name="custom.pdf",
                file_original_path="C:/drop/custom.pdf",
                reason="CONTAINS_CUSTOM_OR_UNSUPPORTED",
            ),
        ],
        printable_pages=[
            PrintablePage(
                file_original_name="ok.pdf",
                file_original_path="C:/drop/ok.pdf",
                page_number=1,
                width_key=297,
                profile_id="P297_A3_STD",
                target_queue="Ploter_A_297mm",
                copies=2,
                status="PLANNED",
                last_error=None,
            ),
            PrintablePage(
                file_original_name="ok2.pdf",
                file_original_path="C:/drop/ok2.pdf",
                page_number=None,
                width_key=594,
                profile_id="P594_A1_LONG_3000_TRIM",
                target_queue="Ploter_C_594mm",
                copies=1,
                status="FAILED",
                last_error="MISSING_PRINTER_QUEUE",
            ),
        ],
        groups=[
            Group(
                group_id="g-1",
                target_queue="Ploter_A_297mm",
                profile_id="P297_A3_STD",
                item_refs=[0],
                status="READY",
                last_error=None,
                confirmation_required=None,
                confirmation_state=None,
            ),
            Group(
                group_id="g-2",
                target_queue="Ploter_C_594mm",
                profile_id="P841_A0_LONG_3000_TRIM",
                item_refs=[1],
                status="READY_WITH_CONFIRMATION",
                last_error=None,
                confirmation_required="ROLL_SELECTION",
                confirmation_state="PENDING",
            ),
        ],
        batch_plan_297=BatchPlan297(
            K=5,
            qA=12,
            qE=7,
            start_printer="Ploter_E_297mm",
            batches=[
                Batch297(
                    batch_index=1,
                    target_queue="Ploter_E_297mm",
                    item_refs=[0],
                    status="READY",
                    last_error=None,
                )
            ],
        ),
        execution_attempts=[
            ExecutionAttempt(
                timestamp="2026-03-05 14:12:00",
                target="group:g-1",
                result="OK",
                error=None,
            ),
            ExecutionAttempt(
                timestamp="2026-03-05 14:13:00",
                target="batch:1",
                result="FAIL",
                error="QUEUE_ERROR",
            ),
        ],
    )

    manifest_path = tmp_path / "manifest.json"
    save_manifest(manifest_path, manifest)
    loaded = load_manifest(manifest_path)

    assert asdict(loaded) == asdict(manifest)
