"""Real Windows submitter for printing single-page PDFs."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from ..domain.models import PrintablePage

RealEngine = Literal["SUMATRA", "RAW", "AUTO"]


class RealSubmitter:
    def __init__(self, temp_dir: str | Path, sumatra_path: str | Path | None = None, engine: RealEngine | None = None):
        self.temp_dir = Path(temp_dir)
        self.sumatra_path = self._resolve_sumatra_path(sumatra_path)
        self.engine: RealEngine = engine or os.getenv("PRINT_DISPATCH_REAL_ENGINE", "SUMATRA").upper()  # type: ignore[assignment]
        self.long_engine: RealEngine = os.getenv("PRINT_DISPATCH_LONG_ENGINE", "RAW").upper()  # type: ignore[assignment]

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

        user_local_candidate = Path(r"C:\Users\DKL\AppData\Local\SumatraPDF\SumatraPDF.exe")
        program_files = os.getenv("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)")
        candidates = [
            user_local_candidate,
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

        direct = self.temp_dir / filename
        if direct.exists():
            return direct

        matches = sorted(self.temp_dir.rglob(filename))
        if matches:
            return matches[0]
        return direct

    @staticmethod
    def _submit_raw_to_queue(queue_name: str, source_pdf: Path) -> None:
        import win32print  # type: ignore[import-not-found]

        printer = win32print.OpenPrinter(queue_name)
        try:
            with source_pdf.open("rb") as f:
                payload = f.read()
            win32print.StartDocPrinter(printer, 1, ("PrintDispatch", None, "RAW"))
            try:
                win32print.StartPagePrinter(printer)
                win32print.WritePrinter(printer, payload)
                win32print.EndPagePrinter(printer)
            finally:
                win32print.EndDocPrinter(printer)
        finally:
            win32print.ClosePrinter(printer)

    def _submit_via_sumatra(self, page: PrintablePage, source_pdf: Path) -> None:
        if self.sumatra_path is None:
            raise RuntimeError(
                "SumatraPDF not found. Set PRINT_DISPATCH_SUMATRA_PATH or add SumatraPDF to PATH."
            )
        command = [
            str(self.sumatra_path),
            "-print-to",
            page.target_queue,
            "-print-settings",
            "noscale",
            "-silent",
            str(source_pdf),
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            details = stderr or stdout or f"exit={result.returncode}"
            raise RuntimeError(f"Sumatra submit failed for {source_pdf}: {details}")

    def _submit_with_engine(self, engine: RealEngine, page: PrintablePage, source_pdf: Path) -> None:
        if engine == "SUMATRA":
            self._submit_via_sumatra(page, source_pdf)
            return
        if engine == "RAW":
            self._submit_raw_to_queue(page.target_queue, source_pdf)
            return
        if engine == "AUTO":
            try:
                self._submit_via_sumatra(page, source_pdf)
            except Exception:
                self._submit_raw_to_queue(page.target_queue, source_pdf)
            return
        raise RuntimeError(f"Unsupported engine: {engine}")

    def submit_page(self, page: PrintablePage) -> None:
        if os.name != "nt":
            raise RuntimeError("REAL mode is supported only on Windows.")
        source_pdf = self._single_page_path(page)
        if not source_pdf.exists():
            raise FileNotFoundError(f"Single-page PDF not found: {source_pdf}")

        effective_engine = self.long_engine if "_LONG_" in page.profile_id else self.engine
        self._submit_with_engine(effective_engine, page, source_pdf)
