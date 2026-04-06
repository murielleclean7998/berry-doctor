from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.paths import i18n_path


def _lookup(payload: dict[str, Any], dotted_key: str) -> Any:
    current: Any = payload
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted_key)
        current = current[part]
    return current


@dataclass(slots=True)
class Translator:
    locale: str = "ko"
    payload: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.payload is None:
            self.payload = self._load(self.locale)

    @staticmethod
    def _load(locale: str) -> dict[str, Any]:
        path = Path(i18n_path(f"{locale}.json"))
        return json.loads(path.read_text(encoding="utf-8"))

    def t(self, key: str, **kwargs: Any) -> str:
        try:
            value = _lookup(self.payload or {}, key)
        except KeyError:
            return key
        if isinstance(value, str):
            return value.format(**kwargs)
        raise TypeError(f"Translation value for '{key}' must be a string")

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return _lookup(self.payload or {}, key)
        except KeyError:
            return default
