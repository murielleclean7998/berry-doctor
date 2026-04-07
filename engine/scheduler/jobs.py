from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
except Exception:  # pragma: no cover
    BackgroundScheduler = None
    CronTrigger = None


@dataclass(slots=True)
class SchedulerService:
    weather_job: Any
    market_job: Any
    report_job: Any
    sensor_health_job: Any
    camera_job: Any | None = None
    monthly_report_job: Any | None = None
    backup_job: Any | None = None
    signal_job: Any | None = None
    satellite_job: Any | None = None
    scheduler: Any = field(default=None, init=False)

    def start(self) -> bool:
        if BackgroundScheduler is None or CronTrigger is None:
            return False
        self.scheduler = BackgroundScheduler(timezone="Asia/Seoul")
        self.scheduler.add_job(self.weather_job, "interval", hours=1, id="weather_refresh", replace_existing=True)
        self.scheduler.add_job(self.market_job, CronTrigger(hour=6, minute=0), id="market_fetch", replace_existing=True)
        self.scheduler.add_job(self.report_job, CronTrigger(hour=21, minute=0), id="daily_report", replace_existing=True)
        self.scheduler.add_job(self.sensor_health_job, CronTrigger(hour=3, minute=15), id="sensor_health", replace_existing=True)
        if self.backup_job is not None:
            self.scheduler.add_job(self.backup_job, CronTrigger(hour=3, minute=40), id="backup", replace_existing=True)
        if self.camera_job is not None:
            self.scheduler.add_job(self.camera_job, CronTrigger(hour=10, minute=0), id="camera_round", replace_existing=True)
        if self.monthly_report_job is not None:
            self.scheduler.add_job(self.monthly_report_job, CronTrigger(day=1, hour=7, minute=0), id="monthly_report", replace_existing=True)
        if self.signal_job is not None:
            self.scheduler.add_job(self.signal_job, "interval", hours=6, id="signal_collect", replace_existing=True)
        if self.satellite_job is not None:
            self.scheduler.add_job(self.satellite_job, CronTrigger(hour=6, minute=30), id="satellite_collect", replace_existing=True)
        self.scheduler.start()
        return True

    def stop(self) -> None:
        if self.scheduler is not None:
            self.scheduler.shutdown(wait=False)
