"""Dry-run submitter for deterministic execution tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.models import PrintablePage


@dataclass(slots=True)
class DryRunSubmitter:
    """Simulate printer submit without touching real printers."""

    fail_once_keys: set[tuple[str, int | None, str]] = field(default_factory=set)
    submitted: list[tuple[str, int | None, str]] = field(default_factory=list)

    def submit_page(self, page: PrintablePage) -> None:
        key = (page.file_original_name, page.page_number, page.target_queue)
        if key in self.fail_once_keys:
            self.fail_once_keys.remove(key)
            raise RuntimeError("DRY_RUN_FORCED_FAILURE")
        self.submitted.append(key)
