from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from engine.db.sqlite import SQLiteRepository


@dataclass(slots=True)
class SecurityMonitor:
    repository: SQLiteRepository
    sender: Any

    def on_motion_detected(self, payload: dict[str, Any]) -> dict[str, Any]:
        photos = [str(item) for item in payload.get("photos", []) if item]
        timestamp = str(payload.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        house_id = int(payload.get("house_id") or 1)
        note = str(payload.get("note") or "").strip() or None

        event_id = self.repository.record_security_event(
            house_id=house_id,
            photo_paths=photos,
            timestamp=timestamp,
            note=note,
        )
        message = (
            f"🚨 {house_id}동에서 움직임이 감지됐어요.\n"
            f"시간: {timestamp}\n"
            f"사진: {len(photos)}장 저장됨\n\n"
            f"야생동물일 수도 있지만 확인해보시는 게 좋겠어요.\n"
            f"기록은 자동 저장됐어요."
        )
        if hasattr(self.sender, "send_with_photos"):
            result = self.sender.send_with_photos(
                message,
                photos,
                severity="warning",
                house_id=house_id,
                rule_id="SECURITY_MOTION",
            )
        else:
            result = self.sender.send_text(
                message,
                severity="warning",
                house_id=house_id,
                rule_id="SECURITY_MOTION",
            )
        return {
            "event_id": event_id,
            "house_id": house_id,
            "photo_count": len(photos),
            "timestamp": timestamp,
            "send_result": result,
        }
