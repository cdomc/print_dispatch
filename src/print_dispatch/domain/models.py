"""Manifest domain models (schema v1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ReviewBucket = Literal["A4_REVIEW", "CUSTOM_REVIEW"]
PageStatus = Literal["PLANNED", "SUBMITTED", "FAILED"]
GroupStatus = Literal[
    "READY",
    "READY_WITH_CONFIRMATION",
    "EXECUTING",
    "COMPLETED",
    "FAILED",
    "BLOCKED",
]
BatchStatus = Literal["READY", "EXECUTING", "COMPLETED", "FAILED"]
AttemptResult = Literal["OK", "FAIL"]
SourceType = Literal["OUTLOOK", "MANUAL"]
OrderState = Literal["ZLECONE", "W_TRAKCIE", "WYDRUKOWANE", "ZAKONCZONE"]
SposobOpracowania = Literal["Zeszyt", "Teczka"]
RollSelection = Literal["ROLL_SELECTION"]
ConfirmationState = Literal["PENDING", "CONFIRMED"]
StartPrinter297 = Literal["Ploter_A_297mm", "Ploter_E_297mm"]


@dataclass(slots=True)
class ReviewItem:
    bucket: ReviewBucket
    file_original_name: str
    file_original_path: str
    reason: str


@dataclass(slots=True)
class PrintablePage:
    file_original_name: str
    file_original_path: str
    page_number: int | None
    width_key: Literal[297, 420, 594, 841]
    profile_id: str
    target_queue: str
    copies: int = 1
    status: PageStatus = "PLANNED"
    last_error: str | None = None


@dataclass(slots=True)
class Group:
    group_id: str
    target_queue: str
    profile_id: str
    item_refs: list[int] = field(default_factory=list)
    status: GroupStatus = "READY"
    last_error: str | None = None
    confirmation_required: RollSelection | None = None
    confirmation_state: ConfirmationState | None = None


@dataclass(slots=True)
class Batch297:
    batch_index: int
    target_queue: StartPrinter297
    item_refs: list[int] = field(default_factory=list)
    status: BatchStatus = "READY"
    last_error: str | None = None


@dataclass(slots=True)
class BatchPlan297:
    K: int = 5
    qA: int = 0
    qE: int = 0
    start_printer: StartPrinter297 = "Ploter_A_297mm"
    batches: list[Batch297] = field(default_factory=list)


@dataclass(slots=True)
class ExecutionAttempt:
    timestamp: str
    target: str
    result: AttemptResult
    error: str | None = None


@dataclass(slots=True)
class Manifest:
    order_id: str
    received_time: str
    source_type: SourceType
    source_paths: list[str]
    source_ref: str
    person: str
    topic: str
    copies_default: int
    persistent_dir: str
    sposob_opracowania: SposobOpracowania | None = None
    state: OrderState = "ZLECONE"
    state_timestamps: dict[str, str] = field(default_factory=dict)
    temp_dir: str | None = None
    review_items: list[ReviewItem] = field(default_factory=list)
    printable_pages: list[PrintablePage] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    batch_plan_297: BatchPlan297 | None = None
    execution_attempts: list[ExecutionAttempt] = field(default_factory=list)
