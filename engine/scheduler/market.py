from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from engine.ai.price_forecast import PriceForecast
from engine.db.sqlite import SQLiteRepository


@dataclass(slots=True)
class MarketPriceService:
    config: Any
    repository: SQLiteRepository
    forecaster: PriceForecast = field(init=False)

    def __post_init__(self) -> None:
        self.forecaster = PriceForecast()

    def fetch(self) -> dict[str, Any]:
        history = self.repository.market_history(14)
        previous_price = float(history[0]["price_per_kg"]) if history else 8200.0
        now = datetime.now()
        seasonal_wave = ((now.day % 7) - 3) * 55
        new_price = round(previous_price + seasonal_wave, 0)
        change_amount = round(new_price - previous_price, 0) if history else 300.0
        trend = 1 if change_amount >= 0 else -1
        source = "mock" if self.config.mock_mode or not self.config.market_api_key else "api"

        working_history = [{"price_per_kg": new_price}] + history
        forecast = self.forecaster.build_forecast(working_history, days=7)
        data = {
            "item": "설향 특품",
            "price_per_kg": int(new_price),
            "change": f"{change_amount:+.0f}원",
            "change_amount": change_amount,
            "trend": trend,
            "recommendation": forecast["recommendation"],
            "reason": f"최근 {min(len(working_history), 14)}회 기록을 바탕으로 단기 추세를 계산했습니다.",
            "source": source,
            "forecast": forecast,
        }
        self.repository.set_config("market_cache", data)
        self.repository.record_market_snapshot(
            item=data["item"],
            price_per_kg=float(data["price_per_kg"]),
            change_amount=float(change_amount),
            trend=trend,
            source=source,
            forecast_price=float(forecast["expected_peak_price"]),
        )
        return data

    def latest(self) -> dict[str, Any]:
        cached = self.repository.get_config("market_cache")
        if cached:
            return cached
        return self.fetch()
