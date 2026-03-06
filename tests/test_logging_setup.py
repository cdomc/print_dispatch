from __future__ import annotations

from datetime import datetime

from print_dispatch.logging_setup import build_submit_log_line, setup_dispatch_logger


def test_build_submit_log_line_without_page():
    line = build_submit_log_line(
        plotter="Ploter_B_420mm",
        copies=2,
        file_original_name="projekt.pdf",
        timestamp=datetime(2026, 2, 20, 14, 23, 11),
    )

    assert line == "2026-02-20 14:23:11 | PLOTER=Ploter_B_420mm | COPIES=2 | FILE=projekt.pdf"


def test_build_submit_log_line_with_page():
    line = build_submit_log_line(
        plotter="Ploter_A_297mm",
        copies=1,
        file_original_name="multi.pdf",
        page_number=3,
        timestamp=datetime(2026, 2, 20, 14, 23, 11),
    )

    assert line.endswith("| PAGE=3")


def test_setup_dispatch_logger_writes_file(tmp_path):
    logger = setup_dispatch_logger(tmp_path)
    logger.info("line-1")

    log_path = tmp_path / "dispatch.log"
    assert log_path.exists()
    assert "line-1" in log_path.read_text(encoding="utf-8")
