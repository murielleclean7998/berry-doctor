from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Thread
from typing import Any

try:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.templating import Jinja2Templates
except Exception:  # pragma: no cover
    uvicorn = None
    FastAPI = None
    Jinja2Templates = None

from engine.paths import app_root


def create_app(repository, coach, config) -> Any:
    if FastAPI is None or Jinja2Templates is None:
        return None
    from engine.web.routes import register_routes

    app = FastAPI(title="BerryDoctor Dashboard")
    templates = Jinja2Templates(directory=str(Path(app_root() / "engine" / "web" / "templates")))
    register_routes(app, templates, repository, coach, config)
    return app


@dataclass(slots=True)
class DashboardServer:
    config: Any
    repository: Any
    coach: Any
    app: Any = field(default=None, init=False)
    server: Any = field(default=None, init=False)
    thread: Thread | None = field(default=None, init=False)

    def start(self) -> bool:
        if uvicorn is None:
            return False
        self.app = create_app(self.repository, self.coach, self.config)
        if self.app is None:
            return False
        cfg = uvicorn.Config(
            self.app,
            host=self.config.dashboard_host,
            port=self.config.dashboard_port,
            log_level="warning",
            log_config=None,
            access_log=False,
        )
        self.server = uvicorn.Server(cfg)
        self.thread = Thread(target=self.server.run, daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
