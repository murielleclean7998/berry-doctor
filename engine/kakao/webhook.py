from __future__ import annotations

import base64
from dataclasses import dataclass, field
from threading import Thread
from typing import Any

import httpx
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from engine.kakao.commands import parse_command


@dataclass(slots=True)
class KakaoWebhookServer:
    config: Any
    coach: Any
    sender: Any
    app: Flask = field(init=False)
    server: Any = field(default=None, init=False)
    thread: Thread | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        app = Flask("berry-doctor-kakao")

        @app.get("/health")
        def health():
            return jsonify({"ok": True})

        @app.post("/kakao/webhook")
        def webhook():
            payload = request.get_json(silent=True) or {}
            text = payload.get("text") or payload.get("message") or ""
            intent = parse_command(text, payload)
            image_bytes = self._extract_image_bytes(payload)
            message = self.handle_intent(intent, image_bytes)
            return jsonify({"ok": True, "text": message})

        self.app = app

    def _extract_image_bytes(self, payload: dict[str, Any]) -> bytes | None:
        if "image_bytes" in payload:
            return base64.b64decode(payload["image_bytes"])
        image_url = payload.get("image_url")
        if image_url:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(image_url)
                response.raise_for_status()
                return response.content
        if "image" in request.files:
            return request.files["image"].read()
        return None

    def handle_intent(self, intent, image_bytes: bytes | None = None) -> str:
        if intent.name == "status":
            return self.coach.build_status()
        if intent.name == "house_status":
            return self.coach.build_status(intent.house_id)
        if intent.name in {"fan_on", "fan_on_house", "curtain_close", "light_on", "water_on", "photo", "set_target_temp"}:
            return self.coach.control_unavailable()
        if intent.name == "today_tasks":
            return self.coach.build_today_tasks()
        if intent.name == "market":
            return self.coach.build_market_message()
        if intent.name == "shipment":
            return self.coach.build_shipment_message()
        if intent.name == "subsidy":
            return self.coach.build_subsidy_message()
        if intent.name == "record_spray" and intent.text_arg:
            return self.coach.record_spray(intent.text_arg)
        if intent.name == "record_harvest" and intent.value is not None:
            return self.coach.record_harvest(intent.value)
        if intent.name == "report":
            return self.coach.build_daily_report()
        if intent.name == "help":
            return self.coach.translator.t("messages.help_body")
        if intent.name == "diagnosis" and image_bytes:
            return self.coach.build_diagnosis_message(image_bytes)
        if intent.name == "note" and intent.raw_text:
            return self.coach.record_note(intent.raw_text)
        return self.coach.translator.t("messages.unknown_command")

    def start(self) -> None:
        self.server = make_server(self.config.webhook_host, self.config.webhook_port, self.app)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
