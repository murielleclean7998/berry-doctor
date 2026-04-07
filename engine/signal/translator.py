from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.signal.models import RawSignal


@dataclass(slots=True)
class SignalTranslator:
    config: Any

    def template_summary(self, signal: RawSignal) -> str:
        lead = signal.title.strip()
        body = signal.summary.strip()
        if signal.language == "ko":
            return f"{lead}\n{body}".strip()
        return (
            f"{lead}\n"
            f"해외 자료라 그대로 믿기보다 참고로 보시면 좋아요. "
            f"지금 우리 농장과 비슷한 조건인지 먼저 확인해보세요."
        ).strip()

    def translate_and_summarize(self, signal: RawSignal) -> str:
        return self.template_summary(signal)
