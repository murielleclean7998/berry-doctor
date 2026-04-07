from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.db.sqlite import SQLiteRepository
from engine.satellite.models import SatelliteObservation


@dataclass(slots=True)
class SatelliteRepository:
    repository: SQLiteRepository

    def save_observation(self, observation: SatelliteObservation) -> int:
        return self.repository.record_satellite_log(
            house_id=observation.house_id,
            capture_date=observation.capture_date,
            satellite=observation.satellite,
            cloud_pct=observation.cloud_pct,
            ndvi_mean=observation.ndvi_mean,
            ndvi_min=observation.ndvi_min,
            ndvi_max=observation.ndvi_max,
            ndwi_mean=observation.ndwi_mean,
            gndvi_mean=observation.gndvi_mean,
            change_vs_prev=observation.change_vs_prev,
            change_vs_year=observation.change_vs_year,
            change_vs_region=observation.change_vs_region,
            raw_data_path=observation.raw_data_path,
            status=observation.status,
            note=observation.note,
            payload=observation.payload,
        )

    def latest(self, house_id: int | None = None) -> dict[str, Any] | None:
        return self.repository.latest_satellite_log(house_id=house_id)

    def recent(self, limit: int = 20, house_id: int | None = None) -> list[dict[str, Any]]:
        return self.repository.recent_satellite_logs(limit=limit, house_id=house_id)
