from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.rules.disease_risk import calculate_disease_risk, top_risk


@dataclass(slots=True)
class RuleEvent:
    rule_id: str
    severity: str
    message_key: str
    payload: dict[str, Any]


class RuleEngine:
    def __init__(self, regional_profile: dict[str, Any]):
        self.profile = regional_profile

    def evaluate_weather(self, weather_snapshot: dict[str, Any]) -> tuple[list[RuleEvent], dict[str, dict[str, Any]]]:
        thresholds = self.profile.get("thresholds", {})
        disease_risk = calculate_disease_risk(
            temp=float(weather_snapshot.get("current_temp", 18)),
            humidity=float(weather_snapshot.get("current_humidity", 70)),
            wet_hours=float(weather_snapshot.get("estimated_wet_hours", 4)),
            soil_temp=float(weather_snapshot.get("soil_temp", weather_snapshot.get("current_temp", 18))),
            profile=self.profile,
        )
        events: list[RuleEvent] = []
        if float(weather_snapshot.get("tomorrow_min_temp", 10)) < thresholds.get("frost_warning_temp", -5):
            events.append(
                RuleEvent(
                    rule_id="FROST_WARNING",
                    severity="warning",
                    message_key="alert_frost",
                    payload={"tomorrow_min": weather_snapshot.get("tomorrow_min_temp", 0)},
                )
            )
        if float(weather_snapshot.get("max_hourly_rainfall", 0)) >= thresholds.get("heavy_rain_mm_per_hour", 20):
            events.append(
                RuleEvent(
                    rule_id="HEAVY_RAIN_WARNING",
                    severity="warning",
                    message_key="alert_rain",
                    payload={"max_rainfall": weather_snapshot.get("max_hourly_rainfall", 0)},
                )
            )
        disease_name, disease_meta = top_risk(disease_risk)
        if disease_meta["risk"] >= 70:
            events.append(
                RuleEvent(
                    rule_id="DISEASE_RISK",
                    severity="warning",
                    message_key="alert_disease",
                    payload={"disease_name": disease_name, "risk": disease_meta["risk"], "action": disease_meta["action"]},
                )
            )
        return events, disease_risk
