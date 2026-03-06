"""Runtime configuration for print dispatch."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ExecutionMode(StrEnum):
    DRY_RUN = "DRY_RUN"
    REAL = "REAL"


@dataclass(slots=True, frozen=True)
class AppConfig:
    persistent_dir: Path
    temp_dir: Path | None
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN
    log_filename: str = "dispatch.log"

    @property
    def log_path(self) -> Path:
        return self.persistent_dir / self.log_filename

    @classmethod
    def from_env(cls) -> "AppConfig":
        persistent_raw = os.getenv("PERSISTENT_DIR", "./data/persistent")
        temp_raw = os.getenv("TEMP_DIR", "./data/temp")
        mode_raw = os.getenv("EXECUTION_MODE", ExecutionMode.DRY_RUN.value)
        log_filename = os.getenv("LOG_FILENAME", "dispatch.log")

        try:
            execution_mode = ExecutionMode(mode_raw)
        except ValueError:
            execution_mode = ExecutionMode.DRY_RUN

        temp_dir = Path(temp_raw) if temp_raw.strip() else None

        return cls(
            persistent_dir=Path(persistent_raw),
            temp_dir=temp_dir,
            execution_mode=execution_mode,
            log_filename=log_filename,
        )


def ensure_runtime_dirs(config: AppConfig) -> None:
    config.persistent_dir.mkdir(parents=True, exist_ok=True)
    if config.temp_dir is not None:
        config.temp_dir.mkdir(parents=True, exist_ok=True)
