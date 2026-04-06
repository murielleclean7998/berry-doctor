from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
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

    def top_tip(self, keyword: str | None = None) -> str:
        for tip in self.tips:
            if keyword and keyword in (tip.get("disease"), tip.get("category")):
                return tip["tip"]
        return self.tips[0]["tip"]

    def _top_tip(self, keyword: str | None = None) -> str:
        return self.top_tip(keyword)

    def _disease_name(self, key: str) -> str:
        mapping = {
            "botrytis": "\ud68c\uc0c9\uacf0\ud321\uc774\ubcd1",
            "powdery_mildew": "\ud770\uac00\ub8e8\ubcd1",
            "anthracnose": "\ud0c4\uc800\ubcd1",
            "fusarium_wilt": "\uc2dc\ub4e4\uc74c\ubcd1",
            "leaf_blight": "\uc810\ubb34\ub2a6\uc74c\ubcd1",
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
            summary = f"{weather.get('current_temp')}\u00b0C / \uc2b5\ub3c4 {weather.get('current_humidity')}% / {weather.get('summary')}"
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
            house_name=f"{house_id}\ub3d9",
            temp=weather.get("current_temp"),
            humidity=weather.get("current_humidity"),
            rainfall=weather.get("max_hourly_rainfall"),
            growth_stage=self.knowledge_graph.stage_for_date().get("label", "\uae30\ubcf8 \ub2e8\uacc4"),
            risk_summary=f"{self._disease_name(risk_key)} {risk_meta['risk']}%",
            recommended_action=risk_meta["action"],
        )

    def build_today_tasks(self) -> str:
        stage = self.knowledge_graph.stage_for_date()
        tasks = self.knowledge_graph.tasks_for_today()
        weather = self.weather_service.latest()
        if weather.get("max_hourly_rainfall", 0) >= self.config.regional_profile.get("thresholds", {}).get("heavy_rain_mm_per_hour", 20):
            tasks = tasks[:2] + ["\ube44 \uc608\ubcf4\uac00 \uc788\uc5b4\uc11c \ubc30\uc218\uad6c\uc640 \ub2e4\uc6b4 \ud558\uc6b0\uc2a4 \uc8fc\ubcc0\uc744 \uba3c\uc800 \ud655\uc778\ud574 \uc8fc\uc138\uc694."]
        return self.translator.t(
            "templates.daily_tasks",
            growth_stage=stage.get("label", "\uc0dd\uc721 \ub2e8\uacc4"),
            weather_summary=weather.get("summary", "\uc608\ubcf4 \uc5c6\uc74c"),
            task_1=tasks[0] if len(tasks) > 0 else "\ud558\uc6b0\uc2a4\ub97c \ud55c \ubc88 \ub3cc\uc544\ubcf4\uc138\uc694.",
            task_2=tasks[1] if len(tasks) > 1 else "\uc624\ub298 \uc2dc\uc138\ub97c \ud655\uc778\ud574 \ubcf4\uc138\uc694.",
            task_3=tasks[2] if len(tasks) > 2 else "\uae30\ub85d\uc744 \ud55c \uac74 \ub0a8\uaca8 \ubcf4\uc138\uc694.",
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

    def build_shipment_message(self, house_id: int | None = None) -> str:
        restrictions = self.repository.active_spray_restrictions(date.today(), house_id=house_id)
        if restrictions:
            blocked_until = restrictions[0]["safe_harvest_date"]
            pesticide_names = ", ".join(
                sorted({row["pesticide_name"] for row in restrictions if row.get("pesticide_name")})
            )
            pesticide_label = pesticide_names or "\ubbf8\ud655\uc778"
            return (
                f"\ucd9c\ud558 \ubcf4\ub958 \uad8c\uc7a5\n"
                f"{blocked_until}\uae4c\uc9c0 \uc548\uc804\ucd9c\ud558\uc77c\uc774 \ub0a8\uc544 \uc788\uc5b4\uc694.\n"
                f"\uad00\ub828 \uc57d\uc81c: {pesticide_label}\n"
                "\uc548\uc804\ucd9c\ud558\uc77c \uc774\ud6c4\uc5d0 \ucd9c\ud558 \ud310\ub2e8\uc744 \ub2e4\uc2dc \ud574\uc8fc\uc138\uc694."
            )
        market = self.market_service.latest()
        day = "\uc774\ubc88 \uc8fc \ucd08\ubc18" if market.get("trend", 0) >= 0 else "\uac00\ub2a5\ud558\uba74 \ube60\ub978 \ucd9c\ud558"
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
        return "\ubbf8\uc0c1", None

    def record_spray(self, pesticide_name: str, house_id: int | None = None) -> str:
        disease_ko, pesticide = self._pesticide_by_name(pesticide_name)
        phi_days = pesticide.get("phi_days", 0) if pesticide else 0
        dilution = pesticide.get("dilution") if pesticide else None
        self.repository.record_spray(
            pesticide_name=pesticide_name,
            target_disease=disease_ko,
            dilution=dilution,
            phi_days=phi_days,
            house_id=house_id,
        )
        self.repository.record_diary(
            f"\ub18d\uc57d \uc0b4\ud3ec \uae30\ub85d: {pesticide_name}",
            house_id=house_id,
            entry_type="spray",
        )
        return self.translator.t("templates.spray_record", pesticide_name=pesticide_name, phi_days=phi_days)

    def record_harvest(self, weight_kg: float, house_id: int | None = None) -> str:
        self.repository.record_harvest(weight_kg=weight_kg, house_id=house_id)
        self.repository.record_diary(
            f"\uc218\ud655 \uae30\ub85d: {weight_kg}kg",
            house_id=house_id,
            entry_type="harvest",
        )
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
        tip = self.top_tip(stage.get("key"))
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

    def build_diagnosis_message(self, image_bytes: bytes, filename: str = "upload.jpg", house_id: int | None = None) -> str:
        result = self.disease_detector.analyze_bytes(image_bytes, filename)
        pesticide_text = "\ub4f1\ub85d \uc57d\uc81c\ub97c \ub2e4\uc2dc \ud655\uc778\ud574 \uc8fc\uc138\uc694."
        phi_text = "\ud655\uc778 \ud544\uc694"
        pesticide_name = None
        phi_days = None
        if result.pesticide:
            pesticide_name = result.pesticide["name"]
            phi_days = result.pesticide["phi_days"]
            pesticide_text = f"{result.pesticide['name']} {result.pesticide['dilution']}\ubc30"
            phi_text = f"\uc218\ud655 {result.pesticide['phi_days']}\uc77c \uc804\uae4c\uc9c0 \uae08\uc9c0"

        self.repository.record_diagnosis(
            disease_key=result.label,
            disease_name=result.label_ko,
            confidence=result.confidence,
            symptoms=result.symptoms,
            model_used=result.model_used,
            pesticide_name=pesticide_name,
            phi_days=phi_days,
            image_name=filename,
            house_id=house_id,
        )
        self.repository.record_diary(
            f"\uc0ac\uc9c4 \uc9c4\ub2e8: {result.label_ko} ({result.confidence}%)",
            house_id=house_id,
            entry_type="diagnosis",
            auto_generated=True,
        )

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
