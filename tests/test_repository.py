import tempfile
import unittest
from pathlib import Path

from engine.db.sqlite import SQLiteRepository


class RepositoryTests(unittest.TestCase):
    def test_all_config_deserializes_without_n_plus_one_helpers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            repo.set_many_config({"mock_mode": True, "house_count": 3, "farm_location": "Nonsan"})

            payload = repo.all_config()

            self.assertEqual(payload["mock_mode"], True)
            self.assertEqual(payload["house_count"], 3)
            self.assertEqual(payload["farm_location"], "Nonsan")

    def test_diagnosis_log_and_spray_restrictions_are_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            repo.record_spray(
                pesticide_name="Test Pesticide",
                target_disease="Gray Mold",
                dilution=1000,
                phi_days=3,
                house_id=2,
            )
            repo.record_diagnosis(
                disease_key="gray_mold",
                disease_name="회색곰팡이병",
                confidence=88.5,
                symptoms="꽃과 과실에 회색 곰팡이가 보입니다.",
                model_used="heuristic",
                pesticide_name="Test Pesticide",
                phi_days=3,
                image_name="sample.jpg",
                house_id=2,
            )

            restrictions = repo.active_spray_restrictions(house_id=2)
            diagnoses = repo.recent_diagnoses(5)

            self.assertEqual(len(restrictions), 1)
            self.assertEqual(restrictions[0]["house_id"], 2)
            self.assertEqual(diagnoses[0]["disease_key"], "gray_mold")
            self.assertEqual(diagnoses[0]["image_name"], "sample.jpg")


if __name__ == "__main__":
    unittest.main()
