from __future__ import annotations

import webbrowser
from dataclasses import dataclass, field
from threading import Thread
from typing import Any
from urllib.parse import quote

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover
    pystray = None
    Image = None
    ImageDraw = None


@dataclass(slots=True)
class TrayController:
    config: Any
    translator: Any
    icon: Any = field(default=None, init=False)
    status: str = field(default="normal", init=False)
    thread: Thread | None = field(default=None, init=False)

    def _icon_image(self, color: str):
        image = Image.new("RGB", (64, 64), color="white")
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 56, 56), fill=color, outline="black")
        draw.rectangle((20, 16, 44, 48), fill="#3aa655")
        return image

    def _color(self) -> str:
        return {"normal": "#2f9e44", "warning": "#f59f00", "critical": "#e03131"}.get(self.status, "#2f9e44")

    def update_status(self, status: str) -> None:
        self.status = status
        if self.icon is not None and Image is not None:
            self.icon.icon = self._icon_image(self._color())

    def start(self) -> bool:
        if pystray is None or Image is None:
            return False

        def open_dashboard(icon=None, item=None):  # noqa: ARG001
            token = quote(self.config.dashboard_access_token or "", safe="")
            suffix = f"?access_token={token}" if token else ""
            webbrowser.open(f"{self.config.dashboard_url}{suffix}")

        def open_settings(icon=None, item=None):  # noqa: ARG001
            token = quote(self.config.dashboard_access_token or "", safe="")
            suffix = f"?access_token={token}" if token else ""
            webbrowser.open(f"{self.config.dashboard_url}/settings{suffix}")

        menu = pystray.Menu(
            pystray.MenuItem(self.translator.t("tray.open_dashboard"), open_dashboard),
            pystray.MenuItem(self.translator.t("tray.settings"), open_settings),
            pystray.MenuItem(self.translator.t("tray.quit"), lambda icon, item: icon.stop()),
        )
        self.icon = pystray.Icon("berry-doctor", self._icon_image(self._color()), self.translator.t("app.name"), menu)
        self.thread = Thread(target=self.icon.run, daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        if self.icon is not None:
            self.icon.stop()
