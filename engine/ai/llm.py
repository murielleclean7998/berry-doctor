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
    knowledge: dict[str, Any] = field(init=False)
    tips: list[dict[str, Any]] = field(init=False)
    model: Any = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.knowledge = json.loads(Path(data_path("knowledge_graph.json")).read_text(encoding="utf-8"))
        self.tips = json.loads(Path(data_path("farmer_tips.json")).read_text(encoding="utf-8"))["tips"]
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
            "당신은 딸기 재배를 돕는 로컬 농업 어시스턴트입니다.\n"
            f"질문: {question}\n"
            f"현재 문맥: {json.dumps(context, ensure_ascii=False)}\n"
            "짧고 실행 가능한 답변을 한국어로 작성하세요."
        )

    def _fallback_answer(self, question: str, context: dict[str, Any]) -> str:
        lowered = question.lower()
        relevant_tips = []
        for tip in self.tips:
            haystack = " ".join(str(value) for value in tip.values()).lower()
            if any(token in haystack for token in lowered.split()):
                relevant_tips.append(tip["tip"])
        weather = context.get("weather", {})
        market = context.get("market", {})
        stage = context.get("stage", {})
        lead = f"현재 생육 단계는 {stage.get('label', '확인 중')}이고, 기상은 {weather.get('summary', '정보 없음')}입니다."
        market_line = f"최근 시세는 {market.get('price_per_kg', '미확인')}원/kg 수준입니다."
        tip_line = relevant_tips[0] if relevant_tips else "지금은 하우스 순회와 병든 과실 제거, 습도 관리부터 확인하는 것이 안전합니다."
        return f"{lead}\n{market_line}\n권장 답변: {tip_line}"
