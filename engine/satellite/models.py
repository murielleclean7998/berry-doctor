from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class SatelliteObservation:
    house_id: int
    capture_date: date
    satellite: str
    cloud_pct: float
    ndvi_mean: float
    ndvi_min: float
    ndvi_max: float
    ndwi_mean: float
    gndvi_mean: float
    change_vs_prev: float = 0.0
    change_vs_year: float = 0.0
    change_vs_region: float = 0.0
    raw_data_path: str | None = None
    status: str = "ok"
    note: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
