import unittest

from engine.rules.disease_risk import calculate_disease_risk


class DiseaseRiskTests(unittest.TestCase):
    def test_botrytis_risk_is_high_in_humid_conditions(self):
        profile = {"type": "coastal", "thresholds": {"humidity_warning": 80}}
        result = calculate_disease_risk(temp=22, humidity=92, wet_hours=8, soil_temp=18, profile=profile)
        self.assertGreaterEqual(result["botrytis"]["risk"], 55)


if __name__ == "__main__":
    unittest.main()
