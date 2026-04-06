import io
import unittest

from PIL import Image

from engine.ai.disease_detector import DiseaseDetector


class DiseaseDetectorTests(unittest.TestCase):
    def test_fallback_detector_returns_result(self):
        image = Image.new("RGB", (64, 64), color=(220, 60, 60))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        result = DiseaseDetector().analyze_bytes(buffer.getvalue(), filename="healthy_sample.png")
        self.assertTrue(result.label_ko)
        self.assertGreater(result.confidence, 0)


if __name__ == "__main__":
    unittest.main()
