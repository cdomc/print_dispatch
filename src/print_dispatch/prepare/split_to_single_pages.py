"""Split source PDF into single-page PDFs in temp directory."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter


def split_pdf_to_single_pages(pdf_path: str | Path, temp_dir: str | Path) -> list[Path]:
    source = Path(pdf_path)
    target_dir = Path(temp_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(source))
    generated_paths: list[Path] = []

    for idx, page in enumerate(reader.pages, start=1):
        out_path = target_dir / f"{source.stem}__p{idx:04d}.pdf"
        writer = PdfWriter()
        writer.add_page(page)
        with out_path.open("wb") as f:
            writer.write(f)
        generated_paths.append(out_path)

    return generated_paths
