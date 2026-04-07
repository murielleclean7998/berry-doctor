from __future__ import annotations

from dataclasses import dataclass

from engine.db.sqlite import SQLiteRepository


@dataclass(slots=True)
class SensorHealthService:
    repository: SQLiteRepository
    raw_retention_days: int = 90
    aggregate_retention_days: int = 365

    def run(self) -> dict:
        deleted = self.repository.prune_old_sensor_logs(self.raw_retention_days, self.aggregate_retention_days)
        return {
            "phase": 0,
            "sensor_mode": "sampled_plus_aggregate",
            **deleted,
        }
