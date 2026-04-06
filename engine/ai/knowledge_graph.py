from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from engine.paths import data_path


@dataclass
class KnowledgeGraph:
    knowledge_path: Path = Path(data_path("knowledge_graph.json"))
    calendar_path: Path = Path(data_path("seolhyang_calendar.json"))

    def __post_init__(self) -> None:
        self.knowledge = json.loads(self.knowledge_path.read_text(encoding="utf-8"))
        self.calendar = json.loads(self.calendar_path.read_text(encoding="utf-8"))

    def stage_for_date(self, day: date | None = None, variety: str = "설향") -> dict[str, Any]:
        day = day or date.today()
        month_info = self.calendar["months"][str(day.month)]
        stage_key = month_info["stage"]
        stage_info = self.knowledge["varieties"][variety]["stages"].get(stage_key, {})
        return {"key": stage_key, **month_info, **stage_info}

    def tasks_for_today(self, day: date | None = None, variety: str = "설향") -> list[str]:
        stage = self.stage_for_date(day, variety)
        tasks = stage.get("tasks", [])
        return tasks[:3] if tasks else ["하우스 상태를 한 번 더 살펴보세요."]

    def why_for_today(self, day: date | None = None, variety: str = "설향") -> str:
        return self.stage_for_date(day, variety).get("why", "지금 단계에 맞는 기본 작업을 지키는 게 가장 중요해요.")
