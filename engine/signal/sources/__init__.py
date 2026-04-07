from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SignalSource:
    source_id: str
    name: str
    language: str = "ko"
    check_interval_hours: int = 6

    async def fetch(self):  # pragma: no cover - interface only
        return []


__all__ = ["SignalSource"]
