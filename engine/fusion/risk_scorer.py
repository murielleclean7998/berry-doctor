from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RiskResult:
    composite: float
    level: str
    breakdown: dict[str, float]
    agreement: str


@dataclass(slots=True)
class RiskScorer:
    def eval_sensor(self, sensor: Any) -> float:
        if isinstance(sensor, list):
            return max((self.eval_sensor(item) for item in sensor), default=0.0)
        if not isinstance(sensor, dict):
            return 0.0
        humidity = float(sensor.get("humidity") or sensor.get("current_humidity") or 0.0)
        wetness = float(sensor.get("leaf_wetness") or 0.0)
        water_level = float(sensor.get("water_level") or 0.0)
        return min(100.0, (humidity * 0.7) + (wetness * 0.2) + (water_level * 15.0))

    def eval_satellite(self, satellite: Any) -> float:
        if isinstance(satellite, list):
            return max((self.eval_satellite(item) for item in satellite), default=0.0)
        if not isinstance(satellite, dict) or satellite.get("status") == "cloud_blocked":
            return 0.0
        ndvi = float(satellite.get("ndvi_mean") or 0.0)
        drop = abs(min(float(satellite.get("change_vs_prev") or 0.0), 0.0))
        return min(100.0, max(0.0, (0.7 - ndvi) * 80.0 + (drop * 250.0)))

    def eval_signal(self, signals: list[Any]) -> float:
        if not signals:
            return 0.0
        urgency_map = {"critical": 85.0, "warning": 68.0, "info": 42.0, "tip": 25.0}
        scores = []
        for signal in signals:
            urgency = signal.get("urgency") if isinstance(signal, dict) else getattr(getattr(signal, "relevance", None), "urgency", "info")
            relevance = signal.get("relevance_score") if isinstance(signal, dict) else getattr(getattr(signal, "relevance", None), "score", 0.4)
            scores.append(urgency_map.get(str(urgency), 35.0) * max(float(relevance), 0.2))
        return min(100.0, max(scores, default=0.0))

    def check_agreement(self, sensor_risk: float, satellite_risk: float, signal_risk: float) -> str:
        scores = [sensor_risk >= 60, satellite_risk >= 60, signal_risk >= 60]
        if all(scores):
            return "all_agree"
        if sum(scores) >= 2:
            return "two_agree"
        return "one_only"

    def composite_score(self, sensor_risk: float, satellite_risk: float, signal_risk: float, agreement: str) -> float:
        risks = [sensor_risk, satellite_risk, signal_risk]
        if agreement == "all_agree":
            return min(100.0, max(risks) * 1.3)
        if agreement == "two_agree":
            agreeing = [risk for risk in risks if risk >= 60]
            return min(100.0, (sum(agreeing) / max(len(agreeing), 1)) * 1.1)
        return min(100.0, max(risks) * 0.8)

    def classify_level(self, composite: float) -> str:
        if composite >= 80:
            return "critical"
        if composite >= 60:
            return "warning"
        if composite >= 40:
            return "caution"
        return "info"

    def calculate(self, context: dict[str, Any]) -> RiskResult:
        sensor_risk = self.eval_sensor(context.get("sensor"))
        satellite_risk = self.eval_satellite(context.get("satellite"))
        signal_risk = self.eval_signal(context.get("signals", []))
        agreement = self.check_agreement(sensor_risk, satellite_risk, signal_risk)
        composite = self.composite_score(sensor_risk, satellite_risk, signal_risk, agreement)
        return RiskResult(
            composite=round(composite, 1),
            level=self.classify_level(composite),
            breakdown={
                "sensor": round(sensor_risk, 1),
                "satellite": round(satellite_risk, 1),
                "signal": round(signal_risk, 1),
            },
            agreement=agreement,
        )
