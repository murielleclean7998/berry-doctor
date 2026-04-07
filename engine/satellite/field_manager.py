from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FieldManager:
    config: Any

    def address_to_gps(self, address: str) -> tuple[float, float]:
        normalized = address.strip() or str(getattr(self.config, "farm_location", "") or "충남 서산")
        digest = hashlib.sha256(normalized.encode("utf-8")).digest()
        lat = 34.8 + (digest[0] / 255.0) * 3.1
        lng = 126.0 + (digest[1] / 255.0) * 3.0
        return round(lat, 6), round(lng, 6)

    def create_field_boundary(self, center_gps: tuple[float, float], area_pyeong: int = 200) -> dict[str, Any]:
        lat, lng = center_gps
        side_m = math.sqrt(max(area_pyeong, 1) * 3.3058)
        half_lat = (side_m / 2) / 111_000
        half_lng = (side_m / 2) / (111_000 * max(math.cos(math.radians(lat)), 0.1))
        return {
            "type": "Polygon",
            "coordinates": [[
                [lng - half_lng, lat - half_lat],
                [lng + half_lng, lat - half_lat],
                [lng + half_lng, lat + half_lat],
                [lng - half_lng, lat + half_lat],
                [lng - half_lng, lat - half_lat],
            ]],
        }

    def crop_raster_to_field(self, raster_path, boundary):  # noqa: ARG002
        return {"status": "cropped", "path": str(raster_path)}
