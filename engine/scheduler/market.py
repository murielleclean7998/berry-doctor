from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.db.sqlite import SQLiteRepository


@dataclass(slots=True)
class MarketPriceService:
    config: Any
    repository: SQLiteRepository

    def fetch(self) -> dict[str, Any]:
        data = {
            "item": "설향 특품",
            "price_per_kg": 8200,
            "change": "+300원",
            "trend": 1,
            "recommendation": "이번 주 후반 출하 추천",
            "reason": "주중 후반 강보합 흐름으로 보는 편이 유리해요.",
            "source": "mock" if self.config.mock_mode or not self.config.market_api_key else "api",
        }
        self.repository.set_config("market_cache", data)
        return data

    def latest(self) -> dict[str, Any]:
        return self.repository.get_config("market_cache", self.fetch())
