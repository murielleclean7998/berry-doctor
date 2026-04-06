from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from engine.paths import bin_path


@dataclass(slots=True)
class MosquittoBroker:
    host: str = "127.0.0.1"
    port: int = 1883
    process: subprocess.Popen | None = field(default=None, init=False)
    config_path: Path | None = field(default=None, init=False)

    def binary_path(self) -> Path:
        return Path(bin_path("mosquitto", "mosquitto.exe"))

    def is_available(self) -> bool:
        binary = self.binary_path()
        return binary.exists() and binary.stat().st_size > 0

    def write_config(self) -> Path:
        config_path = Path(bin_path("mosquitto", "mosquitto.conf"))
        config_path.write_text(
            "\n".join(
                [
                    f"listener {self.port} {self.host}",
                    "allow_anonymous true",
                    "persistence false",
                    "log_type error",
                    "log_type warning",
                    "log_type notice",
                ]
            ),
            encoding="utf-8",
        )
        self.config_path = config_path
        return config_path

    def start(self) -> bool:
        if self.process and self.process.poll() is None:
            return True
        if not self.is_available():
            return False
        config = self.write_config()
        self.process = subprocess.Popen(
            [str(self.binary_path()), "-c", str(config)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.process = None

    def status(self) -> str:
        if not self.is_available():
            return "missing"
        if self.process and self.process.poll() is None:
            return "running"
        return "stopped"
