"""Build dispatch groups and 297 batch plan according to v1 spec."""

from __future__ import annotations

from collections import defaultdict

from ..domain.models import Batch297, BatchPlan297, Group, Manifest
from .plan_297 import apply_batch_plan_to_pages, plan_297_batches
from .queue_depth import get_297_queue_depths

PROFILE_297_STD = "P297_A3_STD"
PROFILE_297_LONG = "P297_A3_LONG_3000_TRIM"


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


def build_groups(manifest: Manifest, queue_depth_provider, k: int = 5) -> Manifest:
    qA, qE = get_297_queue_depths(queue_depth_provider)

    next_batch_index = 1
    all_batches: list[Batch297] = []
    first_start_printer = "Ploter_A_297mm" if qA <= qE else "Ploter_E_297mm"

    for profile_id in (PROFILE_297_STD, PROFILE_297_LONG):
        refs = [
            idx
            for idx, page in enumerate(manifest.printable_pages)
            if page.width_key == 297 and page.profile_id == profile_id
        ]
        if not refs:
            continue

        plan = plan_297_batches(
            printable_pages=manifest.printable_pages,
            item_refs=refs,
            qA=qA,
            qE=qE,
            k=k,
            start_batch_index=next_batch_index,
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
