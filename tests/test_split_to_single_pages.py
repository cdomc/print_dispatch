from __future__ import annotations

from pypdf import PdfReader, PdfWriter

from print_dispatch.prepare.split_to_single_pages import split_pdf_to_single_pages


MM_TO_PT = 72.0 / 25.4


def _mm(value: float) -> float:
    return value * MM_TO_PT


def test_split_rotates_landscape_page_for_print(tmp_path):
    src = tmp_path / "landscape.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=_mm(420), height=_mm(297))
    with src.open("wb") as f:
        writer.write(f)

    output_paths = split_pdf_to_single_pages(src, tmp_path / "out")
    out_reader = PdfReader(str(output_paths[0]))
    out_page = out_reader.pages[0]

    assert out_page.get("/Rotate", 0) in (90, 270)


def test_split_keeps_portrait_page_unrotated(tmp_path):
    src = tmp_path / "portrait.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=_mm(297), height=_mm(420))
    with src.open("wb") as f:
        writer.write(f)

    output_paths = split_pdf_to_single_pages(src, tmp_path / "out")
    out_reader = PdfReader(str(output_paths[0]))
    out_page = out_reader.pages[0]

    assert out_page.get("/Rotate", 0) in (0, None)


def test_split_keeps_long_landscape_unrotated(tmp_path):
    src = tmp_path / "long_landscape.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=_mm(1200), height=_mm(297))
    with src.open("wb") as f:
        writer.write(f)

    output_paths = split_pdf_to_single_pages(src, tmp_path / "out")
    out_reader = PdfReader(str(output_paths[0]))
    out_page = out_reader.pages[0]

    assert out_page.get("/Rotate", 0) in (0, None)


def test_split_normalizes_non_zero_page_origin(tmp_path):
    src = tmp_path / "offset.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=_mm(297), height=_mm(420))
    page.mediabox.lower_left = (10, 15)
    page.mediabox.upper_right = (_mm(297) + 10, _mm(420) + 15)
    page.cropbox.lower_left = (10, 15)
    page.cropbox.upper_right = (_mm(297) + 10, _mm(420) + 15)
    with src.open("wb") as f:
        writer.write(f)

    output_paths = split_pdf_to_single_pages(src, tmp_path / "out")
    out_reader = PdfReader(str(output_paths[0]))
    out_page = out_reader.pages[0]

    assert float(out_page.mediabox.left) == 0.0
    assert float(out_page.mediabox.bottom) == 0.0
    assert float(out_page.cropbox.left) == 0.0
    assert float(out_page.cropbox.bottom) == 0.0
