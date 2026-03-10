from __future__ import annotations

import pytest

reportlab = pytest.importorskip("reportlab")
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from print_dispatch.prepare.pdf_analyze import analyze_pdf


def _make_single_page_pdf(path, width_mm: float, height_mm: float) -> None:
    c = canvas.Canvas(str(path), pagesize=(width_mm * mm, height_mm * mm))
    c.drawString(20, 20, "test")
    c.showPage()
    c.save()


def test_a4_goes_to_a4_review(tmp_path):
    pdf = tmp_path / "a4.pdf"
    _make_single_page_pdf(pdf, 210, 297)

    result = analyze_pdf(pdf)

    assert result.decision == "A4_REVIEW"
    assert result.reason == "CONTAINS_A4"
    assert result.pages[0].kind == "A4"


def test_a3_is_printable(tmp_path):
    pdf = tmp_path / "a3.pdf"
    _make_single_page_pdf(pdf, 297, 420)

    result = analyze_pdf(pdf)

    assert result.decision == "PRINTABLE"
    assert result.reason is None
    page = result.pages[0]
    assert page.kind == "A3"
    assert page.width_key == 297
    assert page.rotation_required is False


def test_a3_with_small_height_drift_is_still_a3(tmp_path):
    pdf = tmp_path / "a3_drift.pdf"
    _make_single_page_pdf(pdf, 297, 420.18)

    result = analyze_pdf(pdf)

    assert result.decision == "PRINTABLE"
    assert result.reason is None
    assert result.pages[0].kind == "A3"


def test_a3_with_larger_height_drift_up_to_430_is_still_a3(tmp_path):
    pdf = tmp_path / "a3_drift_429.pdf"
    _make_single_page_pdf(pdf, 297, 429.0)

    result = analyze_pdf(pdf)

    assert result.decision == "PRINTABLE"
    assert result.reason is None
    assert result.pages[0].kind == "A3"


def test_297_width_above_430_is_long(tmp_path):
    pdf = tmp_path / "297x440.pdf"
    _make_single_page_pdf(pdf, 297, 440.0)

    result = analyze_pdf(pdf)

    assert result.decision == "PRINTABLE"
    assert result.reason is None
    assert result.pages[0].kind == "LONG"


def test_long_297x3000_is_printable(tmp_path):
    pdf = tmp_path / "long_3000.pdf"
    _make_single_page_pdf(pdf, 297, 3000)

    result = analyze_pdf(pdf)

    assert result.decision == "PRINTABLE"
    assert result.reason is None
    page = result.pages[0]
    assert page.kind == "LONG"
    assert page.width_key == 297
    assert page.length_mm == pytest.approx(3000, abs=1.0)


def test_long_297x3100_goes_to_custom_review_length(tmp_path):
    pdf = tmp_path / "long_3100.pdf"
    _make_single_page_pdf(pdf, 297, 3100)

    result = analyze_pdf(pdf)

    assert result.decision == "CUSTOM_REVIEW"
    assert result.reason == "PAGE_LENGTH_GT_3000"


def test_custom_size_goes_to_custom_review(tmp_path):
    pdf = tmp_path / "custom.pdf"
    _make_single_page_pdf(pdf, 500, 500)

    result = analyze_pdf(pdf)

    assert result.decision == "CUSTOM_REVIEW"
    assert result.reason == "CONTAINS_CUSTOM_OR_UNSUPPORTED"
    assert result.pages[0].kind == "CUSTOM"


def test_landscape_a3_is_printable_after_normalization(tmp_path):
    pdf = tmp_path / "a3_landscape.pdf"
    _make_single_page_pdf(pdf, 420, 297)

    result = analyze_pdf(pdf)

    assert result.decision == "PRINTABLE"
    assert result.reason is None
    assert result.pages[0].kind == "A3"
    assert result.pages[0].rotation_required is False
