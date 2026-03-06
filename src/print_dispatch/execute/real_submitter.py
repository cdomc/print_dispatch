"""Real Windows submitter for printing single-page PDFs."""

from __future__ import annotations

import os
from pathlib import Path

from ..domain.models import PrintablePage


class RealSubmitter:
    def __init__(self, temp_dir: str | Path):
        self.temp_dir = Path(temp_dir)

    def _single_page_path(self, page: PrintablePage) -> Path:
        if page.page_number is None:
            raise ValueError("Missing page_number for printable page in REAL mode.")
        filename = f"{Path(page.file_original_name).stem}__p{page.page_number:04d}.pdf"
        return self.temp_dir / filename

    def submit_page(self, page: PrintablePage) -> None:
        if os.name != "nt":
            raise RuntimeError("REAL mode is supported only on Windows.")

        source_pdf = self._single_page_path(page)
        if not source_pdf.exists():
            raise FileNotFoundError(f"Single-page PDF not found: {source_pdf}")

        try:
            import win32api  # type: ignore[import-not-found]

            win32api.ShellExecute(0, "printto", str(source_pdf), f'"{page.target_queue}"', ".", 0)
        except Exception as exc:
            raise RuntimeError(f"REAL submit failed for {source_pdf}: {exc}") from exc
