import unittest

from engine.kakao.commands import parse_command


class KakaoCommandTests(unittest.TestCase):
    def test_parse_status(self):
        intent = parse_command("상태")
        self.assertEqual(intent.name, "status")

    def test_parse_spray_record(self):
        intent = parse_command("기록 농약 프로피네브")
        self.assertEqual(intent.name, "record_spray")
        self.assertEqual(intent.text_arg, "프로피네브")

    def test_parse_harvest_record(self):
        intent = parse_command("기록 수확 30kg")
        self.assertEqual(intent.name, "record_harvest")
        self.assertEqual(intent.value, 30)


if __name__ == "__main__":
    unittest.main()
