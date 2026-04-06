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


def calculate_disease_risk(temp: float, humidity: float, wet_hours: float, soil_temp: float, profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    coastal_bonus = 5 if profile.get("type") == "coastal" else 0
    humidity_warning = profile.get("thresholds", {}).get("humidity_warning", 80)

    botrytis = min(
        100.0,
        0.4 * _gaussian_score(temp, 22, 18)
        + 0.35 * max(0.0, (humidity + coastal_bonus - humidity_warning) * 5)
        + 0.25 * min(100.0, wet_hours * 12),
    )
    powdery = min(
        100.0,
        0.45 * _gaussian_score(temp, 20, 25)
        + 0.35 * _gaussian_score(humidity, 60, 300)
        + 0.20 * max(0.0, 40 - wet_hours * 5),
    )
    anthracnose = min(
        100.0,
        0.45 * _gaussian_score(temp, 28, 20)
        + 0.35 * max(0.0, humidity - 75) * 4
        + 0.20 * min(100.0, wet_hours * 10),
    )
    fusarium = min(
        100.0,
        0.65 * _gaussian_score(soil_temp, 27, 20)
        + 0.35 * max(0.0, temp - 20) * 4,
    )
    leaf_blight = min(
        100.0,
        0.45 * _gaussian_score(temp, 26, 24)
        + 0.35 * max(0.0, humidity - 78) * 4
        + 0.20 * min(100.0, wet_hours * 10),
    )

    return {
        "botrytis": {"risk": round(botrytis, 1), "level": _level(botrytis), "action": "오전 환기와 시든 꽃잎 제거가 필요해요."},
        "powdery_mildew": {"risk": round(powdery, 1), "level": _level(powdery), "action": "잎 표면을 자주 확인하고 초기 병반을 빨리 끊는 게 좋아요."},
        "anthracnose": {"risk": round(anthracnose, 1), "level": _level(anthracnose), "action": "젖은 식물체 접촉을 줄이고 의심 주를 먼저 분리해 주세요."},
        "fusarium_wilt": {"risk": round(fusarium, 1), "level": _level(fusarium), "action": "토양 과습과 연작 피해 징후를 같이 보셔야 해요."},
        "leaf_blight": {"risk": round(leaf_blight, 1), "level": _level(leaf_blight), "action": "고온다습 조건을 짧게 끊어주는 게 중요해요."}
    }


def top_risk(risk_map: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    return max(risk_map.items(), key=lambda item: item[1]["risk"])
