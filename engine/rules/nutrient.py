from __future__ import annotations


def nutrient_hint(cultivation_type: str) -> str:
    if cultivation_type == "토경":
        return "Phase 0에서는 토양수분과 생육 단계 중심으로 관비 리듬만 안내해요."
    return "Phase 0에서는 수경 세부 제어 대신 환경 흐름 위주로 안내해요."
