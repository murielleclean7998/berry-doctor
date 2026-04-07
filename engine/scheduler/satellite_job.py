from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from engine.satellite.change_detector import ChangeDetector
from engine.satellite.copernicus import CopernicusClient
from engine.satellite.db import SatelliteRepository
from engine.satellite.field_manager import FieldManager
from engine.satellite.indices import calc_gndvi, calc_ndvi, calc_ndwi, max_value, mean_value, min_value
from engine.satellite.interpreter import SatelliteInterpreter
from engine.satellite.models import SatelliteObservation


@dataclass(slots=True)
class SatelliteJobService:
    config: Any
    repository: Any
    sender: Any | None = None
    crop_profile: Any | None = None
    fusion: Any | None = None
    db: Any = field(default=None, init=False)
    client: Any = field(default=None, init=False)
    field_manager: Any = field(default=None, init=False)
    change_detector: Any = field(default=None, init=False)
    interpreter: Any = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.db = SatelliteRepository(self.repository)
        self.client = CopernicusClient(self.config)
        self.field_manager = FieldManager(self.config)
        self.change_detector = ChangeDetector()
        self.interpreter = SatelliteInterpreter(crop_profile=self.crop_profile)

    def set_fusion(self, fusion: Any) -> None:
        self.fusion = fusion

    def set_crop_profile(self, crop_profile: Any | None) -> None:
        self.crop_profile = crop_profile
        self.interpreter.set_crop_profile(crop_profile)

    def check_new_image(self) -> dict[str, Any]:
        if not bool(getattr(self.config, "satellite_enabled", True)):
            return {"status": "disabled"}
        lat, lng = self.field_manager.address_to_gps(getattr(self.config, "farm_location", ""))
        candidate = asyncio.run(
            self.client.get_latest_image(
                lat,
                lng,
                max_cloud_pct=int(getattr(self.config, "satellite_max_cloud_pct", 40) or 40),
            )
        )
        if candidate is None:
            message = self.interpreter.interpret({"status": "cloud_blocked"}, self.repository.latest_sensor_snapshot(), self.config)
            if self.sender is not None:
                self.sender.send_text(message, severity="info", rule_id="SATELLITE_CLOUD_BLOCKED")
            return {"status": "cloud_blocked", "message": message}

        latest = self.db.latest()
        if latest is not None and str(latest.get("capture_date")) == str(candidate["capture_date"]):
            return {"status": "unchanged", "capture_date": str(candidate["capture_date"])}

        bands = asyncio.run(self.client.download_bands(candidate["tile_id"]))
        ndvi = calc_ndvi(bands["B04"], bands["B08"])
        ndwi = calc_ndwi(bands["B08"], bands["B11"])
        gndvi = calc_gndvi(bands["B03"], bands["B08"])
        previous_row = self.db.latest()
        previous_value = float(previous_row.get("ndvi_mean") or 0.0) if previous_row else 0.0
        year_row = self.repository.latest_satellite_log(days_ago=365)
        year_value = float(year_row.get("ndvi_mean") or 0.0) if year_row else 0.0

        observation = SatelliteObservation(
            house_id=1,
            capture_date=candidate["capture_date"],
            satellite="sentinel2",
            cloud_pct=float(candidate["cloud_pct"]),
            ndvi_mean=round(mean_value(ndvi), 4),
            ndvi_min=round(min_value(ndvi), 4),
            ndvi_max=round(max_value(ndvi), 4),
            ndwi_mean=round(mean_value(ndwi), 4),
            gndvi_mean=round(mean_value(gndvi), 4),
            change_vs_prev=round(mean_value(ndvi) - previous_value, 4) if previous_row else 0.0,
            change_vs_year=round(mean_value(ndvi) - year_value, 4) if year_row else 0.0,
            change_vs_region=round(mean_value(ndvi) - 0.58, 4),
            raw_data_path=f"satellite/{candidate['tile_id']}",
            payload={"boundary": self.field_manager.create_field_boundary((lat, lng), int(getattr(self.config, 'field_area_pyeong', 200) or 200))},
        )
        row_id = self.db.save_observation(observation)
        row = self.repository.latest_satellite_log()
        message = self.interpreter.interpret(row or observation.__dict__, self.repository.latest_sensor_snapshot(), self.config)
        self.repository.set_config("last_satellite_message", {"id": row_id, "message": message})
        if self.fusion is not None and row is not None:
            self.fusion.on_satellite_update(row)
        return {"status": "ok", "id": row_id, "message": message}
