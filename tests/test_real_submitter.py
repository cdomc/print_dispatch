from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter

from print_dispatch.domain.models import PrintablePage
from print_dispatch.execute.real_submitter import RealSubmitter


def test_single_page_path_finds_file_in_temp_subfolders(tmp_path):
    temp_dir = tmp_path / "temp"
    nested = temp_dir / "LONG_297"
    nested.mkdir(parents=True)

    split_file = nested / "sample__p0003.pdf"
    split_file.write_bytes(b"%PDF-1.4\n%%EOF")

    submitter = RealSubmitter(temp_dir=temp_dir)
    page = PrintablePage(
        file_original_name="sample.pdf",
        file_original_path="C:/in/sample.pdf",
        page_number=3,
        width_key=297,
        profile_id="P297_A3_LONG_3000_TRIM",
        target_queue="Ploter_A_297mm",
        copies=1,
    )

    found = submitter._single_page_path(page)
    assert found == split_file


def test_long_profile_uses_long_engine_by_default(tmp_path):
    submitter = RealSubmitter(temp_dir=tmp_path)
    assert submitter.long_engine == "AUTO"


def test_sumatra_print_settings_portrait(tmp_path):
    pdf = tmp_path / "portrait.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72.0, height=144.0)
    with pdf.open("wb") as f:
        writer.write(f)

    assert RealSubmitter._sumatra_print_settings(pdf) == "noscale,portrait"


def test_sumatra_print_settings_landscape(tmp_path):
    pdf = tmp_path / "landscape.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=144.0, height=72.0)
    with pdf.open("wb") as f:
        writer.write(f)

    assert RealSubmitter._sumatra_print_settings(pdf) == "noscale,landscape"
