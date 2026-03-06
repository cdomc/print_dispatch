"""Materialize order directories and manifest lists from input PDFs."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..domain.models import Manifest, PrintablePage, ReviewItem
from ..manifest_io import save_manifest
from .pdf_analyze import analyze_pdf
from .split_to_single_pages import split_pdf_to_single_pages

PROFILE_BY_KIND_AND_WIDTH: dict[tuple[str, int], str] = {
    ("A3", 297): "P297_A3_STD",
    ("LONG", 297): "P297_A3_LONG_3000_TRIM",
    ("LONG", 420): "P420_A2_LONG_3000_TRIM",
    ("LONG", 594): "P594_A1_LONG_3000_TRIM",
    ("LONG", 841): "P841_A0_LONG_3000_TRIM",
}

QUEUE_BY_WIDTH: dict[int, str] = {
    297: "Ploter_A_297mm",
    420: "Ploter_B_420mm",
    594: "Ploter_C_594mm",
    841: "Ploter_C_594mm",
}


def _collect_pdf_files(source_paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in source_paths:
        path = Path(raw)
        if path.is_file() and path.suffix.lower() == ".pdf":
            files.append(path)
            continue
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf"))
    return sorted(files)


def _ensure_order_dirs(manifest: Manifest) -> tuple[Path, Path, Path, Path]:
    persistent_dir = Path(manifest.persistent_dir)
    if manifest.temp_dir is None:
        manifest.temp_dir = str(persistent_dir / "temp")

    temp_dir = Path(manifest.temp_dir)
    a4_review_dir = persistent_dir / "A4_REVIEW"
    custom_review_dir = persistent_dir / "CUSTOM_REVIEW"

    for directory in (persistent_dir, temp_dir, a4_review_dir, custom_review_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return persistent_dir, temp_dir, a4_review_dir, custom_review_dir


def _build_printable_page(file_path: Path, page_number: int, kind: str, width_key: int, copies: int) -> PrintablePage:
    profile_id = PROFILE_BY_KIND_AND_WIDTH[(kind, width_key)]
    target_queue = QUEUE_BY_WIDTH[width_key]
    return PrintablePage(
        file_original_name=file_path.name,
        file_original_path=str(file_path),
        page_number=page_number,
        width_key=width_key,
        profile_id=profile_id,
        target_queue=target_queue,
        copies=copies,
    )


def materialize_order(manifest: Manifest, manifest_path: str | Path | None = None) -> Manifest:
    _, temp_dir, a4_review_dir, custom_review_dir = _ensure_order_dirs(manifest)

    manifest.review_items = []
    manifest.printable_pages = []

    pdf_files = _collect_pdf_files(manifest.source_paths)

    for file_path in pdf_files:
        analysis = analyze_pdf(file_path)

        if analysis.decision in ("A4_REVIEW", "CUSTOM_REVIEW"):
            review_dir = a4_review_dir if analysis.decision == "A4_REVIEW" else custom_review_dir
            copied_path = review_dir / file_path.name
            shutil.copy2(file_path, copied_path)
            manifest.review_items.append(
                ReviewItem(
                    bucket=analysis.decision,
                    file_original_name=file_path.name,
                    file_original_path=str(file_path),
                    reason=analysis.reason or "UNKNOWN",
                )
            )
            continue

        split_paths = split_pdf_to_single_pages(file_path, temp_dir)
        if len(split_paths) != len(analysis.pages):
            raise ValueError(f"Split page count mismatch for {file_path}")

        for page in analysis.pages:
            if page.width_key is None:
                raise ValueError(f"Printable page without width_key for {file_path}, page {page.page_number}")
            manifest.printable_pages.append(
                _build_printable_page(
                    file_path=file_path,
                    page_number=page.page_number,
                    kind=page.kind,
                    width_key=page.width_key,
                    copies=manifest.copies_default,
                )
            )

    if manifest_path is not None:
        save_manifest(manifest_path, manifest)

    return manifest
