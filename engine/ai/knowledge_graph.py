from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from engine.paths import data_path


@dataclass(slots=True)
class KnowledgeGraph:
    knowledge_graph_path: Path | str | None = None
    calendar_path: Path | str | None = None
    knowledge: dict[str, Any] = field(init=False)
    calendar: dict[str, Any] = field(init=False)

    def __post_init__(self) -> None:
        knowledge_path = Path(self.knowledge_graph_path or data_path("knowledge_graph.json"))
        calendar_path = Path(self.calendar_path or data_path("seolhyang_calendar.json"))
        self.knowledge = json.loads(knowledge_path.read_text(encoding="utf-8"))
        self.calendar = json.loads(calendar_path.read_text(encoding="utf-8"))

    def _variety_payload(self, variety: str | None) -> dict[str, Any]:
        varieties = self.knowledge.get("varieties", {})
        if variety and variety in varieties:
            return varieties[variety]
        if varieties:
            return next(iter(varieties.values()))
        return {"stages": {}}

    def stage_for_date(self, day: date | None = None, variety: str | None = None) -> dict[str, Any]:
        day = day or date.today()
        month_info = self.calendar["months"][str(day.month)]
        stage_key = month_info["stage"]
        stage_info = self._variety_payload(variety).get("stages", {}).get(stage_key, {})
        return {"key": stage_key, **month_info, **stage_info}

    def tasks_for_today(self, day: date | None = None, variety: str | None = None) -> list[str]:
        stage = self.stage_for_date(day, variety)
        tasks = list(stage.get("tasks", []))
        return tasks[:3] if tasks else ["하우스 상태를 두 번 이상 천천히 확인해 주세요."]

    def why_for_today(self, day: date | None = None, variety: str | None = None) -> str:
        return self.stage_for_date(day, variety).get("why", "지금 단계에 맞는 기본 작업을 지키는 게 가장 중요해요.")
