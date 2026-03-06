"""Real Windows submitter for printing single-page PDFs."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ..domain.models import PrintablePage


class RealSubmitter:
    def __init__(self, temp_dir: str | Path, sumatra_path: str | Path | None = None):
        self.temp_dir = Path(temp_dir)
        self.sumatra_path = self._resolve_sumatra_path(sumatra_path)

    @staticmethod
    def _resolve_sumatra_path(explicit_path: str | Path | None) -> Path | None:
        if explicit_path:
            candidate = Path(explicit_path)
            return candidate if candidate.exists() else None

        env_path = os.getenv("PRINT_DISPATCH_SUMATRA_PATH")
        if env_path:
            candidate = Path(env_path)
            if candidate.exists():
                return candidate

        which_path = shutil.which("SumatraPDF.exe") or shutil.which("sumatrapdf")
        if which_path:
            return Path(which_path)

        program_files = os.getenv("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)")
        candidates = [
            Path(program_files) / "SumatraPDF" / "SumatraPDF.exe",
            Path(program_files_x86) / "SumatraPDF" / "SumatraPDF.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _single_page_path(self, page: PrintablePage) -> Path:
        if page.page_number is None:
            raise ValueError("Missing page_number for printable page in REAL mode.")
        filename = f"{Path(page.file_original_name).stem}__p{page.page_number:04d}.pdf"
        return self.temp_dir / filename

    def submit_page(self, page: PrintablePage) -> None:
        if os.name != "nt":
            raise RuntimeError("REAL mode is supported only on Windows.")
        if self.sumatra_path is None:
            raise RuntimeError(
                "SumatraPDF not found. REAL mode requires SumatraPDF to enforce 100% scale (noscale). "
                "Set PRINT_DISPATCH_SUMATRA_PATH if installed in custom location."
            )

        source_pdf = self._single_page_path(page)
        if not source_pdf.exists():
            raise FileNotFoundError(f"Single-page PDF not found: {source_pdf}")

        command = [
            str(self.sumatra_path),
            "-print-to",
            page.target_queue,
            "-print-settings",
            "noscale,portrait",
            "-silent",
            str(source_pdf),
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            details = stderr or stdout or f"exit={result.returncode}"
            raise RuntimeError(f"REAL submit failed for {source_pdf}: {details}")
