from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from engine.crop_profile import DEFAULT_CROP_TYPE, load_crop_profile
from engine.db.sqlite import SQLiteRepository
from engine.paths import data_path, writable_root
from engine.security import generate_token, mask_secret, protect_text, unprotect_text
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
    crop_type: str = DEFAULT_CROP_TYPE
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
    local_llm_model_path: str = ""
    webhook_signature_secret: str = ""
    dashboard_access_token: str = ""
    dashboard_require_auth: bool = True
    backup_retention_count: int = 14
    sensor_log_interval_seconds: int = 30
    control_dedupe_window_seconds: int = 90
    alert_dedupe_window_seconds: int = 1800
    community_insight_dedupe_window_seconds: int = 1800
    raw_sensor_retention_days: int = 90
    aggregate_sensor_retention_days: int = 365
    signal_immediate_daily_limit: int = 2
    signal_merge_window_seconds: int = 3600
    satellite_max_cloud_pct: int = 40
    field_area_pyeong: int = 200
    community_min_user_threshold: int = 5
    share_to_community: bool = False
    satellite_enabled: bool = True

    @property
    def dashboard_url(self) -> str:
        return f"http://{self.dashboard_host}:{self.dashboard_port}"

    @property
    def dashboard_login_url(self) -> str:
        return f"{self.dashboard_url}/login"


def sync_app_config(target: AppConfig, source: AppConfig) -> None:
    for field in fields(AppConfig):
        setattr(target, field.name, getattr(source, field.name))


