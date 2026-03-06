"""PDF page analysis and file-level review decisions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pypdf import PdfReader

MM_PER_INCH = 25.4
PT_PER_INCH = 72.0
MM_PER_PT = MM_PER_INCH / PT_PER_INCH
TOLERANCE_MM = 2.0

A4_W = 210.0
A4_H = 297.0
A3_W = 297.0
A3_H = 420.0
SUPPORTED_WIDTHS = (297, 420, 594, 841)

ReviewBucket = Literal["A4_REVIEW", "CUSTOM_REVIEW"]
ReviewReason = Literal[
    "CONTAINS_A4",
    "CONTAINS_CUSTOM_OR_UNSUPPORTED",
    "PAGE_LENGTH_GT_3000",
    "ROTATION_REQUIRED",
]
FileDecision = Literal["PRINTABLE", "A4_REVIEW", "CUSTOM_REVIEW"]
PageKind = Literal["A4", "A3", "LONG", "CUSTOM"]


@dataclass(slots=True)
class PageAnalysis:
    page_number: int
    width_mm_raw: float
    height_mm_raw: float
    width_mm: float
    length_mm: float
    width_key: int | None
    kind: PageKind
    is_long: bool
    rotation_required: bool


@dataclass(slots=True)
class FileReview:
    decision: FileDecision
    reason: ReviewReason | None
    pages: list[PageAnalysis]


def _pt_to_mm(value: float) -> float:
    return value * MM_PER_PT


def _is_close(value: float, target: float, tol: float = TOLERANCE_MM) -> bool:
    return abs(value - target) <= tol


def _match_supported_width(value_mm: float) -> int | None:
    for width in SUPPORTED_WIDTHS:
        if _is_close(value_mm, float(width)):
            return width
    return None


def _classify_page(page_number: int, width_mm_raw: float, height_mm_raw: float) -> PageAnalysis:
    width_mm = min(width_mm_raw, height_mm_raw)
    length_mm = max(width_mm_raw, height_mm_raw)
    rotation_required = width_mm_raw > height_mm_raw

    if _is_close(width_mm, A4_W) and _is_close(length_mm, A4_H):
        return PageAnalysis(
            page_number=page_number,
            width_mm_raw=width_mm_raw,
            height_mm_raw=height_mm_raw,
            width_mm=width_mm,
            length_mm=length_mm,
            width_key=None,
            kind="A4",
            is_long=False,
            rotation_required=rotation_required,
        )

    if _is_close(width_mm, A3_W) and _is_close(length_mm, A3_H):
        return PageAnalysis(
            page_number=page_number,
            width_mm_raw=width_mm_raw,
            height_mm_raw=height_mm_raw,
            width_mm=width_mm,
            length_mm=length_mm,
            width_key=297,
            kind="A3",
            is_long=False,
            rotation_required=rotation_required,
        )

    width_key = _match_supported_width(width_mm)
    if width_key is None:
        kind: PageKind = "CUSTOM"
        is_long = False
    else:
        kind = "LONG"
        is_long = True

    return PageAnalysis(
        page_number=page_number,
        width_mm_raw=width_mm_raw,
        height_mm_raw=height_mm_raw,
        width_mm=width_mm,
        length_mm=length_mm,
        width_key=width_key,
        kind=kind,
        is_long=is_long,
        rotation_required=rotation_required,
    )


def analyze_pdf(pdf_path: str | Path) -> FileReview:
    source = Path(pdf_path)
    reader = PdfReader(str(source))

    pages: list[PageAnalysis] = []
    for idx, page in enumerate(reader.pages, start=1):
        box = page.mediabox
        width_mm_raw = _pt_to_mm(float(box.width))
        height_mm_raw = _pt_to_mm(float(box.height))
        pages.append(_classify_page(idx, width_mm_raw, height_mm_raw))

    if any(page.kind == "A4" for page in pages):
        return FileReview(decision="A4_REVIEW", reason="CONTAINS_A4", pages=pages)

    if any(page.kind == "CUSTOM" for page in pages):
        return FileReview(decision="CUSTOM_REVIEW", reason="CONTAINS_CUSTOM_OR_UNSUPPORTED", pages=pages)

    if any(page.is_long and page.length_mm > 3000.0 for page in pages):
        return FileReview(decision="CUSTOM_REVIEW", reason="PAGE_LENGTH_GT_3000", pages=pages)

    if any(page.rotation_required for page in pages):
        return FileReview(decision="CUSTOM_REVIEW", reason="ROTATION_REQUIRED", pages=pages)

    return FileReview(decision="PRINTABLE", reason=None, pages=pages)
