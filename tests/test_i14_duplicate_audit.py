"""Disposable tests for the I14 read-only duplicate audit. Never uses dbname memorybox."""
from __future__ import annotations

import inspect
import json
import unittest
import psycopg
from psycopg.rows import dict_row

from memorybox.ops import i14_duplicate_audit as audit
from memorybox.ops.i14_duplicate_audit import AuditError
from tests.test_p2_i14_lineage_pg import SQL_001, _DisposablePg, _apply_file

HASH_A = "a" * 64
HASH_B = "b" * 64


class DuplicateAuditUnits(unittest.TestCase):
    def test_uri_class_and_hash_shape(self) -> None:
        self.assertEqual(audit.uri_class(r"P:\photos\x.mbox"), "mbox")
        self.assertEqual(audit.uri_class("file:///tmp/x.ICS"), "ics")
        self.assertEqual(audit.uri_class("messages.csv"), "csv")
        self.assertEqual(audit.uri_class("/secret/path"), "other")
        self.assertEqual(audit.classify_hash("  " + HASH_A.upper() + "  "), (HASH_A, "ok"))
        self.assertEqual(audit.classify_hash(""), ("", "missing"))
        self.assertEqual(audit.classify_hash("not-a-hash"), ("not-a-hash", "invalid"))

    def test_counts_only_rejects_hex64(self) -> None:
        with self.assertRaises(AuditError):
            audit.assert_counts_only({"x": HASH_A})

    def test_module_does_not_use_hashtext(self) -> None:
        src = inspect.getsource(audit)
        self.assertNotIn("hashtext", src)


class DuplicateAuditPg(_DisposablePg):
    def test_audit_counts_without_emitting_hashes(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            db = conn.execute("SELECT current_database() AS db").fetchone()["db"]
            self.assertNotEqual(db.lower(), "memorybox")
            _apply_file(conn, SQL_001)
            conn.execute(
                """
                CREATE TABLE communication_rfc_ids (
                  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                  evidence_id UUID NOT NULL,
                  role TEXT NOT NULL,
                  rfc_message_id TEXT NOT NULL
                )
                """
            )
            src_a = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('mbox_import', 'a', 'synthetic:/mail-a.mbox', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]
            src_b = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('mbox_import', 'b', 'synthetic:/mail-b.mbox', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]
            src_c = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('ics_import', 'c', 'synthetic:/cal.ics', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]
            src_sms = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('sms_csv', 'sms', 'synthetic:/sms.csv', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]

            def ev(source_id, kind, payload):
                return conn.execute(
                    """
                    INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                    VALUES (%s, %s, 'x', %s::jsonb)
                    RETURNING id
                    """,
                    (kind, source_id, json.dumps(payload)),
                ).fetchone()["id"]

            e1 = ev(src_a, "communication", {"content_hash": HASH_A})
            ev(src_a, "communication", {"content_hash": HASH_A})
            e3 = ev(src_b, "communication", {"content_hash": HASH_A})
            ev(src_c, "calendar_event", {"content_hash": HASH_A})
            ev(src_a, "communication", {"content_hash": HASH_B})
            ev(src_a, "communication", {})
            ev(src_a, "communication", {"content_hash": "nope"})
            ev(src_sms, "communication", {"content_hash": HASH_B})
            conn.execute(
                """
                INSERT INTO communication_rfc_ids (evidence_id, role, rfc_message_id)
                VALUES (%s, 'own', '<same@example.test>'), (%s, 'own', '<same@example.test>')
                """,
                (e1, e3),
            )
            conn.commit()
            report = audit.run_audit(conn)
            conn.rollback()
            self.assertTrue(report["ok"])
            self.assertEqual(report["missing_hash"], 1)
            self.assertEqual(report["invalid_hash"], 1)
            self.assertEqual(report["within_source_duplicates"]["colliding_hashes"], 1)
            self.assertEqual(report["within_source_duplicates"]["extra_rows"], 1)
            self.assertEqual(
                report["cross_source_same_stream_or_cluster"]["mode"],
                "unassigned_cluster",
            )
            self.assertGreaterEqual(
                report["cross_source_same_stream_or_cluster"]["colliding_hashes"], 1
            )
            self.assertGreaterEqual(
                report["same_hash_different_streams_or_clusters"]["colliding_hashes"], 1
            )
            self.assertEqual(
                {row["uri_class"] for row in report["uri_class_inventory"]},
                {"mbox", "ics", "csv"},
            )
            self.assertEqual(report["rfc_own_fanout"]["token_groups"], 1)
            self.assertEqual(report["rfc_own_fanout"]["extra_evidence_rows"], 1)
            blob = json.dumps(report)
            self.assertNotIn(HASH_A, blob)
            self.assertNotIn(HASH_B, blob)
            self.assertNotIn("same@example.test", blob)
            self.assertNotIn("synthetic:/mail-a.mbox", blob)
            mapped = audit.run_audit(
                conn,
                stream_map={
                    str(src_a): "household_email",
                    str(src_b): "household_email",
                    str(src_c): "household_calendar",
                    str(src_sms): "household_sms",
                },
            )
            conn.rollback()
            self.assertEqual(mapped["cross_source_same_stream_or_cluster"]["mode"], "assigned_stream")
            self.assertGreaterEqual(
                mapped["cross_source_same_stream_or_cluster"]["colliding_hashes"], 1
            )
            self.assertGreaterEqual(
                mapped["same_hash_different_streams_or_clusters"]["colliding_hashes"], 1
            )
            audit.assert_counts_only(mapped)


if __name__ == "__main__":
    unittest.main()
