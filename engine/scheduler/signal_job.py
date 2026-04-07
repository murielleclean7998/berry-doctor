from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SignalJobService:
    collector: Any

    def collect_domestic(self) -> dict[str, Any]:
        return self.collector.collect_domestic()

    def collect_global(self) -> dict[str, Any]:
        return self.collector.collect_global()
