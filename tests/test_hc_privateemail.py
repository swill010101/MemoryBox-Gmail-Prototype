"""Historian Capture Namecheap Private Email adapter (offline/mocked)."""
from __future__ import annotations

import json
import os
import smtplib
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from memorybox.historian_capture.privateemail import (
    NamecheapPrivateEmailAdapter,
    is_relevant_hc_folder,
    load_privateemail_config,
)


TOKEN = "aabb11"
MAILBOX = "memorybox@marvinbot.net"


def _raw_reply(*, message_id: str, to_addr: str, subject: str, body: str, from_addr: str = "aunt@example.test") -> bytes:
    return (
        f"From: {from_addr}\r\n"
        f"To: {to_addr}\r\n"
        f"Subject: {subject}\r\n"
        f"Message-ID: {message_id}\r\n"
        f"\r\n"
        f"{body}\r\n"
    ).encode("utf-8")


class FakeIMAP:
    def __init__(self, folders: dict[str, dict[int, bytes]], uidvalidities: dict[str, str] | None = None) -> None:
        self.folders = folders
        self.uidvalidities = uidvalidities or {name: "1" for name in folders}
        self.selected = "INBOX"
        self.readonly = False
        self.fetch_args: list[tuple] = []
        self.logged_out = False

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        if password == "bad-password":
            raise Exception("AUTHENTICATIONFAILED")
        return ("OK", [b"Logged in"])

    def list(self) -> tuple[str, list[bytes]]:
        rows = []
        for name in self.folders:
            rows.append(f'(\\HasNoChildren) "/" {name}'.encode("utf-8"))
        return ("OK", rows)

    def select(self, mailbox: str = "INBOX", readonly: bool = False) -> tuple[str, list[bytes]]:
        self.selected = mailbox
        self.readonly = readonly
        return ("OK", [b"1"])

    def response(self, code: str):
        if code == "UIDVALIDITY":
            val = self.uidvalidities.get(self.selected, "1")
            return ("OK", [val.encode("ascii")])
        return (None, [None])

    def uid(self, cmd: str, *args):
        cmd_u = cmd.upper()
        if cmd_u == "SEARCH":
            uids = sorted(self.folders.get(self.selected, {}))
            blob = " ".join(str(u) for u in uids).encode("ascii")
            return ("OK", [blob])
        if cmd_u == "FETCH":
            self.fetch_args.append(args)
            uid = int(args[0])
            spec = str(args[1])
            raw = self.folders.get(self.selected, {}).get(uid)
            if raw is None:
                return ("OK", [None])
            return ("OK", [(f"{uid} (UID {uid} {spec}".encode("ascii"), raw)])
        raise AssertionError(cmd)

    def logout(self) -> tuple[str, list[bytes]]:
        self.logged_out = True
        return ("BYE", [b""])


class FakeSMTP:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.quit_called = False
        self.login_user = ""

    def login(self, user: str, password: str) -> None:
        if password == "bad-password":
            raise smtplib.SMTPAuthenticationError(535, b"auth")
        self.login_user = user

    def send_message(self, msg: EmailMessage) -> dict:
        self.sent.append(msg)
        return {}

    def quit(self) -> None:
        self.quit_called = True


class HcPrivateEmailTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = {k: os.environ.get(k) for k in list(os.environ) if k.startswith("MEMORYBOX_HC_")}
        for k in list(os.environ):
            if k.startswith("MEMORYBOX_HC_") or k.startswith("MEMORYBOX_GC_EMAIL"):
                os.environ.pop(k, None)
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        os.environ["MEMORYBOX_HC_CONFIG"] = str(self.root / "missing-hc.json")
        os.environ["MEMORYBOX_HC_IMAP_CHECKPOINT"] = str(self.root / "checkpoint.json")
        os.environ["MEMORYBOX_HC_MAIL_DIR"] = str(self.root / "mail")
        os.environ["MEMORYBOX_HC_PRIVATEEMAIL_CREDENTIALS"] = str(self.root / "pe.json")
        from memorybox.historian_capture.email_adapter import set_email_adapter

        set_email_adapter(None)

    def tearDown(self) -> None:
        from memorybox.historian_capture.email_adapter import set_email_adapter

        set_email_adapter(None)
        self._tmp.cleanup()
        for k in list(os.environ):
            if k.startswith("MEMORYBOX_HC_") or k.startswith("MEMORYBOX_GC_EMAIL"):
                os.environ.pop(k, None)
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _write_pe_file(self, **extra: object) -> None:
        payload = {
            "username": MAILBOX,
            "password": "app-password-not-for-commit",
            "imap_host": "mail.privateemail.com",
            "imap_port": 993,
            "smtp_host": "mail.privateemail.com",
            "smtp_port": 465,
            "from_display_name": "MemoryBox Historian for Tom",
        }
        payload.update(extra)
        Path(os.environ["MEMORYBOX_HC_PRIVATEEMAIL_CREDENTIALS"]).write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def test_valid_config_selects_imap_smtp_adapter(self) -> None:
        os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "privateemail"
        os.environ["MEMORYBOX_HC_USER_EMAIL"] = MAILBOX
        os.environ["MEMORYBOX_HC_PRIVATEEMAIL_PASSWORD"] = "app-password-not-for-commit"
        from memorybox.historian_capture.email_adapter import (
            email_adapter_status,
            get_email_adapter,
        )
        from memorybox.historian_capture.privateemail import NamecheapPrivateEmailAdapter

        with patch(
            "memorybox.historian_capture.privateemail.probe_privateemail",
            return_value={"ok": True, "reason": "live_ok"},
        ):
            adapter = get_email_adapter()
            st = email_adapter_status()
        self.assertIsInstance(adapter, NamecheapPrivateEmailAdapter)
        self.assertTrue(st["ok"])
        self.assertEqual(st["reason"], "live_ok")
        self.assertEqual(st["provider_key"], "namecheap_privateemail_imap_smtp")
        self.assertEqual(st["transport_email"], MAILBOX)
        self.assertNotIn("app-password", json.dumps(st))

    def test_missing_app_password_fails_closed(self) -> None:
        os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "privateemail"
        os.environ["MEMORYBOX_HC_USER_EMAIL"] = MAILBOX
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
        self.assertNotIn("password", st["detail"].lower())

    def test_family_gmail_files_never_substituted(self) -> None:
        os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "privateemail"
        os.environ["MEMORYBOX_HC_USER_EMAIL"] = MAILBOX
        family = self.root / "gmail_credentials.json"
        family.write_text("{}", encoding="utf-8")
        os.environ["MEMORYBOX_HC_PRIVATEEMAIL_CREDENTIALS"] = str(family)
        cfg = load_privateemail_config()
        self.assertTrue(cfg["family_gmail_rejected"])
        self.assertFalse(cfg["has_password"])
        from memorybox.historian_capture.email_adapter import email_adapter_status, get_email_adapter

        get_email_adapter()
        st = email_adapter_status()
        self.assertFalse(st["ok"])
        self.assertEqual(st["reason"], "family_gmail_rejected")

    def test_smtp_send_from_and_correlation(self) -> None:
        smtp = FakeSMTP()
        adapter = NamecheapPrivateEmailAdapter(
            {
                "username": MAILBOX,
                "password": "app-password-not-for-commit",
                "from_display_name": "MemoryBox Historian for Tom",
                "smtp_host": "mail.privateemail.com",
                "smtp_port": 465,
            },
            preserve_root=self.root / "mail",
        )
        with patch("memorybox.historian_capture.privateemail.open_smtp", return_value=smtp):
            result = adapter.send_question(
                to_email="respondent@example.test",
                respondent_name="Aunt",
                question_body="What is the story?",
                correlation_token=TOKEN,
                campaign_title="Kitchen memories",
            )
        self.assertTrue(result.ok)
        self.assertTrue(result.reply_to.endswith(f"+hc-{TOKEN}@{MAILBOX.split('@', 1)[1]}"))
        msg = smtp.sent[0]
        self.assertIn(MAILBOX, str(msg["From"]))
        self.assertIn("MemoryBox Historian for Tom", str(msg["From"]))
        self.assertEqual(str(msg["To"]), "respondent@example.test")
        self.assertEqual(str(msg["Subject"]), f"[MB-HC-{TOKEN}] Kitchen memories")
        self.assertEqual(str(msg["Reply-To"]), result.reply_to)
        self.assertEqual(result.outbound_message_id, str(msg["Message-ID"]))
        body = msg.get_content()
        self.assertIn("What is the story?", body)
        self.assertNotIn("app-password", body)

    def test_imap_polling_uses_peek_and_readonly(self) -> None:
        raw = _raw_reply(
            message_id="<inbox-1@test>",
            to_addr=MAILBOX,
            subject=f"[MB-HC-{TOKEN}] Kitchen memories",
            body="The pie was apple.",
        )
        imap = FakeIMAP({"INBOX": {3: raw}, "Sent": {9: b"nope"}})
        adapter = NamecheapPrivateEmailAdapter(
            {"username": MAILBOX, "password": "x"},
            preserve_root=self.root / "mail",
        )
        with patch("memorybox.historian_capture.privateemail.open_imap", return_value=imap):
            items = adapter.poll_inbound()
        self.assertTrue(imap.readonly)
        self.assertTrue(any("BODY.PEEK[]" in str(args[1]) for args in imap.fetch_args))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].correlation_token, TOKEN)
        self.assertIn("pie was apple", items[0].extracted_text)

    def test_inbox_reply_normalized(self) -> None:
        raw = _raw_reply(
            message_id="<norm-1@test>",
            to_addr=f"memorybox+hc-{TOKEN}@marvinbot.net",
            subject="Re: memories",
            body="Yes, that Sunday.",
        )
        imap = FakeIMAP({"INBOX": {1: raw}})
        adapter = NamecheapPrivateEmailAdapter({"username": MAILBOX, "password": "x"}, preserve_root=self.root / "mail")
        with patch("memorybox.historian_capture.privateemail.open_imap", return_value=imap):
            item = adapter.poll_inbound()[0]
        self.assertEqual(item.inbound_message_id, "<norm-1@test>")
        self.assertEqual(item.correlation_token, TOKEN)
        self.assertEqual(item.raw_headers["x-mb-imap-folder"], "INBOX")

    def test_plus_address_folder_reply_correlated(self) -> None:
        folder = f"hc-{TOKEN}"
        raw = _raw_reply(
            message_id="<plus-1@test>",
            to_addr=f"memorybox+hc-{TOKEN}@marvinbot.net",
            subject="Re:",
            body="From the tagged folder.",
        )
        imap = FakeIMAP({"INBOX": {}, folder: {4: raw}})
        adapter = NamecheapPrivateEmailAdapter({"username": MAILBOX, "password": "x"}, preserve_root=self.root / "mail")
        with patch("memorybox.historian_capture.privateemail.open_imap", return_value=imap):
            items = adapter.poll_inbound()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].correlation_token, TOKEN)
        self.assertEqual(items[0].raw_headers["x-mb-imap-folder"], folder)

    def test_repeat_poll_does_not_duplicate_after_mark(self) -> None:
        raw = _raw_reply(
            message_id="<dup-1@test>",
            to_addr=MAILBOX,
            subject=f"[MB-HC-{TOKEN}] Kitchen memories",
            body="Once.",
        )
        imap = FakeIMAP({"INBOX": {1: raw}})
        adapter = NamecheapPrivateEmailAdapter({"username": MAILBOX, "password": "x"}, preserve_root=self.root / "mail")
        with patch("memorybox.historian_capture.privateemail.open_imap", return_value=imap):
            first = adapter.poll_inbound()
            adapter.mark_processed(first[0].inbound_message_id)
            second = adapter.poll_inbound()
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_restart_checkpoint_skips_processed(self) -> None:
        raw = _raw_reply(
            message_id="<rst-1@test>",
            to_addr=MAILBOX,
            subject=f"[MB-HC-{TOKEN}] Kitchen memories",
            body="Restart safe.",
        )
        imap = FakeIMAP({"INBOX": {2: raw}})
        first = NamecheapPrivateEmailAdapter({"username": MAILBOX, "password": "x"}, preserve_root=self.root / "mail")
        with patch("memorybox.historian_capture.privateemail.open_imap", return_value=imap):
            items = first.poll_inbound()
            first.mark_processed(items[0].inbound_message_id)
        restarted = NamecheapPrivateEmailAdapter({"username": MAILBOX, "password": "x"}, preserve_root=self.root / "mail")
        with patch("memorybox.historian_capture.privateemail.open_imap", return_value=imap):
            again = restarted.poll_inbound()
        self.assertEqual(again, [])

    def test_uidvalidity_change_does_not_reimport_processed(self) -> None:
        raw = _raw_reply(
            message_id="<uidv-1@test>",
            to_addr=MAILBOX,
            subject=f"[MB-HC-{TOKEN}] Kitchen memories",
            body="Same rfc id.",
        )
        imap1 = FakeIMAP({"INBOX": {8: raw}}, uidvalidities={"INBOX": "100"})
        adapter = NamecheapPrivateEmailAdapter({"username": MAILBOX, "password": "x"}, preserve_root=self.root / "mail")
        with patch("memorybox.historian_capture.privateemail.open_imap", return_value=imap1):
            items = adapter.poll_inbound()
            adapter.mark_processed(items[0].inbound_message_id)
        imap2 = FakeIMAP({"INBOX": {1: raw}}, uidvalidities={"INBOX": "200"})
        with patch("memorybox.historian_capture.privateemail.open_imap", return_value=imap2):
            again = adapter.poll_inbound()
        self.assertEqual(again, [])

    def test_auth_and_network_failures_are_sanitized(self) -> None:
        os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "privateemail"
        os.environ["MEMORYBOX_HC_USER_EMAIL"] = MAILBOX
        os.environ["MEMORYBOX_HC_PRIVATEEMAIL_PASSWORD"] = "bad-password"
        from memorybox.historian_capture.email_adapter import email_adapter_status, get_email_adapter

        with patch(
            "memorybox.historian_capture.privateemail.probe_privateemail",
            return_value={"ok": False, "reason": "authentication_failed"},
        ):
            get_email_adapter()
            st = email_adapter_status()
        self.assertFalse(st["ok"])
        self.assertEqual(st["reason"], "authentication_failed")
        self.assertNotIn("bad-password", st["detail"])
        self.assertNotIn("\\", st["detail"])

        from memorybox.historian_capture.email_adapter import set_email_adapter

        set_email_adapter(None)
        with patch(
            "memorybox.historian_capture.privateemail.probe_privateemail",
            return_value={"ok": False, "reason": "imap_unavailable"},
        ):
            get_email_adapter()
            st = email_adapter_status()
        self.assertEqual(st["reason"], "imap_unavailable")
        self.assertNotIn("Exception", st["detail"])

    def test_auto_does_not_fallback_to_gmail_when_privateemail_fails(self) -> None:
        os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "auto"
        os.environ["MEMORYBOX_HC_USER_EMAIL"] = MAILBOX
        os.environ["MEMORYBOX_HC_PRIVATEEMAIL_PASSWORD"] = "app-password-not-for-commit"
        creds = self.root / "historian_capture_gmail_credentials.json"
        token = self.root / "historian_capture_gmail_token.json"
        creds.write_text("{}", encoding="utf-8")
        token.write_text("{}", encoding="utf-8")
        os.environ["MEMORYBOX_HC_GMAIL_CREDENTIALS"] = str(creds)
        os.environ["MEMORYBOX_HC_GMAIL_TOKEN"] = str(token)
        from memorybox.historian_capture.email_adapter import (
            UnavailableHistorianEmailAdapter,
            email_adapter_status,
            get_email_adapter,
        )

        with patch(
            "memorybox.historian_capture.privateemail.probe_privateemail",
            return_value={"ok": False, "reason": "smtp_unavailable"},
        ):
            adapter = get_email_adapter()
            st = email_adapter_status()
        self.assertIsInstance(adapter, UnavailableHistorianEmailAdapter)
        self.assertEqual(st["reason"], "smtp_unavailable")
        self.assertFalse(st["live"])
        self.assertNotEqual(st["provider_key"], "marvin_historian_gmail")

    def test_env_overrides_credentials_file(self) -> None:
        self._write_pe_file(password="file-secret")
        os.environ["MEMORYBOX_HC_USER_EMAIL"] = MAILBOX
        os.environ["MEMORYBOX_HC_PRIVATEEMAIL_PASSWORD"] = "env-secret"
        os.environ["MEMORYBOX_HC_IMAP_HOST"] = "imap.test.example"
        cfg = load_privateemail_config()
        self.assertEqual(cfg["password"], "env-secret")
        self.assertEqual(cfg["imap_host"], "imap.test.example")
        self.assertTrue(cfg["has_password"])

    def test_sent_folder_is_not_polled(self) -> None:
        self.assertFalse(is_relevant_hc_folder("Sent"))
        self.assertTrue(is_relevant_hc_folder("INBOX"))
        self.assertTrue(is_relevant_hc_folder(f"hc-{TOKEN}"))

    def test_checkpoint_is_repo_state_not_cwd(self) -> None:
        from memorybox.historian_capture.privateemail import _REPO_ROOT, checkpoint_path

        os.environ.pop("MEMORYBOX_HC_IMAP_CHECKPOINT", None)
        os.environ["MEMORYBOX_HC_USER_EMAIL"] = MAILBOX
        other = self.root / "not-repo-cwd"
        other.mkdir()
        old = Path.cwd()
        try:
            os.chdir(other)
            path = checkpoint_path(username=MAILBOX)
        finally:
            os.chdir(old)
        self.assertTrue(str(path).startswith(str(_REPO_ROOT / ".memorybox_hc_state")))
        self.assertIn("namecheap_privateemail_imap_smtp", str(path))
        self.assertIn("memorybox_marvinbot_net", str(path))
        other_acct = checkpoint_path(username="other@example.test")
        self.assertNotEqual(path, other_acct)

    def test_checkpoint_file_has_no_secrets(self) -> None:
        raw = _raw_reply(
            message_id="<sec-1@test>",
            to_addr=MAILBOX,
            subject=f"[MB-HC-{TOKEN}] Kitchen memories",
            body="Secret body should not be checkpointed.",
        )
        imap = FakeIMAP({"INBOX": {1: raw}})
        adapter = NamecheapPrivateEmailAdapter(
            {"username": MAILBOX, "password": "app-password-not-for-commit"},
            preserve_root=self.root / "mail",
        )
        with patch("memorybox.historian_capture.privateemail.open_imap", return_value=imap):
            items = adapter.poll_inbound()
            adapter.mark_processed(items[0].inbound_message_id)
        data = Path(os.environ["MEMORYBOX_HC_IMAP_CHECKPOINT"]).read_text(encoding="utf-8")
        self.assertNotIn("app-password", data)
        self.assertNotIn("Secret body", data)
        parsed = json.loads(data)
        self.assertIn("processed_ids", parsed)
        self.assertIn("folders", parsed)

    def test_subject_without_token_correlates_via_plus_address(self) -> None:
        from memorybox.historian_capture.email_adapter import (
            extract_correlation_token,
            format_question_subject,
            format_thankyou_subject,
        )

        token = extract_correlation_token(
            subject="A MemoryBox question from Tom about Kitchen memories",
            to_addrs=[f"memorybox+hc-{TOKEN}@marvinbot.net"],
            headers={"to": f"memorybox+hc-{TOKEN}@marvinbot.net"},
        )
        self.assertEqual(token, TOKEN)
        os.environ["MEMORYBOX_HC_QUESTION_SUBJECT_TEMPLATE"] = (
            "A MemoryBox question from Tom about {title}"
        )
        os.environ["MEMORYBOX_HC_THANKYOU_SUBJECT_TEMPLATE"] = "Thank you for sharing this memory"
        q = format_question_subject(correlation_token=TOKEN, campaign_title="Peggy")
        ty = format_thankyou_subject(correlation_token=TOKEN)
        self.assertEqual(q, "A MemoryBox question from Tom about Peggy")
        self.assertEqual(ty, "Thank you for sharing this memory")
        self.assertNotIn("[MB-HC-", q)
        smtp = FakeSMTP()
        adapter = NamecheapPrivateEmailAdapter(
            {"username": MAILBOX, "password": "x", "from_display_name": "MemoryBox Historian for Tom"},
            preserve_root=self.root / "mail",
        )
        with patch("memorybox.historian_capture.privateemail.open_smtp", return_value=smtp):
            result = adapter.send_question(
                to_email="respondent@example.test",
                respondent_name="Aunt",
                question_body="What is the story?",
                correlation_token=TOKEN,
                campaign_title="Peggy",
            )
        msg = smtp.sent[0]
        self.assertEqual(str(msg["Subject"]), q)
        self.assertEqual(str(msg["Reply-To"]), result.reply_to)
        self.assertTrue(str(msg["Reply-To"]).startswith("memorybox+hc-"))
        self.assertEqual(str(msg["X-MemoryBox-HC-Token"]), TOKEN)

    def test_default_subject_still_includes_token(self) -> None:
        from memorybox.historian_capture.email_adapter import format_question_subject

        os.environ.pop("MEMORYBOX_HC_QUESTION_SUBJECT_TEMPLATE", None)
        subject = format_question_subject(correlation_token=TOKEN, campaign_title="Kitchen memories")
        self.assertEqual(subject, f"[MB-HC-{TOKEN}] Kitchen memories")


if __name__ == "__main__":
    unittest.main()
