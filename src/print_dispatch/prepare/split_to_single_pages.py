"""Split source PDF into single-page PDFs in temp directory."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf import Transformation
from pypdf.generic import RectangleObject

MM_PER_PT = 25.4 / 72.0


def _normalize_page_orientation(page):
    """
    Rotate only standard-format landscape pages.
    Long pages keep native orientation to avoid printer clipping on rolls.
    """
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    longest_mm = max(width, height) * MM_PER_PT
    if width > height and longest_mm <= 600.0:
        return page.rotate(90)
    return page


def _flatten_rotation_to_content(page):
    """Apply /Rotate to content stream to keep printer behavior predictable."""
    rotation = int(getattr(page, "rotation", 0) or 0)
    if rotation % 360 != 0:
        page.transfer_rotation_to_content()
    return page


def _normalize_page_origin(page):
    """Ensure page box origin is (0,0) to avoid clipping on some printer drivers."""
    llx = float(page.mediabox.left)
    lly = float(page.mediabox.bottom)
    urx = float(page.mediabox.right)
    ury = float(page.mediabox.top)

    if llx == 0.0 and lly == 0.0:
        return page

    width = urx - llx
    height = ury - lly
    page.add_transformation(Transformation().translate(tx=-llx, ty=-lly))
    normalized_box = RectangleObject([0, 0, width, height])
    page.mediabox = normalized_box
    page.cropbox = RectangleObject([0, 0, width, height])
    return page


def split_pdf_to_single_pages(pdf_path: str | Path, temp_dir: str | Path) -> list[Path]:
    source = Path(pdf_path)
    target_dir = Path(temp_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(source))
    generated_paths: list[Path] = []

    for idx, page in enumerate(reader.pages, start=1):
        out_path = target_dir / f"{source.stem}__p{idx:04d}.pdf"
        writer = PdfWriter()
        processed_page = _flatten_rotation_to_content(page)
        processed_page = _normalize_page_orientation(processed_page)
        processed_page = _normalize_page_origin(processed_page)
        writer.add_page(processed_page)
        with out_path.open("wb") as f:
            writer.write(f)
        generated_paths.append(out_path)

    return generated_paths
