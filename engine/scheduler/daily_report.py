from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class DailyReportService:
    coach: Any
    sender: Any

    def send(self) -> str:
        message = self.coach.build_daily_report(datetime.now())
        self.sender.send_text(message, severity="info")
        return message
