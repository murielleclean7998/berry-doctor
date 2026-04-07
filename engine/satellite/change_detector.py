from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ChangeDetector:
    def compare_temporal(self, current, previous):
        delta = float(current.ndvi_mean) - float(previous.ndvi_mean)
        return {"delta": delta, "direction": "up" if delta > 0 else "down"}

    def compare_yearly(self, current, year_ago):
        delta = float(current.ndvi_mean) - float(year_ago.ndvi_mean)
        return {"delta": delta, "direction": "up" if delta > 0 else "down"}

    def compare_regional(self, field_ndvi: float, region_avg_ndvi: float):
        delta = float(field_ndvi) - float(region_avg_ndvi)
        return {"delta": delta, "direction": "up" if delta > 0 else "down"}

    def detect_anomaly(self, current, history_list: list[Any]) -> dict[str, Any]:
        if not history_list:
            return {"is_anomaly": False, "reason": "history_missing"}
        deltas = [float(current.ndvi_mean) - float(item.ndvi_mean) for item in history_list[:3]]
        min_delta = min(deltas)
        return {"is_anomaly": min_delta <= -0.1, "reason": "rapid_drop" if min_delta <= -0.1 else "stable"}
