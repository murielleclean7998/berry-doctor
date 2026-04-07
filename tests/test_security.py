import tempfile
import unittest
from pathlib import Path

from engine.db.sqlite import SQLiteRepository
from engine.security.monitor import SecurityMonitor


class _FakeSender:
    def __init__(self):
        self.payloads = []

    def send_with_photos(self, message, photos, severity="warning", house_id=None, rule_id="manual"):  # noqa: ARG002
        self.payloads.append({"message": message, "photos": photos})
        return {"ok": True}


class SecurityMonitorTests(unittest.TestCase):
    def test_motion_event_is_saved_and_forwarded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            sender = _FakeSender()
            monitor = SecurityMonitor(repo, sender)

            result = monitor.on_motion_detected(
                {
                    "house_id": 2,
                    "timestamp": "2026-04-07 03:14:00",
                    "photos": ["a.jpg", "b.jpg"],
                }
            )
            events = repo.recent_security_events(days=7, limit=5)

            self.assertEqual(result["photo_count"], 2)
            self.assertEqual(len(events), 1)
            self.assertIn("야생동물일 수도 있지만", sender.payloads[0]["message"])


if __name__ == "__main__":
    unittest.main()
