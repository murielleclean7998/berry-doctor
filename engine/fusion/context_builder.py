from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ContextBuilder:
    config: Any

    def build(
        self,
        trigger: str,
        sensor_data: Any,
        satellite_data: Any,
        signals: list[dict[str, Any]] | list[Any],
        trigger_detail: str | None = None,
        extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        extras = extras or {}
        cross = self._cross_validation(sensor_data or {}, satellite_data or {}, signals)
        return {
            "trigger": trigger,
            "trigger_detail": trigger_detail or cross["trigger_detail"],
            "sensor": sensor_data or {},
            "satellite": satellite_data or {},
            "signals": list(signals or []),
            "farm": {
                "region": getattr(self.config, "farm_location", ""),
                "variety": getattr(self.config, "variety", "설향"),
                "growth_stage": extras.get("growth_stage", "과실비대기"),
                "regional_note": getattr(self.config, "farm_location", ""),
            },
            "cross_validation": cross,
            "extras": extras,
        }

    def _cross_validation(self, sensor: Any, satellite: Any, signals: list[Any]) -> dict[str, str]:
        sensor_says = "센서는 아직 큰 이상을 강하게 말하진 않아요."
        if isinstance(sensor, dict):
            humidity = float(sensor.get("humidity") or sensor.get("current_humidity") or 0.0)
            if humidity >= 85:
                sensor_says = "센서는 고습이라 곰팡이 쪽을 조심하라고 말해요."
        elif isinstance(sensor, list) and sensor:
            if any(float(item.get("humidity") or item.get("current_humidity") or 0.0) >= 85 for item in sensor if isinstance(item, dict)):
                sensor_says = "센서는 고습 구간이 있다고 말해요."

        satellite_says = "바깥에서 본 흐름은 큰 변화가 뚜렷하진 않아요."
        if isinstance(satellite, dict) and float(satellite.get("change_vs_prev") or 0.0) <= -0.1:
            satellite_says = "바깥에서 본 흐름은 최근 조금 약해진다고 말해요."
        elif isinstance(satellite, list) and satellite:
            if any(float(item.get("change_vs_prev") or 0.0) <= -0.1 for item in satellite if isinstance(item, dict)):
                satellite_says = "바깥에서 본 흐름은 약해지는 구간이 있다고 말해요."

        signal_says = "주변 소식은 잠잠한 편이에요."
        if signals:
            signal_says = "주변 소식도 비슷한 조건을 말하고 있어요."

        agreement = "한쪽만 강하게 말하고 있어요."
        if "고습" in sensor_says and "약해" in satellite_says and signals:
            agreement = "세 쪽이 비슷한 방향을 말하고 있어요."
        elif ("고습" in sensor_says and signals) or ("약해" in satellite_says and signals):
            agreement = "두 쪽이 비슷한 방향을 말하고 있어요."

        return {
            "sensor_says": sensor_says,
            "satellite_says": satellite_says,
            "signal_says": signal_says,
            "agreement": agreement,
            "trigger_detail": agreement,
        }
