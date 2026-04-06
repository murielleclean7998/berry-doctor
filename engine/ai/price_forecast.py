from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PriceForecast:
    baseline_price: int = 8200

    def recommend_shipment_day(self, price: int, trend: int) -> str:
        if trend > 0:
            return "이번 주 후반"
        return "가능하면 오늘 또는 내일"