class ConfigManager:
    SECRET_KEYS = {
        "wifi_password",
        "kakao_access_token",
        "kma_api_key",
        "farmmap_api_key",
        "market_api_key",
        "webhook_signature_secret",
        "dashboard_access_token",
    }

    INT_KEYS = {
        "house_count",
        "webhook_port",
        "dashboard_port",
        "backup_retention_count",
        "sensor_log_interval_seconds",
        "control_dedupe_window_seconds",
        "alert_dedupe_window_seconds",
        "community_insight_dedupe_window_seconds",
        "raw_sensor_retention_days",
        "aggregate_sensor_retention_days",
        "signal_immediate_daily_limit",
        "signal_merge_window_seconds",
        "satellite_max_cloud_pct",
        "field_area_pyeong",
        "community_min_user_threshold",
    }
    BOOL_KEYS = {"mock_mode", "dashboard_require_auth", "share_to_community", "satellite_enabled"}

    def __init__(self, repository: SQLiteRepository):
        self.repository = repository
        self.profile_path = Path(data_path("regional_profiles.json"))
        self.profiles = load_profiles(self.profile_path)

    def is_configured(self) -> bool:
        return bool(self.repository.get_config("farm_location"))

    def ensure_setup(self, translator) -> None:
        if not self.is_configured():
            result = run_setup_wizard(self.profiles, translator)
            self.save_setup(result)
        self.ensure_runtime_defaults()

    def ensure_runtime_defaults(self) -> None:
        defaults: dict[str, Any] = {}
        if self.repository.get_config("locale") is None:
            defaults["locale"] = "ko"
        if self.repository.get_config("crop_type") is None:
            defaults["crop_type"] = DEFAULT_CROP_TYPE
        if self.repository.get_config("mock_mode") is None:
            defaults["mock_mode"] = True
        if self.repository.get_config("dashboard_require_auth") is None:
            defaults["dashboard_require_auth"] = True
        if self.repository.get_config("backup_retention_count") is None:
            defaults["backup_retention_count"] = 14
        if self.repository.get_config("sensor_log_interval_seconds") is None:
            defaults["sensor_log_interval_seconds"] = 30
        if self.repository.get_config("control_dedupe_window_seconds") is None:
            defaults["control_dedupe_window_seconds"] = 90
        if self.repository.get_config("alert_dedupe_window_seconds") is None:
            defaults["alert_dedupe_window_seconds"] = 1800
        if self.repository.get_config("community_insight_dedupe_window_seconds") is None:
            defaults["community_insight_dedupe_window_seconds"] = 1800
        if self.repository.get_config("raw_sensor_retention_days") is None:
            defaults["raw_sensor_retention_days"] = 90
        if self.repository.get_config("aggregate_sensor_retention_days") is None:
            defaults["aggregate_sensor_retention_days"] = 365
        if self.repository.get_config("local_llm_model_path") is None:
            defaults["local_llm_model_path"] = ""
        if self.repository.get_config("signal_immediate_daily_limit") is None:
            defaults["signal_immediate_daily_limit"] = 2
        if self.repository.get_config("signal_merge_window_seconds") is None:
            defaults["signal_merge_window_seconds"] = 3600
        if self.repository.get_config("satellite_max_cloud_pct") is None:
            defaults["satellite_max_cloud_pct"] = 40
        if self.repository.get_config("field_area_pyeong") is None:
            defaults["field_area_pyeong"] = 200
        if self.repository.get_config("community_min_user_threshold") is None:
            defaults["community_min_user_threshold"] = 5
        if self.repository.get_config("share_to_community") is None:
            defaults["share_to_community"] = False
        if self.repository.get_config("satellite_enabled") is None:
            defaults["satellite_enabled"] = True
        if not self.repository.get_config("dashboard_access_token"):
            defaults["dashboard_access_token"] = protect_text(generate_token(), "dashboard_access_token")
        if not self.repository.get_config("webhook_signature_secret"):
            defaults["webhook_signature_secret"] = protect_text(generate_token(), "webhook_signature_secret")
        if defaults:
            self.repository.set_many_config(defaults)
        self._write_runtime_hints(self.load())

    def save_setup(self, result: SetupResult) -> None:
        entries = result.as_config_entries()
        entries["wifi_password"] = protect_text(result.wifi_password, "wifi_password")
        entries["mock_mode"] = True
        entries["locale"] = "ko"
        self.repository.set_many_config(entries)
        self._write_firmware_seed(
            {
                **entries,
                "wifi_password_plain": result.wifi_password,
            }
        )

    def settings_view(self) -> dict[str, Any]:
        data = self._decode_config(self.repository.all_config(), migrate_plaintext=False)
        view = dict(data)
        for key in self.SECRET_KEYS:
            view[key] = mask_secret(str(data.get(key, "")))
        return view

    def update_settings(self, updates: dict[str, Any]) -> None:
        prepared: dict[str, Any] = {}
        for key, value in updates.items():
            if key not in self.allowed_setting_keys():
                continue
            if key in self.BOOL_KEYS:
                prepared[key] = bool(value)
                continue
            if value is None:
                continue
            if key in self.SECRET_KEYS:
                text = str(value).strip()
                if not text:
                    continue
                prepared[key] = protect_text(text, key)
                continue
            if key in self.INT_KEYS:
                text = str(value).strip()
                if not text:
                    continue
                prepared[key] = int(float(text))
                continue
            text = str(value).strip()
            if not text and key == "crop_type":
                continue
            prepared[key] = text
        if prepared:
            self.repository.set_many_config(prepared)
        self._write_runtime_hints(self.load())

    def load(self) -> AppConfig:
        self.ensure_runtime_defaults_if_needed()
        data = self._decode_config(self.repository.all_config(), migrate_plaintext=True)
        farm_location = data.get("farm_location", next(iter(self.profiles)))
        regional_profile = self.profiles.get(farm_location, next(iter(self.profiles.values())))
        crop_type = str(data.get("crop_type", DEFAULT_CROP_TYPE))
        crop_profile = load_crop_profile(crop_type)
        allowed_varieties = list(getattr(crop_profile, "varieties", []) or [])
        default_variety = crop_profile.default_variety or (allowed_varieties[0] if allowed_varieties else "설향")
        loaded_variety = str(data.get("variety", default_variety))
        variety = loaded_variety if loaded_variety in allowed_varieties or not allowed_varieties else default_variety
        return AppConfig(
            farm_location=farm_location,
            house_count=int(data.get("house_count", 3)),
            variety=variety,
            cultivation_type=str(data.get("cultivation_type", "토경")),
            wifi_ssid=str(data.get("wifi_ssid", "")),
            wifi_password=str(data.get("wifi_password", "")),
            regional_profile=regional_profile,
            mock_mode=bool(data.get("mock_mode", True)),
            crop_type=crop_type,
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
            local_llm_model_path=str(data.get("local_llm_model_path", "")),
            webhook_signature_secret=str(data.get("webhook_signature_secret", "")),
            dashboard_access_token=str(data.get("dashboard_access_token", "")),
            dashboard_require_auth=bool(data.get("dashboard_require_auth", True)),
            backup_retention_count=int(data.get("backup_retention_count", 14)),
            sensor_log_interval_seconds=int(data.get("sensor_log_interval_seconds", 30)),
            control_dedupe_window_seconds=int(data.get("control_dedupe_window_seconds", 90)),
            alert_dedupe_window_seconds=int(data.get("alert_dedupe_window_seconds", 1800)),
            community_insight_dedupe_window_seconds=int(data.get("community_insight_dedupe_window_seconds", 1800)),
            raw_sensor_retention_days=int(data.get("raw_sensor_retention_days", 90)),
            aggregate_sensor_retention_days=int(data.get("aggregate_sensor_retention_days", 365)),
            signal_immediate_daily_limit=int(data.get("signal_immediate_daily_limit", 2)),
            signal_merge_window_seconds=int(data.get("signal_merge_window_seconds", 3600)),
            satellite_max_cloud_pct=int(data.get("satellite_max_cloud_pct", 40)),
            field_area_pyeong=int(data.get("field_area_pyeong", 200)),
            community_min_user_threshold=int(data.get("community_min_user_threshold", 5)),
            share_to_community=bool(data.get("share_to_community", False)),
            satellite_enabled=bool(data.get("satellite_enabled", True)),
        )

    def ensure_runtime_defaults_if_needed(self) -> None:
        if (
            self.repository.get_config("dashboard_access_token") is None
            or self.repository.get_config("webhook_signature_secret") is None
            or self.repository.get_config("crop_type") is None
        ):
            self.ensure_runtime_defaults()

    def allowed_setting_keys(self) -> set[str]:
        return {
            "farm_location",
            "house_count",
            "variety",
            "crop_type",
            "cultivation_type",
            "wifi_ssid",
            "wifi_password",
            "mock_mode",
            "webhook_host",
            "webhook_port",
            "dashboard_host",
            "dashboard_port",
            "kakao_api_url",
            "kakao_access_token",
            "kakao_channel_id",
            "kma_api_key",
            "farmmap_api_key",
            "market_api_key",
            "local_llm_model_path",
            "webhook_signature_secret",
            "dashboard_access_token",
            "dashboard_require_auth",
            "backup_retention_count",
            "sensor_log_interval_seconds",
            "control_dedupe_window_seconds",
            "alert_dedupe_window_seconds",
            "community_insight_dedupe_window_seconds",
            "raw_sensor_retention_days",
            "aggregate_sensor_retention_days",
            "signal_immediate_daily_limit",
            "signal_merge_window_seconds",
            "satellite_max_cloud_pct",
            "field_area_pyeong",
            "community_min_user_threshold",
            "share_to_community",
            "satellite_enabled",
        }

    def _decode_config(self, data: dict[str, Any], migrate_plaintext: bool) -> dict[str, Any]:
        decoded = dict(data)
        migrated: dict[str, Any] = {}
        for key in self.SECRET_KEYS:
            raw_value = decoded.get(key, "")
            if not isinstance(raw_value, str):
                continue
            if raw_value and not raw_value.startswith(("dpapi:", "b64:")):
                decoded[key] = raw_value
                if migrate_plaintext:
                    migrated[key] = protect_text(raw_value, key)
                continue
            decoded[key] = unprotect_text(raw_value, key)
        if migrate_plaintext and migrated:
            self.repository.set_many_config(migrated)
        return decoded

    def _write_firmware_seed(self, entries: dict[str, Any]) -> None:
        payload = {
            "wifi_ssid": str(entries.get("wifi_ssid", "")),
            "wifi_password": str(entries.get("wifi_password_plain", entries.get("wifi_password", ""))),
            "farm_location": str(entries.get("farm_location", "")),
            "house_count": int(entries.get("house_count", 3)),
            "crop_type": str(entries.get("crop_type", DEFAULT_CROP_TYPE)),
            "variety": str(entries.get("variety", "")),
        }
        firmware_dir = writable_root() / "firmware"
        firmware_dir.mkdir(parents=True, exist_ok=True)
        target = firmware_dir / "wifi.generated.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_runtime_hints(self, config: AppConfig) -> None:
        self._write_firmware_seed(
            {
                "wifi_ssid": config.wifi_ssid,
                "wifi_password_plain": config.wifi_password,
                "farm_location": config.farm_location,
                "house_count": config.house_count,
                "crop_type": config.crop_type,
                "variety": config.variety,
            }
        )
        runtime_dir = writable_root() / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        access_file = runtime_dir / "dashboard-access.txt"
        access_file.write_text(
            "\n".join(
                [
                    f"Dashboard URL: {config.dashboard_login_url}",
                    f"Dashboard Token: {config.dashboard_access_token}",
                    f"Webhook Signature Secret: {config.webhook_signature_secret}",
                ]
            ),
            encoding="utf-8",
        )
