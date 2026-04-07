from __future__ import annotations

import ctypes
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from engine.ai.coach import CropCoach
from engine.crop_profile import load_crop_profile
from engine.backup import BackupService
from engine.config import ConfigManager, sync_app_config
from engine.control.greenhouse import GreenhouseController
from engine.db.sqlite import SQLiteRepository
from engine.fusion.intelligence import FusionIntelligence
from engine.i18n import Translator
from engine.kakao.sender import KakaoSender
from engine.kakao.webhook import KakaoWebhookServer
from engine.mqtt_broker import MosquittoBroker
from engine.mqtt_client import MQTTClient
from engine.rules.engine import RuleEngine, RuleEvent
from engine.satellite.db import SatelliteRepository
from engine.satellite.timeline import FarmTimeline
from engine.scheduler.camera import CameraService
from engine.scheduler.daily_report import DailyReportService
from engine.scheduler.farmmap import FarmMapService
from engine.scheduler.jobs import SchedulerService
from engine.scheduler.market import MarketPriceService
from engine.scheduler.monthly_report import MonthlyReportService
from engine.scheduler.satellite_job import SatelliteJobService
from engine.scheduler.sensor_health import SensorHealthService
from engine.scheduler.signal_job import SignalJobService
from engine.scheduler.weather import WeatherService
from engine.security.monitor import SecurityMonitor
from engine.signal.collector import SignalCollector
from engine.signal.db import SignalRepository
from engine.tray.icon import TrayController
from engine.web.app import DashboardServer

logger = logging.getLogger(__name__)


def _prevent_sleep() -> None:
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    except Exception:
        return


