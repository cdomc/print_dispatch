from __future__ import annotations

from pathlib import Path

import pytest

pypdf = pytest.importorskip("pypdf")
from pypdf import PdfWriter

from print_dispatch.domain.models import Manifest
from print_dispatch.manifest_io import load_manifest
from print_dispatch.prepare.materialize_order import materialize_order


MM_PER_INCH = 25.4
PT_PER_INCH = 72.0
PT_PER_MM = PT_PER_INCH / MM_PER_INCH


def _mm_to_pt(value_mm: float) -> float:
    return value_mm * PT_PER_MM


def _make_pdf(path: Path, page_sizes_mm: list[tuple[float, float]]) -> None:
    writer = PdfWriter()
    for width_mm, height_mm in page_sizes_mm:
        writer.add_blank_page(width=_mm_to_pt(width_mm), height=_mm_to_pt(height_mm))
    with path.open("wb") as f:
        writer.write(f)


def test_materialize_order_creates_dirs_copies_review_and_builds_manifest(tmp_path):
    input_dir = tmp_path / "in"
    input_dir.mkdir(parents=True)

    a4_pdf = input_dir / "a4.pdf"
    auto_pdf = input_dir / "auto_a3_multi.pdf"
    long_over_pdf = input_dir / "long_3100.pdf"

    _make_pdf(a4_pdf, [(210, 297)])
    _make_pdf(auto_pdf, [(297, 420), (297, 420)])
    _make_pdf(long_over_pdf, [(297, 3100)])

    persistent_dir = tmp_path / "persistent"
    temp_dir = tmp_path / "temp"
    manifest_path = persistent_dir / "manifest.json"

    manifest = Manifest(
        order_id="order-1",
        received_time="2026-03-06 10:00:00",
        source_type="MANUAL",
        source_paths=[str(input_dir)],
        source_ref="manual:20260306100000",
        person="Ręczne",
        topic="Test",
        copies_default=2,
        persistent_dir=str(persistent_dir),
        temp_dir=str(temp_dir),
    )

    result = materialize_order(manifest, manifest_path=manifest_path)

    assert persistent_dir.exists()
    assert (persistent_dir / "A4_REVIEW").exists()
    assert (persistent_dir / "CUSTOM_REVIEW").exists()
    assert temp_dir.exists()

    assert (persistent_dir / "A4_REVIEW" / "a4.pdf").exists()
    assert (persistent_dir / "CUSTOM_REVIEW" / "long_3100.pdf").exists()

    split_files = sorted(temp_dir.glob("auto_a3_multi__p*.pdf"))
    assert len(split_files) == 2

    review_map = {(item.file_original_name, item.reason, item.bucket) for item in result.review_items}
    assert ("a4.pdf", "CONTAINS_A4", "A4_REVIEW") in review_map
    assert ("long_3100.pdf", "PAGE_LENGTH_GT_3000", "CUSTOM_REVIEW") in review_map

    assert len(result.printable_pages) == 2
    assert {p.file_original_name for p in result.printable_pages} == {"auto_a3_multi.pdf"}
    assert {p.page_number for p in result.printable_pages} == {1, 2}
    assert all(p.copies == 2 for p in result.printable_pages)

    assert manifest_path.exists()
    loaded = load_manifest(manifest_path)
    assert len(loaded.review_items) == 2
    assert len(loaded.printable_pages) == 2


def test_materialize_order_collects_uppercase_pdf_extension(tmp_path):
    input_dir = tmp_path / "in_upper"
    input_dir.mkdir(parents=True)
    upper_pdf = input_dir / "RYSUNEK.PDF"
    _make_pdf(upper_pdf, [(297, 420)])

    persistent_dir = tmp_path / "persistent_upper"
    manifest = Manifest(
        order_id="order-upper",
        received_time="2026-03-06 10:00:00",
        source_type="MANUAL",
        source_paths=[str(input_dir)],
        source_ref="manual:20260306100000",
        person="Ręczne",
        topic="Upper",
        copies_default=1,
        persistent_dir=str(persistent_dir),
        temp_dir=str(tmp_path / "temp_upper"),
    )

    result = materialize_order(manifest)

    assert len(result.printable_pages) == 1
    assert result.printable_pages[0].file_original_name == "RYSUNEK.PDF"
