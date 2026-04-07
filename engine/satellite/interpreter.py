from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.satellite.indices import index_to_grade


@dataclass(slots=True)
class SatelliteInterpreter:
    crop_profile: Any | None = None

    def set_crop_profile(self, crop_profile: Any | None) -> None:
        self.crop_profile = crop_profile

    def interpret(self, sat_data: dict[str, Any], sensor_data: dict[str, Any] | None, farm_config: Any) -> str:  # noqa: ARG002
        if sat_data.get("status") == "cloud_blocked":
            return (
                "구름 때문에 최근 촬영을 참고하기 어려웠어요.\n"
                "위성은 바깥에서 본 참고 정보예요.\n"
                "오늘은 센서와 현장 확인을 먼저 믿어 주세요."
            )

        thresholds = getattr(self.crop_profile, "ndvi_thresholds", None)
        crop_type = getattr(self.crop_profile, "crop_type", "strawberry")
        grade = index_to_grade(float(sat_data.get("ndvi_mean") or 0.0), crop=crop_type, thresholds=thresholds)
        change = float(sat_data.get("change_vs_prev") or 0.0)
        house_id = int(sat_data.get("house_id") or 1)
        lines = [
            f"위성으로 봤을 때 {house_id}동 주변은 전체적으로 {grade['grade']} 쪽이에요.",
            "위성은 바깥에서 본 참고 정보예요.",
        ]
        if change <= -0.1:
            lines.append("지난 촬영보다 기운이 조금 떨어진 흐름이 보여요.")
        elif change >= 0.08:
            lines.append("지난 촬영보다 상태가 조금 나아진 흐름이 보여요.")
        else:
            lines.append("지난 촬영과 비교해도 큰 변화는 없어요.")

        if sensor_data:
            soil = sensor_data.get("soil_moisture_1")
            humidity = sensor_data.get("humidity")
            if soil is not None and float(soil) < 30:
                lines.append(f"센서를 보니 토양 수분이 {float(soil):.0f}% 수준이라 관수도 같이 점검해 주세요.")
            elif humidity is not None and float(humidity) >= 85:
                lines.append(f"센서를 보니 습도가 {float(humidity):.0f}%로 높아서 환기를 먼저 보는 게 좋아 보여요.")

        if grade["action"]:
            lines.append(f"{grade['action']} 쪽으로 보고 직접 확인해보시는 게 좋겠어요.")
        else:
            lines.append("급한 조정보다는 현장 흐름을 한 번 더 확인해보시는 게 좋겠어요.")
        return "\n".join(lines)
