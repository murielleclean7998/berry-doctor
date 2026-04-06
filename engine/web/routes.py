from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates


def register_routes(app: FastAPI, templates: Jinja2Templates, repository, coach, config) -> None:
    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "status_text": coach.build_status(),
                "alerts": repository.recent_alerts(10),
                "dashboard_url": config.dashboard_url,
            },
        )

    @app.get("/history", response_class=HTMLResponse)
    async def history(request: Request):
        return templates.TemplateResponse(
            "history.html",
            {
                "request": request,
                "alerts": repository.recent_alerts(30),
                "sprays": repository.recent_sprays(20),
                "harvests": repository.recent_harvests(20),
                "diagnoses": repository.recent_diagnoses(20),
            },
        )

    @app.get("/settings", response_class=HTMLResponse)
    async def settings(request: Request):
        return templates.TemplateResponse(
            "settings.html",
            {"request": request, "config": repository.all_config()},
        )

    @app.get("/diary", response_class=HTMLResponse)
    async def diary(request: Request):
        with repository.connect() as conn:
            entries = [dict(row) for row in conn.execute("SELECT * FROM farm_diary ORDER BY timestamp DESC LIMIT 20").fetchall()]
        return templates.TemplateResponse(
            "diary.html",
            {"request": request, "entries": entries},
        )

    @app.get("/api/status", response_class=JSONResponse)
    async def api_status():
        return {
            "weather": coach.weather_service.latest(),
            "market": coach.market_service.latest(),
            "alerts": repository.recent_alerts(5),
        }

    @app.get("/api/records/spray", response_class=JSONResponse)
    async def api_sprays():
        return {"items": repository.recent_sprays(30)}

    @app.get("/api/records/harvest", response_class=JSONResponse)
    async def api_harvests():
        return {"items": repository.recent_harvests(30)}

    @app.get("/api/records/diagnosis", response_class=JSONResponse)
    async def api_diagnoses():
        return {"items": repository.recent_diagnoses(30)}
