from __future__ import annotations


def flood_action(max_hourly_rainfall: float) -> str:
    if max_hourly_rainfall >= 20:
        return "배수로와 하우스 주변 물길을 미리 확인해 주세요."
    return "침수 위험은 높지 않아요."
