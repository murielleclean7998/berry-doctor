from __future__ import annotations


def ventilation_recommendation(humidity: float, humidity_warning: float) -> str:
    if humidity >= humidity_warning + 5:
        return "환기를 바로 시작하는 게 좋겠어요."
    if humidity >= humidity_warning:
        return "짧게라도 오전 환기를 권장해요."
    return "지금은 급한 환기까지는 아니에요."
