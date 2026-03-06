from __future__ import annotations

from pathlib import Path

from print_dispatch.config import AppConfig, ExecutionMode, ensure_runtime_dirs


def test_from_env_defaults(monkeypatch):
    monkeypatch.delenv("PERSISTENT_DIR", raising=False)
    monkeypatch.delenv("TEMP_DIR", raising=False)
    monkeypatch.delenv("EXECUTION_MODE", raising=False)
    monkeypatch.delenv("LOG_FILENAME", raising=False)

    config = AppConfig.from_env()

    assert config.persistent_dir == Path("./data/persistent")
    assert config.temp_dir == Path("./data/temp")
    assert config.execution_mode == ExecutionMode.DRY_RUN
    assert config.log_filename == "dispatch.log"


def test_from_env_invalid_mode_falls_back_to_dry_run(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "INVALID")

    config = AppConfig.from_env()

    assert config.execution_mode == ExecutionMode.DRY_RUN


def test_ensure_runtime_dirs_creates_directories(tmp_path):
    config = AppConfig(
        persistent_dir=tmp_path / "persistent",
        temp_dir=tmp_path / "temp",
        execution_mode=ExecutionMode.DRY_RUN,
    )

    ensure_runtime_dirs(config)

    assert config.persistent_dir.exists()
    assert config.temp_dir is not None and config.temp_dir.exists()
    assert config.log_path == config.persistent_dir / "dispatch.log"
