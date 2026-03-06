"""Manifest JSON persistence utilities."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .domain.models import (
    Batch297,
    BatchPlan297,
    ExecutionAttempt,
    Group,
    Manifest,
    PrintablePage,
    ReviewItem,
)


def _batch297_from_dict(raw: dict[str, Any]) -> Batch297:
    return Batch297(
        batch_index=raw["batch_index"],
        target_queue=raw["target_queue"],
        item_refs=list(raw.get("item_refs", [])),
        status=raw.get("status", "READY"),
        last_error=raw.get("last_error"),
    )


def _batch_plan_297_from_dict(raw: dict[str, Any]) -> BatchPlan297:
    return BatchPlan297(
        K=raw.get("K", 5),
        qA=raw.get("qA", 0),
        qE=raw.get("qE", 0),
        start_printer=raw.get("start_printer", "Ploter_A_297mm"),
        batches=[_batch297_from_dict(item) for item in raw.get("batches", [])],
    )


def _review_item_from_dict(raw: dict[str, Any]) -> ReviewItem:
    return ReviewItem(
        bucket=raw["bucket"],
        file_original_name=raw["file_original_name"],
        file_original_path=raw["file_original_path"],
        reason=raw["reason"],
    )


def _printable_page_from_dict(raw: dict[str, Any]) -> PrintablePage:
    return PrintablePage(
        file_original_name=raw["file_original_name"],
        file_original_path=raw["file_original_path"],
        page_number=raw.get("page_number"),
        width_key=raw["width_key"],
        profile_id=raw["profile_id"],
        target_queue=raw["target_queue"],
        copies=raw.get("copies", 1),
        status=raw.get("status", "PLANNED"),
        last_error=raw.get("last_error"),
    )


def _group_from_dict(raw: dict[str, Any]) -> Group:
    return Group(
        group_id=raw["group_id"],
        target_queue=raw["target_queue"],
        profile_id=raw["profile_id"],
        item_refs=list(raw.get("item_refs", [])),
        status=raw.get("status", "READY"),
        last_error=raw.get("last_error"),
        confirmation_required=raw.get("confirmation_required"),
        confirmation_state=raw.get("confirmation_state"),
    )


def _execution_attempt_from_dict(raw: dict[str, Any]) -> ExecutionAttempt:
    return ExecutionAttempt(
        timestamp=raw["timestamp"],
        target=raw["target"],
        result=raw["result"],
        error=raw.get("error"),
    )


def manifest_to_dict(manifest: Manifest) -> dict[str, Any]:
    return asdict(manifest)


def manifest_from_dict(raw: dict[str, Any]) -> Manifest:
    batch_plan_raw = raw.get("batch_plan_297")
    return Manifest(
        order_id=raw["order_id"],
        received_time=raw["received_time"],
        source_type=raw["source_type"],
        source_paths=list(raw["source_paths"]),
        source_ref=raw["source_ref"],
        person=raw["person"],
        topic=raw["topic"],
        copies_default=raw["copies_default"],
        persistent_dir=raw["persistent_dir"],
        sposob_opracowania=raw.get("sposob_opracowania"),
        state=raw.get("state", "ZLECONE"),
        state_timestamps=dict(raw.get("state_timestamps", {})),
        temp_dir=raw.get("temp_dir"),
        review_items=[_review_item_from_dict(item) for item in raw.get("review_items", [])],
        printable_pages=[_printable_page_from_dict(item) for item in raw.get("printable_pages", [])],
        groups=[_group_from_dict(item) for item in raw.get("groups", [])],
        batch_plan_297=_batch_plan_297_from_dict(batch_plan_raw) if batch_plan_raw is not None else None,
        execution_attempts=[_execution_attempt_from_dict(item) for item in raw.get("execution_attempts", [])],
    )


def save_manifest(path: str | Path, manifest: Manifest) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        json.dump(manifest_to_dict(manifest), f, ensure_ascii=False, indent=2)


def load_manifest(path: str | Path) -> Manifest:
    source = Path(path)
    with source.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return manifest_from_dict(raw)
