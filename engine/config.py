from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.db.sqlite import SQLiteRepository
from engine.paths import data_path, writable_root
from engine.setup_wizard import SetupResult, load_profiles, run_setup_wizard


@dataclass(slots=True)
class AppConfig:
    farm_location: str
    house_count: int
    variety: str
    cultivation_type: str
    wifi_ssid: str
    wifi_password: str
    regional_profile: dict[str, Any]
    mock_mode: bool
    locale: str = "ko"
    webhook_host: str = "127.0.0.1"
    webhook_port: int = 5005
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8080
    kakao_api_url: str = "https://kapi.kakao.com"
    kakao_access_token: str = ""
    kakao_channel_id: str = ""
    kma_api_key: str = ""
    farmmap_api_key: str = ""
    market_api_key: str = ""

    @property
    def dashboard_url(self) -> str:
        return f"http://{self.dashboard_host}:{self.dashboard_port}"


class ConfigManager:
    def __init__(self, repository: SQLiteRepository):
        self.repository = repository
        self.profile_path = Path(data_path("regional_profiles.json"))
        self.profiles = load_profiles(self.profile_path)

    def is_configured(self) -> bool:
        return bool(self.repository.get_config("farm_location"))

    def ensure_setup(self, translator) -> None:
        if self.is_configured():
            return
        result = run_setup_wizard(self.profiles, translator)
        self.save_setup(result)

    def save_setup(self, result: SetupResult) -> None:
        self.repository.set_many_config(result.as_config_entries())
        self.repository.set_config("mock_mode", True)
        self.repository.set_config("locale", "ko")
        self._write_firmware_seed(result)

    def _write_firmware_seed(self, result: SetupResult) -> None:
        payload = {
            "wifi_ssid": result.wifi_ssid,
            "wifi_password": result.wifi_password,
            "farm_location": result.farm_location,
            "house_count": result.house_count,
        }
        firmware_dir = writable_root() / "firmware"
        firmware_dir.mkdir(parents=True, exist_ok=True)
        target = firmware_dir / "wifi.generated.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> AppConfig:
        data = self.repository.all_config()
        farm_location = data.get("farm_location", next(iter(self.profiles)))
        profile = self.profiles.get(farm_location, next(iter(self.profiles.values())))
        return AppConfig(
            farm_location=farm_location,
            house_count=int(data.get("house_count", 3)),
            variety=str(data.get("variety", "설향")),
            cultivation_type=str(data.get("cultivation_type", "토경")),
            wifi_ssid=str(data.get("wifi_ssid", "")),
            wifi_password=str(data.get("wifi_password", "")),
            regional_profile=profile,
            mock_mode=bool(data.get("mock_mode", True)),
            locale=str(data.get("locale", "ko")),
            webhook_host=str(data.get("webhook_host", "127.0.0.1")),
            webhook_port=int(data.get("webhook_port", 5005)),
            dashboard_host=str(data.get("dashboard_host", "127.0.0.1")),
            dashboard_port=int(data.get("dashboard_port", 8080)),
            kakao_api_url=str(data.get("kakao_api_url", "https://kapi.kakao.com")),
            kakao_access_token=str(data.get("kakao_access_token", "")),
            kakao_channel_id=str(data.get("kakao_channel_id", "")),
            kma_api_key=str(data.get("kma_api_key", "")),
            farmmap_api_key=str(data.get("farmmap_api_key", "")),
            market_api_key=str(data.get("market_api_key", "")),
        )
