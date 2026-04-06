from __future__ import annotations


def frost_action(tomorrow_min_temp: float, threshold: float) -> str:
    if tomorrow_min_temp < threshold:
        return "오늘 밤 보온 준비와 외기 유입 구간 점검이 필요해요."
    return "동해 위험은 낮아 보여요."
