from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.control.greenhouse import ControlActionProposal
from engine.control.pid import NutrientPIDController, PIDSummary
from engine.rules.climate import ventilation_recommendation
from engine.rules.disease_risk import calculate_disease_risk, top_risk
from engine.rules.flood import flood_action
from engine.rules.frost import frost_action
from engine.rules.light import light_action


@dataclass(slots=True)
class RuleEvent:
    rule_id: str
    severity: str
    message_key: str
    payload: dict[str, Any]


@dataclass(slots=True)
class ControlEvaluation:
    events: list[RuleEvent]
    proposals: list[ControlActionProposal]
    disease_risk: dict[str, dict[str, Any]]
    pid_summary: PIDSummary


class RuleEngine:
    def __init__(self, regional_profile: dict[str, Any]):
        self.profile = regional_profile
        self.thresholds = regional_profile.get("thresholds", {})
        self.pid = NutrientPIDController(target_ec=1.0, target_ph=6.0)

    def update_profile(self, regional_profile: dict[str, Any]) -> None:
        self.profile = regional_profile
        self.thresholds = regional_profile.get("thresholds", {})

    def evaluate_weather(self, weather_snapshot: dict[str, Any]) -> tuple[list[RuleEvent], dict[str, dict[str, Any]]]:
        thresholds = self.thresholds
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
                    payload={
                        "tomorrow_min": weather_snapshot.get("tomorrow_min_temp", 0),
                        "action": frost_action(
                            float(weather_snapshot.get("tomorrow_min_temp", 0)),
                            float(thresholds.get("frost_warning_temp", -5)),
                        ),
                    },
                )
            )
        if float(weather_snapshot.get("max_hourly_rainfall", 0)) >= thresholds.get("heavy_rain_mm_per_hour", 20):
            events.append(
                RuleEvent(
                    rule_id="HEAVY_RAIN_WARNING",
                    severity="warning",
                    message_key="alert_rain",
                    payload={
                        "max_rainfall": weather_snapshot.get("max_hourly_rainfall", 0),
                        "action": flood_action(float(weather_snapshot.get("max_hourly_rainfall", 0))),
                    },
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

    def evaluate_environment(self, sensor_snapshot: dict[str, Any], weather_snapshot: dict[str, Any] | None = None) -> ControlEvaluation:
        weather_snapshot = weather_snapshot or {}
        house_id = int(sensor_snapshot.get("house_id") or 1)
        risk_source = weather_snapshot if weather_snapshot else sensor_snapshot
        events, disease_risk = self.evaluate_weather(risk_source)
        proposals: list[ControlActionProposal] = []

        humidity = float(sensor_snapshot.get("humidity") or weather_snapshot.get("current_humidity") or 0)
        temp_indoor = float(sensor_snapshot.get("temp_indoor") or weather_snapshot.get("current_temp") or 0)
        light_lux = float(sensor_snapshot.get("light_lux") or 0)
        water_level = float(sensor_snapshot.get("water_level") or 0)
        co2_ppm = float(sensor_snapshot.get("co2_ppm") or 0)
        soil_values = [value for value in [sensor_snapshot.get("soil_moisture_1"), sensor_snapshot.get("soil_moisture_2")] if value is not None]
        avg_soil = sum(float(value) for value in soil_values) / len(soil_values) if soil_values else None

        if humidity >= float(self.thresholds.get("humidity_warning", 80)):
            reason = ventilation_recommendation(humidity, float(self.thresholds.get("humidity_warning", 80)))
            proposals.append(
                ControlActionProposal(
                    house_id=house_id,
                    device="ventilation",
                    action="on",
                    mode="auto",
                    reason=reason,
                    payload={"duration_minutes": 15},
                )
            )
            events.append(
                RuleEvent(
                    rule_id="VENTILATION_RECOMMENDED",
                    severity="warning" if humidity >= float(self.thresholds.get("humidity_critical", 88)) else "info",
                    message_key="alert_disease",
                    payload={"disease_name": "humidity", "risk": round(humidity, 1), "action": reason},
                )
            )

        if temp_indoor >= 28:
            proposals.append(
                ControlActionProposal(
                    house_id=house_id,
                    device="ventilation",
                    action="boost",
                    mode="auto",
                    reason="실내 온도가 높아 환기 강도를 올립니다.",
                    payload={"duration_minutes": 20},
                )
            )

        if light_lux and light_lux < max(10000.0, float(self.thresholds.get("light_target_umol", 150)) * 70):
            proposals.append(
                ControlActionProposal(
                    house_id=house_id,
                    device="supplemental_light",
                    action="on",
                    mode="auto",
                    reason=light_action(light_lux),
                    payload={"duration_minutes": 30},
                )
            )

        if avg_soil is not None and avg_soil < 28:
            proposals.append(
                ControlActionProposal(
                    house_id=house_id,
                    device="irrigation",
                    action="pulse",
                    mode="auto",
                    reason="토양 수분이 낮아 관수 펄스를 권장합니다.",
                    payload={"duration_seconds": 20, "average_soil_moisture": round(avg_soil, 1)},
                )
            )

        if water_level >= 0.8 or float(weather_snapshot.get("max_hourly_rainfall", 0) or 0) >= float(self.thresholds.get("heavy_rain_mm_per_hour", 20)):
            proposals.append(
                ControlActionProposal(
                    house_id=house_id,
                    device="drain_pump",
                    action="on",
                    mode="auto",
                    reason=flood_action(float(weather_snapshot.get("max_hourly_rainfall", 0) or 0)),
                    payload={"duration_minutes": 10},
                )
            )

        if co2_ppm and co2_ppm < 450:
            proposals.append(
                ControlActionProposal(
                    house_id=house_id,
                    device="co2",
                    action="on",
                    mode="auto",
                    reason="CO2 농도가 낮아 보강을 권장합니다.",
                    payload={"duration_minutes": 10},
                )
            )

        pid_summary = self.pid.evaluate(sensor_snapshot.get("solution_ec"), sensor_snapshot.get("solution_ph"))
        for command in pid_summary.commands:
            proposals.append(
                ControlActionProposal(
                    house_id=house_id,
                    device=command.device,
                    action=command.direction,
                    mode="auto",
                    reason=command.reason,
                    payload={"duration_seconds": command.duration_seconds},
                )
            )

        return ControlEvaluation(
            events=events,
            proposals=proposals,
            disease_risk=disease_risk,
            pid_summary=pid_summary,
        )
