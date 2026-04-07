from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.db.sqlite import SQLiteRepository


@dataclass(slots=True)
class SecurityRepository:
    repository: SQLiteRepository

    def save_event(
        self,
        house_id: int,
        photo_paths: list[str],
        timestamp: str | None = None,
        acknowledged: bool = False,
        note: str | None = None,
    ) -> int:
        return self.repository.record_security_event(
            house_id=house_id,
            photo_paths=photo_paths,
            timestamp=timestamp,
            acknowledged=acknowledged,
            note=note,
        )

    def recent_events(self, days: int = 7, limit: int = 20) -> list[dict[str, Any]]:
        return self.repository.recent_security_events(days=days, limit=limit)
