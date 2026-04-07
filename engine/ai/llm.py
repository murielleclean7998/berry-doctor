from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.paths import data_path

try:
    from llama_cpp import Llama
except Exception:  # pragma: no cover
    Llama = None


@dataclass(slots=True)
class LocalAgronomyAssistant:
    config: Any
    knowledge_path: Path | str | None = None
    tips_path: Path | str | None = None
    crop_name_ko: str = "딸기"
    knowledge: dict[str, Any] = field(init=False)
    tips: list[dict[str, Any]] = field(init=False)
    model: Any = field(default=None, init=False)

    def __post_init__(self) -> None:
        knowledge_path = Path(self.knowledge_path or data_path("knowledge_graph.json"))
        tips_path = Path(self.tips_path or data_path("farmer_tips.json"))
        self.knowledge = json.loads(knowledge_path.read_text(encoding="utf-8"))
        self.tips = json.loads(tips_path.read_text(encoding="utf-8")).get("tips", [])
        self.model = self._load_model()

    def _load_model(self):
        model_path = getattr(self.config, "local_llm_model_path", "")
        if not model_path or Llama is None:
            return None
        try:
            return Llama(model_path=model_path, n_ctx=4096, verbose=False)
        except Exception:
            return None

    def answer(self, question: str, context: dict[str, Any]) -> dict[str, Any]:
        if self.model is not None:
            prompt = self._build_prompt(question, context)
            output = self.model.create_completion(prompt=prompt, max_tokens=256, temperature=0.2)
            text = output["choices"][0]["text"].strip()
            return {"mode": "llama_cpp", "text": text}
        return {"mode": "retrieval", "text": self._fallback_answer(question, context)}

    def _build_prompt(self, question: str, context: dict[str, Any]) -> str:
        return (
            f"당신은 {self.crop_name_ko} 재배를 돕는 로컬 농업 어시스턴트입니다.\n"
            f"질문: {question}\n"
            f"현재 문맥: {json.dumps(context, ensure_ascii=False)}\n"
            "지금 바로 실행 가능한 답을 한국어 해요체로 짧고 분명하게 작성해 주세요."
        )

    def _fallback_answer(self, question: str, context: dict[str, Any]) -> str:
        lowered = question.lower()
        relevant_tips: list[str] = []
        for tip in self.tips:
            haystack = " ".join(str(value) for value in tip.values()).lower()
            if any(token in haystack for token in lowered.split()):
                relevant_tips.append(str(tip.get("tip", "")))
        weather = context.get("weather", {})
        market = context.get("market", {})
        stage = context.get("stage", {})
        lead = f"지금 {self.crop_name_ko} 생육 단계는 {stage.get('label', '확인 중')}이고, 날씨는 {weather.get('summary', '정보 없음')} 쪽이에요."
        market_line = f"최근 시세는 {market.get('price_per_kg', '미확인')}원/kg 수준이에요."
        tip_line = relevant_tips[0] if relevant_tips else "당장은 하우스 순회, 병든 잎과 과실 제거, 습도 흐름 확인부터 시작해 주세요."
        return f"{lead}\n{market_line}\n권장 팁: {tip_line}"
