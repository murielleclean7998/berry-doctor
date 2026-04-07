from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from engine.signal.models import RawSignal
from engine.signal.sources import SignalSource


@dataclass(slots=True)
class MarketAlertSource(SignalSource):
    config: Any = None
    repository: Any = None

    def __init__(self, config: Any, repository: Any) -> None:
        SignalSource.__init__(self, source_id="market_alert", name="도매시장 가격 급변", language="ko", check_interval_hours=1)
        self.config = config
        self.repository = repository

    async def fetch(self) -> list[RawSignal]:
        history = self.repository.market_history(2)
        if len(history) < 2:
            return []
        latest = history[0]
        previous = history[1]
        previous_price = float(previous.get("price_per_kg") or 0.0)
        latest_price = float(latest.get("price_per_kg") or 0.0)
        if previous_price <= 0:
            return []
        delta_pct = ((latest_price - previous_price) / previous_price) * 100
        if abs(delta_pct) < 10:
            return []
        direction = "급등" if delta_pct > 0 else "급락"
        now = datetime.now()
        return [
            RawSignal(
                source_id=self.source_id,
                source=self.name,
                title=f"설향 시세 {direction}",
                summary=f"직전 시세 대비 {delta_pct:+.1f}% 움직였어요. 출하 계획을 다시 보시면 좋아요.",
                url=f"https://at.agromarket.kr/mock/{now:%Y%m%d%H}",
                published_at=now,
                tags=["딸기", "설향", "시세", direction],
                payload={"market": {"delta_pct": round(delta_pct, 1), "price_per_kg": latest_price}},
            )
        ]
