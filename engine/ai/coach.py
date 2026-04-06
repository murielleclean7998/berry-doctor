from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from engine.ai.disease_detector import DiseaseDetector
from engine.ai.disease_predictor import DiseasePredictor
from engine.ai.knowledge_graph import KnowledgeGraph
from engine.db.sqlite import SQLiteRepository
from engine.i18n import Translator
from engine.paths import data_path
from engine.rules.disease_risk import top_risk


@dataclass
class StrawberryCoach:
    config: Any
    repository: SQLiteRepository
    translator: Translator
    weather_service: Any
    market_service: Any

    def __post_init__(self) -> None:
        self.knowledge_graph = KnowledgeGraph()
        self.disease_detector = DiseaseDetector()
        self.disease_predictor = DiseasePredictor(self.config.regional_profile)
        self.subsidies = json.loads(Path(data_path("subsidy_db.json")).read_text(encoding="utf-8"))["programs"]
        self.pesticide_db = json.loads(Path(data_path("pesticide_db.json")).read_text(encoding="utf-8"))["entries"]
        self.tips = json.loads(Path(data_path("farmer_tips.json")).read_text(encoding="utf-8"))["tips"]

    def _top_tip(self, keyword: str | None = None) -> str:
        for tip in self.tips:
            if keyword and keyword in (tip.get("disease"), tip.get("category")):
                return tip["tip"]
        return self.tips[0]["tip"]

    def _disease_name(self, key: str) -> str:
        mapping = {
            "botrytis": "잿빛곰팡이병",
            "powdery_mildew": "흰가루병",
            "anthracnose": "탄저병",
            "fusarium_wilt": "시들음병",
            "leaf_blight": "잎마름병",
        }
        return mapping.get(key, key)

    def build_status(self, house_id: int | None = None) -> str:
        weather = self.weather_service.latest()
        risk_map = self.disease_predictor.predict(
            temp=float(weather.get("current_temp", 18)),
            humidity=float(weather.get("current_humidity", 70)),
            wet_hours=float(weather.get("estimated_wet_hours", 4)),
            soil_temp=float(weather.get("soil_temp", 15)),
        )
        risk_key, risk_meta = top_risk(risk_map)
        if house_id is None:
            summary = f"{weather.get('current_temp')}°C / 습도 {weather.get('current_humidity')}% / {weather.get('summary')}"
            return self.translator.t(
                "templates.status",
                farm_name=self.translator.t("app.name"),
                summary=summary,
                phase0_note=self.translator.t("status.phase0_note"),
                tomorrow_min=weather.get("tomorrow_min_temp"),
                max_rainfall=weather.get("max_hourly_rainfall"),
                top_risk_name=self._disease_name(risk_key),
                top_risk_value=risk_meta["risk"],
                recommended_action=risk_meta["action"],
            )
        return self.translator.t(
            "templates.house_status",
            house_name=f"{house_id}동",
            temp=weather.get("current_temp"),
            humidity=weather.get("current_humidity"),
            rainfall=weather.get("max_hourly_rainfall"),
            growth_stage=self.knowledge_graph.stage_for_date().get("label", "기본 단계"),
            risk_summary=f"{self._disease_name(risk_key)} {risk_meta['risk']}%",
            recommended_action=risk_meta["action"],
        )

    def build_today_tasks(self) -> str:
        stage = self.knowledge_graph.stage_for_date()
        tasks = self.knowledge_graph.tasks_for_today()
        weather = self.weather_service.latest()
        if weather.get("max_hourly_rainfall", 0) >= self.config.regional_profile.get("thresholds", {}).get("heavy_rain_mm_per_hour", 20):
            tasks = tasks[:2] + ["비 예보가 있어서 배수구 점검을 먼저 넣어 주세요."]
        return self.translator.t(
            "templates.daily_tasks",
            growth_stage=stage.get("label", "생육 단계"),
            weather_summary=weather.get("summary", "예보 없음"),
            task_1=tasks[0] if len(tasks) > 0 else "하우스를 한 번 돌아보세요.",
            task_2=tasks[1] if len(tasks) > 1 else "오늘 시세를 확인해 보세요.",
            task_3=tasks[2] if len(tasks) > 2 else "기록을 남겨 두세요.",
            reason=self.knowledge_graph.why_for_today(),
        )

    def build_market_message(self) -> str:
        market = self.market_service.latest()
        return self.translator.t(
            "templates.market",
            price=market["price_per_kg"],
            change=market["change"],
            recommendation=market["recommendation"],
            reason=market["reason"],
        )

    def build_shipment_message(self) -> str:
        market = self.market_service.latest()
        day = "이번 주 후반" if market.get("trend", 0) >= 0 else "가능하면 빠른 출하"
        return self.translator.t(
            "templates.shipment",
            day=day,
            price=market["price_per_kg"],
            reason=market["reason"],
        )

    def build_subsidy_message(self) -> str:
        items = "\n".join(f"- {program['name']}: {program['summary']}" for program in self.subsidies[:3])
        return self.translator.t("templates.subsidy", items=items)

    def _pesticide_by_name(self, name: str) -> tuple[str, dict[str, Any] | None]:
        for entry in self.pesticide_db:
            for pesticide in entry.get("pesticides", []):
                if name in pesticide["name"] or pesticide["name"] in name:
                    return entry["disease_ko"], pesticide
        return "미상", None

    def record_spray(self, pesticide_name: str) -> str:
        disease_ko, pesticide = self._pesticide_by_name(pesticide_name)
        phi_days = pesticide.get("phi_days", 0) if pesticide else 0
        dilution = pesticide.get("dilution") if pesticide else None
        self.repository.record_spray(
            pesticide_name=pesticide_name,
            target_disease=disease_ko,
            dilution=dilution,
            phi_days=phi_days,
        )
        self.repository.record_diary(f"농약 살포 기록: {pesticide_name}", entry_type="spray")
        return self.translator.t("templates.spray_record", pesticide_name=pesticide_name, phi_days=phi_days)

    def record_harvest(self, weight_kg: float) -> str:
        self.repository.record_harvest(weight_kg=weight_kg)
        self.repository.record_diary(f"수확 기록: {weight_kg}kg", entry_type="harvest")
        return self.translator.t(
            "templates.harvest_record",
            weight_kg=weight_kg,
            monthly_total=self.repository.monthly_harvest_total(),
        )

    def record_note(self, text: str) -> str:
        self.repository.record_diary(text, entry_type="note")
        return self.translator.t("templates.note_record")

    def build_daily_report(self, now: datetime | None = None) -> str:
        now = now or datetime.now()
        weather = self.weather_service.latest()
        market = self.market_service.latest()
        stage = self.knowledge_graph.stage_for_date(now.date())
        tasks = "\n".join(f"- {task}" for task in self.knowledge_graph.tasks_for_today(now.date()))
        tip = self._top_tip(stage.get("key"))
        return self.translator.t(
            "templates.report",
            date=now.strftime("%Y-%m-%d"),
            weather_summary=weather.get("summary"),
            tomorrow_summary=weather.get("tomorrow_summary"),
            growth_stage=stage.get("label"),
            price=market.get("price_per_kg"),
            tasks=tasks,
            tip=tip,
        )

    def build_diagnosis_message(self, image_bytes: bytes, filename: str = "upload.jpg") -> str:
        result = self.disease_detector.analyze_bytes(image_bytes, filename)
        pesticide_text = "등록 약제를 다시 확인해 주세요."
        phi_text = "확인 필요"
        if result.pesticide:
            pesticide_text = f"{result.pesticide['name']} {result.pesticide['dilution']}배"
            phi_text = f"수확 {result.pesticide['phi_days']}일 전까지만"
        low_confidence_note = self.translator.t("messages.low_confidence_note") if result.confidence < 70 else ""
        return self.translator.t(
            "templates.diagnosis",
            disease_name=result.label_ko,
            confidence=result.confidence,
            symptoms=result.symptoms,
            pesticide=pesticide_text,
            phi_days=phi_text,
            farmer_tip=result.tip,
            low_confidence_note=low_confidence_note,
        )

    def control_unavailable(self) -> str:
        return self.translator.t("messages.phase0_control_unavailable")
