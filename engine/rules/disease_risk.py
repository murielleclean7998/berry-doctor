from __future__ import annotations

from math import exp
from typing import Any


def _gaussian_score(value: float, center: float, spread: float) -> float:
    return max(0.0, min(100.0, 100.0 * exp(-((value - center) ** 2) / max(spread, 1e-6))))


def _level(risk: float) -> str:
    if risk >= 75:
        return "critical"
    if risk >= 55:
        return "high"
    if risk >= 30:
        return "medium"
    return "low"


def _default_disease_params() -> dict[str, dict[str, Any]]:
    return {
        "botrytis": {
            "center_temp": 22,
            "spread": 18,
            "weight_temp": 0.4,
            "weight_humidity": 0.35,
            "weight_other": 0.25,
            "humidity_factor": 5,
            "other_factor_key": "wet_hours",
            "other_multiplier": 12,
            "action_ko": "환기와 시든 꽃잎 제거를 함께 해주세요.",
        },
        "powdery_mildew": {
            "center_temp": 20,
            "spread": 25,
            "weight_temp": 0.45,
            "weight_humidity": 0.35,
            "weight_other": 0.2,
            "humidity_center": 60,
            "humidity_spread": 300,
            "other_factor_key": "dry_hours",
            "other_base": 40,
            "other_multiplier": 5,
            "action_ko": "잎 뒷면을 자주 확인하고 초기 병반은 빨리 떼어내는 게 좋아요.",
        },
        "anthracnose": {
            "center_temp": 28,
            "spread": 20,
            "weight_temp": 0.45,
            "weight_humidity": 0.35,
            "weight_other": 0.2,
            "humidity_threshold": 75,
            "humidity_factor": 4,
            "other_factor_key": "wet_hours",
            "other_multiplier": 10,
            "action_ko": "육묘와 상처 난 주를 먼저 분리해서 퍼지는 걸 막아주세요.",
        },
        "fusarium_wilt": {
            "center_temp": 27,
            "spread": 20,
            "weight_temp": 0.65,
            "weight_humidity": 0.35,
            "use_soil_temp": True,
            "humidity_threshold": 20,
            "humidity_factor": 4,
            "action_ko": "토양 과습과 뿌리 상태를 같이 확인해보셔야 해요.",
        },
        "leaf_blight": {
            "center_temp": 26,
            "spread": 24,
            "weight_temp": 0.45,
            "weight_humidity": 0.35,
            "weight_other": 0.2,
            "humidity_threshold": 78,
            "humidity_factor": 4,
            "other_factor_key": "wet_hours",
            "other_multiplier": 10,
            "action_ko": "고온다습 조건은 오래 끌지 않게 관리해 주세요.",
        },
    }


def _other_component(params: dict[str, Any], wet_hours: float) -> float:
    key = str(params.get("other_factor_key") or "")
    if not key:
        return 0.0
    multiplier = float(params.get("other_multiplier", 0.0) or 0.0)
    if key == "wet_hours":
        return min(100.0, wet_hours * multiplier)
    if key == "dry_hours":
        base = float(params.get("other_base", 0.0) or 0.0)
        return max(0.0, base - (wet_hours * multiplier))
    return 0.0


def _humidity_component(
    humidity: float,
    temp: float,
    profile: dict[str, Any],
    params: dict[str, Any],
    coastal_bonus: float,
) -> float:
    if "humidity_center" in params and "humidity_spread" in params:
        return _gaussian_score(humidity, float(params["humidity_center"]), float(params["humidity_spread"]))

    threshold = params.get("humidity_threshold")
    if threshold is None and "humidity_factor" in params:
        threshold = profile.get("thresholds", {}).get("humidity_warning", 80)
    if threshold is None:
        return 0.0

    factor = float(params.get("humidity_factor", 0.0) or 0.0)
    if params.get("use_soil_temp") and not params.get("other_factor_key"):
        return max(0.0, temp - float(threshold)) * factor
    return max(0.0, (humidity + coastal_bonus) - float(threshold)) * factor


def _calculate_entry(
    disease_key: str,
    params: dict[str, Any],
    temp: float,
    humidity: float,
    wet_hours: float,
    soil_temp: float,
    profile: dict[str, Any],
    coastal_bonus: float,
) -> dict[str, Any]:
    base_temp_value = soil_temp if params.get("use_soil_temp") else temp
    temp_component = _gaussian_score(base_temp_value, float(params["center_temp"]), float(params["spread"]))
    humidity_component = _humidity_component(humidity, temp, profile, params, coastal_bonus)
    other_component = _other_component(params, wet_hours)

    risk = min(
        100.0,
        (float(params.get("weight_temp", 0.0) or 0.0) * temp_component)
        + (float(params.get("weight_humidity", 0.0) or 0.0) * humidity_component)
        + (float(params.get("weight_other", 0.0) or 0.0) * other_component),
    )
    return {
        "risk": round(risk, 1),
        "level": _level(risk),
        "action": str(params.get("action_ko") or disease_key),
    }


def calculate_disease_risk(
    temp: float,
    humidity: float,
    wet_hours: float,
    soil_temp: float,
    profile: dict[str, Any],
    disease_params: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    params_map = disease_params or _default_disease_params()
    coastal_bonus = 5.0 if profile.get("type") == "coastal" else 0.0
    return {
        disease_key: _calculate_entry(
            disease_key,
            params,
            temp=temp,
            humidity=humidity,
            wet_hours=wet_hours,
            soil_temp=soil_temp,
            profile=profile,
            coastal_bonus=coastal_bonus,
        )
        for disease_key, params in params_map.items()
    }


def top_risk(risk_map: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    return max(risk_map.items(), key=lambda item: item[1]["risk"])
