from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from engine.ai.disease_detector import DiseaseDetector
from engine.ai.disease_predictor import DiseasePredictor
from engine.ai.knowledge_graph import KnowledgeGraph
from engine.ai.llm import LocalAgronomyAssistant
from engine.ai.yield_estimator import YieldEstimator
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
    controller: Any | None = None

    def __post_init__(self) -> None:
        self.knowledge_graph = KnowledgeGraph()
        self.disease_detector = DiseaseDetector()
        self.disease_predictor = DiseasePredictor(self.config.regional_profile)
        self.yield_estimator = YieldEstimator()
        self.local_assistant = LocalAgronomyAssistant(self.config)
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
            "botrytis": "회색곰팡이병",
            "powdery_mildew": "흰가루병",
            "anthracnose": "탄저병",
            "fusarium_wilt": "시들음병",
            "leaf_blight": "잎마름병",
            "humidity": "고습 경보",
        }
        return mapping.get(key, key)

    def _current_stage(self, day: date | None = None) -> dict[str, Any]:
        return self.knowledge_graph.stage_for_date(day, self.config.variety)

    def _yield_summary(self) -> dict[str, Any]:
        market = self.market_service.latest()
        stage = self._current_stage()
        return self.yield_estimator.estimate(
            recent_harvests=self.repository.recent_harvests(20),
            monthly_total_kg=self.repository.monthly_harvest_total(),
            expected_price_per_kg=float(market.get("forecast", {}).get("expected_peak_price", market.get("price_per_kg", 8200))),
            growth_stage=stage.get("label", "확인 중"),
            house_count=max(int(getattr(self.config, "house_count", 1)), 1),
        )

    def yield_summary(self) -> dict[str, Any]:
        return self._yield_summary()

    def build_status(self, house_id: int | None = None) -> str:
        weather = self.weather_service.latest()
        sensor = self.repository.latest_sensor_snapshot(house_id)
        risk_map = self.disease_predictor.predict(
            temp=float((sensor or {}).get("temp_indoor", weather.get("current_temp", 18))),
            humidity=float((sensor or {}).get("humidity", weather.get("current_humidity", 70))),
            wet_hours=float(weather.get("estimated_wet_hours", 4)),
            soil_temp=float((sensor or {}).get("soil_temp", weather.get("soil_temp", 15))),
        )
        risk_key, risk_meta = top_risk(risk_map)

        if sensor:
            summary = (
                f"{(sensor or {}).get('temp_indoor', weather.get('current_temp'))}°C / "
                f"습도 {(sensor or {}).get('humidity', weather.get('current_humidity'))}% / "
                f"토양 {(sensor or {}).get('soil_moisture_1', '-')}"
            )
        else:
            summary = f"{weather.get('current_temp')}°C / 습도 {weather.get('current_humidity')}% / {weather.get('summary')}"

        if house_id is None:
            return self.translator.t(
                "templates.status",
                farm_name=self.translator.t("app.name"),
                summary=summary,
                phase0_note="센서/제어/예측 기능을 함께 사용하는 통합 상태입니다.",
                tomorrow_min=weather.get("tomorrow_min_temp"),
                max_rainfall=weather.get("max_hourly_rainfall"),
                top_risk_name=self._disease_name(risk_key),
                top_risk_value=risk_meta["risk"],
                recommended_action=risk_meta["action"],
            )

        return self.translator.t(
            "templates.house_status",
            house_name=f"{house_id}동",
            temp=(sensor or {}).get("temp_indoor", weather.get("current_temp")),
            humidity=(sensor or {}).get("humidity", weather.get("current_humidity")),
            rainfall=weather.get("max_hourly_rainfall"),
            growth_stage=self._current_stage().get("label", "기본 단계"),
            risk_summary=f"{self._disease_name(risk_key)} {risk_meta['risk']}%",
            recommended_action=risk_meta["action"],
        )

    def build_today_tasks(self) -> str:
        stage = self._current_stage()
        tasks = self.knowledge_graph.tasks_for_today(variety=self.config.variety)
        weather = self.weather_service.latest()
        sensor = self.repository.latest_sensor_snapshot()
        if sensor and sensor.get("humidity") and float(sensor["humidity"]) >= self.config.regional_profile.get("thresholds", {}).get("humidity_warning", 80):
            tasks = tasks[:2] + ["하우스 습도가 높아 환기와 병든 과실 제거를 먼저 확인하세요."]
        if sensor and sensor.get("solution_ec") is not None:
            ph_value = sensor.get("solution_ph")
            ph_label = f"{float(ph_value):.2f}" if ph_value is not None else "-"
            tasks = tasks[:2] + [f"양액 EC {sensor['solution_ec']} / pH {ph_label} 상태를 보고 조정 여부를 확인하세요."]
        return self.translator.t(
            "templates.daily_tasks",
            growth_stage=stage.get("label", "생육 단계"),
            weather_summary=weather.get("summary", "예보 없음"),
            task_1=tasks[0] if len(tasks) > 0 else "하우스를 한 번 돌아보세요.",
            task_2=tasks[1] if len(tasks) > 1 else "오늘 시세를 확인해 보세요.",
            task_3=tasks[2] if len(tasks) > 2 else "기록을 한 건 남겨 보세요.",
            reason=self.knowledge_graph.why_for_today(variety=self.config.variety),
        )

    def build_market_message(self) -> str:
        market = self.market_service.latest()
        forecast = market.get("forecast", {})
        return (
            self.translator.t(
                "templates.market",
                price=market["price_per_kg"],
                change=market["change"],
                recommendation=market["recommendation"],
                reason=market["reason"],
            )
            + f"\n예상 최고가는 {forecast.get('expected_peak_price', market['price_per_kg'])}원/kg, "
            + f"권장 시점은 {forecast.get('recommendation', '즉시 출하')}입니다."
        )

    def build_shipment_message(self, house_id: int | None = None) -> str:
        restrictions = self.repository.active_spray_restrictions(date.today(), house_id=house_id)
        if restrictions:
            blocked_until = restrictions[0]["safe_harvest_date"]
            pesticide_names = ", ".join(sorted({row["pesticide_name"] for row in restrictions if row.get("pesticide_name")}))
            return (
                f"출하 보류 권장\n{blocked_until}까지 안전출하일이 남아 있습니다.\n"
                f"관련 약제: {pesticide_names or '미확인'}\n안전출하일 이후에 다시 출하 판단을 내려주세요."
            )
        market = self.market_service.latest()
        forecast = market.get("forecast", {})
        day = forecast.get("recommendation", "오늘 또는 내일 출하")
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
            f"농약 살포 기록: {pesticide_name}",
            house_id=house_id,
            entry_type="spray",
        )
        return self.translator.t("templates.spray_record", pesticide_name=pesticide_name, phi_days=phi_days)

    def record_harvest(self, weight_kg: float, house_id: int | None = None) -> str:
        market_price = float(self.market_service.latest().get("price_per_kg", 0))
        self.repository.record_harvest(
            weight_kg=weight_kg,
            house_id=house_id,
            sale_price_per_kg=market_price,
            note="auto market snapshot",
        )
        self.repository.record_diary(
            f"수확 기록: {weight_kg}kg",
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

    def answer_or_record(self, text: str) -> str:
        stripped = text.strip()
        if "?" in stripped or any(keyword in stripped for keyword in ["왜", "어떻게", "언제", "무엇", "도와줘", "추천"]):
            context = {
                "weather": self.weather_service.latest(),
                "market": self.market_service.latest(),
                "stage": self._current_stage(),
            }
            return self.local_assistant.answer(stripped, context)["text"]
        return self.record_note(stripped)

    def _manual_control(self, house_id: int, device: str, action: str, reason: str, payload: dict[str, Any] | None = None) -> str:
        if self.controller is None:
            return self.control_unavailable()
        result = self.controller.manual_action(house_id=house_id, device=device, action=action, reason=reason, payload=payload)
        return f"{house_id}동 {device} 제어를 요청했습니다. 결과: {result['result']}"

    def turn_on_fan(self, house_id: int = 1) -> str:
        return self._manual_control(house_id, "ventilation", "on", "사용자 수동 명령")

    def close_curtain(self, house_id: int = 1) -> str:
        return self._manual_control(house_id, "curtain", "close", "사용자 수동 명령")

    def turn_on_light(self, house_id: int = 1) -> str:
        return self._manual_control(house_id, "supplemental_light", "on", "사용자 수동 명령")

    def water_now(self, house_id: int = 1) -> str:
        return self._manual_control(house_id, "irrigation", "pulse", "사용자 수동 명령", {"duration_seconds": 20})

    def set_target_temp(self, value: float, house_id: int = 1) -> str:
        return self._manual_control(house_id, "target_temp", "set", "사용자 목표온도 변경", {"target_temp_c": value})

    def build_daily_report(self, now: datetime | None = None) -> str:
        now = now or datetime.now()
        weather = self.weather_service.latest()
        market = self.market_service.latest()
        stage = self._current_stage(now.date())
        yield_summary = self._yield_summary()
        tasks = "\n".join(f"- {task}" for task in self.knowledge_graph.tasks_for_today(now.date(), self.config.variety))
        tip = self.top_tip(stage.get("key"))
        return (
            self.translator.t(
                "templates.report",
                date=now.strftime("%Y-%m-%d"),
                weather_summary=weather.get("summary"),
                tomorrow_summary=weather.get("tomorrow_summary"),
                growth_stage=stage.get("label"),
                price=market.get("price_per_kg"),
                tasks=tasks,
                tip=tip,
            )
            + f"\n예상 월 수확 {yield_summary['projected_month_kg']}kg / 예상 시즌 매출 {yield_summary['projected_revenue']:.0f}원"
        )

    def build_monthly_report(self, now: datetime | None = None) -> str:
        now = now or datetime.now()
        month_key = now.strftime("%Y-%m")
        yield_summary = self._yield_summary()
        alert_count = len(self.repository.recent_alerts(50))
        control_count = len(self.repository.recent_control_actions(50))
        feedback_count = len(self.repository.recent_pilot_feedback(20))
        return (
            f"📈 {month_key} 월간 리포트\n"
            f"- 월 누적 수확: {yield_summary['monthly_total_kg']}kg\n"
            f"- 예상 월 수확: {yield_summary['projected_month_kg']}kg\n"
            f"- 예상 시즌 매출: {yield_summary['projected_revenue']:.0f}원\n"
            f"- 최근 알림 수: {alert_count}\n"
            f"- 최근 제어 실행 수: {control_count}\n"
            f"- 파일럿 피드백 수: {feedback_count}\n"
            f"- 핵심 메모: {self.top_tip('market')}"
        )

    def build_diagnosis_message(self, image_bytes: bytes, filename: str = "upload.jpg", house_id: int | None = None) -> str:
        result = self.disease_detector.analyze_bytes(image_bytes, filename)
        pesticide_text = "등록 약제를 다시 확인해 주세요."
        phi_text = "확인 필요"
        pesticide_name = None
        phi_days = None
        if result.pesticide:
            pesticide_name = result.pesticide["name"]
            phi_days = result.pesticide["phi_days"]
            pesticide_text = f"{result.pesticide['name']} {result.pesticide['dilution']}배"
            phi_text = f"수확 {result.pesticide['phi_days']}일 전까지만"

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
            f"사진 진단: {result.label_ko} ({result.confidence}%)",
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
        return "제어 경로가 아직 연결되지 않았습니다. MQTT/ESP32 연결 상태를 확인해 주세요."
