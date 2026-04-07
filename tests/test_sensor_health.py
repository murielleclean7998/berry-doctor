import tempfile
import unittest
from pathlib import Path

from engine.db.sqlite import SQLiteRepository
from engine.scheduler.sensor_health import SensorHealthService


class SensorHealthTests(unittest.TestCase):
    def test_sensor_health_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            service = SensorHealthService(repo)
            result = service.run()
            self.assertEqual(result["phase"], 0)
            self.assertEqual(result["sensor_mode"], "sampled_plus_aggregate")
            self.assertIn("raw_pruned_rows", result)
            self.assertIn("aggregate_pruned_rows", result)


if __name__ == "__main__":
    unittest.main()
