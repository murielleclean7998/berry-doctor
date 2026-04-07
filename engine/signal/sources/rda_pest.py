from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from engine.signal.models import RawSignal
from engine.signal.sources import SignalSource


@dataclass(slots=True)
class RDAPestSource(SignalSource):
    config: Any = None
    repository: Any = None

    def __init__(self, config: Any, repository: Any) -> None:
        SignalSource.__init__(self, source_id="rda_pest", name="농진청 병해충 예찰", language="ko", check_interval_hours=6)
        self.config = config
        self.repository = repository

    async def fetch(self) -> list[RawSignal]:
        weather = self.repository.get_config("weather_cache", {})
        humidity = float(weather.get("current_humidity") or 0.0)
        if humidity < 80:
            return []
        now = datetime.now()
        province = str(getattr(self.config, "farm_location", "")).split()[0] if getattr(self.config, "farm_location", "") else "현지"
        return [
            RawSignal(
                source_id=self.source_id,
                source=self.name,
                title=f"{province} 딸기 잿빛곰팡이 주의",
                summary="습도가 높은 날이 이어져 잿빛곰팡이 예방 관리가 필요해요.",
                url=f"https://ncpms.rda.go.kr/mock/{now:%Y%m%d}",
                published_at=now,
                tags=["딸기", "잿빛곰팡이", province],
                payload={"environment": {"humidity_min": 80, "temp_min": 12, "temp_max": 25}},
            )
        ]
