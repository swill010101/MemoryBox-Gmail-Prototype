"""Admin API and I13 status tests."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from memorybox.admin import i13_admin


class AdminApiTests(unittest.TestCase):
    def test_active_admission_id_rejects_invalid(self):
        with patch.dict("os.environ", {"MEMORYBOX_I13_ADMISSION_ID": "not-a-uuid"}, clear=False):
            self.assertIsNone(i13_admin.active_admission_id())

    def test_active_admission_id_accepts_uuid(self):
        uid = "458d1a76-4ecb-4722-bd76-20125b14c1d3"
        with patch.dict("os.environ", {"MEMORYBOX_I13_ADMISSION_ID": uid}, clear=False):
            self.assertEqual(i13_admin.active_admission_id(), uid)

    @patch("memorybox.admin.i13_admin.connection")
    def test_i13_status_reports_learn_disabled_without_started_admission(self, conn_ctx):
        conn = MagicMock()
        conn_ctx.return_value.__enter__.return_value = conn
        conn.execute.side_effect = [
            MagicMock(fetchone=lambda: None),
            MagicMock(fetchall=lambda: []),
            MagicMock(fetchall=lambda: []),
            MagicMock(fetchall=lambda: []),
            MagicMock(fetchall=lambda: []),
            MagicMock(fetchall=lambda: []),
        ]
        with patch.dict("os.environ", {"MEMORYBOX_I13_ADMISSION_ID": ""}, clear=False):
            result = i13_admin.i13_status()
        self.assertFalse(result["interactive_learn_enabled"])
        self.assertTrue(result["archive_processing_locked"])

    def test_bounded_plan_preview_from_repo(self):
        import json
        from pathlib import Path
        from memorybox.processing import scope

        plan = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "docs/implementation/p2-i13-stage-a/acceptance-learning-bounded-plan.json"
            ).read_text(encoding="utf-8")
        )
        preview = scope.preview(plan)
        self.assertEqual(preview["purpose"], "acceptance_learning")
        self.assertEqual(preview["source_count"], 22)
        self.assertLessEqual(preview["work_items"], preview["max_work_items"])


if __name__ == "__main__":
    unittest.main()
