import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from engine.crop_profile import load_crop_profile, resolve_data_path
from engine.rules.disease_risk import calculate_disease_risk
from engine.satellite.indices import index_to_grade
from engine.signal.analyzer import SignalAnalyzer
from engine.signal.models import RawSignal


class CropProfileTests(unittest.TestCase):
    def test_load_strawberry_profile_has_all_fields(self):
        profile = load_crop_profile("strawberry")

        self.assertEqual(profile.crop_type, "strawberry")
        self.assertEqual(profile.crop_name_ko, "딸기")
        self.assertEqual(profile.default_variety, "설향")
        self.assertTrue(resolve_data_path(profile, "knowledge_graph").exists())
        self.assertIn("botrytis", profile.diseases)

    def test_load_tomato_profile_has_different_diseases(self):
        profile = load_crop_profile("tomato")

        self.assertEqual(profile.crop_type, "tomato")
        self.assertEqual(profile.crop_name_ko, "토마토")
        self.assertIn("late_blight", profile.diseases)
        self.assertNotIn("botrytis", profile.diseases)
        self.assertEqual(profile.market_item_name, "완숙토마토 상품")

    def test_unknown_crop_falls_back_to_strawberry(self):
        profile = load_crop_profile("pepper")

        self.assertEqual(profile.crop_type, "strawberry")
        self.assertEqual(profile.crop_name_ko, "딸기")

    def test_disease_risk_uses_profile_params_when_provided(self):
        params = {
            "custom_rot": {
                "center_temp": 25,
                "spread": 20,
                "weight_temp": 0.5,
                "weight_humidity": 0.3,
                "weight_other": 0.2,
                "humidity_threshold": 70,
                "humidity_factor": 4,
                "other_factor_key": "wet_hours",
                "other_multiplier": 10,
                "action_ko": "맞춤 조치를 해주세요.",
            }
        }

        result = calculate_disease_risk(
            temp=25,
            humidity=90,
            wet_hours=8,
            soil_temp=20,
            profile={"type": "coastal", "thresholds": {"humidity_warning": 80}},
            disease_params=params,
        )

        self.assertEqual(set(result.keys()), {"custom_rot"})
        self.assertEqual(result["custom_rot"]["action"], "맞춤 조치를 해주세요.")
        self.assertGreater(result["custom_rot"]["risk"], 40)

    def test_signal_analyzer_uses_crop_keywords(self):
        tomato = load_crop_profile("tomato")
        analyzer = SignalAnalyzer(SimpleNamespace(farm_location="충남 서산", variety="완숙토마토"), crop_profile=tomato)
        signal = RawSignal(
            source_id="test",
            source="테스트",
            title="충남 토마토 습해 주의",
            summary="토마토 하우스 관리가 필요합니다.",
            url="https://example.com/tomato",
            published_at=datetime(2026, 4, 8, 9, 0, tzinfo=UTC),
            tags=["토마토", "충남"],
            payload={},
        )

        relevance = analyzer.evaluate(signal, {"farm_location": "충남 서산"}, latest_sensor=None, current_stage=None)

        self.assertGreaterEqual(relevance.score, 0.3)
        self.assertIn("토마토 관련", relevance.reason)

    def test_ndvi_grade_uses_crop_thresholds(self):
        strawberry = load_crop_profile("strawberry")
        tomato = load_crop_profile("tomato")

        strawberry_grade = index_to_grade(0.28, thresholds=strawberry.ndvi_thresholds)
        tomato_grade = index_to_grade(0.28, thresholds=tomato.ndvi_thresholds)

        self.assertEqual(strawberry_grade["grade"], "위험")
        self.assertEqual(tomato_grade["grade"], "주의")


if __name__ == "__main__":
    unittest.main()
