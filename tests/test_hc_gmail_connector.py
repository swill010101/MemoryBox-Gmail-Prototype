"""Historian Capture Gmail connector: dedicated files, fail-closed, safe status."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TEST_CAPTURE_MAILBOX = "hc-live@tests.local"


class FakeProfileClient:
    def __init__(self, email: str = TEST_CAPTURE_MAILBOX) -> None:
        self._email = email
        self.service = self

    def users(self) -> "FakeProfileClient":
        return self

    def getProfile(self, userId: str = "me") -> "FakeProfileClient":
        return self

    def execute(self) -> dict[str, str]:
        return {"emailAddress": self._email}


class HcGmailConnectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = {k: os.environ.get(k) for k in list(os.environ) if k.startswith("MEMORYBOX_HC_")}
        for k in list(os.environ):
            if k.startswith("MEMORYBOX_HC_") or k.startswith("MEMORYBOX_GC_EMAIL"):
                os.environ.pop(k, None)
        os.environ["MEMORYBOX_HC_CONFIG"] = str(
            Path(tempfile.gettempdir()) / "hc-connector-missing-config.json"
        )
        from memorybox.historian_capture.email_adapter import set_email_adapter

        set_email_adapter(None)

    def tearDown(self) -> None:
        from memorybox.historian_capture.email_adapter import set_email_adapter

        set_email_adapter(None)
        for k in list(os.environ):
            if k.startswith("MEMORYBOX_HC_") or k.startswith("MEMORYBOX_GC_EMAIL"):
                os.environ.pop(k, None)
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_fake_provider_ok(self) -> None:
        os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "fake"
        from memorybox.historian_capture.email_adapter import email_adapter_status, get_email_adapter

        get_email_adapter()
        st = email_adapter_status()
        self.assertTrue(st["ok"])
        self.assertEqual(st["reason"], "fake_ok")
        self.assertFalse(st["live"])
        self.assertNotIn("\\", st["detail"])
        self.assertNotIn("credentials.json", st["detail"])

    def test_missing_dedicated_config_fails_closed(self) -> None:
        os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "auto"
        os.environ["MEMORYBOX_HC_USER_EMAIL"] = TEST_CAPTURE_MAILBOX
        os.environ["MEMORYBOX_HC_GMAIL_CREDENTIALS"] = str(
            Path(tempfile.gettempdir()) / "hc-missing-credentials.json"
        )
        os.environ["MEMORYBOX_HC_GMAIL_TOKEN"] = str(
            Path(tempfile.gettempdir()) / "hc-missing-token.json"
        )
        from memorybox.historian_capture.email_adapter import (
            UnavailableHistorianEmailAdapter,
            email_adapter_status,
            get_email_adapter,
        )

        adapter = get_email_adapter()
        st = email_adapter_status()
        self.assertIsInstance(adapter, UnavailableHistorianEmailAdapter)
        self.assertFalse(st["ok"])
        self.assertEqual(st["reason"], "missing_credentials")
        self.assertIn("Dedicated Historian Capture", st["detail"])
        self.assertNotIn("hc-missing", st["detail"])
        self.assertNotIn("Temp", st["detail"])

    def test_family_gmail_files_are_not_substituted(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            family_creds = root / "gmail_credentials.json"
            family_token = root / "gmail_token.json"
            family_creds.write_text("{}", encoding="utf-8")
            family_token.write_text("{}", encoding="utf-8")
            os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "auto"
            os.environ["MEMORYBOX_HC_USER_EMAIL"] = TEST_CAPTURE_MAILBOX
            os.environ["MEMORYBOX_HC_GMAIL_CREDENTIALS"] = str(
                root / "historian_capture_gmail_credentials.json"
            )
            os.environ["MEMORYBOX_HC_GMAIL_TOKEN"] = str(
                root / "historian_capture_gmail_token.json"
            )
            from memorybox.historian_capture.email_adapter import (
                UnavailableHistorianEmailAdapter,
                email_adapter_status,
                get_email_adapter,
            )

            adapter = get_email_adapter()
            st = email_adapter_status()
            self.assertIsInstance(adapter, UnavailableHistorianEmailAdapter)
            self.assertFalse(st["ok"])
            self.assertEqual(st["reason"], "missing_credentials")
            self.assertFalse(st["live"])

    def test_explicit_family_gmail_paths_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            creds = root / "gmail_credentials.json"
            token = root / "gmail_token.json"
            creds.write_text("{}", encoding="utf-8")
            token.write_text("{}", encoding="utf-8")
            os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "auto"
            os.environ["MEMORYBOX_HC_GMAIL_CREDENTIALS"] = str(creds)
            os.environ["MEMORYBOX_HC_GMAIL_TOKEN"] = str(token)
            from memorybox.historian_capture.email_adapter import (
                UnavailableHistorianEmailAdapter,
                email_adapter_status,
                get_email_adapter,
            )

            adapter = get_email_adapter()
            st = email_adapter_status()
            self.assertIsInstance(adapter, UnavailableHistorianEmailAdapter)
            self.assertFalse(st["ok"])
            self.assertEqual(st["reason"], "family_gmail_rejected")
            self.assertIn("Family Gmail", st["detail"])
            self.assertNotIn(str(root), st["detail"])

    def test_missing_token_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            creds = root / "historian_capture_gmail_credentials.json"
            creds.write_text("{}", encoding="utf-8")
            os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "auto"
            os.environ["MEMORYBOX_HC_USER_EMAIL"] = TEST_CAPTURE_MAILBOX
            os.environ["MEMORYBOX_HC_GMAIL_CREDENTIALS"] = str(creds)
            os.environ["MEMORYBOX_HC_GMAIL_TOKEN"] = str(
                root / "historian_capture_gmail_token.json"
            )
            from memorybox.historian_capture.email_adapter import email_adapter_status, get_email_adapter

            get_email_adapter()
            st = email_adapter_status()
            self.assertFalse(st["ok"])
            self.assertEqual(st["reason"], "missing_token")
            self.assertNotIn("historian_capture_gmail_token", st["detail"])

    def test_missing_transport_package_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            creds = root / "historian_capture_gmail_credentials.json"
            token = root / "historian_capture_gmail_token.json"
            creds.write_text("{}", encoding="utf-8")
            token.write_text("{}", encoding="utf-8")
            os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "auto"
            os.environ["MEMORYBOX_HC_USER_EMAIL"] = TEST_CAPTURE_MAILBOX
            os.environ["MEMORYBOX_HC_GMAIL_CREDENTIALS"] = str(creds)
            os.environ["MEMORYBOX_HC_GMAIL_TOKEN"] = str(token)
            from memorybox.historian_capture.email_adapter import email_adapter_status, get_email_adapter

            with patch(
                "memorybox.historian_capture.gmail_live.build_historian_gmail_client",
                side_effect=ImportError("application.marvin_capture required"),
            ):
                get_email_adapter()
                st = email_adapter_status()
            self.assertFalse(st["ok"])
            self.assertEqual(st["reason"], "missing_transport")
            self.assertNotIn("marvin_capture", st["detail"])
            self.assertNotIn("ImportError", st["detail"])

    def test_live_adapter_loads_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            creds = root / "historian_capture_gmail_credentials.json"
            token = root / "historian_capture_gmail_token.json"
            creds.write_text(json.dumps({"installed": {"client_id": "test"}}), encoding="utf-8")
            token.write_text(json.dumps({"token": "not-used"}), encoding="utf-8")
            os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "auto"
            os.environ["MEMORYBOX_HC_USER_EMAIL"] = TEST_CAPTURE_MAILBOX
            os.environ["MEMORYBOX_HC_GMAIL_CREDENTIALS"] = str(creds)
            os.environ["MEMORYBOX_HC_GMAIL_TOKEN"] = str(token)
            from memorybox.historian_capture.email_adapter import (
                email_adapter_status,
                get_email_adapter,
            )
            from memorybox.historian_capture.gmail_live import MarvinGmailHistorianEmailAdapter

            with patch(
                "memorybox.historian_capture.gmail_live.build_historian_gmail_client",
                return_value=FakeProfileClient(),
            ):
                adapter = get_email_adapter()
                st = email_adapter_status()
            self.assertIsInstance(adapter, MarvinGmailHistorianEmailAdapter)
            self.assertTrue(st["ok"])
            self.assertTrue(st["live"])
            self.assertEqual(st["reason"], "live_ok")
            self.assertEqual(st["capture_mailbox"], TEST_CAPTURE_MAILBOX)
            self.assertIn(TEST_CAPTURE_MAILBOX, st["detail"])
            self.assertNotIn(str(root), st["detail"])

    def test_missing_user_email_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            creds = root / "historian_capture_gmail_credentials.json"
            token = root / "historian_capture_gmail_token.json"
            creds.write_text("{}", encoding="utf-8")
            token.write_text("{}", encoding="utf-8")
            os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "auto"
            os.environ.pop("MEMORYBOX_HC_USER_EMAIL", None)
            os.environ["MEMORYBOX_HC_GMAIL_CREDENTIALS"] = str(creds)
            os.environ["MEMORYBOX_HC_GMAIL_TOKEN"] = str(token)
            from memorybox.historian_capture.email_adapter import (
                UnavailableHistorianEmailAdapter,
                email_adapter_status,
                get_email_adapter,
            )

            adapter = get_email_adapter()
            st = email_adapter_status()
            self.assertIsInstance(adapter, UnavailableHistorianEmailAdapter)
            self.assertFalse(st["ok"])
            self.assertEqual(st["reason"], "missing_user_email")
            self.assertIn("mailbox address is not configured", st["detail"])
            self.assertNotIn("marvinbot.net", st["detail"])
            self.assertNotIn(str(root), st["detail"])
            self.assertFalse(st["live"])

    def test_placeholder_user_email_fails_closed(self) -> None:
        os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "auto"
        os.environ["MEMORYBOX_HC_USER_EMAIL"] = "historian-capture@example.invalid"
        from memorybox.historian_capture.email_adapter import email_adapter_status, get_email_adapter

        get_email_adapter()
        st = email_adapter_status()
        self.assertFalse(st["ok"])
        self.assertEqual(st["reason"], "missing_user_email")
        self.assertNotIn("example.invalid", st["detail"])
        self.assertNotIn("marvinbot.net", st["detail"])

    def test_status_endpoint_uses_safe_reason(self) -> None:
        os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "auto"
        os.environ.pop("MEMORYBOX_HC_USER_EMAIL", None)
        from memorybox.historian_capture.email_adapter import set_email_adapter

        set_email_adapter(None)
        from fastapi.testclient import TestClient
        from memorybox.app import app

        client = TestClient(app)
        data = client.get("/historian-capture/email-status").json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["reason"], "missing_user_email")
        self.assertIn("mailbox address is not configured", data["detail"])
        self.assertNotIn("Exception", data["detail"])
        self.assertNotIn("marvinbot.net", data["detail"])

    def test_serve_defaults_use_privateemail_mailbox(self) -> None:
        root = Path(__file__).resolve().parents[1]
        startmb = (root / "startmb.ps1").read_text(encoding="utf-8")
        env_example = (root / "config" / "memorybox_app.env.example").read_text(encoding="utf-8")
        reqs = (root / "memorybox" / "requirements.txt").read_text(encoding="utf-8")
        gitignore = (root / ".gitignore").read_text(encoding="utf-8")
        self.assertIn('$env:MEMORYBOX_HC_EMAIL_PROVIDER = "privateemail"', startmb)
        self.assertIn('$env:MEMORYBOX_HC_USER_EMAIL = "memorybox@marvinbot.net"', startmb)
        self.assertIn("MEMORYBOX_HC_EMAIL_PROVIDER=privateemail", env_example)
        self.assertIn("MEMORYBOX_HC_USER_EMAIL=memorybox@marvinbot.net", env_example)
        self.assertIn("historian_capture_privateemail_credentials.json", gitignore)
        self.assertIn(".memorybox_hc_state/", gitignore)
        self.assertIn("google-api-python-client>=", reqs)
        self.assertIn("google-auth-oauthlib>=", reqs)

    def test_ui_banner_includes_detail(self) -> None:
        html = (
            Path(__file__).resolve().parents[1]
            / "memorybox"
            / "historian_capture"
            / "static"
            / "historian_capture.html"
        ).read_text(encoding="utf-8")
        self.assertIn("m.detail", html)
        self.assertIn("Email is not connected yet.", html)


if __name__ == "__main__":
    unittest.main()
