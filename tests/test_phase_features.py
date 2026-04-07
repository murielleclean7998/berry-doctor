import unittest

from engine.ai.price_forecast import PriceForecast
from engine.rules.engine import RuleEngine


class PhaseFeatureTests(unittest.TestCase):
    def test_price_forecast_builds_peak_day(self):
        history = [
            {"price_per_kg": 8600},
            {"price_per_kg": 8400},
            {"price_per_kg": 8300},
            {"price_per_kg": 8100},
        ]
        forecast = PriceForecast().build_forecast(history, days=5)

        self.assertEqual(len(forecast["predicted_prices"]), 5)
        self.assertIn("recommendation", forecast)
        self.assertGreater(forecast["confidence"], 0)

    def test_rule_engine_creates_control_proposals_for_humid_house(self):
        engine = RuleEngine(
            {
                "type": "coastal",
                "thresholds": {
                    "humidity_warning": 80,
                    "humidity_critical": 88,
                    "heavy_rain_mm_per_hour": 20,
                    "light_target_umol": 150,
                    "frost_warning_temp": -5,
                },
            }
        )
        evaluation = engine.evaluate_environment(
            {
                "house_id": 2,
                "temp_indoor": 29,
                "humidity": 92,
                "soil_moisture_1": 21,
                "soil_moisture_2": 25,
                "solution_ec": 0.6,
                "solution_ph": 5.2,
                "light_lux": 7000,
            },
            {"current_temp": 21, "current_humidity": 86, "max_hourly_rainfall": 0, "estimated_wet_hours": 6, "soil_temp": 18},
        )

        devices = {proposal.device for proposal in evaluation.proposals}
        self.assertIn("ventilation", devices)
        self.assertIn("irrigation", devices)
        self.assertIn("supplemental_light", devices)
        self.assertTrue(evaluation.pid_summary.commands)

    def test_rule_engine_updates_profile_thresholds(self):
        engine = RuleEngine({"type": "coastal", "thresholds": {"humidity_warning": 80}})

        engine.update_profile({"type": "inland", "thresholds": {"humidity_warning": 72}})

        self.assertEqual(engine.profile["type"], "inland")
        self.assertEqual(engine.thresholds["humidity_warning"], 72)


if __name__ == "__main__":
    unittest.main()
