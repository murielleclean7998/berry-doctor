from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class CommandIntent:
    name: str
    raw_text: str
    house_id: int | None = None
    value: float | None = None
    text_arg: str | None = None
    has_image: bool = False


def parse_command(text: str | None, payload: dict[str, Any] | None = None) -> CommandIntent:
    payload = payload or {}
    raw_text = (text or "").strip()
    has_image = bool(payload.get("image_url") or payload.get("image_bytes") or payload.get("has_image"))

    if not raw_text and has_image:
        return CommandIntent(name="diagnosis", raw_text="", has_image=True)

    patterns: list[tuple[str, str]] = [
        (r"^(?P<house>\d+)\s*\ub3d9\s*\uc0c1\ud0dc$", "house_status"),
        (r"^(?P<house>\d+)\s*\ub3d9\s*\ud658\ud48d\uae30\s*\ucf1c$", "fan_on_house"),
        (r"^\ud658\ud48d\uae30\s*\ucf1c$", "fan_on"),
        (r"^\ucee4\ud2bc\s*\ub2eb\uc544$", "curtain_close"),
        (r"^\ubcf4\uad11\ub4f1\s*\ucf1c$", "light_on"),
        (r"^\ubb3c\s*\uc918$", "water_on"),
        (r"^\uc0ac\uc9c4$", "photo"),
        (r"^\uc9c4\ub2e8$", "diagnosis"),
        (r"^\uc0c1\ud0dc$|^\uc804\uccb4\s*\uc0c1\ud0dc$", "status"),
        (r"^\uc624\ub298\s*\ud560\uc77c$", "today_tasks"),
        (r"^\uc2dc\uc138$", "market"),
        (r"^(?:(?P<house>\d+)\s*\ub3d9\s*)?\ucd9c\ud558$", "shipment"),
        (r"^\ubcf4\uc870\uae08$", "subsidy"),
        (r"^\ub9ac\ud3ec\ud2b8$", "report"),
        (r"^\ub3c4\uc6c0\ub9d0$", "help"),
        (r"^\ubaa9\ud45c\uc628\ub3c4\s*(?P<value>-?\d+(\.\d+)?)$", "set_target_temp"),
        (r"^\uae30\ub85d\s*\ub18d\uc57d\s*(?:(?P<house>\d+)\s*\ub3d9\s*)?(?P<text>.+)$", "record_spray"),
        (r"^\uae30\ub85d\s*\uc218\ud655\s*(?:(?P<house>\d+)\s*\ub3d9\s*)?(?P<value>\d+(\.\d+)?)kg$", "record_harvest"),
    ]

    for pattern, name in patterns:
        match = re.match(pattern, raw_text)
        if not match:
            continue
        groups = match.groupdict()
        return CommandIntent(
            name=name,
            raw_text=raw_text,
            house_id=int(groups["house"]) if groups.get("house") else None,
            value=float(groups["value"]) if groups.get("value") else None,
            text_arg=groups.get("text"),
            has_image=has_image,
        )

    if has_image:
        return CommandIntent(name="diagnosis", raw_text=raw_text, has_image=True)
    return CommandIntent(name="note", raw_text=raw_text)
