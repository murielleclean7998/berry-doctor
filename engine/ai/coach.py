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
from engine.crop_profile import load_crop_profile, resolve_data_path
from engine.db.sqlite import SQLiteRepository
from engine.i18n import Translator
from engine.paths import data_path
from engine.rules.disease_risk import top_risk


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class CropCoach:
    config: Any
    repository: SQLiteRepository
    translator: Translator
    weather_service: Any
    market_service: Any
    controller: Any | None = None
    crop_profile: Any | None = None

    def __post_init__(self) -> None:
        self.fusion_intelligence = None
        self.satellite_timeline = None
        self.security_repository = None
        self.yield_estimator = YieldEstimator()
        self.subsidies = _read_json(Path(data_path("subsidy_db.json"))).get("programs", [])
        self.set_crop_profile(self.crop_profile)

    def set_crop_profile(self, crop_profile: Any | None) -> None:
        self.crop_profile = crop_profile or load_crop_profile(getattr(self.config, "crop_type", "strawberry"))
        knowledge_path = resolve_data_path(self.crop_profile, "knowledge_graph")
        calendar_path = resolve_data_path(self.crop_profile, "calendar")
        tips_path = resolve_data_path(self.crop_profile, "farmer_tips")
        pesticide_path = resolve_data_path(self.crop_profile, "pesticide_db")

        self.knowledge_graph = KnowledgeGraph(knowledge_graph_path=knowledge_path, calendar_path=calendar_path)
        self.disease_detector = DiseaseDetector(crop_profile=self.crop_profile)
        self.disease_predictor = DiseasePredictor(
            self.config.regional_profile,
            disease_params=getattr(self.crop_profile, "diseases", None),
        )
        self.local_assistant = LocalAgronomyAssistant(
            self.config,
            knowledge_path=knowledge_path,
            tips_path=tips_path,
            crop_name_ko=getattr(self.crop_profile, "crop_name_ko", "딸기"),
        )
        self.pesticide_db = _read_json(pesticide_path).get("entries", [])
        self.tips = _read_json(tips_path).get("tips", [])
        if hasattr(self.market_service, "set_crop_profile"):
            self.market_service.set_crop_profile(self.crop_profile)

    def _crop_name(self) -> str:
        return getattr(self.crop_profile, "crop_name_ko", "딸기")

    def _crop_item(self) -> str:
        return getattr(self.crop_profile, "market_item_name", "설향 상품")

    def _current_variety(self) -> str:
        variety = str(getattr(self.config, "variety", "") or "")
        if variety and variety in getattr(self.crop_profile, "varieties", []):
            return variety
        return getattr(self.crop_profile, "default_variety", variety or "설향")

    def top_tip(self, keyword: str | None = None) -> str:
        for tip in self.tips:
            if keyword and keyword in (tip.get("disease"), tip.get("category")):
                return str(tip.get("tip", ""))
        return str(self.tips[0]["tip"]) if self.tips else "오늘은 하우스 순회와 습도 흐름 확인부터 해주세요."

    def _top_tip(self, keyword: str | None = None) -> str:
        return self.top_tip(keyword)

    def _disease_name(self, key: str) -> str:
        names = getattr(self.crop_profile, "disease_names_ko", {})
        if key in names:
            return names[key]
        fallback = {
            "botrytis": "잿빛곰팡이병",
            "powdery_mildew": "흰가루병",
            "anthracnose": "탄저병",
            "fusarium_wilt": "시들음병",
            "leaf_blight": "잎마름병",
            "humidity": "고습 경보",
        }
        return fallback.get(key, key)

    def _current_stage(self, day: date | None = None) -> dict[str, Any]:
        return self.knowledge_graph.stage_for_date(day, self._current_variety())

    def _yield_summary(self) -> dict[str, Any]:
        market = self.market_service.latest()
        stage = self._current_stage()
        baseline_price = float(getattr(self.crop_profile, "baseline_price_per_kg", 8200) or 8200)
        expected_price = float(market.get("forecast", {}).get("expected_peak_price", market.get("price_per_kg", baseline_price)))
        return self.yield_estimator.estimate(
            recent_harvests=self.repository.recent_harvests(20),
            monthly_total_kg=self.repository.monthly_harvest_total(),
            expected_price_per_kg=expected_price,
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
                f"{sensor.get('temp_indoor', weather.get('current_temp'))}°C / "
                f"습도 {sensor.get('humidity', weather.get('current_humidity'))}% / "
                f"토양 {sensor.get('soil_moisture_1', '-')}"
            )
        else:
            summary = f"{weather.get('current_temp')}°C / 습도 {weather.get('current_humidity')}% / {weather.get('summary')}"

        if house_id is None:
            return (
                "현재 상태\n"
                f"- 작물: {self._crop_name()} ({self._current_variety()})\n"
                f"- 요약: {summary}\n"
                f"- 내일 최저: {weather.get('tomorrow_min_temp')}°C\n"
                f"- 강우 위험: {weather.get('max_hourly_rainfall')}mm/h\n"
                f"- 가장 주의할 병: {self._disease_name(risk_key)} {risk_meta['risk']}%\n"
                f"- 권장 조치: {risk_meta['action']}"
            )

        return (
            f"{house_id}동 상태\n"
            f"- 작물: {self._crop_name()} ({self._current_variety()})\n"
            f"- 온도: {(sensor or {}).get('temp_indoor', weather.get('current_temp'))}°C\n"
            f"- 습도: {(sensor or {}).get('humidity', weather.get('current_humidity'))}%\n"
            f"- 생육 단계: {self._current_stage().get('label', '기본 단계')}\n"
            f"- 위험 요약: {self._disease_name(risk_key)} {risk_meta['risk']}%\n"
            f"- 권장 조치: {risk_meta['action']}"
        )

    def build_today_tasks(self) -> str:
        stage = self._current_stage()
        tasks = list(self.knowledge_graph.tasks_for_today(variety=self._current_variety()))
        weather = self.weather_service.latest()
        sensor = self.repository.latest_sensor_snapshot()
        humidity_warning = float(self.config.regional_profile.get("thresholds", {}).get("humidity_warning", 80))
        if sensor and sensor.get("humidity") and float(sensor["humidity"]) >= humidity_warning:
            tasks = tasks[:2] + ["습도가 높으니 환기와 병든 부위 점검을 먼저 해주세요."]
        if sensor and sensor.get("solution_ec") is not None:
            ph_value = sensor.get("solution_ph")
            ph_label = f"{float(ph_value):.2f}" if ph_value is not None else "-"
            tasks = tasks[:2] + [f"양액 EC {sensor['solution_ec']} / pH {ph_label} 흐름을 같이 확인해 주세요."]
        while len(tasks) < 3:
            tasks.append("하우스를 한 바퀴 더 돌며 상태를 눈으로 확인해 주세요.")
        return (
            "오늘 할 일\n"
            f"- 작물: {self._crop_name()} ({self._current_variety()})\n"
            f"- 생육 단계: {stage.get('label', '생육 단계')}\n"
            f"- 날씨: {weather.get('summary', '예보 없음')}\n"
            f"1. {tasks[0]}\n"
            f"2. {tasks[1]}\n"
            f"3. {tasks[2]}\n"
            f"이유: {self.knowledge_graph.why_for_today(variety=self._current_variety())}"
        )

    def build_market_message(self) -> str:
        market = self.market_service.latest()
        forecast = market.get("forecast", {})
        item_name = str(market.get("item") or self._crop_item())
        return (
            f"{item_name} 시세\n"
            f"- 현재: {market['price_per_kg']}원/kg ({market['change']})\n"
            f"- 권장: {market['recommendation']}\n"
            f"- 이유: {market['reason']}\n"
            f"- 예상 최고가: {forecast.get('expected_peak_price', market['price_per_kg'])}원/kg"
        )

    def build_shipment_message(self, house_id: int | None = None) -> str:
        restrictions = self.repository.active_spray_restrictions(date.today(), house_id=house_id)
        if restrictions:
            blocked_until = restrictions[0]["safe_harvest_date"]
            pesticide_names = ", ".join(sorted({row["pesticide_name"] for row in restrictions if row.get("pesticide_name")}))
            return (
                "출하 보류 권장\n"
                f"- 안전 출하일: {blocked_until}\n"
                f"- 관련 약제: {pesticide_names or '미확인'}\n"
                "안전 출하일 이후에 다시 판단해 주세요."
            )
        market = self.market_service.latest()
        forecast = market.get("forecast", {})
        day = forecast.get("recommendation", "오늘 또는 내일 출하")
        return f"출하 판단\n- 권장 시점: {day}\n- 시세: {market['price_per_kg']}원/kg\n- 이유: {market['reason']}"

    def build_subsidy_message(self) -> str:
        items = "\n".join(f"- {program['name']}: {program['summary']}" for program in self.subsidies[:3])
        return f"지금 살펴볼 지원사업\n{items}"

    def _pesticide_by_name(self, name: str) -> tuple[str, dict[str, Any] | None]:
        for entry in self.pesticide_db:
            for pesticide in entry.get("pesticides", []):
                pesticide_name = str(pesticide.get("name", ""))
                if name in pesticide_name or pesticide_name in name:
                    return str(entry.get("disease_ko", "미상")), pesticide
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
        self.repository.record_diary(f"농약 기록: {pesticide_name}", house_id=house_id, entry_type="spray")
        return f"농약 기록 완료\n- 약제: {pesticide_name}\n- 안전 출하일 기준: {phi_days}일"

    def record_harvest(self, weight_kg: float, house_id: int | None = None) -> str:
        market_price = float(self.market_service.latest().get("price_per_kg", 0))
        self.repository.record_harvest(
            weight_kg=weight_kg,
            house_id=house_id,
            sale_price_per_kg=market_price,
            note="auto market snapshot",
        )
        self.repository.record_diary(f"수확 기록: {weight_kg}kg", house_id=house_id, entry_type="harvest")
        return f"수확 기록 완료\n- 중량: {weight_kg}kg\n- 이번 달 누적: {self.repository.monthly_harvest_total()}kg"

    def record_note(self, text: str) -> str:
        self.repository.record_diary(text, entry_type="note")
        return "메모로 저장했어요."

    def answer_or_record(self, text: str) -> str:
        stripped = text.strip()
        if "?" in stripped or any(keyword in stripped for keyword in ["왜", "어떻게", "언제", "무엇", "추천"]):
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
        return f"{house_id}동 {device} 제어를 요청했어요. 결과: {result['result']}"

    def turn_on_fan(self, house_id: int = 1) -> str:
        return self._manual_control(house_id, "ventilation", "on", "사용자 수동 명령")

    def close_curtain(self, house_id: int = 1) -> str:
        return self._manual_control(house_id, "curtain", "close", "사용자 수동 명령")

    def turn_on_light(self, house_id: int = 1) -> str:
        return self._manual_control(house_id, "supplemental_light", "on", "사용자 수동 명령")

    def water_now(self, house_id: int = 1) -> str:
        return self._manual_control(house_id, "irrigation", "pulse", "사용자 수동 명령", {"duration_seconds": 20})

    def set_target_temp(self, value: float, house_id: int = 1) -> str:
        return self._manual_control(house_id, "target_temp", "set", "사용자 목표 온도 변경", {"target_temp_c": value})

    def build_daily_report(self, now: datetime | None = None) -> str:
        now = now or datetime.now()
        if self.fusion_intelligence is not None:
            return self.fusion_intelligence.build_daily_report_message(now)
        weather = self.weather_service.latest()
        market = self.market_service.latest()
        stage = self._current_stage(now.date())
        yield_summary = self._yield_summary()
        tasks = "\n".join(f"- {task}" for task in self.knowledge_graph.tasks_for_today(now.date(), self._current_variety()))
        tip = self.top_tip(stage.get("key"))
        return (
            f"{now:%Y-%m-%d} 리포트\n"
            f"- 작물: {self._crop_name()} ({self._current_variety()})\n"
            f"- 오늘 날씨: {weather.get('summary')}\n"
            f"- 내일 예보: {weather.get('tomorrow_summary')}\n"
            f"- 생육 단계: {stage.get('label')}\n"
            f"- 시세: {market.get('price_per_kg')}원/kg\n"
            f"- 오늘 할 일\n{tasks}\n"
            f"- 팁: {tip}\n"
            f"- 예상 월 수확: {yield_summary['projected_month_kg']}kg\n"
            f"- 예상 시즌 매출: {yield_summary['projected_revenue']:.0f}원"
        )

    def build_monthly_report(self, now: datetime | None = None) -> str:
        now = now or datetime.now()
        month_key = now.strftime("%Y-%m")
        yield_summary = self._yield_summary()
        alert_count = len(self.repository.recent_alerts(50))
        control_count = len(self.repository.recent_control_actions(50))
        feedback_count = len(self.repository.recent_pilot_feedback(20))
        return (
            f"{month_key} 월간 리포트\n"
            f"- 작물: {self._crop_name()} ({self._current_variety()})\n"
            f"- 실적 수확: {yield_summary['monthly_total_kg']}kg\n"
            f"- 예상 월 수확: {yield_summary['projected_month_kg']}kg\n"
            f"- 예상 시즌 매출: {yield_summary['projected_revenue']:.0f}원\n"
            f"- 최근 알림: {alert_count}건\n"
            f"- 최근 제어 실행: {control_count}건\n"
            f"- 파일럿 피드백: {feedback_count}건\n"
            f"- 운영 팁: {self.top_tip('market')}"
        )

    def build_diagnosis_message(self, image_bytes: bytes, filename: str = "upload.jpg", house_id: int | None = None) -> str:
        result = self.disease_detector.analyze_bytes(
            image_bytes,
            filename,
            context={
                "house_id": house_id,
                "farm_location": self.config.farm_location,
                "region_name": self.config.farm_location,
                "share_to_community": getattr(self.config, "share_to_community", False),
                "sensor": self.repository.latest_sensor_snapshot(house_id),
                "crop_name_ko": self._crop_name(),
            },
        )
        pesticide_text = "등록 약제를 다시 확인해 주세요."
        phi_text = "확인 필요"
        pesticide_name = None
        phi_days = None
        if result.pesticide:
            pesticide_name = result.pesticide["name"]
            phi_days = result.pesticide["phi_days"]
            pesticide_text = f"{result.pesticide['name']} {result.pesticide['dilution']}배"
            phi_text = f"수확 {result.pesticide['phi_days']}일 전까지"

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
        return (
            f"진단 결과\n"
            f"- 작물: {self._crop_name()}\n"
            f"- 병명: {result.label_ko}\n"
            f"- 신뢰도: {result.confidence}%\n"
            f"- 증상: {result.symptoms}\n"
            f"- 약제: {pesticide_text}\n"
            f"- 사용 제한: {phi_text}\n"
            f"- 팁: {result.tip}\n"
            f"{low_confidence_note}"
        ).strip()

    def build_timeline_message(self, house_id: int = 1) -> str:
        if self.satellite_timeline is None:
            return "위성 기록이 아직 준비되지 않았어요."
        summary = self.satellite_timeline.generate_season_summary(house_id, None)
        return summary["message"]

    def build_year_compare_message(self, house_id: int = 1) -> str:
        if self.satellite_timeline is None:
            return "작년 비교에 쓸 위성 기록이 아직 없어요."
        summary = self.satellite_timeline.generate_season_summary(house_id, None)
        return (
            f"{house_id}동 작년 비교\n"
            f"- 가장 좋았던 시기: {summary['best_month']}\n"
            f"- 작년 같은 시기 대비: {summary['year_compare']:+.2f}\n"
            "- 참고: 위성은 바깥에서 본 정보예요."
        )

    def build_security_history_message(self, days: int = 7) -> str:
        if self.security_repository is None:
            events = self.repository.recent_security_events(days=days, limit=5)
        else:
            events = self.security_repository.recent_events(days=days, limit=5)
        if not events:
            return f"최근 {days}일 보안 기록은 없어요."
        lines = [f"최근 {days}일 보안 기록"]
        for event in events[:5]:
            lines.append(f"- {event.get('timestamp')} / {event.get('house_id')}동 / 사진 {len(event.get('photo_paths_list', []))}장")
        return "\n".join(lines)

    def control_unavailable(self) -> str:
        return "제어 경로가 아직 연결되지 않았습니다. MQTT/ESP32 연결 상태를 확인해 주세요."


StrawberryCoach = CropCoach
