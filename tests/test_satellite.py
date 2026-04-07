import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from engine.db.sqlite import SQLiteRepository
from engine.scheduler.satellite_job import SatelliteJobService
from engine.satellite.indices import calc_ndvi, index_to_grade, mean_value
from engine.satellite.timeline import FarmTimeline


class _FakeSender:
    def __init__(self):
        self.messages = []

    def send_text(self, message, severity="info", house_id=None, rule_id="manual"):  # noqa: ARG002
        self.messages.append(message)
        return {"ok": True}


class _StubClient:
    async def get_latest_image(self, lat, lng, max_cloud_pct=40):  # noqa: ARG002
        return {"tile_id": "S2-test", "capture_date": date(2026, 4, 7), "cloud_pct": 12.0}

    async def download_bands(self, tile_id, bands=None):  # noqa: ARG002
        return {
            "B04": [[0.2, 0.2], [0.2, 0.2]],
            "B08": [[0.6, 0.6], [0.6, 0.6]],
            "B03": [[0.18, 0.18], [0.18, 0.18]],
            "B11": [[0.15, 0.15], [0.15, 0.15]],
            "SCL": [[0, 0], [0, 0]],
        }


class SatelliteTests(unittest.TestCase):
    def test_indices_grade_health(self):
        ndvi = calc_ndvi([[0.2, 0.2]], [[0.6, 0.6]])
        avg = mean_value(ndvi)
        grade = index_to_grade(avg)
        self.assertGreater(avg, 0.4)
        self.assertIn(grade["grade"], {"보통", "좋음"})

    def test_satellite_job_records_observation_and_message(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            repo.upsert_latest_sensor_snapshot({"house_id": 1, "humidity": 88, "soil_moisture_1": 24})
            sender = _FakeSender()
            config = SimpleNamespace(
                farm_location="충남 서산",
                satellite_enabled=True,
                satellite_max_cloud_pct=40,
                field_area_pyeong=200,
            )
            service = SatelliteJobService(config, repo, sender=sender)
            service.client = _StubClient()

            result = service.check_new_image()
            latest = repo.latest_satellite_log()

            self.assertEqual(result["status"], "ok")
            self.assertIsNotNone(latest)
            self.assertIn("위성은 바깥에서 본 참고 정보예요", result["message"])

    def test_timeline_summary_uses_satellite_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            repo.record_satellite_log(1, date(2026, 1, 10), "sentinel2", 10, 0.55, 0.5, 0.6, 0.22, 0.51, 0.03, 0.02, -0.01)
            repo.record_satellite_log(1, date(2026, 2, 10), "sentinel2", 10, 0.62, 0.57, 0.66, 0.24, 0.58, 0.05, 0.03, 0.01)
            timeline = FarmTimeline(repo)

            summary = timeline.generate_season_summary(1, "2025~2026")

            self.assertTrue(summary["monthly"])
            self.assertIn("시즌 기록", summary["message"])


if __name__ == "__main__":
    unittest.main()
