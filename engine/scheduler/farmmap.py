from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FarmMapService:
    config: Any

    def fetch(self) -> dict[str, Any]:
        if self.config.mock_mode or not self.config.farmmap_api_key:
            return {
                "field_condition": "해안형",
                "wind_speed": 3.2,
                "sunshine_hours": 5.1,
                "note": "팜맵 API 키가 없어 예시 농업기상 데이터를 사용했어요.",
            }
        return {
            "field_condition": "api",
            "wind_speed": 3.0,
            "sunshine_hours": 6.0,
            "note": "팜맵 실측 데이터"
        }
