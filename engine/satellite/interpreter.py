from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.satellite.indices import index_to_grade


@dataclass(slots=True)
class SatelliteInterpreter:
    def interpret(self, sat_data: dict[str, Any], sensor_data: dict[str, Any] | None, farm_config: Any) -> str:  # noqa: ARG002
        if sat_data.get("status") == "cloud_blocked":
            return (
                "구름 때문에 최근 촬영이 제대로 안 됐어요.\n"
                "위성은 바깥에서 본 참고 정보예요.\n"
                "오늘은 센서와 현장 확인을 먼저 보시면 좋아요."
            )

        grade = index_to_grade(float(sat_data.get("ndvi_mean") or 0.0))
        change = float(sat_data.get("change_vs_prev") or 0.0)
        house_id = int(sat_data.get("house_id") or 1)
        lines = [
            f"위성으로 봤을 때 {house_id}동 주변은 전체적으로 {grade['grade']} 쪽이에요.",
            "위성은 바깥에서 본 참고 정보예요.",
        ]
        if change <= -0.1:
            lines.append("지난 촬영보다 기운이 조금 떨어진 흐름이에요.")
        elif change >= 0.08:
            lines.append("지난 촬영보다 흐름은 조금 나아졌어요.")
        else:
            lines.append("지난 촬영과 비교하면 큰 변화는 크지 않아요.")

        if sensor_data:
            soil = sensor_data.get("soil_moisture_1")
            humidity = sensor_data.get("humidity")
            if soil is not None and float(soil) < 30:
                lines.append(f"센서를 보면 토양 수분이 {float(soil):.0f}% 수준이라 관수 점검이 좋아 보여요.")
            elif humidity is not None and float(humidity) >= 85:
                lines.append(f"센서를 보면 습도가 {float(humidity):.0f}%로 높아서 환기를 같이 보시면 좋아요.")

        if grade["action"]:
            lines.append(f"{grade['action']} 쪽으로 보고 직접 확인해보시는 게 좋겠어요.")
        else:
            lines.append("급한 조정보다는 현장 흐름을 함께 보시면 좋겠어요.")
        return "\n".join(lines)
