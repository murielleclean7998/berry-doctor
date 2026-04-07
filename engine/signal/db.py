from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from engine.db.sqlite import SQLiteRepository
from engine.signal.models import RawSignal


@dataclass(slots=True)
class SignalRepository:
    repository: SQLiteRepository

    def is_duplicate(self, signal_hash: str) -> bool:
        return self.repository.find_signal_by_hash(signal_hash) is not None

    def save_signal(self, signal: RawSignal) -> int:
        relevance = signal.relevance.score if signal.relevance else 0.0
        urgency = signal.relevance.urgency if signal.relevance else "info"
        return self.repository.record_signal(
            source=signal.source_id,
            title=signal.title,
            summary=signal.translated_summary or signal.summary,
            url=signal.url,
            language=signal.language,
            relevance_score=relevance,
            urgency=urgency,
            signal_hash=signal.hash,
            tags=signal.tags,
            payload=signal.payload,
            published_at=signal.published_at,
        )

    def recent_relevant(self, hours: int = 48, limit: int = 20) -> list[dict[str, Any]]:
        return self.repository.recent_signals(hours=hours, limit=limit)

    def immediate_count_today(self, on_day: date | None = None) -> int:
        return self.repository.count_signal_deliveries_today(on_day)
