from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class YieldEstimator:
    def estimate(
        self,
        recent_harvests: list[dict[str, Any]],
        monthly_total_kg: float,
        expected_price_per_kg: float,
        growth_stage: str,
        house_count: int,
    ) -> dict[str, Any]:
        harvest_count = max(len(recent_harvests), 1)
        average_harvest = monthly_total_kg / harvest_count if monthly_total_kg else 0.0

        stage_multiplier = 0.55
        if "개화" in growth_stage:
            stage_multiplier = 0.75
        elif "과실" in growth_stage:
            stage_multiplier = 1.0
        elif "수확" in growth_stage:
            stage_multiplier = 1.15

        projected_month_kg = round(max(monthly_total_kg, average_harvest * 12) * stage_multiplier, 1)
        projected_season_kg = round(projected_month_kg * max(house_count, 1) * 4.2, 1)
        projected_revenue = round(projected_season_kg * expected_price_per_kg, 0)

        return {
            "monthly_total_kg": round(monthly_total_kg, 1),
            "average_harvest_kg": round(average_harvest, 1),
            "projected_month_kg": projected_month_kg,
            "projected_season_kg": projected_season_kg,
            "projected_revenue": projected_revenue,
            "growth_stage": growth_stage,
        }
