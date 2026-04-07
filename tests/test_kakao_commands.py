import unittest

from engine.kakao.commands import parse_command


class KakaoCommandTests(unittest.TestCase):
    def test_parse_status(self):
        intent = parse_command("\uc0c1\ud0dc")
        self.assertEqual(intent.name, "status")

    def test_parse_house_status(self):
        intent = parse_command("2\ub3d9 \uc0c1\ud0dc")
        self.assertEqual(intent.name, "house_status")
        self.assertEqual(intent.house_id, 2)

    def test_parse_spray_record(self):
        intent = parse_command("\uae30\ub85d \ub18d\uc57d \ud504\ub85c\ud30c\ub124\ube0c")
        self.assertEqual(intent.name, "record_spray")
        self.assertEqual(intent.text_arg, "\ud504\ub85c\ud30c\ub124\ube0c")

    def test_parse_harvest_record(self):
        intent = parse_command("\uae30\ub85d \uc218\ud655 30kg")
        self.assertEqual(intent.name, "record_harvest")
        self.assertEqual(intent.value, 30)

    def test_parse_harvest_record_with_house(self):
        intent = parse_command("\uae30\ub85d \uc218\ud655 2\ub3d9 30kg")
        self.assertEqual(intent.name, "record_harvest")
        self.assertEqual(intent.house_id, 2)
        self.assertEqual(intent.value, 30)

    def test_parse_timeline_commands(self):
        self.assertEqual(parse_command("\uae30\ub85d").name, "timeline")
        self.assertEqual(parse_command("\uc791\ub144 \ube44\uad50").name, "year_compare")
        self.assertEqual(parse_command("\ubcf4\uc548 \uae30\ub85d").name, "security_history")


if __name__ == "__main__":
    unittest.main()
