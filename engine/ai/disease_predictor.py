from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.rules.disease_risk import calculate_disease_risk


@dataclass(slots=True)
class DiseasePredictor:
    profile: dict[str, Any]
    disease_params: dict[str, dict[str, Any]] | None = None

    def predict(self, temp: float, humidity: float, wet_hours: float, soil_temp: float) -> dict[str, dict[str, Any]]:
        return calculate_disease_risk(temp, humidity, wet_hours, soil_temp, self.profile, self.disease_params)
