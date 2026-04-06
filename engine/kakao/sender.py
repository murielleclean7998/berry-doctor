from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from engine.db.sqlite import SQLiteRepository


@dataclass(slots=True)
class KakaoSender:
    config: Any
    repository: SQLiteRepository

    def send_text(self, message: str, severity: str = "info", house_id: int | None = None, rule_id: str = "manual") -> dict[str, Any]:
        if not self.config.kakao_access_token or self.config.mock_mode:
            self.repository.set_config("last_sent_message", {"message": message, "severity": severity})
            if severity != "info":
                self.repository.record_alert(rule_id=rule_id, severity=severity, message=message, house_id=house_id)
            return {"ok": True, "mode": "mock"}

        headers = {"Authorization": f"Bearer {self.config.kakao_access_token}"}
        payload = {"channel_public_id": self.config.kakao_channel_id, "text": message}
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{self.config.kakao_api_url}/v1/api/talk/channels/messages", headers=headers, json=payload)
            response.raise_for_status()
        if severity != "info":
            self.repository.record_alert(rule_id=rule_id, severity=severity, message=message, house_id=house_id)
        return {"ok": True, "mode": "live"}
