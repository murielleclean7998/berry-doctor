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
        (r"^(?P<house>\d+)동 상태$", "house_status"),
        (r"^(?P<house>\d+)동 환풍기 켜$", "fan_on_house"),
        (r"^환풍기 켜$", "fan_on"),
        (r"^커튼 닫아$", "curtain_close"),
        (r"^보광 켜$", "light_on"),
        (r"^물 줘$", "water_on"),
        (r"^사진$", "photo"),
        (r"^진단$", "diagnosis"),
        (r"^상태$|^전체 상태$", "status"),
        (r"^오늘 할일$", "today_tasks"),
        (r"^시세$", "market"),
        (r"^출하$", "shipment"),
        (r"^보조금$", "subsidy"),
        (r"^리포트$", "report"),
        (r"^도움말$", "help"),
        (r"^목표온도\s*(?P<value>-?\d+(\.\d+)?)$", "set_target_temp"),
        (r"^기록 농약\s+(?P<text>.+)$", "record_spray"),
        (r"^기록 수확\s+(?P<value>\d+(\.\d+)?)kg$", "record_harvest"),
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
