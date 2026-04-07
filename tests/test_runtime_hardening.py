import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from engine.backup import BackupService
from engine.config import ConfigManager
from engine.control.greenhouse import ControlActionProposal, GreenhouseController
from engine.db.sqlite import SQLiteRepository
from engine.i18n import Translator
from engine.setup_wizard import SetupResult
from engine.web.app import create_app


class _DummyService:
    def __init__(self, payload):
        self.payload = payload
        self.config = None

    def latest(self):
        return self.payload


class _DummyCoach:
    def __init__(self):
        self.market_service = _DummyService({"price_per_kg": 8200, "change": "+0", "forecast": {"expected_peak_price": 8400}})
        self.weather_service = _DummyService({"current_temp": 20, "current_humidity": 70, "summary": "clear"})
        self.config = None

    def build_status(self, house_id=None):  # noqa: ARG002
        return "ok"

    def yield_summary(self):
        return {"monthly_total_kg": 10, "projected_month_kg": 20, "projected_revenue": 150000}


class _FakeMQTTClient:
    def __init__(self):
        self.client = object()
        self.published = []

    def publish(self, topic, payload):
        self.published.append((topic, payload))


class RuntimeHardeningTests(unittest.TestCase):
    def test_sensor_latest_and_minute_aggregate_are_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            base_time = datetime(2026, 4, 7, 9, 30, 5, tzinfo=UTC)

            repo.upsert_latest_sensor_snapshot({"house_id": 1, "temp_indoor": 21.0, "humidity": 80.0})
            repo.record_sensor_minute_aggregate({"house_id": 1, "temp_indoor": 21.0, "humidity": 80.0}, timestamp=base_time)
            repo.upsert_latest_sensor_snapshot({"house_id": 1, "temp_indoor": 23.0, "humidity": 90.0})
            repo.record_sensor_minute_aggregate({"house_id": 1, "temp_indoor": 23.0, "humidity": 90.0}, timestamp=base_time)

            latest = repo.latest_sensor_snapshot(1)
            history = repo.sensor_history(limit=5, house_id=1)

            self.assertEqual(latest["temp_indoor"], 23.0)
            self.assertEqual(latest["humidity"], 90.0)
            self.assertEqual(history[0]["sample_count"], 2)
            self.assertAlmostEqual(history[0]["temp_indoor"], 22.0)
            self.assertAlmostEqual(history[0]["humidity"], 85.0)

    def test_greenhouse_controller_skips_duplicate_auto_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            mqtt_client = _FakeMQTTClient()
            controller = GreenhouseController(repo, mqtt_client, dedupe_window_seconds=120)
            proposal = ControlActionProposal(
                house_id=1,
                device="ventilation",
                action="on",
                mode="auto",
                reason="humid",
                payload={"duration_minutes": 15},
            )

            first = controller.publish_action(proposal)
            second = controller.publish_action(proposal)
            actions = repo.recent_control_actions(10)

            self.assertEqual(first["result"], "published")
            self.assertEqual(second["result"], "skipped_duplicate")
            self.assertEqual(len(actions), 1)
            self.assertEqual(len(mqtt_client.published), 1)

    def test_community_insight_dedupe_and_sensor_indexes_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()

            first = repo.record_community_insight(
                title="house-1 auto control",
                summary="ventilation:on",
                tags=["control", "phase2"],
                source_site="house-1",
                payload={"house_id": 1},
                dedupe_window_seconds=1800,
            )
            second = repo.record_community_insight(
                title="house-1 auto control",
                summary="ventilation:on",
                tags=["control", "phase2"],
                source_site="house-1",
                payload={"house_id": 1},
                dedupe_window_seconds=1800,
            )

            insights = repo.recent_community_insights(10)
            with repo.connect() as conn:
                sensor_indexes = {row["name"] for row in conn.execute("PRAGMA index_list(sensor_log)").fetchall()}
                minute_indexes = {row["name"] for row in conn.execute("PRAGMA index_list(sensor_minute_log)").fetchall()}

            self.assertEqual(first, second)
            self.assertEqual(len(insights), 1)
            self.assertIn("idx_sensor_log_house_timestamp", sensor_indexes)
            self.assertIn("idx_sensor_minute_log_house_bucket", minute_indexes)

    def test_dashboard_post_requires_csrf(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            manager = ConfigManager(repo)
            manager.save_setup(
                SetupResult(
                    farm_location="논산시",
                    house_count=3,
                    variety="설향",
                    cultivation_type="토경",
                    wifi_ssid="farm-net",
                    wifi_password="pw",
                )
            )
            manager.ensure_runtime_defaults()
            config = manager.load()
            coach = _DummyCoach()
            coach.config = config
            coach.market_service.config = config
            coach.weather_service.config = config
            app = create_app(repo, coach, config, manager, BackupService(repo), runtime_reload_callback=None)
            client = TestClient(app)

            page = client.get(f"/settings?access_token={config.dashboard_access_token}")
            csrf_token = client.cookies.get("berry_dashboard_csrf")
            self.assertEqual(page.status_code, 200)
            self.assertTrue(csrf_token)

            rejected = client.post("/community", data={"title": "x", "summary": "y"}, follow_redirects=False)
            accepted = client.post(
                "/community",
                data={"title": "x", "summary": "y", "csrf_token": csrf_token},
                follow_redirects=False,
            )

            self.assertEqual(rejected.status_code, 403)
            self.assertEqual(accepted.status_code, 303)


if __name__ == "__main__":
    unittest.main()
