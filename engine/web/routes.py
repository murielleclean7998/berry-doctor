from __future__ import annotations

import secrets
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from engine.config import sync_app_config
from engine.crop_profile import crop_options, load_crop_profile
from engine.security import generate_token


SESSION_COOKIE = "berry_dashboard_token"
CSRF_COOKIE = "berry_dashboard_csrf"


def register_routes(app: FastAPI, templates: Jinja2Templates, repository, coach, config, config_manager, backup_service, runtime_reload_callback=None) -> None:
    crop_catalog = {
        crop_type: {
            "label": profile.crop_name_ko,
            "varieties": profile.varieties,
            "default_variety": profile.default_variety,
        }
        for crop_type, _crop_name in crop_options()
        for profile in [load_crop_profile(crop_type)]
    }

    def _template_response(request: Request, name: str, context: dict[str, object], status_code: int = 200):
        return templates.TemplateResponse(request, name, context, status_code=status_code)

    def _token_matches(token: str | None) -> bool:
        expected = config.dashboard_access_token
        return bool(expected and token and secrets.compare_digest(token, expected))

    def _request_token(request: Request) -> str | None:
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            return authorization.removeprefix("Bearer ").strip()
        return (
            request.cookies.get(SESSION_COOKIE)
            or request.headers.get("X-Dashboard-Token")
            or request.query_params.get("access_token")
        )

    def _persist_session_if_needed(request: Request, response):
        query_token = request.query_params.get("access_token")
        if _token_matches(query_token):
            response.set_cookie(SESSION_COOKIE, query_token, httponly=True, samesite="lax", max_age=60 * 60 * 12)
        return response

    def _csrf_cookie_value(request: Request) -> str:
        return request.cookies.get(CSRF_COOKIE) or generate_token(12)

    def _persist_csrf_cookie(request: Request, response):
        token = _csrf_cookie_value(request)
        response.set_cookie(CSRF_COOKIE, token, httponly=False, samesite="lax", max_age=60 * 60 * 12)
        return response

    def _finalize_response(request: Request, response):
        _persist_session_if_needed(request, response)
        _persist_csrf_cookie(request, response)
        return response

    def _authorized(request: Request) -> bool:
        if not config.dashboard_require_auth or not config.dashboard_access_token:
            return True
        return _token_matches(_request_token(request))

    def _reject(request: Request, api: bool = False):
        if api:
            return JSONResponse({"ok": False, "error": "dashboard_auth_required"}, status_code=401)
        next_path = request.url.path
        if request.url.query:
            next_path = f"{next_path}?{request.url.query}"
        return RedirectResponse(f"/login?next={quote(next_path, safe='/%?=&')}", status_code=303)

    def _sync_runtime_config() -> None:
        if runtime_reload_callback is not None:
            runtime_reload_callback()
            return
        updated = config_manager.load()
        sync_app_config(config, updated)
        if getattr(coach, "config", None) is not None:
            sync_app_config(coach.config, updated)
        if getattr(coach, "weather_service", None) is not None:
            sync_app_config(coach.weather_service.config, updated)
        if getattr(coach, "market_service", None) is not None:
            sync_app_config(coach.market_service.config, updated)
        backup_service.retention_count = config.backup_retention_count

    @app.get("/login", response_class=HTMLResponse)
    async def login(request: Request, next: str = "/"):  # noqa: A002
        token = request.query_params.get("access_token")
        if _token_matches(token):
            response = RedirectResponse(next if next.startswith("/") else "/", status_code=303)
            response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 12)
            return response
        if _authorized(request):
            return RedirectResponse("/", status_code=303)
        return _template_response(
            request,
            "login.html",
            {"request": request, "next": next if next.startswith("/") else "/", "error": None, "csrf_token": _csrf_cookie_value(request)},
        )

    @app.post("/login", response_class=HTMLResponse)
    async def login_submit(request: Request):
        form = await request.form()
        token = str(form.get("access_token") or "").strip()
        next_path = str(form.get("next") or "/").strip()
        if _token_matches(token):
            response = RedirectResponse(next_path if next_path.startswith("/") else "/", status_code=303)
            response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 12)
            return response
        return _template_response(
            request,
            "login.html",
            {
                "request": request,
                "next": next_path if next_path.startswith("/") else "/",
                "error": "접근 토큰이 올바르지 않습니다.",
                "csrf_token": _csrf_cookie_value(request),
            },
            status_code=401,
        )

    @app.get("/logout")
    async def logout():
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(SESSION_COOKIE)
        return response

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        rejected = _reject(request) if not _authorized(request) else None
        if rejected:
            return rejected
        response = _template_response(
            request,
            "dashboard.html",
            {
                "request": request,
                "status_text": coach.build_status(),
                "alerts": repository.recent_alerts(10),
                "sensor": repository.latest_sensor_snapshot(),
                "sensor_history": list(reversed(repository.sensor_history(24))),
                "controls": repository.recent_control_actions(12),
                "market": coach.market_service.latest(),
                "yield_summary": coach.yield_summary(),
                "community": repository.recent_community_insights(6),
                "pilot_feedback": repository.recent_pilot_feedback(6),
                "monthly_report": repository.latest_monthly_report(),
                "dashboard_url": config.dashboard_url,
                "backups": backup_service.list_backups(5),
                "auth_enabled": config.dashboard_require_auth,
                "csrf_token": _csrf_cookie_value(request),
            },
        )
        return _finalize_response(request, response)

    @app.get("/history", response_class=HTMLResponse)
    async def history(request: Request):
        rejected = _reject(request) if not _authorized(request) else None
        if rejected:
            return rejected
        response = _template_response(
            request,
            "history.html",
            {
                "request": request,
                "alerts": repository.recent_alerts(30),
                "sprays": repository.recent_sprays(20),
                "harvests": repository.recent_harvests(20),
                "diagnoses": repository.recent_diagnoses(20),
                "controls": repository.recent_control_actions(20),
                "captures": repository.recent_camera_captures(20),
                "csrf_token": _csrf_cookie_value(request),
            },
        )
        return _finalize_response(request, response)

    @app.get("/settings", response_class=HTMLResponse)
    async def settings(request: Request, saved: int = 0):
        rejected = _reject(request) if not _authorized(request) else None
        if rejected:
            return rejected
        response = _template_response(
            request,
            "settings.html",
            {
                "request": request,
                "config_view": config_manager.settings_view(),
                "config": config,
                "profiles": sorted(config_manager.profiles.keys()),
                "crop_options": crop_options(),
                "crop_catalog": crop_catalog,
                "saved": bool(saved),
                "backups": backup_service.list_backups(10),
                "csrf_token": _csrf_cookie_value(request),
            },
        )
        return _finalize_response(request, response)

    @app.post("/settings")
    async def update_settings(request: Request):
        rejected = _reject(request) if not _authorized(request) else None
        if rejected:
            return rejected
        form = await request.form()
        csrf_token = str(form.get("csrf_token") or "")
        if csrf_token != request.cookies.get(CSRF_COOKIE):
            return JSONResponse({"ok": False, "error": "csrf_invalid"}, status_code=403)
        config_manager.update_settings(
            {
                "farm_location": form.get("farm_location"),
                "house_count": form.get("house_count"),
                "variety": form.get("variety"),
                "crop_type": form.get("crop_type"),
                "cultivation_type": form.get("cultivation_type"),
                "wifi_ssid": form.get("wifi_ssid"),
                "wifi_password": form.get("wifi_password"),
                "webhook_host": form.get("webhook_host"),
                "webhook_port": form.get("webhook_port"),
                "dashboard_host": form.get("dashboard_host"),
                "dashboard_port": form.get("dashboard_port"),
                "kakao_api_url": form.get("kakao_api_url"),
                "kakao_access_token": form.get("kakao_access_token"),
                "kakao_channel_id": form.get("kakao_channel_id"),
                "kma_api_key": form.get("kma_api_key"),
                "farmmap_api_key": form.get("farmmap_api_key"),
                "market_api_key": form.get("market_api_key"),
                "local_llm_model_path": form.get("local_llm_model_path"),
                "webhook_signature_secret": form.get("webhook_signature_secret"),
                "dashboard_access_token": form.get("dashboard_access_token"),
                "backup_retention_count": form.get("backup_retention_count"),
                "sensor_log_interval_seconds": form.get("sensor_log_interval_seconds"),
                "control_dedupe_window_seconds": form.get("control_dedupe_window_seconds"),
                "alert_dedupe_window_seconds": form.get("alert_dedupe_window_seconds"),
                "community_insight_dedupe_window_seconds": form.get("community_insight_dedupe_window_seconds"),
                "raw_sensor_retention_days": form.get("raw_sensor_retention_days"),
                "aggregate_sensor_retention_days": form.get("aggregate_sensor_retention_days"),
                "mock_mode": form.get("mock_mode") == "on",
                "dashboard_require_auth": form.get("dashboard_require_auth") == "on",
            }
        )
        _sync_runtime_config()
        response = RedirectResponse("/settings?saved=1", status_code=303)
        response.set_cookie(SESSION_COOKIE, config.dashboard_access_token, httponly=True, samesite="lax", max_age=60 * 60 * 12)
        return _persist_csrf_cookie(request, response)

    @app.post("/settings/backup")
    async def create_backup(request: Request):
        rejected = _reject(request) if not _authorized(request) else None
        if rejected:
            return rejected
        form = await request.form()
        csrf_token = str(form.get("csrf_token") or "")
        if csrf_token != request.cookies.get(CSRF_COOKIE):
            return JSONResponse({"ok": False, "error": "csrf_invalid"}, status_code=403)
        backup_service.create_backup()
        return RedirectResponse("/settings?saved=1", status_code=303)

    @app.get("/diary", response_class=HTMLResponse)
    async def diary(request: Request):
        rejected = _reject(request) if not _authorized(request) else None
        if rejected:
            return rejected
        response = _template_response(
            request,
            "diary.html",
            {"request": request, "entries": repository.recent_diary(30), "csrf_token": _csrf_cookie_value(request)},
        )
        return _finalize_response(request, response)

    @app.get("/community", response_class=HTMLResponse)
    async def community(request: Request, saved: int = 0):
        rejected = _reject(request) if not _authorized(request) else None
        if rejected:
            return rejected
        response = _template_response(
            request,
            "community.html",
            {
                "request": request,
                "items": repository.recent_community_insights(20),
                "saved": bool(saved),
                "csrf_token": _csrf_cookie_value(request),
            },
        )
        return _finalize_response(request, response)

    @app.post("/community")
    async def create_community_item(request: Request):
        rejected = _reject(request) if not _authorized(request) else None
        if rejected:
            return rejected
        form = await request.form()
        csrf_token = str(form.get("csrf_token") or "")
        if csrf_token != request.cookies.get(CSRF_COOKIE):
            return JSONResponse({"ok": False, "error": "csrf_invalid"}, status_code=403)
        tags = [item.strip() for item in str(form.get("tags") or "").split(",") if item.strip()]
        repository.record_community_insight(
            title=str(form.get("title") or "현장 인사이트").strip(),
            summary=str(form.get("summary") or "").strip(),
            tags=tags,
            source_site=str(form.get("source_site") or "manual").strip() or "manual",
            payload={"entered_from": "dashboard"},
        )
        return RedirectResponse("/community?saved=1", status_code=303)

    @app.get("/pilot", response_class=HTMLResponse)
    async def pilot(request: Request, saved: int = 0):
        rejected = _reject(request) if not _authorized(request) else None
        if rejected:
            return rejected
        response = _template_response(
            request,
            "pilot.html",
            {
                "request": request,
                "items": repository.recent_pilot_feedback(20),
                "saved": bool(saved),
                "csrf_token": _csrf_cookie_value(request),
            },
        )
        return _finalize_response(request, response)

    @app.post("/pilot")
    async def create_pilot_feedback(request: Request):
        rejected = _reject(request) if not _authorized(request) else None
        if rejected:
            return rejected
        form = await request.form()
        csrf_token = str(form.get("csrf_token") or "")
        if csrf_token != request.cookies.get(CSRF_COOKIE):
            return JSONResponse({"ok": False, "error": "csrf_invalid"}, status_code=403)
        repository.record_pilot_feedback(
            site_name=str(form.get("site_name") or "Pilot").strip() or "Pilot",
            category=str(form.get("category") or "operations").strip() or "operations",
            sentiment=str(form.get("sentiment") or "neutral").strip() or "neutral",
            feedback=str(form.get("feedback") or "").strip(),
            status=str(form.get("status") or "open").strip() or "open",
            action_item=str(form.get("action_item") or "").strip() or None,
        )
        return RedirectResponse("/pilot?saved=1", status_code=303)

    @app.get("/api/status", response_class=JSONResponse)
    async def api_status(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        return {
            "weather": coach.weather_service.latest(),
            "market": coach.market_service.latest(),
            "alerts": repository.recent_alerts(5),
            "sensor": repository.latest_sensor_snapshot(),
            "controls": repository.recent_control_actions(5),
            "yield_summary": coach.yield_summary(),
            "monthly_report": repository.latest_monthly_report(),
            "backups": backup_service.list_backups(3),
        }

    @app.get("/api/sensors/history", response_class=JSONResponse)
    async def api_sensor_history(request: Request, limit: int = 48):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        return {"items": repository.sensor_history(limit)}

    @app.get("/api/records/spray", response_class=JSONResponse)
    async def api_sprays(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        return {"items": repository.recent_sprays(30)}

    @app.get("/api/records/harvest", response_class=JSONResponse)
    async def api_harvests(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        return {"items": repository.recent_harvests(30)}

    @app.get("/api/records/diagnosis", response_class=JSONResponse)
    async def api_diagnoses(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        return {"items": repository.recent_diagnoses(30)}

    @app.get("/api/control/actions", response_class=JSONResponse)
    async def api_controls(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        return {"items": repository.recent_control_actions(30)}

    @app.get("/api/community", response_class=JSONResponse)
    async def api_community(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        return {"items": repository.recent_community_insights(30)}

    @app.post("/api/community", response_class=JSONResponse)
    async def api_create_community(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        payload = await request.json()
        csrf_token = request.headers.get("X-CSRF-Token") or str(payload.get("csrf_token") or "")
        if csrf_token != request.cookies.get(CSRF_COOKIE):
            return JSONResponse({"ok": False, "error": "csrf_invalid"}, status_code=403)
        repository.record_community_insight(
            title=str(payload.get("title") or "현장 인사이트").strip(),
            summary=str(payload.get("summary") or "").strip(),
            tags=list(payload.get("tags") or []),
            source_site=str(payload.get("source_site") or "api").strip() or "api",
            payload={"entered_from": "api"},
        )
        return {"ok": True}

    @app.get("/api/pilot", response_class=JSONResponse)
    async def api_pilot(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        return {"items": repository.recent_pilot_feedback(30)}

    @app.post("/api/pilot", response_class=JSONResponse)
    async def api_create_pilot(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        payload = await request.json()
        csrf_token = request.headers.get("X-CSRF-Token") or str(payload.get("csrf_token") or "")
        if csrf_token != request.cookies.get(CSRF_COOKIE):
            return JSONResponse({"ok": False, "error": "csrf_invalid"}, status_code=403)
        repository.record_pilot_feedback(
            site_name=str(payload.get("site_name") or "Pilot").strip() or "Pilot",
            category=str(payload.get("category") or "operations").strip() or "operations",
            sentiment=str(payload.get("sentiment") or "neutral").strip() or "neutral",
            feedback=str(payload.get("feedback") or "").strip(),
            status=str(payload.get("status") or "open").strip() or "open",
            action_item=str(payload.get("action_item") or "").strip() or None,
        )
        return {"ok": True}

    @app.get("/api/settings", response_class=JSONResponse)
    async def api_settings(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        return {"items": config_manager.settings_view()}

    @app.get("/api/backups", response_class=JSONResponse)
    async def api_backups(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        return {"items": backup_service.list_backups(20)}

    @app.post("/api/backups/create", response_class=JSONResponse)
    async def api_create_backup(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        csrf_token = request.headers.get("X-CSRF-Token") or request.query_params.get("csrf_token") or ""
        if csrf_token != request.cookies.get(CSRF_COOKIE):
            return JSONResponse({"ok": False, "error": "csrf_invalid"}, status_code=403)
        target = backup_service.create_backup()
        return {"ok": True, "path": str(target)}

    @app.get("/api/backups/latest")
    async def api_download_latest_backup(request: Request):
        rejected = _reject(request, api=True) if not _authorized(request) else None
        if rejected:
            return rejected
        latest = backup_service.latest_backup()
        if latest is None or not latest.exists():
            return JSONResponse({"ok": False, "error": "backup_not_found"}, status_code=404)
        return FileResponse(Path(latest), filename=latest.name, media_type="application/octet-stream")
