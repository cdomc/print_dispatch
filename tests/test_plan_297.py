from __future__ import annotations

from print_dispatch.dispatch.plan_297 import plan_297_batches
from print_dispatch.domain.models import PrintablePage


def _make_pages(num: int) -> list[PrintablePage]:
    pages: list[PrintablePage] = []
    for idx in range(1, num + 1):
        pages.append(
            PrintablePage(
                file_original_name=f"file_{idx:02d}.pdf",
                file_original_path=f"C:/in/file_{idx:02d}.pdf",
                page_number=1,
                width_key=297,
                profile_id="P297_A3_STD",
                target_queue="Ploter_A_297mm",
                copies=1,
            )
        )
    return pages


def test_plan_297_qA_less_than_qE_starts_with_A_and_alternates():
    pages = _make_pages(11)
    refs_unsorted = [10, 2, 0, 9, 3, 1, 4, 5, 6, 7, 8]

    plan = plan_297_batches(pages, refs_unsorted, qA=1, qE=5, k=5)

    assert plan.start_printer == "Ploter_A_297mm"
    assert [b.target_queue for b in plan.batches] == [
        "Ploter_A_297mm",
        "Ploter_E_297mm",
        "Ploter_A_297mm",
    ]
    assert plan.batches[0].item_refs == [0, 1, 2, 3, 4]
    assert plan.batches[1].item_refs == [5, 6, 7, 8, 9]
    assert plan.batches[2].item_refs == [10]


def test_plan_297_qE_less_than_qA_starts_with_E_and_alternates():
    pages = _make_pages(6)
    refs_unsorted = [5, 4, 3, 2, 1, 0]

    plan = plan_297_batches(pages, refs_unsorted, qA=10, qE=2, k=5)

    assert plan.start_printer == "Ploter_E_297mm"
    assert [b.target_queue for b in plan.batches] == [
        "Ploter_E_297mm",
        "Ploter_A_297mm",
    ]


def test_plan_297_tie_starts_with_A():
    pages = _make_pages(5)
    refs_unsorted = [4, 3, 2, 1, 0]

    plan = plan_297_batches(pages, refs_unsorted, qA=3, qE=3, k=5)

    assert plan.start_printer == "Ploter_A_297mm"
    assert len(plan.batches) == 1
    assert plan.batches[0].target_queue == "Ploter_A_297mm"
