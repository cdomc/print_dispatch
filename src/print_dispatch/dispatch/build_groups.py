"""Build dispatch groups and 297 batch plan according to v1 spec."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from ..domain.models import Batch297, BatchPlan297, Group, Manifest
from .plan_297 import apply_batch_plan_to_pages, plan_297_batches
from .queue_depth import get_297_queue_depths

PROFILE_297_STD = "P297_A3_STD"
PROFILE_297_LONG = "P297_A3_LONG_3000_TRIM"
QUEUE_A_297 = "Ploter_A_297mm"
QUEUE_E_297 = "Ploter_E_297mm"
Prefer297 = Literal["PREFER_A", "PREFER_E", "ONLY_A", "ONLY_E"]


def _group_sort_key(group: Group) -> tuple[int, str, str]:
    order_by_profile = {
        PROFILE_297_STD: 1,
        PROFILE_297_LONG: 2,
        "P420_A2_LONG_3000_TRIM": 3,
        "P594_A1_LONG_3000_TRIM": 4,
        "P841_A0_LONG_3000_TRIM": 5,
    }
    return (order_by_profile.get(group.profile_id, 99), group.target_queue, group.group_id)


def _build_groups_from_pages(manifest: Manifest) -> list[Group]:
    grouped_refs: dict[tuple[str, str], list[int]] = defaultdict(list)
    for idx, page in enumerate(manifest.printable_pages):
        grouped_refs[(page.target_queue, page.profile_id)].append(idx)

    groups: list[Group] = []
    for (queue, profile_id), refs in grouped_refs.items():
        groups.append(
            Group(
                group_id=f"{profile_id}__{queue}",
                target_queue=queue,
                profile_id=profile_id,
                item_refs=sorted(
                    refs,
                    key=lambda ref: (
                        manifest.printable_pages[ref].file_original_name,
                        manifest.printable_pages[ref].page_number
                        if manifest.printable_pages[ref].page_number is not None
                        else 0,
                        ref,
                    ),
                ),
            )
        )

    return sorted(groups, key=_group_sort_key)


def _build_only_queue_batches(
    manifest: Manifest,
    refs: list[int],
    queue_name: Literal["Ploter_A_297mm", "Ploter_E_297mm"],
    k: int,
    start_batch_index: int,
    qA: int,
    qE: int,
) -> BatchPlan297:
    ordered_refs = sorted(
        refs,
        key=lambda ref: (
            manifest.printable_pages[ref].file_original_name,
            manifest.printable_pages[ref].page_number if manifest.printable_pages[ref].page_number is not None else 0,
            ref,
        ),
    )
    batches: list[Batch297] = []
    for offset in range(0, len(ordered_refs), k):
        batch_refs = ordered_refs[offset : offset + k]
        batch_number = offset // k
        batches.append(
            Batch297(
                batch_index=start_batch_index + batch_number,
                target_queue=queue_name,
                item_refs=batch_refs,
            )
        )
    return BatchPlan297(K=k, qA=qA, qE=qE, start_printer=queue_name, batches=batches)


def _build_small_load_half_split_batches(
    manifest: Manifest,
    refs: list[int],
    k: int,
    start_batch_index: int,
    qA: int,
    qE: int,
) -> BatchPlan297:
    ordered_refs = sorted(
        refs,
        key=lambda ref: (
            manifest.printable_pages[ref].file_original_name,
            manifest.printable_pages[ref].page_number if manifest.printable_pages[ref].page_number is not None else 0,
            ref,
        ),
    )
    split_idx = len(ordered_refs) // 2
    refs_a = ordered_refs[:split_idx]
    refs_e = ordered_refs[split_idx:]

    batches: list[Batch297] = []
    batch_index = start_batch_index
    if refs_a:
        batches.append(Batch297(batch_index=batch_index, target_queue=QUEUE_A_297, item_refs=refs_a))
        batch_index += 1
    if refs_e:
        batches.append(Batch297(batch_index=batch_index, target_queue=QUEUE_E_297, item_refs=refs_e))

    return BatchPlan297(K=k, qA=qA, qE=qE, start_printer=QUEUE_A_297, batches=batches)


def build_groups(manifest: Manifest, queue_depth_provider, k: int = 5, prefer_297: Prefer297 | None = None) -> Manifest:
    qA, qE = get_297_queue_depths(queue_depth_provider)

    next_batch_index = 1
    all_batches: list[Batch297] = []
    first_start_printer = QUEUE_A_297 if qA <= qE else QUEUE_E_297

    for profile_id in (PROFILE_297_STD, PROFILE_297_LONG):
        refs = [
            idx
            for idx, page in enumerate(manifest.printable_pages)
            if page.width_key == 297 and page.profile_id == profile_id
        ]
        if not refs:
            continue

        if prefer_297 in (None, "PREFER_A", "PREFER_E") and len(refs) < 10:
            plan = _build_small_load_half_split_batches(
                manifest=manifest,
                refs=refs,
                k=k,
                start_batch_index=next_batch_index,
                qA=qA,
                qE=qE,
            )
        elif prefer_297 == "ONLY_A":
            plan = _build_only_queue_batches(
                manifest=manifest,
                refs=refs,
                queue_name=QUEUE_A_297,
                k=k,
                start_batch_index=next_batch_index,
                qA=qA,
                qE=qE,
            )
        elif prefer_297 == "ONLY_E":
            plan = _build_only_queue_batches(
                manifest=manifest,
                refs=refs,
                queue_name=QUEUE_E_297,
                k=k,
                start_batch_index=next_batch_index,
                qA=qA,
                qE=qE,
            )
        else:
            forced_start = None
            if prefer_297 == "PREFER_A":
                forced_start = QUEUE_A_297
            elif prefer_297 == "PREFER_E":
                forced_start = QUEUE_E_297

            plan = plan_297_batches(
                printable_pages=manifest.printable_pages,
                item_refs=refs,
                qA=qA,
                qE=qE,
                k=k,
                start_batch_index=next_batch_index,
                forced_start_printer=forced_start,
            )
        if next_batch_index == 1:
            first_start_printer = plan.start_printer
        next_batch_index += len(plan.batches)

        apply_batch_plan_to_pages(manifest.printable_pages, plan)
        all_batches.extend(plan.batches)

    manifest.batch_plan_297 = BatchPlan297(
        K=k,
        qA=qA,
        qE=qE,
        start_printer=first_start_printer,
        batches=all_batches,
    ) if all_batches else None

    manifest.groups = _build_groups_from_pages(manifest)
    return manifest
