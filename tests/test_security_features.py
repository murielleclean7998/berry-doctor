import hashlib
import hmac
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from engine.backup import BackupService
from engine.config import ConfigManager
from engine.kakao.webhook import KakaoWebhookServer
from engine.db.sqlite import SQLiteRepository
from engine.setup_wizard import SetupResult


class _DummyTranslator:
    def get(self, key, default):
        return default

    def t(self, key):
        return key


class _DummyCoach:
    def __init__(self):
        self.translator = _DummyTranslator()

    def build_status(self, house_id=None):  # noqa: ARG002
        return "status-ok"

    def answer_or_record(self, text):  # noqa: ARG002
        return "noted"


class SecurityFeatureTests(unittest.TestCase):
    def test_config_manager_encrypts_wifi_password_and_recovers_plaintext(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            manager = ConfigManager(repo)
            manager.save_setup(
                SetupResult(
                    farm_location="논산시",
                    house_count=3,
                    variety="설향",
                    cultivation_type="토경",
                    wifi_ssid="farm-net",
                    wifi_password="super-secret",
                )
            )

            stored = repo.get_config("wifi_password")
            loaded = manager.load()

            self.assertIsInstance(stored, str)
            self.assertNotEqual(stored, "super-secret")
            self.assertTrue(stored.startswith(("dpapi:", "b64:")))
            self.assertEqual(loaded.wifi_password, "super-secret")
            self.assertTrue(loaded.dashboard_access_token)

    def test_webhook_rejects_missing_signature_when_secret_is_enabled(self):
        config = SimpleNamespace(
            webhook_host="127.0.0.1",
            webhook_port=5005,
            webhook_signature_secret="shared-secret",
        )
        server = KakaoWebhookServer(config, _DummyCoach(), sender=None)
        client = server.app.test_client()
        body = '{"text":"상태"}'.encode("utf-8")

        rejected = client.post("/kakao/webhook", data=body, content_type="application/json")
        accepted = client.post(
            "/kakao/webhook",
            data=body,
            content_type="application/json",
            headers={
                "X-Kakao-Signature": hmac.new(
                    b"shared-secret",
                    body,
                    hashlib.sha256,
                ).hexdigest()
            },
        )

        self.assertEqual(rejected.status_code, 401)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.get_json()["text"], "status-ok")

    def test_backup_service_creates_sqlite_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteRepository(Path(tmpdir) / "berry.db")
            repo.initialize()
            repo.record_diary("backup test", house_id=1)
            service = BackupService(repo, retention_count=3)

            target = service.create_backup()

            self.assertTrue(target.exists())
            self.assertGreater(target.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
