from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass
from datetime import datetime

from engine.ai.coach import StrawberryCoach
from engine.config import ConfigManager
from engine.db.sqlite import SQLiteRepository
from engine.i18n import Translator
from engine.kakao.sender import KakaoSender
from engine.kakao.webhook import KakaoWebhookServer
from engine.mqtt_broker import MosquittoBroker
from engine.mqtt_client import MQTTClient
from engine.rules.engine import RuleEngine
from engine.scheduler.daily_report import DailyReportService
from engine.scheduler.farmmap import FarmMapService
from engine.scheduler.jobs import SchedulerService
from engine.scheduler.market import MarketPriceService
from engine.scheduler.sensor_health import SensorHealthService
from engine.scheduler.weather import WeatherService
from engine.tray.icon import TrayController
from engine.web.app import DashboardServer


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
        self.broker = MosquittoBroker()
        self.mqtt_client = MQTTClient()
        self.farmmap_service = FarmMapService(self.config)
        self.weather_service = WeatherService(self.config, self.repository, self.farmmap_service)
        self.market_service = MarketPriceService(self.config, self.repository)
        self.coach = StrawberryCoach(self.config, self.repository, self.translator, self.weather_service, self.market_service)
        self.sender = KakaoSender(self.config, self.repository)
        self.rule_engine = RuleEngine(self.config.regional_profile)
        self.report_service = DailyReportService(self.coach, self.sender)
        self.sensor_health_service = SensorHealthService(self.repository)
        self.scheduler_service = SchedulerService(
            self.run_weather_cycle,
            self.market_service.fetch,
            self.report_service.send,
            self.sensor_health_service.run,
        )
        self.webhook_server = KakaoWebhookServer(self.config, self.coach, self.sender)
        self.dashboard_server = DashboardServer(self.config, self.repository, self.coach)
        self.tray_controller = TrayController(self.config, self.translator)

    def _render_alert(self, rule_id: str, weather: dict, payload: dict) -> str:
        tip = self.coach._top_tip("rain")
        region_note = self.config.regional_profile.get("notes", ["지역 메모 없음"])[0]
        if rule_id == "FROST_WARNING":
            tip = self.coach._top_tip("frost")
            return self.translator.t("templates.alert_frost", tomorrow_min=payload["tomorrow_min"], region_note=region_note, tip=tip)
        if rule_id == "HEAVY_RAIN_WARNING":
            return self.translator.t("templates.alert_rain", max_rainfall=payload["max_rainfall"], tip=tip)
        return self.translator.t(
            "templates.alert_disease",
            disease_name=payload["disease_name"],
            risk=payload["risk"],
            condition_summary=f"{weather.get('current_temp')}°C / 습도 {weather.get('current_humidity')}%",
            action=payload["action"],
            tip=self.coach._top_tip("disease"),
        )

    def run_weather_cycle(self) -> dict:
        weather = self.weather_service.refresh()
        events, _ = self.rule_engine.evaluate_weather(weather)
        severity = "normal"
        for event in events:
            self.sender.send_text(
                self._render_alert(event.rule_id, weather, event.payload),
                severity="warning",
                rule_id=event.rule_id,
            )
            severity = "warning"
        self.tray_controller.update_status(severity)
        return weather

    def start(self) -> None:
        _prevent_sleep()
        weather = self.run_weather_cycle()
        self.market_service.fetch()
        if not self.broker.start():
            self.repository.record_alert("MQTT_BROKER", "warning", self.translator.t("messages.mosquitto_missing"))
            self.tray_controller.update_status("warning")
        else:
            self.mqtt_client.connect()
            self.mqtt_client.subscribe("sensor/#")
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
