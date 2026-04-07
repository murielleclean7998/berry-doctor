from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class RelevanceScore:
    score: float
    urgency: str
    reason: str


@dataclass(slots=True)
class RawSignal:
    source_id: str
    source: str
    title: str
    summary: str
    url: str
    published_at: datetime
    language: str = "ko"
    hash: str = ""
    tags: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    relevance: RelevanceScore | None = None
    translated_summary: str | None = None

    def __post_init__(self) -> None:
        if not self.hash:
            base = "|".join(
                [
                    self.source_id,
                    self.url,
                    self.title,
                    self.published_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )
            self.hash = hashlib.sha256(base.encode("utf-8")).hexdigest()
