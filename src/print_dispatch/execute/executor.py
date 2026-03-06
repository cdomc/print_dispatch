"""Commit dispatch plan execution."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config import ExecutionMode
from ..domain.models import ExecutionAttempt, Group, Manifest
from ..logging_setup import build_submit_log_line, setup_dispatch_logger
from .dry_run import DryRunSubmitter
from .real_submitter import RealSubmitter

PROFILE_EXECUTION_ORDER = {
    "P297_A3_STD": 1,
    "P297_A3_LONG_3000_TRIM": 2,
    "P420_A2_LONG_3000_TRIM": 3,
    "P594_A1_LONG_3000_TRIM": 4,
    "P841_A0_LONG_3000_TRIM": 5,
}


@dataclass(slots=True)
class FrozenPlan:
    frozen_at: str
    group_ids: list[str]


def _group_sort_key(group: Group) -> tuple[int, str, str]:
    return (
        PROFILE_EXECUTION_ORDER.get(group.profile_id, 99),
        group.target_queue,
        group.group_id,
    )


def _source_page_counts(manifest: Manifest) -> Counter[tuple[str, str]]:
    counts: Counter[tuple[str, str]] = Counter()
    for page in manifest.printable_pages:
        key = (page.file_original_name, page.file_original_path)
        counts[key] += 1
    return counts


def _freeze_plan(manifest: Manifest) -> FrozenPlan:
    return FrozenPlan(
        frozen_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        group_ids=[group.group_id for group in sorted(manifest.groups, key=_group_sort_key)],
    )


def _append_attempt(manifest: Manifest, target: str, result: str, error: str | None) -> None:
    manifest.execution_attempts.append(
        ExecutionAttempt(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            target=target,
            result=result,
            error=error,
        )
    )


def commit_print(
    manifest: Manifest,
    *,
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN,
    submitter=None,
    log_filename: str = "dispatch.log",
) -> Manifest:
    if execution_mode == ExecutionMode.DRY_RUN:
        submitter = submitter or DryRunSubmitter()
    else:
        if manifest.temp_dir is None:
            raise ValueError("REAL mode requires manifest.temp_dir.")
        submitter = submitter or RealSubmitter(manifest.temp_dir)

    manifest.state = "W_TRAKCIE"
    manifest.state_timestamps["W_TRAKCIE"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    _ = _freeze_plan(manifest)
    page_counts = _source_page_counts(manifest)

    logger = setup_dispatch_logger(Path(manifest.persistent_dir), log_filename=log_filename)

    for group in sorted(manifest.groups, key=_group_sort_key):
        if group.status in {"BLOCKED", "READY_WITH_CONFIRMATION"}:
            continue

        group.status = "EXECUTING"
        group.last_error = None

        failed = False
        for ref in group.item_refs:
            page = manifest.printable_pages[ref]
            if page.status == "SUBMITTED":
                continue

            try:
                submitter.submit_page(page)
                page.status = "SUBMITTED"
                page.last_error = None

                source_key = (page.file_original_name, page.file_original_path)
                include_page = page_counts[source_key] > 1
                log_line = build_submit_log_line(
                    plotter=page.target_queue,
                    copies=page.copies,
                    file_original_name=page.file_original_name,
                    page_number=page.page_number if include_page else None,
                )
                logger.info(log_line)
                _append_attempt(manifest, target=f"group:{group.group_id}", result="OK", error=None)
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                page.status = "FAILED"
                page.last_error = message
                group.status = "FAILED"
                group.last_error = message
                _append_attempt(manifest, target=f"group:{group.group_id}", result="FAIL", error=message)
                failed = True
                break

        if not failed:
            group.status = "COMPLETED"
            group.last_error = None

    return manifest
