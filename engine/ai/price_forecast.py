from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any


@dataclass(slots=True)
class PriceForecast:
    baseline_price: int = 8200

    def build_forecast(self, history: list[dict[str, Any]], days: int = 7) -> dict[str, Any]:
        if not history:
            prices = [float(self.baseline_price)]
        else:
            prices = [float(item.get("price_per_kg", self.baseline_price)) for item in history[:14]]

        last_price = prices[0]
        avg_price = mean(prices)
        short_window = prices[:3] if len(prices) >= 3 else prices
        momentum = last_price - mean(short_window)
        slope = (last_price - prices[-1]) / max(len(prices) - 1, 1)

        forecast_days: list[dict[str, Any]] = []
        best_price = last_price
        best_day_index = 0
        for day_index in range(days):
            projected = last_price + (slope * (day_index + 1)) + (momentum * 0.35)
            projected = round((projected * 0.7) + (avg_price * 0.3), 0)
            forecast_days.append({"day_offset": day_index + 1, "price_per_kg": projected})
            if projected > best_price:
                best_price = projected
                best_day_index = day_index + 1

        volatility = max(prices) - min(prices) if len(prices) > 1 else 0.0
        recommendation = self.recommend_shipment_day(best_day_index, volatility)
        return {
            "predicted_prices": forecast_days,
            "expected_peak_price": best_price,
            "expected_peak_day_offset": best_day_index,
            "volatility": round(volatility, 1),
            "recommendation": recommendation,
            "confidence": self._confidence(history),
        }

    def recommend_shipment_day(self, best_day_index: int, volatility: float) -> str:
        if best_day_index <= 1:
            return "오늘 또는 내일 출하"
        if best_day_index <= 3:
            return f"{best_day_index}일 뒤 출하 검토"
        if volatility >= 900:
            return "변동성이 커서 분할 출하를 권장해요"
        return f"{best_day_index}일 뒤 출하 유리"

    def _confidence(self, history: list[dict[str, Any]]) -> float:
        coverage = min(len(history), 14) / 14
        return round(55 + (coverage * 35), 1)
