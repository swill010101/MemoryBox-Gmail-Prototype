import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi import HTTPException

from memorybox import app


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.sql = []

    def execute(self, sql):
        self.sql.append(sql)
        return _Cursor(self.rows)


class VoicePilotResultsTests(unittest.TestCase):
    def test_read_only_result_projection_omits_private_payload(self):
        row = {
            "admission_id": "admission-123",
            "created_at": "2026-09-06T00:00:00Z",
            "stale": False,
            "state": "stopped",
            "thresholds": {"match": 0.45, "uncertain": 0.30},
            "spans": [{"key": "H1", "source_id": "vid-held-out", "start": 12.5, "end": 20.0}],
            "payload": {
                "results": [{"key": "H1", "expected_match": True, "score": 0.63, "decision": "match"}],
                "embedding": "must-not-leak",
            },
        }
        conn = _Connection([row])

        @contextmanager
        def connection():
            yield conn

        with patch("memorybox.db.connection", connection):
            result = app.review_voice_pilot_results()

        self.assertTrue(result["ok"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["processing_started"])
        self.assertEqual(result["runs"][0]["outcomes"], [{
            "key": "H1", "source_id": "vid-held-out", "start_sec": 12.5,
            "end_sec": 20.0, "expected_match": True, "score": 0.63, "decision": "match",
        }])
        self.assertNotIn("payload", result["runs"][0])
        self.assertNotIn("embedding", str(result))
        self.assertEqual(len(conn.sql), 1)
        self.assertIn("SELECT", conn.sql[0])
        self.assertNotIn("INSERT", conn.sql[0])

    def test_unavailable_evidence_returns_service_error(self):
        @contextmanager
        def unavailable():
            raise RuntimeError("database unavailable")
            yield

        with patch("memorybox.db.connection", unavailable):
            with self.assertRaises(HTTPException) as raised:
                app.review_voice_pilot_results()
        self.assertEqual(raised.exception.status_code, 503)

    def test_review_page_wires_read_only_results_to_existing_deep_link(self):
        html = (app.REVIEW_STATIC).read_text(encoding="utf-8")
        self.assertIn('id="voicePilotResults"', html)
        self.assertIn('/review/voice-pilot-results', html)
        self.assertIn('url.searchParams.set("video", sourceId)', html)
        self.assertIn('url.searchParams.set("t", String(startSec))', html)
        self.assertIn('loadVoicePilotResults();', html)


if __name__ == "__main__":
    unittest.main()
