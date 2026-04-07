from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from engine.fusion.context_builder import ContextBuilder
from engine.fusion.message_composer import MessageComposer
from engine.fusion.risk_scorer import RiskScorer


@dataclass(slots=True)
class FusionIntelligence:
    repository: Any
    signal_db: Any
    satellite_db: Any
    kakao: Any
    config: Any
    coach: Any | None = None
    context: Any = field(default=None, init=False)
    scorer: Any = field(default=None, init=False)
    composer: Any = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.context = ContextBuilder(self.config)
        self.scorer = RiskScorer()
        self.composer = MessageComposer()

    def _dispatch(self, trigger_source: str, context: dict[str, Any], risk: Any) -> str:
        merge_window = int(getattr(self.config, "signal_merge_window_seconds", 3600) or 3600)
        recent = self.repository.find_recent_fusion_event(trigger_source=trigger_source, within_seconds=merge_window)
        message = self.composer.compose_daily(context, risk) if trigger_source == "daily" else self.composer.compose(context, risk)
        merged = recent is not None and recent.get("level") == risk.level and risk.level != "critical"
        if merged:
            message = f"비슷한 흐름이 이어지고 있어요.\n{message}"
        self.repository.record_fusion_log(
            trigger_source=trigger_source,
            trigger_detail=context.get("trigger_detail", ""),
            sensor_risk=risk.breakdown["sensor"],
            satellite_risk=risk.breakdown["satellite"],
            signal_risk=risk.breakdown["signal"],
            composite_risk=risk.composite,
            agreement=risk.agreement,
            level=risk.level,
            message_sent=message,
        )
        if not merged:
            severity = "warning" if risk.level in {"critical", "warning"} else "info"
            self.kakao.send_text(message, severity=severity, rule_id=f"FUSION_{trigger_source.upper()}")
        return message

    def on_sensor_alert(self, alert: dict[str, Any] | Any) -> str | None:
        sensor = alert if isinstance(alert, dict) else getattr(alert, "payload", {}) or {}
        satellite = self.satellite_db.latest(sensor.get("house_id") if isinstance(sensor, dict) else None) or {}
        signals = self.signal_db.recent_relevant(hours=48, limit=5)
        context = self.context.build("sensor", sensor, satellite, signals, trigger_detail="센서 이상 감지")
        risk = self.scorer.calculate(context)
        if risk.level == "info":
            return None
        return self._dispatch("sensor", context, risk)

    def on_satellite_update(self, sat_data: dict[str, Any]) -> str | None:
        sensors = self.repository.latest_sensor_snapshots()
        signals = self.signal_db.recent_relevant(hours=72, limit=5)
        context = self.context.build("satellite", sensors, sat_data, signals, trigger_detail="새 위성 촬영 반영")
        risk = self.scorer.calculate(context)
        return self._dispatch("satellite", context, risk)

    def on_new_signal(self, signal: dict[str, Any]) -> str | None:
        if str(signal.get("urgency") or "info") not in {"critical", "warning"}:
            return None
        sensors = self.repository.latest_sensor_snapshots()
        satellite = self.satellite_db.latest() or {}
        context = self.context.build("signal", sensors, satellite, [signal], trigger_detail=signal.get("title", "새 소식 반영"))
        risk = self.scorer.calculate(context)
        return self._dispatch("signal", context, risk)

    def _build_daily_context_and_risk(self, now: datetime | None = None) -> tuple[datetime, dict[str, Any], Any, str]:
        now = now or datetime.now()
        crop_item = "설향"
        extras = {"date_label": now.strftime("%m/%d"), "tasks": [], "market": {}, "crop_item": crop_item}
        if self.coach is not None:
            coach_variety = self.coach._current_variety() if hasattr(self.coach, "_current_variety") else getattr(self.config, "variety", None)
            extras["tasks"] = self.coach.knowledge_graph.tasks_for_today(now.date(), coach_variety)
            extras["market"] = self.coach.market_service.latest()
            extras["crop_item"] = getattr(getattr(self.coach, "crop_profile", None), "market_item_name", crop_item)
        context = self.context.build(
            "daily",
            self.repository.latest_sensor_snapshots(),
            self.satellite_db.recent(limit=5),
            self.signal_db.recent_relevant(hours=24, limit=5),
            trigger_detail="하루 종합",
            extras=extras,
        )
        risk = self.scorer.calculate(context)
        message = self.composer.compose_daily(context, risk)
        return now, context, risk, message

    def build_daily_report_message(self, now: datetime | None = None) -> str:
        _, _, _, message = self._build_daily_context_and_risk(now)
        return message

    def daily_report(self) -> str:
        _, _, risk, message = self._build_daily_context_and_risk()
        self.repository.record_fusion_log(
            trigger_source="daily",
            trigger_detail="하루 종합",
            sensor_risk=risk.breakdown["sensor"],
            satellite_risk=risk.breakdown["satellite"],
            signal_risk=risk.breakdown["signal"],
            composite_risk=risk.composite,
            agreement=risk.agreement,
            level=risk.level,
            message_sent=message,
        )
        self.kakao.send_text(message, severity="info", rule_id="FUSION_DAILY")
        return message