@dataclass
class BerryDoctorApplication:
    repository: SQLiteRepository
    translator: Translator
    config_manager: ConfigManager

    def __post_init__(self) -> None:
        self.repository.initialize()
        self.config_manager.ensure_setup(self.translator)
        self.config = self.config_manager.load()
        self.crop_profile = load_crop_profile(self.config.crop_type)

        self.broker = MosquittoBroker()
        self.mqtt_client = MQTTClient()
        self.mqtt_client.on_message = self.handle_mqtt_message

        self.farmmap_service = FarmMapService(self.config)
        self.weather_service = WeatherService(self.config, self.repository, self.farmmap_service)
        self.market_service = MarketPriceService(self.config, self.repository, crop_profile=self.crop_profile)
        self.sender = KakaoSender(self.config, self.repository)
        self.rule_engine = RuleEngine(self.config.regional_profile)
        self.controller = GreenhouseController(
            self.repository,
            self.mqtt_client,
            dedupe_window_seconds=self.config.control_dedupe_window_seconds,
        )
        self.backup_service = BackupService(self.repository, retention_count=self.config.backup_retention_count)
        self.coach = CropCoach(
            self.config,
            self.repository,
            self.translator,
            self.weather_service,
            self.market_service,
            controller=self.controller,
            crop_profile=self.crop_profile,
        )
        self.signal_repository = SignalRepository(self.repository)
        self.satellite_repository = SatelliteRepository(self.repository)
        self.signal_collector = SignalCollector(self.config, self.repository, sender=self.sender, crop_profile=self.crop_profile)
        self.satellite_job_service = SatelliteJobService(self.config, self.repository, sender=self.sender, crop_profile=self.crop_profile)
        self.fusion = FusionIntelligence(
            self.repository,
            self.signal_repository,
            self.satellite_repository,
            self.sender,
            self.config,
            coach=self.coach,
        )
        self.signal_collector.set_fusion(self.fusion)
        self.satellite_job_service.set_fusion(self.fusion)
        self.signal_job_service = SignalJobService(self.signal_collector)
        self.security_monitor = SecurityMonitor(self.repository, self.sender)
        self.coach.fusion_intelligence = self.fusion
        self.coach.satellite_timeline = FarmTimeline(self.repository)
        self.coach.security_repository = None
        self.coach.disease_detector.community_source = self.signal_collector.community_source

        self.report_service = DailyReportService(self.coach, self.sender)
        self.monthly_report_service = MonthlyReportService(self.coach, self.sender, self.repository)
        self.sensor_health_service = SensorHealthService(
            self.repository,
            raw_retention_days=self.config.raw_sensor_retention_days,
            aggregate_retention_days=self.config.aggregate_sensor_retention_days,
        )
        self.camera_service = CameraService(self.repository, self.mqtt_client, self.config.house_count)
        self.scheduler_service = SchedulerService(
            self.run_weather_cycle,
            self.market_service.fetch,
            self.fusion.daily_report,
            self.sensor_health_service.run,
            camera_job=self.camera_service.run_round,
            monthly_report_job=self.monthly_report_service.send,
            backup_job=self.backup_service.create_backup,
            signal_job=self.signal_job_service.collect_domestic,
            satellite_job=self.satellite_job_service.check_new_image,
        )
        self.webhook_server = KakaoWebhookServer(self.config, self.coach, self.sender)
        self.dashboard_server = DashboardServer(
            self.config,
            self.repository,
            self.coach,
            self.config_manager,
            self.backup_service,
            runtime_reload_callback=self.reload_runtime_config,
        )
        self.tray_controller = TrayController(self.config, self.translator)
        self._last_sensor_log_times: dict[int, datetime] = {}
        self._seed_phase45_records()

    def reload_runtime_config(self) -> None:
        previous_crop_type = getattr(self.config, "crop_type", "strawberry")
        updated = self.config_manager.load()
        sync_app_config(self.config, updated)
        sync_app_config(self.coach.config, updated)
        sync_app_config(self.weather_service.config, updated)
        sync_app_config(self.market_service.config, updated)
        sync_app_config(self.sender.config, updated)
        sync_app_config(self.webhook_server.config, updated)
        sync_app_config(self.dashboard_server.config, updated)
        sync_app_config(self.tray_controller.config, updated)
        sync_app_config(self.signal_collector.config, updated)
        sync_app_config(self.satellite_job_service.config, updated)
        sync_app_config(self.fusion.config, updated)
        self.rule_engine.update_profile(updated.regional_profile)
        self.camera_service.house_count = updated.house_count
        self.backup_service.retention_count = updated.backup_retention_count
        self.controller.dedupe_window_seconds = updated.control_dedupe_window_seconds
        self.sensor_health_service.raw_retention_days = updated.raw_sensor_retention_days
        self.sensor_health_service.aggregate_retention_days = updated.aggregate_sensor_retention_days
        self.coach.disease_predictor = self.coach.disease_predictor.__class__(
            updated.regional_profile,
            disease_params=getattr(self.crop_profile, "diseases", None),
        )
        if previous_crop_type != updated.crop_type:
            self.crop_profile = load_crop_profile(updated.crop_type)
            self.market_service.set_crop_profile(self.crop_profile)
            self.coach.set_crop_profile(self.crop_profile)
            self.signal_collector.set_crop_profile(self.crop_profile)
            self.satellite_job_service.set_crop_profile(self.crop_profile)
            self.coach.disease_detector.community_source = self.signal_collector.community_source

    def _seed_phase45_records(self) -> None:
        if not self.repository.recent_community_insights(1):
            self.repository.record_community_insight(
                title="초기 운영 체크리스트",
                summary="환기, 배수구, 안전출하일, 수확 기록 루틴을 먼저 고정하세요.",
                tags=["phase4", "operations"],
                source_site="BerryDoctor Project",
                payload={"type": "seed"},
            )
        if not self.repository.recent_pilot_feedback(1):
            for site in ["Pilot-A", "Pilot-B", "Pilot-C"]:
                self.repository.record_pilot_feedback(
                    site_name=site,
                    category="readiness",
                    sentiment="neutral",
                    feedback="설치 전 체크리스트와 운영 목표를 확정해야 합니다.",
                    status="planned",
                    action_item="센서 배치도와 수동/자동 전환 규칙 검토",
                )

    def _render_alert(self, rule_id: str, weather: dict[str, Any], payload: dict[str, Any]) -> str:
        tip = self.coach.top_tip("rain")
        region_note = self.config.regional_profile.get("notes", ["지역 메모 없음"])[0]
        if rule_id == "FROST_WARNING":
            tip = self.coach.top_tip("frost")
            return self.translator.t("templates.alert_frost", tomorrow_min=payload["tomorrow_min"], region_note=region_note, tip=tip)
        if rule_id == "HEAVY_RAIN_WARNING":
            return self.translator.t("templates.alert_rain", max_rainfall=payload["max_rainfall"], tip=tip)
        return self.translator.t(
            "templates.alert_disease",
            disease_name=payload["disease_name"],
            risk=payload["risk"],
            condition_summary=f"{weather.get('current_temp')}°C / 습도 {weather.get('current_humidity')}%",
            action=payload["action"],
            tip=self.coach.top_tip("disease"),
        )

    def _emit_rule_events(self, weather: dict[str, Any], events: list[RuleEvent], send_remote: bool = True) -> None:
        for event in events:
            message = self._render_alert(event.rule_id, weather, event.payload)
            house_id = event.payload.get("house_id") if isinstance(event.payload, dict) else None
            if send_remote and event.severity in {"warning", "critical"}:
                self.sender.send_text(message, severity=event.severity, house_id=house_id, rule_id=event.rule_id)
            else:
                self.repository.record_alert(
                    event.rule_id,
                    event.severity,
                    message,
                    house_id=house_id,
                    dedupe_window_seconds=self.config.alert_dedupe_window_seconds,
                )

    def run_weather_cycle(self) -> dict[str, Any]:
        try:
            weather = self.weather_service.refresh()
            events, _ = self.rule_engine.evaluate_weather(weather)
            self._emit_rule_events(weather, events)

            sensor = self.repository.latest_sensor_snapshot()
            if sensor:
                evaluation = self.rule_engine.evaluate_environment(sensor, weather)
                self.controller.apply_proposals(evaluation.proposals)
                self.repository.set_config(
                    "last_pid_summary",
                    {
                        "ec_error": evaluation.pid_summary.ec_error,
                        "ph_error": evaluation.pid_summary.ph_error,
                        "note": evaluation.pid_summary.note,
                    },
                )

            severity = "warning" if events else "normal"
            self.tray_controller.update_status(severity)
            return weather
        except Exception:
            logger.exception("Weather cycle failed.")
            self.repository.record_alert(
                "WEATHER_CYCLE",
                "warning",
                "날씨 주기 처리에 실패했습니다. 직전 데이터로 계속 운영합니다.",
            )
            self.tray_controller.update_status("warning")
            return self.weather_service.latest()

    def _parse_topic_house(self, topic: str) -> int | None:
        parts = topic.split("/")
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1])
        return None

    def _should_persist_sensor_log(self, house_id: int, now: datetime) -> bool:
        last_logged_at = self._last_sensor_log_times.get(house_id)
        interval_seconds = max(int(self.config.sensor_log_interval_seconds), 5)
        if last_logged_at is None or (now - last_logged_at).total_seconds() >= interval_seconds:
            self._last_sensor_log_times[house_id] = now
            return True
        return False

    def handle_mqtt_message(self, topic: str, payload: bytes) -> None:
        try:
            text = payload.decode("utf-8")
            data = json.loads(text)
        except Exception:
            logger.warning("Received non-JSON MQTT payload on topic %s", topic)
            return

        house_id = self._parse_topic_house(topic) or data.get("house_id") or 1
        if topic.startswith("sensor/"):
            data["house_id"] = int(house_id)
            now = datetime.now(UTC)
            self.repository.upsert_latest_sensor_snapshot(data, house_id=int(house_id))
            self.repository.record_sensor_minute_aggregate(data, house_id=int(house_id), timestamp=now)
            persisted = self._should_persist_sensor_log(int(house_id), now)
            if persisted:
                self.repository.record_sensor_snapshot(data, house_id=int(house_id))
            weather = self.weather_service.latest()
            evaluation = self.rule_engine.evaluate_environment(data, weather)
            self.controller.apply_proposals(evaluation.proposals)
            if evaluation.proposals:
                self.repository.record_community_insight(
                    title=f"{house_id}동 자동 제어 제안",
                    summary=", ".join(f"{proposal.device}:{proposal.action}" for proposal in evaluation.proposals[:3]),
                    tags=["control", "phase2"],
                    source_site=f"house-{house_id}",
                    payload={"house_id": house_id},
                    dedupe_window_seconds=self.config.community_insight_dedupe_window_seconds,
                )
            if persisted and (evaluation.proposals or evaluation.events):
                fusion_payload = dict(data)
                fusion_payload["current_humidity"] = weather.get("current_humidity")
                fusion_payload["current_temp"] = weather.get("current_temp")
                fusion_payload["events"] = [event.rule_id for event in evaluation.events]
                self.fusion.on_sensor_alert(fusion_payload)
        elif topic.startswith("camera/"):
            self.repository.record_camera_capture(
                house_id=int(house_id),
                trigger_source="mqtt",
                status=str(data.get("status", "received")),
                image_name=data.get("image_name"),
                note=data.get("note"),
            )
        elif topic.startswith("security/"):
            self.security_monitor.on_motion_detected(data)

    def start(self) -> None:
        _prevent_sleep()
        self.run_weather_cycle()
        try:
            self.market_service.fetch()
        except Exception:
            logger.exception("Initial market fetch failed.")
            self.repository.record_alert(
                "MARKET_STARTUP",
                "warning",
                "시세 데이터 갱신에 실패했습니다. 직전 값 또는 모의 데이터로 계속합니다.",
            )
            self.tray_controller.update_status("warning")
        if not self.broker.start():
            self.repository.record_alert("MQTT_BROKER", "warning", self.translator.t("messages.mosquitto_missing"))
            self.tray_controller.update_status("warning")
        else:
            self.mqtt_client.connect()
            self.mqtt_client.subscribe("sensor/#")
            self.mqtt_client.subscribe("camera/#")
            self.mqtt_client.subscribe("security/#")
        self.webhook_server.start()
        self.dashboard_server.start()
        self.scheduler_service.start()
        self.tray_controller.start()
        self.repository.set_config("started_at", datetime.now().isoformat())

    def stop(self) -> None:
        self.scheduler_service.stop()
        self.webhook_server.stop()
        self.dashboard_server.stop()
        self.tray_controller.stop()
        self.mqtt_client.stop()
        self.broker.stop()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    repository = SQLiteRepository()
    app = BerryDoctorApplication(
        repository=repository,
        translator=Translator(),
        config_manager=ConfigManager(repository),
    )
    app.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        app.stop()


if __name__ == "__main__":
    main()
