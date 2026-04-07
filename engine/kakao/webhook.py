from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from pathlib import Path
from threading import Thread
from typing import Any

import httpx
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from engine.kakao.commands import parse_command
from engine.security import verify_hmac_signature

logger = logging.getLogger(__name__)


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
            raw_body = request.get_data(cache=True)
            if not self._authorized_request(raw_body):
                return jsonify({"ok": False, "error": "invalid_signature"}), 401
            payload = request.get_json(silent=True) or {}
            text = payload.get("text") or payload.get("message") or ""
            intent = parse_command(text, payload)
            try:
                image_bytes, image_name = self._extract_image_payload(payload)
                message = self.handle_intent(intent, image_bytes=image_bytes, image_name=image_name)
            except Exception:
                logger.exception("Failed to process Kakao webhook payload.")
                message = self.coach.translator.get(
                    "messages.webhook_error",
                    "\uc694\uccad\uc744 \ucc98\ub9ac\ud558\ub294 \ub3d9\uc548 \uc624\ub958\uac00 \ub0ac\uc5b4\uc694. \uc7a0\uc2dc \ud6c4 \ub2e4\uc2dc \uc2dc\ub3c4\ud574 \uc8fc\uc138\uc694.",
                )
            return jsonify({"ok": True, "text": message})

        self.app = app

    def _authorized_request(self, raw_body: bytes) -> bool:
        secret = str(getattr(self.config, "webhook_signature_secret", "") or "").strip()
        if not secret:
            return True
        for header_name in ("X-Kakao-Signature", "X-BerryDoctor-Signature", "X-Signature-256"):
            provided = request.headers.get(header_name)
            if verify_hmac_signature(raw_body, secret, provided):
                return True
        logger.warning("Rejected webhook request due to missing or invalid signature.")
        return False

    def _extract_image_payload(self, payload: dict[str, Any]) -> tuple[bytes | None, str | None]:
        if "image_bytes" in payload:
            try:
                return base64.b64decode(payload["image_bytes"]), str(payload.get("image_name") or "upload.jpg")
            except Exception:
                logger.warning("Invalid base64 image payload received from Kakao webhook.")
                return None, str(payload.get("image_name") or "upload.jpg")

        image_url = payload.get("image_url")
        if image_url:
            try:
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(image_url)
                    response.raise_for_status()
                return response.content, str(payload.get("image_name") or Path(image_url).name or "download.jpg")
            except httpx.HTTPError as exc:
                logger.warning("Failed to download webhook image from %s: %s", image_url, exc)
                return None, str(payload.get("image_name") or "download.jpg")

        if "image" in request.files:
            uploaded = request.files["image"]
            return uploaded.read(), uploaded.filename or "upload.jpg"

        return None, None

    def handle_intent(self, intent, image_bytes: bytes | None = None, image_name: str | None = None) -> str:
        if intent.name == "status":
            return self.coach.build_status()
        if intent.name == "house_status":
            return self.coach.build_status(intent.house_id)
        if intent.name == "fan_on":
            return self.coach.turn_on_fan(1)
        if intent.name == "fan_on_house":
            return self.coach.turn_on_fan(intent.house_id or 1)
        if intent.name == "curtain_close":
            return self.coach.close_curtain(1)
        if intent.name == "curtain_close_house":
            return self.coach.close_curtain(intent.house_id or 1)
        if intent.name == "light_on":
            return self.coach.turn_on_light(1)
        if intent.name == "light_on_house":
            return self.coach.turn_on_light(intent.house_id or 1)
        if intent.name == "water_on":
            return self.coach.water_now(1)
        if intent.name == "water_on_house":
            return self.coach.water_now(intent.house_id or 1)
        if intent.name == "photo":
            return self.coach.control_unavailable()
        if intent.name == "today_tasks":
            return self.coach.build_today_tasks()
        if intent.name == "market":
            return self.coach.build_market_message()
        if intent.name == "shipment":
            return self.coach.build_shipment_message(intent.house_id)
        if intent.name == "subsidy":
            return self.coach.build_subsidy_message()
        if intent.name == "record_spray" and intent.text_arg:
            return self.coach.record_spray(intent.text_arg, house_id=intent.house_id)
        if intent.name == "record_harvest" and intent.value is not None:
            return self.coach.record_harvest(intent.value, house_id=intent.house_id)
        if intent.name == "set_target_temp" and intent.value is not None:
            return self.coach.set_target_temp(intent.value, house_id=intent.house_id or 1)
        if intent.name == "report":
            return self.coach.build_daily_report()
        if intent.name == "timeline":
            return self.coach.build_timeline_message(intent.house_id or 1)
        if intent.name == "year_compare":
            return self.coach.build_year_compare_message(intent.house_id or 1)
        if intent.name == "security_history":
            return self.coach.build_security_history_message()
        if intent.name == "help":
            return self.coach.translator.t("messages.help_body")
        if intent.name == "diagnosis":
            if image_bytes:
                return self.coach.build_diagnosis_message(image_bytes, filename=image_name or "upload.jpg", house_id=intent.house_id)
            return self.coach.translator.get(
                "messages.image_download_failed",
                "\uc0ac\uc9c4\uc744 \ub2e4\uc2dc \ubcf4\ub0b4\uc8fc\uc138\uc694. \uc774\ubbf8\uc9c0 \ub2e4\uc6b4\ub85c\ub4dc \ub610\ub294 \uc77d\uae30\uc5d0 \uc2e4\ud328\ud588\uc5b4\uc694.",
            )
        if intent.name == "note" and intent.raw_text:
            return self.coach.answer_or_record(intent.raw_text)
        return self.coach.translator.t("messages.unknown_command")

    def start(self) -> None:
        self.server = make_server(self.config.webhook_host, self.config.webhook_port, self.app)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
