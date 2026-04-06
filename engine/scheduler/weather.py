from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

import httpx

from engine.db.sqlite import SQLiteRepository
from engine.scheduler.farmmap import FarmMapService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WeatherService:
    config: Any
    repository: SQLiteRepository
    farmmap_service: FarmMapService

    def _mock_snapshot(self) -> dict[str, Any]:
        now = datetime.now()
        return {
            "observed_at": now.isoformat(),
            "current_temp": 18.6,
            "current_humidity": 82.0,
            "summary": "흐리고 습도가 높은 편",
            "tomorrow_min_temp": -2.0 if self.config.regional_profile.get("type") == "coastal" else 1.0,
            "tomorrow_summary": "밤사이 구름 많고 아침 서늘",
            "max_hourly_rainfall": 6.0,
            "estimated_wet_hours": 5.0,
            "soil_temp": 14.0,
            "source": "mock",
        }

    def _fetch_openweather(self) -> dict[str, Any]:
        profile = self.config.regional_profile
        params = {
            "lat": profile.get("latitude"),
            "lon": profile.get("longitude"),
            "appid": self.config.kma_api_key,
            "units": "metric",
            "lang": "kr",
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.get("https://api.openweathermap.org/data/2.5/forecast", params=params)
            response.raise_for_status()
            payload = response.json()
        entries = payload.get("list", [])
        current = entries[0] if entries else {}
        tomorrow = datetime.now(UTC).date() + timedelta(days=1)
        tomorrow_entries = [
            item for item in entries
            if datetime.fromtimestamp(item["dt"], tz=UTC).date() == tomorrow
        ]
        rain_max = max((item.get("rain", {}).get("3h", 0.0) for item in entries[:8]), default=0.0)
        return {
            "observed_at": datetime.now().isoformat(),
            "current_temp": float(current.get("main", {}).get("temp", 18.0)),
            "current_humidity": float(current.get("main", {}).get("humidity", 75.0)),
            "summary": current.get("weather", [{}])[0].get("description", "예보 데이터"),
            "tomorrow_min_temp": min((item.get("main", {}).get("temp_min", 5.0) for item in tomorrow_entries), default=5.0),
            "tomorrow_summary": tomorrow_entries[0].get("weather", [{}])[0].get("description", "예보 없음") if tomorrow_entries else "예보 없음",
            "max_hourly_rainfall": round(rain_max / 3 if rain_max else 0.0, 1),
            "estimated_wet_hours": float(sum(3 for item in tomorrow_entries if item.get("main", {}).get("humidity", 0) >= 85)),
            "soil_temp": float(current.get("main", {}).get("temp", 18.0)) - 2.0,
            "source": "openweather",
        }

    def refresh(self) -> dict[str, Any]:
        try:
            snapshot = self._mock_snapshot() if self.config.mock_mode or not self.config.kma_api_key else self._fetch_openweather()
        except Exception:
            logger.exception("Weather refresh failed. Falling back to cache or mock snapshot.")
            cached = self.repository.get_config("weather_cache")
            if cached:
                cached["fallback"] = "cache"
                return cached
            snapshot = self._mock_snapshot()
            snapshot["fallback"] = "mock"
        try:
            snapshot["farmmap"] = self.farmmap_service.fetch()
        except Exception:
            logger.exception("Farm map refresh failed. Continuing with cached placeholder data.")
            snapshot["farmmap"] = {
                "field_condition": "unknown",
                "wind_speed": 0.0,
                "sunshine_hours": 0.0,
                "note": "FarmMap data unavailable",
                "source": "fallback",
            }
        self.repository.set_config("weather_cache", snapshot)
        return snapshot

    def latest(self) -> dict[str, Any]:
        return self.repository.get_config("weather_cache", self._mock_snapshot())
