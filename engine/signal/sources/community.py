from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from engine.signal.models import RawSignal
from engine.signal.sources import SignalSource


@dataclass(slots=True)
class CommunitySource(SignalSource):
    config: Any = None
    repository: Any = None
    emit_callback: Callable[[RawSignal], Any] | None = None
    crop_profile: Any | None = None

    def __init__(
        self,
        config: Any,
        repository: Any,
        emit_callback: Callable[[RawSignal], Any] | None = None,
        crop_profile: Any | None = None,
    ) -> None:
        SignalSource.__init__(self, source_id="community", name="BerryDoctor 커뮤니티", language="ko", check_interval_hours=1)
        self.config = config
        self.repository = repository
        self.emit_callback = emit_callback
        self.crop_profile = crop_profile

    async def fetch(self) -> list[RawSignal]:
        return []

    def on_local_detection(self, detection: Any, farm_context: dict[str, Any] | None = None) -> RawSignal | None:
        context = farm_context or {}
        if not bool(context.get("share_to_community", getattr(self.config, "share_to_community", False))):
            return None
        threshold = int(getattr(self.config, "community_min_user_threshold", 5) or 5)
        community_users = int(self.repository.get_config("community_user_count", 0) or 0)
        if community_users < threshold:
            return None

        full_location = str(context.get("region_name") or getattr(self.config, "farm_location", "지역")).strip() or "지역"
        region_name = full_location.split("_")[0].split()[0] if full_location else "지역"
        sensor = context.get("sensor") or {}
        crop_name = str(context.get("crop_name_ko") or getattr(self.crop_profile, "crop_name_ko", "딸기"))

        signal = RawSignal(
            source_id=self.source_id,
            source=self.name,
            title=f"{region_name}에서 {getattr(detection, 'label_ko', '병해')} 감지",
            summary=(
                f"확신도 {getattr(detection, 'confidence', 0):.1f}%"
                f", 환경 {sensor.get('temp_indoor', '-')}°C / {sensor.get('humidity', '-')}%"
            ),
            url=f"community://{region_name}/{datetime.now():%Y%m%d%H%M%S}",
            published_at=datetime.now(),
            tags=[crop_name, region_name, getattr(detection, "label", "disease"), "커뮤니티"],
            payload={
                "environment": {
                    "humidity_min": float(sensor.get("humidity") or 0.0),
                    "temp_min": float(sensor.get("temp_indoor") or sensor.get("temp_outdoor") or 0.0) - 2.0,
                    "temp_max": float(sensor.get("temp_indoor") or sensor.get("temp_outdoor") or 0.0) + 2.0,
                }
            },
        )
        if self.emit_callback is not None:
            self.emit_callback(signal)
        return signal
