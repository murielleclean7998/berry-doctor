from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

try:
    import paho.mqtt.client as mqtt
except Exception:  # pragma: no cover - optional dependency during authoring
    mqtt = None


MessageHandler = Callable[[str, bytes], None]


@dataclass(slots=True)
class MQTTClient:
    host: str = "127.0.0.1"
    port: int = 1883
    on_message: MessageHandler | None = None
    client: Any = field(default=None, init=False)

    def connect(self) -> bool:
        if mqtt is None:
            return False
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        def _handle(_client, _userdata, message):
            if self.on_message:
                self.on_message(message.topic, message.payload)

        self.client.on_message = _handle
        self.client.connect_async(self.host, self.port)
        self.client.loop_start()
        return True

    def subscribe(self, topic: str) -> None:
        if self.client is not None:
            self.client.subscribe(topic)

    def publish(self, topic: str, payload: str) -> None:
        if self.client is not None:
            self.client.publish(topic, payload)

    def stop(self) -> None:
        if self.client is not None:
            self.client.loop_stop()
            self.client.disconnect()
