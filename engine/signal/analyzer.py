from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.signal.models import RawSignal, RelevanceScore


@dataclass(slots=True)
class SignalAnalyzer:
    config: Any
    crop_profile: Any | None = None
    signal_keywords: set[str] = field(default_factory=set, init=False)
    crop_name_ko: str = field(default="딸기", init=False)

    def __post_init__(self) -> None:
        self.set_crop_profile(self.crop_profile)

    def set_crop_profile(self, crop_profile: Any | None) -> None:
        self.crop_profile = crop_profile
        keywords = set(getattr(crop_profile, "signal_keywords", []) or ["딸기", "strawberry"])
        variety = str(getattr(self.config, "variety", "") or "")
        if variety:
            keywords.add(variety)
        self.signal_keywords = {str(keyword).lower() for keyword in keywords}
        self.crop_name_ko = str(getattr(crop_profile, "crop_name_ko", "딸기"))

    def _farm_region_tokens(self) -> list[str]:
        location = str(getattr(self.config, "farm_location", "") or "")
        return [token for token in location.replace(",", " ").split() if token]

    def calc_region_distance(self, signal: RawSignal) -> str:
        tags = {str(tag).lower() for tag in signal.tags}
        region_tokens = self._farm_region_tokens()
        if not region_tokens:
            return "unknown"
        province = region_tokens[0].lower()
        if province in tags:
            return "same_province"
        for token in region_tokens[1:]:
            if token.lower() in tags:
                return "same_city"
        return "overseas_similar" if signal.language != "ko" else "unknown"

    def environment_matches(self, signal: RawSignal, latest_sensor: dict[str, Any] | None) -> bool:
        if not latest_sensor:
            return False
        hint = signal.payload.get("environment") if isinstance(signal.payload, dict) else None
        if not isinstance(hint, dict):
            return False
        humidity = float(latest_sensor.get("humidity") or 0.0)
        temp = float(latest_sensor.get("temp_indoor") or latest_sensor.get("temp_outdoor") or 0.0)
        humidity_hint = float(hint.get("humidity_min") or 0.0)
        temp_min = float(hint.get("temp_min") or -999.0)
        temp_max = float(hint.get("temp_max") or 999.0)
        return humidity >= humidity_hint and temp_min <= temp <= temp_max

    def growth_stage_relevant(self, signal: RawSignal, current_stage: str | None) -> bool:
        if not current_stage:
            return False
        stages = {str(item).lower() for item in signal.payload.get("growth_stages", [])}
        return not stages or current_stage.lower() in stages

    def classify_urgency(self, signal: RawSignal, score: float) -> str:
        lowered = f"{signal.title} {signal.summary}".lower()
        if any(keyword in lowered for keyword in ["경보", "주의보", "특보", "급등", "급락"]):
            return "critical" if score >= 0.55 else "warning"
        if score >= 0.6:
            return "warning"
        if score >= 0.4:
            return "info"
        return "tip"

    def evaluate(
        self,
        signal: RawSignal,
        farm_profile: dict[str, Any],
        latest_sensor: dict[str, Any] | None = None,
        current_stage: str | None = None,
    ) -> RelevanceScore:
        score = 0.0
        reasons: list[str] = []
        tags = {str(tag).lower() for tag in signal.tags}
        combined = " ".join(tags)

        if self.signal_keywords & tags or any(keyword in combined for keyword in self.signal_keywords):
            score += 0.3
            reasons.append(f"{self.crop_name_ko} 관련")
        elif any(keyword in combined for keyword in ["fruit", "과일", "채소", "vegetable"]):
            score += 0.15
            reasons.append("원예 작물 관련")

        distance = self.calc_region_distance(signal)
        if distance in {"same_province", "same_city"}:
            score += 0.3
            reasons.append(f"{farm_profile.get('farm_location') or getattr(self.config, 'farm_location', '')} 인근")
        elif distance == "overseas_similar":
            score += 0.1
            reasons.append("해외 사례지만 참고할 만함")

        if self.environment_matches(signal, latest_sensor):
            score += 0.2
            reasons.append("현재 환경 조건과 유사")

        if self.growth_stage_relevant(signal, current_stage):
            score += 0.1
            reasons.append("현재 생육 단계와 맞음")

        urgency = self.classify_urgency(signal, score)
        reason = " + ".join(reasons) if reasons else "관련성 낮음"
        return RelevanceScore(score=min(score, 1.0), urgency=urgency, reason=reason)
