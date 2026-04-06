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
    scheduler: Any = field(default=None, init=False)

    def start(self) -> bool:
        if BackgroundScheduler is None:
            return False
        self.scheduler = BackgroundScheduler(timezone="Asia/Seoul")
        self.scheduler.add_job(self.weather_job, "interval", hours=1, id="weather_refresh", replace_existing=True)
        self.scheduler.add_job(self.market_job, CronTrigger(hour=6, minute=0), id="market_fetch", replace_existing=True)
        self.scheduler.add_job(self.report_job, CronTrigger(hour=21, minute=0), id="daily_report", replace_existing=True)
        self.scheduler.add_job(self.sensor_health_job, CronTrigger(hour=3, minute=15), id="sensor_health", replace_existing=True)
        self.scheduler.start()
        return True

    def stop(self) -> None:
        if self.scheduler is not None:
            self.scheduler.shutdown(wait=False)
