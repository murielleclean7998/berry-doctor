from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class MonthlyReportService:
    coach: Any
    sender: Any
    repository: Any

    def build(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now()
        summary = self.coach.build_monthly_report(now)
        month_key = now.strftime("%Y-%m")
        return {"month_key": month_key, "message": summary}

    def send(self) -> str:
        payload = self.build()
        self.sender.send_text(payload["message"], severity="info", rule_id="MONTHLY_REPORT")
        self.repository.record_monthly_report(payload["month_key"], payload, sent=True)
        return payload["message"]
