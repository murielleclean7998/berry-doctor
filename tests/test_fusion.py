import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

from engine.db.sqlite import SQLiteRepository
from engine.fusion.context_builder import ContextBuilder
from engine.fusion.intelligence import FusionIntelligence
from engine.fusion.message_composer import MessageComposer
from engine.fusion.risk_scorer import RiskScorer
from engine.signal.db import SignalRepository
from engine.satellite.db import SatelliteRepository


class _FakeSender:
    def __init__(self):
        self.messages = []

    def send_text(self, message, severity="info", house_id=None, rule_id="manual"):  # noqa: ARG002
        self.messages.append({"message": message, "severity": severity, "rule_id": rule_id})
        return {"ok": True}


class _FakeCoach:
    class _KG:
        @staticmethod
        def tasks_for_today(day=None, variety=None):  # noqa: ARG002
            return ["환기 확인", "관수 확인", "꽃잎 정리"]

    class _Market:
        @staticmethod
        def latest():
            return {"price_per_kg": 8200}

    knowledge_graph = _KG()
    market_service = _Market()


class FusionTests(unittest.TestCase):
    def test_risk_scorer_and_message_composer_reflect_agreement(self):
        config = SimpleNamespace(farm_location="충남 서산", variety="설향")
        context = ContextBuilder(config).build(
            "sensor",
            {"house_id": 2, "humidity": 90, "leaf_wetness": 35},
            {"house_id": 2, "ndvi_mean": 0.42, "change_vs_prev": -0.12},
            [{"title": "충남 딸기 특보", "urgency": "critical", "relevance_score": 0.8}],
        )
        risk = RiskScorer().calculate(context)
        message = MessageComposer().compose(context, risk)

        self.assertIn(risk.agreement, {"all_agree", "two_agree"})
        self.assertIn("직접 확인해보시는 게 좋겠어요", message)

    def test_fusion_daily_report_uses_three_sources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            repo.upsert_latest_sensor_snapshot({"house_id": 1, "humidity": 88, "temp_indoor": 22})
            repo.record_satellite_log(1, date(2026, 4, 7), "sentinel2", 12, 0.45, 0.4, 0.5, 0.2, 0.43, -0.11, -0.05, -0.02)
            repo.record_signal(
                source="rda_pest",
                title="충남 딸기 잿빛곰팡이 특보",
                summary="습한 조건이 이어져 주의가 필요해요.",
                url="https://example.com/1",
                language="ko",
                relevance_score=0.8,
                urgency="critical",
                signal_hash="fusion-test",
                tags=["딸기", "충남"],
                payload={},
                published_at=datetime(2026, 4, 7, 9, 0, tzinfo=UTC),
            )
            sender = _FakeSender()
            config = SimpleNamespace(signal_merge_window_seconds=3600, farm_location="충남 서산", variety="설향")
            fusion = FusionIntelligence(repo, SignalRepository(repo), SatelliteRepository(repo), sender, config, coach=_FakeCoach())

            message = fusion.build_daily_report_message(datetime(2026, 4, 7, 21, 0))

            self.assertIn("하루 정리", message)
            self.assertIn("오늘의 소식", message)


if __name__ == "__main__":
    unittest.main()
