from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None


@dataclass(slots=True)
class CopernicusClient:
    config: Any

    async def get_latest_image(self, lat: float, lng: float, max_cloud_pct: int = 40) -> dict[str, Any] | None:
        seed = hashlib.sha256(f"{lat:.6f}:{lng:.6f}:{date.today():%Y-%m-%d}".encode("utf-8")).digest()
        cloud_pct = float(seed[0] % 65)
        if cloud_pct > max_cloud_pct:
            return None
        return {
            "tile_id": f"S2-{seed.hex()[:10]}",
            "capture_date": date.today(),
            "cloud_pct": cloud_pct,
            "download_url": "mock://copernicus",
        }

    async def download_bands(self, tile_id: str, bands: list[str] | None = None) -> dict[str, Any]:
        bands = bands or ["B04", "B08", "B03", "B11", "SCL"]
        seed = hashlib.sha256(tile_id.encode("utf-8")).digest()
        base = 0.2 + (seed[1] / 255.0) * 0.5
        if np is not None:
            red = np.full((3, 3), base, dtype=float)
            nir = np.full((3, 3), min(base + 0.25, 0.95), dtype=float)
            green = np.full((3, 3), max(base - 0.05, 0.05), dtype=float)
            swir = np.full((3, 3), max(base - 0.08, 0.03), dtype=float)
            scl = np.zeros((3, 3), dtype=int)
        else:
            red = [[base] * 3 for _ in range(3)]
            nir = [[min(base + 0.25, 0.95)] * 3 for _ in range(3)]
            green = [[max(base - 0.05, 0.05)] * 3 for _ in range(3)]
            swir = [[max(base - 0.08, 0.03)] * 3 for _ in range(3)]
            scl = [[0] * 3 for _ in range(3)]
        await asyncio.sleep(0)
        payload = {"B04": red, "B08": nir, "B03": green, "B11": swir, "SCL": scl}
        return {band: payload[band] for band in bands if band in payload}
