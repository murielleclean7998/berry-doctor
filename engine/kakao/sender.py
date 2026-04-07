from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import httpx

from engine.db.sqlite import SQLiteRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class KakaoSender:
    config: Any
    repository: SQLiteRepository

    def _record_alert_if_needed(self, message: str, severity: str, house_id: int | None, rule_id: str) -> None:
        if severity == "info":
            return
        self.repository.record_alert(
            rule_id=rule_id,
            severity=severity,
            message=message,
            house_id=house_id,
            dedupe_window_seconds=int(getattr(self.config, "alert_dedupe_window_seconds", 1800) or 1800),
        )

    def send_text(self, message: str, severity: str = "info", house_id: int | None = None, rule_id: str = "manual") -> dict[str, Any]:
        if not self.config.kakao_access_token or self.config.mock_mode:
            self.repository.set_config("last_sent_message", {"message": message, "severity": severity})
            self._record_alert_if_needed(message, severity, house_id, rule_id)
            return {"ok": True, "mode": "mock"}

        headers = {"Authorization": f"Bearer {self.config.kakao_access_token}"}
        payload = {"channel_public_id": self.config.kakao_channel_id, "text": message}
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(f"{self.config.kakao_api_url}/v1/api/talk/channels/messages", headers=headers, json=payload)
                    response.raise_for_status()
                self._record_alert_if_needed(message, severity, house_id, rule_id)
                self.repository.set_config("last_sent_message", {"message": message, "severity": severity, "mode": "live"})
                return {"ok": True, "mode": "live"}
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("Kakao send attempt %s failed: %s", attempt + 1, exc)

        logger.error("Kakao send failed. Falling back to local persistence only. Last error: %s", last_error)
        self.repository.set_config(
            "last_sent_message",
            {"message": message, "severity": severity, "mode": "fallback", "error": str(last_error) if last_error else "unknown"},
        )
        self._record_alert_if_needed(message, severity, house_id, rule_id)
        self.repository.set_config("last_send_error", str(last_error) if last_error else "unknown")
        return {"ok": False, "mode": "fallback", "error": str(last_error) if last_error else "unknown"}

    def send_with_photos(
        self,
        message: str,
        photos: list[str],
        severity: str = "warning",
        house_id: int | None = None,
        rule_id: str = "manual",
    ) -> dict[str, Any]:
        if photos:
            photo_lines = "\n".join(f"- {photo}" for photo in photos[:5])
            message = f"{message}\n\n사진 기록:\n{photo_lines}"
        result = self.send_text(message, severity=severity, house_id=house_id, rule_id=rule_id)
        self.repository.set_config("last_sent_photos", photos)
        return result
