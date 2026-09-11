"""Admin Processing Jobs Scheduled Services (HC-2 amendment)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from memorybox.historian_capture.cadence import persist_heartbeat
from memorybox.historian_capture.scheduled_status import (
    derive_service_status,
    historian_capture_service,
    list_scheduled_services,
)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class Hc2AdminScheduledTests(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.env = {
            "MEMORYBOX_HC_STATE_DIR": self._td.name,
            "MEMORYBOX_HC_HEARTBEAT_SKIP_DB": "1",
            "MEMORYBOX_HC_SKIP_TASK_QUERY": "1",
            "MEMORYBOX_HC_EMAIL_PROVIDER": "fake",
            "MEMORYBOX_HC_USER_EMAIL": "memorybox@marvinbot.net",
            "MEMORYBOX_HC_TASK_STATE": "missing",
        }
        self._patch = patch.dict(os.environ, self.env, clear=False)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._td.cleanup()
        from memorybox.historian_capture.scheduled_status import _TASK_STATE_MEM

        _TASK_STATE_MEM.clear()

    def test_admin_jobs_html_keeps_i13_table_and_one_scheduled_section(self) -> None:
        html = (
            Path(__file__).resolve().parents[1]
            / "memorybox"
            / "admin"
            / "static"
            / "jobs.html"
        ).read_text(encoding="utf-8")
        self.assertIn("Processing Jobs", html)
        self.assertIn("Scheduled Services", html)
        self.assertIn("id=\"rows\"", html)
        self.assertIn("Lane", html)
        self.assertIn("owner_learn", html)
        self.assertIn("/admin/api/jobs", html)
        self.assertIn("/admin/api/scheduled-services", html)
        self.assertNotIn("Enable-ScheduledTask", html)
        self.assertNotIn("force-send", html)
        self.assertEqual(html.count("Scheduled Services"), 1)

    def test_hc_panel_view_run_history_link(self) -> None:
        html = (
            Path(__file__).resolve().parents[1]
            / "memorybox"
            / "historian_capture"
            / "static"
            / "historian_capture.html"
        ).read_text(encoding="utf-8")
        self.assertIn("View run history", html)
        self.assertIn("/admin/jobs/ui?mb_return=/historian-capture/ui#scheduled-services", html)

    def test_not_configured_without_cadence(self) -> None:
        svc = historian_capture_service(now=datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc))
        self.assertEqual(svc["status"], "Not configured")
        self.assertEqual(svc["id"], "historian_capture_email")
        self.assertEqual(svc["kind"], "recurring_service")
        self.assertEqual(svc["title"], "Historian Capture email")
        self.assertEqual(svc["schedule"], "Every 5 minutes")
        payload = list_scheduled_services(now=datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc))
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["services"]), 1)
        self.assertIsNone(svc["next_expected_run_at"])

    def test_unregistered_old_failure_is_not_configured(self) -> None:
        now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
        persist_heartbeat(
            {
                "started_at": _iso(now - timedelta(days=14)),
                "completed_at": _iso(now - timedelta(days=14)),
                "result": "imap_unavailable",
                "failure_category": "imap_unavailable",
            }
        )
        svc = historian_capture_service(now=now)
        self.assertEqual(svc["status"], "Not configured")
        self.assertIsNone(svc["next_expected_run_at"])
        self.assertEqual(svc["last_error"], "imap_unavailable")

    def test_disabled_overrides_old_failure(self) -> None:
        now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
        persist_heartbeat(
            {
                "started_at": _iso(now - timedelta(hours=1)),
                "completed_at": _iso(now - timedelta(hours=1)),
                "result": "smtp_send_failed",
                "failure_category": "smtp_send_failed",
            }
        )
        with patch.dict(os.environ, {"MEMORYBOX_HC_TASK_STATE": "disabled"}, clear=False):
            svc = historian_capture_service(now=now)
        self.assertEqual(svc["status"], "Disabled")
        self.assertIsNone(svc["next_expected_run_at"])

    def test_active_recent_success(self) -> None:
        now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
        persist_heartbeat(
            {
                "started_at": _iso(now - timedelta(minutes=3)),
                "completed_at": _iso(now - timedelta(minutes=2)),
                "last_successful_at": _iso(now - timedelta(minutes=2)),
                "result": "ok",
                "replies_found": 2,
                "replies_imported": 1,
                "outbound_attempted": 1,
                "outbound_sent": 1,
                "deferred": 0,
            }
        )
        with patch.dict(os.environ, {"MEMORYBOX_HC_TASK_STATE": "enabled"}, clear=False):
            svc = historian_capture_service(now=now)
        self.assertEqual(svc["status"], "Active")
        self.assertIsNotNone(svc["next_expected_run_at"])
        self.assertEqual(svc["replies_imported"], 1)
        self.assertEqual(svc["emails_sent"], 1)
        self.assertEqual(svc["actions_deferred"], 0)
        self.assertEqual(svc["provider"], "Test email provider")
        self.assertEqual(svc["mailbox"], "memorybox@marvinbot.net")
        self.assertIsNone(svc["last_error"])

    def test_delayed_after_15_minutes(self) -> None:
        now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
        persist_heartbeat(
            {
                "started_at": _iso(now - timedelta(minutes=22)),
                "completed_at": _iso(now - timedelta(minutes=22)),
                "last_successful_at": _iso(now - timedelta(minutes=22)),
                "result": "ok",
            }
        )
        with patch.dict(os.environ, {"MEMORYBOX_HC_TASK_STATE": "enabled"}, clear=False):
            svc = historian_capture_service(now=now)
        self.assertEqual(svc["status"], "Delayed")

    def test_disabled_registered_task(self) -> None:
        now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
        persist_heartbeat(
            {
                "started_at": _iso(now - timedelta(minutes=2)),
                "completed_at": _iso(now - timedelta(minutes=2)),
                "last_successful_at": _iso(now - timedelta(minutes=2)),
                "result": "ok",
            }
        )
        with patch.dict(os.environ, {"MEMORYBOX_HC_TASK_STATE": "disabled"}, clear=False):
            svc = historian_capture_service(now=now)
        self.assertEqual(svc["status"], "Disabled")
        self.assertIsNone(svc["next_expected_run_at"])
        now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
        persist_heartbeat(
            {
                "started_at": _iso(now - timedelta(minutes=1)),
                "completed_at": _iso(now - timedelta(minutes=1)),
                "result": "imap_unavailable",
                "failure_category": "imap_unavailable",
            }
        )
        with patch.dict(os.environ, {"MEMORYBOX_HC_TASK_STATE": "enabled"}, clear=False):
            svc = historian_capture_service(now=now)
        self.assertEqual(svc["status"], "Error")
        self.assertEqual(svc["last_error"], "imap_unavailable")
        blob = json.dumps(svc)
        self.assertNotIn("Exception", blob)
        self.assertNotIn("password", blob.lower())
        self.assertNotIn("Traceback", blob)

    def test_already_running_is_not_error(self) -> None:
        now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
        persist_heartbeat(
            {
                "started_at": _iso(now - timedelta(minutes=1)),
                "completed_at": _iso(now - timedelta(minutes=1)),
                "last_successful_at": _iso(now - timedelta(minutes=4)),
                "result": "already_running",
                "failure_category": "already_running",
                "already_running": True,
            }
        )
        with patch.dict(os.environ, {"MEMORYBOX_HC_TASK_STATE": "enabled"}, clear=False):
            svc = historian_capture_service(now=now)
        self.assertNotEqual(svc["status"], "Error")
        self.assertTrue(svc["already_running"])
        self.assertEqual(
            derive_service_status(
                now=now,
                registered=True,
                enabled=True,
                heartbeat={
                    "result": "already_running",
                    "last_successful_at": _iso(now - timedelta(minutes=4)),
                },
            ),
            "Active",
        )

    def test_fresh_task_status_file_does_not_call_schtasks(self) -> None:
        from memorybox.historian_capture.scheduled_status import (
            persist_task_status,
            scheduler_registration_state,
        )

        persist_task_status(registered=True, enabled=False, source="file")
        with patch.dict(
            os.environ,
            {"MEMORYBOX_HC_TASK_STATE": "", "MEMORYBOX_HC_SKIP_TASK_QUERY": "0"},
            clear=False,
        ):
            os.environ.pop("MEMORYBOX_HC_TASK_STATE", None)
            with patch("memorybox.historian_capture.scheduled_status.subprocess.run") as run:
                state = scheduler_registration_state()
                run.assert_not_called()
        self.assertTrue(state["registered"])
        self.assertFalse(state["enabled"])
        self.assertEqual(state["source"], "file")

    def test_history_newest_first_limited_to_20(self) -> None:
        now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
        for i in range(25):
            persist_heartbeat(
                {
                    "started_at": _iso(now - timedelta(minutes=25 - i)),
                    "completed_at": _iso(now - timedelta(minutes=25 - i) + timedelta(seconds=1)),
                    "last_successful_at": _iso(now - timedelta(minutes=25 - i) + timedelta(seconds=1)),
                    "result": "ok",
                    "replies_imported": i,
                    "outbound_sent": 0,
                }
            )
        with patch.dict(os.environ, {"MEMORYBOX_HC_TASK_STATE": "enabled"}, clear=False):
            svc = historian_capture_service(now=now)
        self.assertEqual(len(svc["recent_runs"]), 20)
        imported = [r["replies_imported"] for r in svc["recent_runs"]]
        self.assertEqual(imported[0], 24)
        self.assertEqual(imported[-1], 5)
        self.assertEqual(svc["recent_runs"][0]["emails_sent"], 0)

    def test_jobs_api_not_mixed_with_ticks(self) -> None:
        from memorybox.admin.i13_admin import list_jobs

        src = Path(list_jobs.__code__.co_filename).read_text(encoding="utf-8")
        self.assertIn("recognition_queue_items", src)
        self.assertNotIn("historian_capture_tick", src)
        jobs_html = (
            Path(__file__).resolve().parents[1] / "memorybox" / "admin" / "static" / "jobs.html"
        ).read_text(encoding="utf-8")
        self.assertIn("data.items", jobs_html)
        self.assertIn("payload.services", jobs_html)

    def test_scheduled_services_endpoint_shape(self) -> None:
        from fastapi.testclient import TestClient
        from memorybox.app import app

        client = TestClient(app)
        data = client.get("/admin/api/scheduled-services").json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["services"]), 1)
        svc = data["services"][0]
        for key in (
            "id",
            "kind",
            "title",
            "status",
            "schedule",
            "provider",
            "mailbox",
            "last_successful_run_at",
            "next_expected_run_at",
            "last_result",
            "replies_imported",
            "emails_sent",
            "actions_deferred",
            "last_error",
            "recent_runs",
        ):
            self.assertIn(key, svc)
        self.assertEqual(svc["kind"], "recurring_service")
        blob = json.dumps(data)
        self.assertNotIn("MEMORYBOX_DATABASE_URL", blob)
        self.assertNotIn("privateemail_password", blob.lower())

    def test_write_rendered_admin_fixtures(self) -> None:
        now = datetime(2026, 9, 11, 20, 0, tzinfo=timezone.utc)
        persist_heartbeat(
            {
                "started_at": _iso(now - timedelta(minutes=3)),
                "completed_at": _iso(now - timedelta(minutes=2)),
                "last_successful_at": _iso(now - timedelta(minutes=2)),
                "result": "ok",
                "replies_found": 1,
                "replies_imported": 1,
                "outbound_attempted": 1,
                "outbound_sent": 1,
                "deferred": 0,
            }
        )
        with patch.dict(os.environ, {"MEMORYBOX_HC_TASK_STATE": "enabled"}, clear=False):
            svc = historian_capture_service(now=now)
        out_dir = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "test-output"
            / "historian-capture"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "admin-scheduled-services-sample.json").write_text(
            json.dumps({"ok": True, "services": [svc]}, indent=2, default=str),
            encoding="utf-8",
        )
        collapsed = out_dir / "admin-jobs-scheduled-collapsed.html"
        expanded = out_dir / "admin-jobs-scheduled-expanded.html"
        self.assertTrue(collapsed.is_file())
        self.assertTrue(expanded.is_file())
        self.assertIn("Scheduled Services", collapsed.read_text(encoding="utf-8"))
        self.assertIn("Recent run history", expanded.read_text(encoding="utf-8"))
        self.assertIn("No I13-scoped queue items", collapsed.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
