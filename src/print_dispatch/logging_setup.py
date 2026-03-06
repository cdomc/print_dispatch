"""Logging setup utilities."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def setup_dispatch_logger(persistent_dir: Path, log_filename: str = "dispatch.log") -> logging.Logger:
    persistent_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("print_dispatch")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_path = persistent_dir / log_filename
    target_path = str(log_path.resolve())

    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and str(Path(handler.baseFilename).resolve()) == target_path:
            return logger

    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)
    return logger


def build_submit_log_line(
    *,
    plotter: str,
    copies: int,
    file_original_name: str,
    page_number: int | None = None,
    timestamp: datetime | None = None,
) -> str:
    ts = (timestamp or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    parts = [
        ts,
        f"PLOTER={plotter}",
        f"COPIES={copies}",
        f"FILE={file_original_name}",
    ]
    if page_number is not None:
        parts.append(f"PAGE={page_number}")
    return " | ".join(parts)
