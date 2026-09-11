"""HC-2 autonomous cadence: inbound-first tick, lock, cap, heartbeat (fake time/providers)."""
from __future__ import annotations

import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from memorybox.historian_capture.email_adapter import (
    DEFAULT_QUESTION_SUBJECT_TEMPLATE,
    DEFAULT_THANKYOU_SUBJECT_TEMPLATE,
    FakeHistorianEmailAdapter,
    set_email_adapter,
)


def _hc_db_available() -> bool:
    try:
        from memorybox.db import connection, ping

        ping()
        with connection() as conn:
            conn.execute("SELECT 1 FROM historian_capture_items LIMIT 1")
        return True
    except Exception:
        return False


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class OrderFake(FakeHistorianEmailAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def poll_inbound(self):
        self.calls.append("poll")
        return super().poll_inbound()

    def send_question(self, **kwargs):
        self.calls.append("send")
        return super().send_question(**kwargs)


class Hc2OfflineContractTests(unittest.TestCase):
    def test_subject_templates_unchanged(self) -> None:
        self.assertEqual(DEFAULT_QUESTION_SUBJECT_TEMPLATE, "[MB-HC-{token}] {title}")
        self.assertEqual(DEFAULT_THANKYOU_SUBJECT_TEMPLATE, "[MB-HC-{token}] Thank you — MemoryBox")

    def test_task_package_is_disabled_by_default(self) -> None:
        root = Path(__file__).resolve().parents[1]
        register = (root / "scripts" / "historian-capture" / "Register-HcTickTask.ps1").read_text(
            encoding="utf-8"
        )
        launcher = (root / "scripts" / "historian-capture" / "Invoke-HcTick.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("MemoryBox Historian Capture Tick", register)
        self.assertIn("Disable-ScheduledTask", register)
        self.assertIn("Refusing to enable", register)
        self.assertIn("python.exe", launcher)
        self.assertIn("hc-tick", launcher)
        self.assertNotIn("MEMORYBOX_HC_PRIVATEEMAIL_PASSWORD", launcher.split("hc-tick")[-1])
        sql = (root / "memorybox" / "migrations" / "034_historian_capture_hc2_tick.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("historian_capture_tick_heartbeat", sql)

    def test_poll_failure_is_fail_closed_without_db(self) -> None:
        from memorybox.historian_capture import poll_and_ingest

        fake = FakeHistorianEmailAdapter()
        fake.poll_error = "imap_poll_failed"
        out = poll_and_ingest(adapter=fake)
        self.assertFalse(out["ok"])
        self.assertEqual(out["reason"], "imap_unavailable")
        self.assertEqual(out["created"], [])
        self.assertNotIn("imap_poll_failed", str(out))

    def test_delayed_status_after_15_minutes(self) -> None:
        from memorybox.historian_capture.cadence import cadence_public_status, persist_heartbeat

        now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            os.environ["MEMORYBOX_HC_STATE_DIR"] = td
            os.environ["MEMORYBOX_HC_HEARTBEAT_SKIP_DB"] = "1"
            try:
                persist_heartbeat(
                    {
                        "started_at": _iso(now - timedelta(minutes=22)),
                        "completed_at": _iso(now - timedelta(minutes=22)),
                        "last_successful_at": _iso(now - timedelta(minutes=22)),
                        "result": "ok",
                        "duration_ms": 12,
                        "replies_found": 0,
                        "replies_imported": 0,
                        "outbound_attempted": 0,
                        "outbound_sent": 0,
                        "deferred": 0,
                    }
                )
                st = cadence_public_status(now=now)
                self.assertTrue(st["delayed"])
                self.assertEqual(st["display_state"], "delayed")
                self.assertIn("22 minutes ago", st["summary"])
                persist_heartbeat(
                    {
                        "started_at": _iso(now - timedelta(minutes=2)),
                        "completed_at": _iso(now - timedelta(minutes=2)),
                        "last_successful_at": _iso(now - timedelta(minutes=2)),
                        "result": "ok",
                    }
                )
                st2 = cadence_public_status(now=now)
                self.assertFalse(st2["delayed"])
                self.assertEqual(st2["display_state"], "active")
                os.environ["MEMORYBOX_HC_TICK_HEARTBEAT"] = str(Path(td) / "missing.json")
                st3 = cadence_public_status(now=now)
                self.assertEqual(st3["display_state"], "not_configured")
            finally:
                os.environ.pop("MEMORYBOX_HC_TICK_HEARTBEAT", None)
                os.environ.pop("MEMORYBOX_HC_HEARTBEAT_SKIP_DB", None)
                os.environ.pop("MEMORYBOX_HC_STATE_DIR", None)


@unittest.skipUnless(_hc_db_available(), "Historian Capture Postgres not available")
class Hc2CadenceDbTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "fake"
        os.environ["MEMORYBOX_HC_MAX_SENDS_PER_TICK"] = "5"
        os.environ["MEMORYBOX_HC_HEARTBEAT_SKIP_DB"] = "1"
        self._state = tempfile.TemporaryDirectory()
        os.environ["MEMORYBOX_HC_STATE_DIR"] = self._state.name
        set_email_adapter(None)
        # Frozen past clock so live FlightSim due rows (2026) are not selected.
        self.t0 = datetime(1999, 6, 15, 12, 0, tzinfo=timezone.utc)
        self._campaign_ids: list[str] = []

    def tearDown(self) -> None:
        from memorybox.historian_capture import pause_campaign

        for cid in self._campaign_ids:
            try:
                pause_campaign(cid)
            except Exception:
                pass
        set_email_adapter(None)
        os.environ.pop("MEMORYBOX_HC_HEARTBEAT_SKIP_DB", None)
        self._state.cleanup()

    def _campaign(self, fake, *, questions=None, respondents=None, follow_up=1, title=None):
        from memorybox.historian_capture import create_campaign
        from memorybox.historian_capture.acceptance import _seed_person

        tag = uuid4().hex[:8]
        people_id = _seed_person()
        if respondents is None:
            respondents = [
                {
                    "people_id": people_id,
                    "display_name_snapshot": f"Pat {tag}",
                    "contact_route_value": f"pat.{tag}@example.com",
                }
            ]
        camp = create_campaign(
            title=title or f"HC2 {tag}",
            cadence_config_json={"pattern": "seconds", "interval_seconds": 3600},
            follow_up_interval_seconds=follow_up,
            send_thank_you_ack=True,
            respondents=respondents,
            questions=questions or [f"Q for {tag}?"],
        )
        self._campaign_ids.append(str(camp["id"]))
        camp["_tag"] = tag
        camp["_to"] = respondents[0]["contact_route_value"]
        return camp

    def _sent_to(self, fake, to_email: str, *, reminder: bool | None = None):
        rows = [s for s in fake.sent if s.get("to") == to_email]
        if reminder is None:
            return rows
        return [s for s in rows if bool(s.get("is_reminder")) is reminder]

    def test_poll_before_followup_and_reply_suppresses_reminder(self) -> None:
        from memorybox.historian_capture import get_campaign, start_campaign, tick_scheduler

        fake = OrderFake()
        set_email_adapter(fake)
        camp = self._campaign(fake)
        to_email = camp["_to"]
        start_campaign(camp["id"], now=self.t0)
        self.assertEqual(fake.calls[0], "poll")
        self.assertEqual(len(self._sent_to(fake, to_email, reminder=False)), 1)
        token = get_campaign(camp["id"])["deliveries"][0]["correlation_token"]
        fake.inject_reply(
            correlation_token=token,
            from_addr=to_email,
            text="Here is the memory.",
        )
        fake.calls.clear()
        result = tick_scheduler(now=self.t0 + timedelta(seconds=5), adapter=fake)
        self.assertEqual(fake.calls[0], "poll")
        self.assertEqual(len(self._sent_to(fake, to_email, reminder=True)), 0)
        self.assertNotIn(str(get_campaign(camp["id"])["deliveries"][0]["id"]), result.get("reminders") or [])
        d = get_campaign(camp["id"])["deliveries"][0]
        self.assertEqual(d["status"], "answered")

    def test_due_question_and_followup_send_once(self) -> None:
        from memorybox.historian_capture import get_campaign, start_campaign, tick_scheduler

        fake = FakeHistorianEmailAdapter()
        set_email_adapter(fake)
        camp = self._campaign(fake)
        to_email = camp["_to"]
        start_campaign(camp["id"], now=self.t0)
        self.assertEqual(len(self._sent_to(fake, to_email, reminder=False)), 1)
        tick_scheduler(now=self.t0, adapter=fake)
        self.assertEqual(len(self._sent_to(fake, to_email, reminder=False)), 1)
        tick_scheduler(now=self.t0 + timedelta(seconds=5), adapter=fake)
        self.assertEqual(len(self._sent_to(fake, to_email, reminder=True)), 1)
        tick_scheduler(now=self.t0 + timedelta(seconds=5), adapter=fake)
        self.assertEqual(len(self._sent_to(fake, to_email, reminder=True)), 1)
        tick_scheduler(now=self.t0 + timedelta(seconds=10), adapter=fake)
        camp = get_campaign(camp["id"])
        statuses = {d["status"] for d in camp["deliveries"]}
        self.assertIn("no_response", statuses)

    def test_paused_campaign_does_not_send_followup(self) -> None:
        from memorybox.historian_capture import pause_campaign, start_campaign, tick_scheduler

        fake = FakeHistorianEmailAdapter()
        set_email_adapter(fake)
        camp = self._campaign(fake)
        to_email = camp["_to"]
        start_campaign(camp["id"], now=self.t0)
        pause_campaign(camp["id"])
        before = len(self._sent_to(fake, to_email))
        tick_scheduler(now=self.t0 + timedelta(seconds=5), adapter=fake)
        self.assertEqual(len(self._sent_to(fake, to_email)), before)

    def test_repeat_tick_does_not_duplicate(self) -> None:
        from memorybox.historian_capture import start_campaign, tick_scheduler

        fake = FakeHistorianEmailAdapter()
        set_email_adapter(fake)
        camp = self._campaign(fake)
        to_email = camp["_to"]
        start_campaign(camp["id"], now=self.t0)
        tick_scheduler(now=self.t0, adapter=fake)
        tick_scheduler(now=self.t0, adapter=fake)
        self.assertEqual(len(self._sent_to(fake, to_email, reminder=False)), 1)

    def test_concurrent_tick_already_running(self) -> None:
        from memorybox.historian_capture import start_campaign, tick_scheduler
        from memorybox.historian_capture.cadence import hc_tick_lock

        fake = FakeHistorianEmailAdapter()
        set_email_adapter(fake)
        camp = self._campaign(fake)
        start_campaign(camp["id"], now=self.t0)
        with hc_tick_lock() as held:
            self.assertTrue(held)
            result = tick_scheduler(now=self.t0 + timedelta(seconds=5), adapter=fake)
            self.assertEqual(result.get("result"), "already_running")
            self.assertEqual(result.get("ok"), True)

    def test_manual_advance_and_scheduled_tick_share_lock(self) -> None:
        from memorybox.historian_capture import (
            HistorianCaptureError,
            advance_campaign,
            start_campaign,
            tick_scheduler,
        )
        from memorybox.historian_capture.cadence import hc_tick_lock

        fake = FakeHistorianEmailAdapter()
        set_email_adapter(fake)
        camp = self._campaign(fake, questions=["Q1?", "Q2?"])
        started = start_campaign(camp["id"], now=self.t0)
        token = started["deliveries"][0]["correlation_token"]
        fake.inject_reply(
            correlation_token=token,
            from_addr="pat@example.com",
            text="Answered.",
        )
        tick_scheduler(now=self.t0 + timedelta(seconds=1), adapter=fake)
        with hc_tick_lock() as held:
            self.assertTrue(held)
            with self.assertRaises(HistorianCaptureError) as ctx:
                advance_campaign(
                    camp["id"], now=self.t0 + timedelta(seconds=2), adapter=fake
                )
            self.assertIn("automatic check", str(ctx.exception).lower())

    def test_imap_failure_blocks_reminder(self) -> None:
        from memorybox.historian_capture import start_campaign, tick_scheduler

        fake = FakeHistorianEmailAdapter()
        set_email_adapter(fake)
        camp = self._campaign(fake)
        to_email = camp["_to"]
        start_campaign(camp["id"], now=self.t0)
        fake.poll_error = "imap_poll_failed"
        before = len(self._sent_to(fake, to_email))
        result = tick_scheduler(now=self.t0 + timedelta(seconds=5), adapter=fake)
        self.assertEqual(len(self._sent_to(fake, to_email)), before)
        self.assertEqual(result.get("result"), "imap_unavailable")
        self.assertEqual(result.get("reminders") or [], [])

    def test_smtp_failure_leaves_pending_retryable(self) -> None:
        from memorybox.historian_capture import get_campaign, start_campaign, tick_scheduler

        fake = FakeHistorianEmailAdapter(fail_next_send=True)
        set_email_adapter(fake)
        camp = self._campaign(fake)
        start_campaign(camp["id"], now=self.t0)
        row = get_campaign(camp["id"])["deliveries"][0]
        self.assertEqual(row["status"], "pending")
        self.assertTrue(row.get("fail_detail"))
        tick_scheduler(now=self.t0, adapter=fake)
        row2 = get_campaign(camp["id"])["deliveries"][0]
        self.assertEqual(row2["status"], "waiting")
        self.assertEqual(len(fake.sent), 1)

    def test_per_tick_cap_defers_without_loss(self) -> None:
        from memorybox.historian_capture import create_campaign, start_campaign, tick_scheduler
        from memorybox.historian_capture.acceptance import _seed_person

        fake = FakeHistorianEmailAdapter()
        set_email_adapter(fake)
        people_id = _seed_person()
        tag = uuid4().hex[:6]
        respondents = []
        for i in range(6):
            respondents.append(
                {
                    "people_id": people_id if i == 0 else _seed_person(),
                    "display_name_snapshot": f"R{i} {tag}",
                    "contact_route_value": f"r{i}.{tag}@example.com",
                }
            )
        camp = create_campaign(
            title=f"Cap {tag}",
            follow_up_interval_seconds=3600,
            respondents=respondents,
            questions=[f"Cap Q {tag}?"],
        )
        self._campaign_ids.append(str(camp["id"]))
        result = start_campaign(camp["id"], now=self.t0)
        del result
        mine = [s for s in fake.sent if str(s.get("to") or "").endswith(f".{tag}@example.com")]
        self.assertEqual(len(mine), 5)
        tick_scheduler(now=self.t0, adapter=fake)
        mine = [s for s in fake.sent if str(s.get("to") or "").endswith(f".{tag}@example.com")]
        self.assertEqual(len(mine), 6)

    def test_heartbeat_updates(self) -> None:
        from memorybox.historian_capture import start_campaign, tick_scheduler
        from memorybox.historian_capture.cadence import load_heartbeat

        fake = FakeHistorianEmailAdapter()
        set_email_adapter(fake)
        camp = self._campaign(fake)
        start_campaign(camp["id"], now=self.t0)
        hb = load_heartbeat()
        self.assertEqual(hb.get("result"), "ok")
        self.assertGreaterEqual(int(hb.get("outbound_sent") or 0), 1)
        self.assertTrue(hb.get("started_at"))
        self.assertTrue(hb.get("completed_at"))


class Hc2LockHoldTests(unittest.TestCase):
    @unittest.skipUnless(_hc_db_available(), "Historian Capture Postgres not available")
    def test_overlapping_threads_one_already_running(self) -> None:
        from memorybox.historian_capture.cadence import hc_tick_lock, run_historian_capture_tick

        os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "fake"
        os.environ["MEMORYBOX_HC_HEARTBEAT_SKIP_DB"] = "1"
        fake = FakeHistorianEmailAdapter()
        set_email_adapter(fake)
        barrier = threading.Barrier(2)
        results: list[str] = []

        def holder() -> None:
            with hc_tick_lock() as held:
                self.assertTrue(held)
                barrier.wait(timeout=10)
                barrier.wait(timeout=10)

        def ticker() -> None:
            barrier.wait(timeout=10)
            payload = run_historian_capture_tick(adapter=fake, now=datetime.now(timezone.utc))
            results.append(str(payload.get("result")))
            barrier.wait(timeout=10)

        t1 = threading.Thread(target=holder)
        t2 = threading.Thread(target=ticker)
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)
        self.assertEqual(results, ["already_running"])


if __name__ == "__main__":
    unittest.main()
