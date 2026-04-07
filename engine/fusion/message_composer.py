from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.fusion.templates import LEVEL_PREFIX


@dataclass(slots=True)
class MessageComposer:
    def compose(self, context: dict[str, Any], risk: Any) -> str:
        prefix = LEVEL_PREFIX.get(risk.level, LEVEL_PREFIX["info"])
        sensor = context.get("sensor") or {}
        satellite = context.get("satellite") or {}
        signals = context.get("signals") or []
        house_id = int(sensor.get("house_id") or satellite.get("house_id") or 1)
        lines = [prefix, f"{house_id}동 흐름을 같이 보면 이래요."]

        humidity = sensor.get("humidity") or sensor.get("current_humidity")
        if humidity is not None:
            lines.append(f"지금 습도는 {float(humidity):.0f}% 쪽이에요.")

        if satellite:
            if satellite.get("status") == "cloud_blocked":
                lines.append("최근 바깥 촬영은 구름 때문에 못 봤어요.")
            elif float(satellite.get("change_vs_prev") or 0.0) <= -0.1:
                lines.append("바깥에서 본 흐름도 최근 조금 약해졌어요.")
            else:
                lines.append("바깥에서 본 흐름은 크게 무너지진 않았어요.")

        if signals:
            first = signals[0]
            title = first.get("title") if isinstance(first, dict) else getattr(first, "title", "")
            lines.append(f"주변 소식도 비슷한 방향이에요: {title}")

        if risk.agreement == "all_agree":
            lines.append("세 쪽이 비슷한 말을 하고 있어서 우선순위를 높게 보시면 좋아요.")
        elif risk.agreement == "two_agree":
            lines.append("두 쪽이 비슷하게 말하고 있어서 그냥 넘기긴 아쉬워요.")
        else:
            lines.append("아직은 한쪽 신호가 더 강한 정도예요.")

        lines.append("자동으로 기계를 움직인 건 아니고, 직접 확인해보시는 게 좋겠어요.")
        return "\n".join(lines)[:500]

    def compose_daily(self, context: dict[str, Any], risk: Any) -> str:
        sensors = context.get("sensor") or []
        signals = context.get("signals") or []
        satellite = context.get("satellite") or []
        if isinstance(sensors, dict):
            sensors = [sensors]
        if isinstance(satellite, dict):
            satellite = [satellite]
        lines = [f"📋 {context.get('extras', {}).get('date_label', '오늘')} 하루 정리"]
        if sensors:
            house_lines = []
            for item in sensors[:5]:
                humidity = float(item.get("humidity") or item.get("current_humidity") or 0.0)
                status = "주의" if humidity >= 85 else "좋음"
                emoji = "🟡" if humidity >= 85 else "🟢"
                house_lines.append(f"{int(item.get('house_id') or 1)}동 {status} {emoji}")
            lines.append("🌱 하우스 상태: " + " / ".join(house_lines))
        if satellite:
            recent = satellite[0]
            if recent.get("status") == "cloud_blocked":
                lines.append("🛰 바깥에서 본 상태: 구름 때문에 새 촬영이 없었어요.")
            else:
                lines.append("🛰 바깥에서 본 상태: 최근 흐름을 참고로 같이 보고 있어요.")
        if signals:
            lines.append("📡 오늘의 소식:")
            for item in signals[:2]:
                title = item.get("title") if isinstance(item, dict) else getattr(item, "title", "")
                lines.append(f"• {title}")
        tasks = context.get("extras", {}).get("tasks") or []
        if tasks:
            lines.append("📅 내일 할 일:")
            for index, task in enumerate(tasks[:3], start=1):
                lines.append(f"{index}. {task}")
        market = context.get("extras", {}).get("market") or {}
        if market:
            lines.append(f"💰 설향 시세: {market.get('price_per_kg', '-')}원/kg")
        lines.append("오늘 내용도 참고 자료를 묶어 본 거라, 직접 확인해보시는 게 좋겠어요.")
        return "\n".join(lines)[:500]
