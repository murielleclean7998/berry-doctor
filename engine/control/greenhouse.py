from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from engine.db.sqlite import SQLiteRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ControlActionProposal:
    house_id: int
    device: str
    action: str
    mode: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GreenhouseController:
    repository: SQLiteRepository
    mqtt_client: Any
    dedupe_window_seconds: int = 90

    def _topic_for(self, proposal: ControlActionProposal) -> str:
        return f"control/{proposal.house_id}/{proposal.device}"

    def publish_action(self, proposal: ControlActionProposal) -> dict[str, Any]:
        payload = {
            "device": proposal.device,
            "action": proposal.action,
            "mode": proposal.mode,
            **proposal.payload,
        }
        payload_json = json.dumps(payload, ensure_ascii=False)
        if proposal.mode == "auto" and self.dedupe_window_seconds > 0:
            duplicate = self.repository.find_recent_control_action(
                action=proposal.action,
                device=proposal.device,
                mode=proposal.mode,
                house_id=proposal.house_id,
                payload_json=payload_json,
                within_seconds=self.dedupe_window_seconds,
            )
            if duplicate is not None:
                return {"result": "skipped_duplicate", "topic": self._topic_for(proposal), "payload": payload}
        result = "mock"
        try:
            if getattr(self.mqtt_client, "client", None) is not None:
                self.mqtt_client.publish(self._topic_for(proposal), payload_json)
                result = "published"
        except Exception:
            logger.exception("Failed to publish control action for house %s", proposal.house_id)
            result = "failed"

        self.repository.record_control_action(
            action=proposal.action,
            device=proposal.device,
            mode=proposal.mode,
            reason=proposal.reason,
            payload=payload,
            result=result,
            house_id=proposal.house_id,
            dedupe_window_seconds=self.dedupe_window_seconds if proposal.mode == "auto" else None,
        )
        return {"result": result, "topic": self._topic_for(proposal), "payload": payload}

    def apply_proposals(self, proposals: list[ControlActionProposal]) -> list[dict[str, Any]]:
        return [self.publish_action(proposal) for proposal in proposals]

    def manual_action(self, house_id: int, device: str, action: str, reason: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        proposal = ControlActionProposal(
            house_id=house_id,
            device=device,
            action=action,
            mode="manual",
            reason=reason,
            payload=payload or {},
        )
        return self.publish_action(proposal)
