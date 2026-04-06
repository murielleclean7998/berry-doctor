from __future__ import annotations


def light_action(lux: float, threshold_lux: float = 10000) -> str:
    if lux < threshold_lux:
        return "광량이 부족해서 보광 또는 비닐 청소를 검토해 주세요."
    return "현재 광량은 크게 부족하지 않아요."
