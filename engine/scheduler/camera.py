from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.db.sqlite import SQLiteRepository


@dataclass(slots=True)
class CameraService:
    repository: SQLiteRepository
    mqtt_client: Any
    house_count: int

    def trigger_capture(self, house_id: int | None = None, trigger_source: str = "scheduler") -> dict[str, Any]:
        target_house = house_id or 0
        topic = f"camera/{target_house}/capture"
        result = "mock"
        if getattr(self.mqtt_client, "client", None) is not None:
            self.mqtt_client.publish(topic, '{"command":"capture"}')
            result = "published"
        self.repository.record_camera_capture(
            house_id=house_id,
            trigger_source=trigger_source,
            status=result,
            note="Phase 3 camera capture trigger",
        )
        return {"enabled": True, "topic": topic, "result": result}

    def run_round(self) -> list[dict[str, Any]]:
        results = []
        for house_id in range(1, self.house_count + 1):
            results.append(self.trigger_capture(house_id=house_id))
        return results
