import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from engine.db.sqlite import SQLiteRepository
from engine.signal.collector import SignalCollector
from engine.signal.models import RawSignal


class _FakeSender:
    def __init__(self):
        self.messages = []

    def send_text(self, message, severity="info", house_id=None, rule_id="manual"):  # noqa: ARG002
        self.messages.append({"message": message, "severity": severity, "rule_id": rule_id})
        return {"ok": True}


class _StaticSource:
    def __init__(self, items):
        self.items = items
        self.source_id = "static"

    async def fetch(self):
        return self.items


class SignalTests(unittest.TestCase):
    def test_signal_collector_saves_relevant_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            repo.set_config("weather_cache", {"current_humidity": 90})
            sender = _FakeSender()
            config = SimpleNamespace(
                farm_location="충남 서산",
                variety="설향",
                signal_immediate_daily_limit=2,
                share_to_community=False,
                community_min_user_threshold=5,
            )
            collector = SignalCollector(config, repo, sender=sender)
            collector.sources = [
                _StaticSource(
                    [
                        RawSignal(
                            source_id="rda_pest",
                            source="농진청 병해충 예찰",
                            title="충남 딸기 잿빛곰팡이 특보",
                            summary="습한 조건이 이어져 주의가 필요해요.",
                            url="https://example.com/1",
                            published_at=datetime(2026, 4, 7, 9, 0, tzinfo=UTC),
                            tags=["딸기", "충남", "특보"],
                            payload={"environment": {"humidity_min": 80, "temp_min": 10, "temp_max": 25}},
                        )
                    ]
                )
            ]

            result = collector.collect_domestic()
            saved = repo.recent_signals(hours=24, limit=5)

            self.assertEqual(result["saved"], 1)
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["source"], "rda_pest")

    def test_signal_immediate_limit_caps_at_two(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            repo.set_config("weather_cache", {"current_humidity": 90})
            sender = _FakeSender()
            config = SimpleNamespace(
                farm_location="충남 서산",
                variety="설향",
                signal_immediate_daily_limit=2,
                share_to_community=False,
                community_min_user_threshold=5,
            )
            collector = SignalCollector(config, repo, sender=sender)
            collector.sources = [
                _StaticSource(
                    [
                        RawSignal("rda_pest", "농진청", "충남 딸기 특보 1", "요약", "https://example.com/a", datetime(2026, 4, 7, 9, 0, tzinfo=UTC), tags=["딸기", "충남", "특보"]),
                        RawSignal("rda_pest", "농진청", "충남 딸기 특보 2", "요약", "https://example.com/b", datetime(2026, 4, 7, 10, 0, tzinfo=UTC), tags=["딸기", "충남", "특보"]),
                        RawSignal("rda_pest", "농진청", "충남 딸기 특보 3", "요약", "https://example.com/c", datetime(2026, 4, 7, 11, 0, tzinfo=UTC), tags=["딸기", "충남", "특보"]),
                    ]
                )
            ]

            collector.collect_domestic()

            self.assertEqual(len(sender.messages), 2)
            self.assertEqual(repo.count_signal_deliveries_today(), 2)


if __name__ == "__main__":
    unittest.main()
