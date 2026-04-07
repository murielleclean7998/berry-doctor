from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from engine.signal.analyzer import SignalAnalyzer
from engine.signal.db import SignalRepository
from engine.signal.models import RawSignal
from engine.signal.sources.community import CommunitySource
from engine.signal.sources.kma_special import KMASpecialSource
from engine.signal.sources.market_alert import MarketAlertSource
from engine.signal.sources.rda_pest import RDAPestSource
from engine.signal.translator import SignalTranslator

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SignalCollector:
    config: Any
    repository: Any
    sender: Any | None = None
    crop_profile: Any | None = None
    fusion: Any | None = None
    sources: list[Any] = field(default_factory=list)
    db: Any = field(default=None, init=False)
    analyzer: Any = field(default=None, init=False)
    translator: Any = field(default=None, init=False)
    community_source: Any = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.db = SignalRepository(self.repository)
        self.analyzer = SignalAnalyzer(self.config, crop_profile=self.crop_profile)
        self.translator = SignalTranslator(self.config)
        self.community_source = CommunitySource(
            self.config,
            self.repository,
            emit_callback=self._handle_external_signal,
            crop_profile=self.crop_profile,
        )
        if not self.sources:
            self.sources = [
                RDAPestSource(self.config, self.repository),
                KMASpecialSource(self.config, self.repository),
                MarketAlertSource(self.config, self.repository),
            ]

    def set_fusion(self, fusion: Any) -> None:
        self.fusion = fusion

    def set_crop_profile(self, crop_profile: Any | None) -> None:
        self.crop_profile = crop_profile
        self.analyzer.set_crop_profile(crop_profile)
        self.community_source.crop_profile = crop_profile

    def _farm_profile(self) -> dict[str, Any]:
        return {
            "farm_location": getattr(self.config, "farm_location", ""),
            "province": str(getattr(self.config, "farm_location", "")).split()[0] if getattr(self.config, "farm_location", "") else "",
            "current_stage": self.repository.get_config("current_growth_stage", "과실비대기"),
        }

    def _signal_message(self, signal: RawSignal) -> str:
        summary = signal.translated_summary or signal.summary
        reason = signal.relevance.reason if signal.relevance else "우리 농장과 관련 있을 가능성이 있어 보여요."
        return f"📡 {signal.title}\n\n{summary}\n\n왜 중요하냐면: {reason}\n직접 확인해보시는 게 좋겠어요."

    def _remaining_immediate_slots(self, on_day: date | None = None) -> int:
        limit = int(getattr(self.config, "signal_immediate_daily_limit", 2) or 2)
        used = self.db.immediate_count_today(on_day)
        return max(limit - used, 0)

    def _handle_candidate(self, signal: RawSignal, remaining_immediate_slots: list[int] | None = None) -> dict[str, Any] | None:
        if self.db.is_duplicate(signal.hash):
            return None
        signal.relevance = self.analyzer.evaluate(
            signal,
            self._farm_profile(),
            latest_sensor=self.repository.latest_sensor_snapshot(),
            current_stage=self.repository.get_config("current_growth_stage", "과실비대기"),
        )
        if signal.relevance.score <= 0.3:
            return None
        if signal.language != "ko":
            signal.translated_summary = self.translator.translate_and_summarize(signal)
        signal_id = self.db.save_signal(signal)
        row = self.repository.find_signal_by_hash(signal.hash) or {"id": signal_id}
        available_slots = remaining_immediate_slots[0] if remaining_immediate_slots is not None else self._remaining_immediate_slots()
        if signal.relevance.urgency == "critical" and self.sender is not None and available_slots > 0:
            self.sender.send_text(
                self._signal_message(signal),
                severity="warning",
                rule_id=f"SIGNAL_{signal.source_id.upper()}",
            )
            self.repository.mark_signal_delivered(int(row["id"]))
            if remaining_immediate_slots is not None:
                remaining_immediate_slots[0] = max(remaining_immediate_slots[0] - 1, 0)
        if self.fusion is not None:
            try:
                self.fusion.on_new_signal(self.repository.find_signal_by_hash(signal.hash) or row)
            except Exception:
                logger.exception("Fusion notification failed for signal %s", signal.hash)
        return self.repository.find_signal_by_hash(signal.hash) or row

    def _handle_external_signal(self, signal: RawSignal) -> dict[str, Any] | None:
        return self._handle_candidate(signal)

    async def _collect_sources(self, selected_sources: list[Any]) -> dict[str, Any]:
        saved = 0
        skipped = 0
        remaining_immediate_slots = [self._remaining_immediate_slots()]
        for source in selected_sources:
            try:
                raw_items = await source.fetch()
            except Exception:
                logger.exception("Signal source %s failed.", getattr(source, "source_id", source.__class__.__name__))
                continue
            for item in raw_items:
                result = self._handle_candidate(item, remaining_immediate_slots)
                if result is None:
                    skipped += 1
                else:
                    saved += 1
        return {"saved": saved, "skipped": skipped, "sources": len(selected_sources)}

    def collect_domestic(self) -> dict[str, Any]:
        return asyncio.run(self._collect_sources(self.sources))

    def collect_global(self) -> dict[str, Any]:
        return {"saved": 0, "skipped": 0, "sources": 0, "status": "domestic_only"}
