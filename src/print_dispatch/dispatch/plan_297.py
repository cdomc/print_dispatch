"""Batch planning for 297mm queues (A/E), packets of 5 pages."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from ..domain.models import Batch297, BatchPlan297, PrintablePage

QUEUE_A_297 = "Ploter_A_297mm"
QUEUE_E_297 = "Ploter_E_297mm"
StartPrinter = Literal["Ploter_A_297mm", "Ploter_E_297mm"]


def _sort_item_refs(printable_pages: Sequence[PrintablePage], item_refs: Sequence[int]) -> list[int]:
    return sorted(
        item_refs,
        key=lambda ref: (
            printable_pages[ref].file_original_name,
            printable_pages[ref].page_number if printable_pages[ref].page_number is not None else 0,
            ref,
        ),
    )


def plan_297_batches(
    printable_pages: Sequence[PrintablePage],
    item_refs: Sequence[int],
    qA: int,
    qE: int,
    k: int = 5,
    start_batch_index: int = 1,
    forced_start_printer: StartPrinter | None = None,
) -> BatchPlan297:
    if k <= 0:
        raise ValueError("k must be > 0")

    ordered_refs = _sort_item_refs(printable_pages, item_refs)
    start_printer = forced_start_printer or (QUEUE_A_297 if qA <= qE else QUEUE_E_297)
    other_printer = QUEUE_E_297 if start_printer == QUEUE_A_297 else QUEUE_A_297

    batches: list[Batch297] = []
    for offset in range(0, len(ordered_refs), k):
        batch_refs = ordered_refs[offset : offset + k]
        batch_number = offset // k
        queue = start_printer if batch_number % 2 == 0 else other_printer
        batches.append(
            Batch297(
                batch_index=start_batch_index + batch_number,
                target_queue=queue,
                item_refs=batch_refs,
            )
        )

    return BatchPlan297(K=k, qA=qA, qE=qE, start_printer=start_printer, batches=batches)


def apply_batch_plan_to_pages(printable_pages: list[PrintablePage], plan: BatchPlan297) -> None:
    for batch in plan.batches:
        for ref in batch.item_refs:
            printable_pages[ref].target_queue = batch.target_queue
