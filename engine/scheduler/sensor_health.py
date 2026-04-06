from __future__ import annotations

from dataclasses import dataclass

from engine.db.sqlite import SQLiteRepository


@dataclass(slots=True)
class SensorHealthService:
    repository: SQLiteRepository

    def run(self) -> dict:
        deleted = self.repository.prune_old_sensor_logs(90)
        return {
            "phase": 0,
            "sensor_mode": "software_only",
            "pruned_rows": deleted,
        }
