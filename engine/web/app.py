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


def create_app(repository, coach, config, config_manager, backup_service, runtime_reload_callback=None) -> Any:
    if FastAPI is None or Jinja2Templates is None:
        return None
    from engine.web.routes import register_routes

    app = FastAPI(title="BerryDoctor Dashboard")
    templates = Jinja2Templates(directory=str(Path(app_root() / "engine" / "web" / "templates")))
    register_routes(app, templates, repository, coach, config, config_manager, backup_service, runtime_reload_callback)
    return app


@dataclass(slots=True)
class DashboardServer:
    config: Any
    repository: Any
    coach: Any
    config_manager: Any
    backup_service: Any
    runtime_reload_callback: Any = None
    app: Any = field(default=None, init=False)
    server: Any = field(default=None, init=False)
    thread: Thread | None = field(default=None, init=False)

    def start(self) -> bool:
        if uvicorn is None:
            return False
        self.app = create_app(
            self.repository,
            self.coach,
            self.config,
            self.config_manager,
            self.backup_service,
            self.runtime_reload_callback,
        )
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
