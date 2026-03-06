"""Queue depth providers used by 297 planner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

QUEUE_A_297 = "Ploter_A_297mm"
QUEUE_E_297 = "Ploter_E_297mm"


class QueueDepthProvider(Protocol):
    def get_depth(self, queue_name: str) -> int:
        """Return queued pages/jobs depth for a Windows queue."""


@dataclass(slots=True)
class FakeQueueDepth:
    depths: dict[str, int]

    def get_depth(self, queue_name: str) -> int:
        return int(self.depths.get(queue_name, 0))


class RealQueueDepth:
    def get_depth(self, queue_name: str) -> int:
        raise NotImplementedError("Real Windows queue depth lookup will be added in later milestone.")


def get_297_queue_depths(provider: QueueDepthProvider) -> tuple[int, int]:
    """Read qA/qE with deterministic fallback required by spec."""
    try:
        qA = int(provider.get_depth(QUEUE_A_297))
        qE = int(provider.get_depth(QUEUE_E_297))
    except Exception:
        return 0, 0
    return qA, qE
