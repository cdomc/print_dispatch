from __future__ import annotations

from print_dispatch.dispatch.build_groups import build_groups
from print_dispatch.dispatch.queue_depth import FakeQueueDepth
from print_dispatch.domain.models import Manifest, PrintablePage


def _manifest_with_297_pages(num_pages: int) -> Manifest:
    manifest = Manifest(
        order_id="ord-bg-1",
        received_time="2026-03-06 12:00:00",
        source_type="MANUAL",
        source_paths=["C:/in"],
        source_ref="manual:20260306120000",
        person="Test",
        topic="BuildGroups",
        copies_default=1,
        persistent_dir="C:/persistent/ord-bg-1",
        temp_dir="C:/temp/ord-bg-1",
    )
    manifest.printable_pages = [
        PrintablePage(
            file_original_name=f"p{idx:02d}.pdf",
            file_original_path=f"C:/in/p{idx:02d}.pdf",
            page_number=1,
            width_key=297,
            profile_id="P297_A3_STD",
            target_queue="Ploter_A_297mm",
            copies=1,
        )
        for idx in range(1, num_pages + 1)
    ]
    return manifest


def test_build_groups_prefer_a_forces_start_with_a():
    manifest = _manifest_with_297_pages(6)

    build_groups(
        manifest,
        FakeQueueDepth({"Ploter_A_297mm": 10, "Ploter_E_297mm": 0}),
        prefer_297="PREFER_A",
    )

    assert manifest.batch_plan_297 is not None
    assert manifest.batch_plan_297.start_printer == "Ploter_A_297mm"
    assert [b.target_queue for b in manifest.batch_plan_297.batches] == [
        "Ploter_A_297mm",
        "Ploter_E_297mm",
    ]


def test_build_groups_only_a_routes_all_297_to_a():
    manifest = _manifest_with_297_pages(8)

    build_groups(
        manifest,
        FakeQueueDepth({"Ploter_A_297mm": 0, "Ploter_E_297mm": 0}),
        prefer_297="ONLY_A",
    )

    assert manifest.batch_plan_297 is not None
    assert all(batch.target_queue == "Ploter_A_297mm" for batch in manifest.batch_plan_297.batches)
    assert all(page.target_queue == "Ploter_A_297mm" for page in manifest.printable_pages)


def test_build_groups_only_e_routes_all_297_to_e():
    manifest = _manifest_with_297_pages(8)

    build_groups(
        manifest,
        FakeQueueDepth({"Ploter_A_297mm": 0, "Ploter_E_297mm": 0}),
        prefer_297="ONLY_E",
    )

    assert manifest.batch_plan_297 is not None
    assert all(batch.target_queue == "Ploter_E_297mm" for batch in manifest.batch_plan_297.batches)
    assert all(page.target_queue == "Ploter_E_297mm" for page in manifest.printable_pages)


def test_build_groups_small_load_two_items_split_one_one_by_default():
    manifest = _manifest_with_297_pages(2)

    build_groups(
        manifest,
        FakeQueueDepth({"Ploter_A_297mm": 0, "Ploter_E_297mm": 0}),
        prefer_297="PREFER_A",
    )

    assert manifest.batch_plan_297 is not None
    assert [b.target_queue for b in manifest.batch_plan_297.batches] == [
        "Ploter_A_297mm",
        "Ploter_E_297mm",
    ]
    assert len(manifest.batch_plan_297.batches[0].item_refs) == 1
    assert len(manifest.batch_plan_297.batches[1].item_refs) == 1


def test_build_groups_small_load_seven_items_split_three_four_by_default():
    manifest = _manifest_with_297_pages(7)

    build_groups(
        manifest,
        FakeQueueDepth({"Ploter_A_297mm": 0, "Ploter_E_297mm": 0}),
        prefer_297="PREFER_A",
    )

    assert manifest.batch_plan_297 is not None
    assert [b.target_queue for b in manifest.batch_plan_297.batches] == [
        "Ploter_A_297mm",
        "Ploter_E_297mm",
    ]
    assert len(manifest.batch_plan_297.batches[0].item_refs) == 3
    assert len(manifest.batch_plan_297.batches[1].item_refs) == 4
