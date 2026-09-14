"""Disposable PostgreSQL proofs for the I14 pre-load census. Never production load."""
from __future__ import annotations

import json
import os
import unittest

import psycopg
from psycopg.rows import dict_row

from memorybox.ops.i14_preload_census import CensusError, run_census
from tests.test_i14_prepared_loader import SQL_037, _payload, _hash
from tests.test_p2_i14_036_schema import SQL_036
from tests.test_p2_i14_lineage_pg import SQL_001, SQL_035, _DisposablePg, _apply_file

RFC_SQL = """
CREATE TABLE IF NOT EXISTS communication_rfc_ids (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  evidence_id UUID NOT NULL,
  role TEXT NOT NULL,
  rfc_message_id TEXT NOT NULL
)
"""


class PreloadCensusPg(_DisposablePg):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if cls.boot_error or not cls.dsn:
            return
        with psycopg.connect(cls.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            if str(conn.execute("SELECT current_database() AS db").fetchone()["db"]).lower() == "memorybox":
                cls.boot_error = "refused_memorybox_on_fixture_dsn"
                return
            _apply_file(conn, SQL_001)
            conn.execute(RFC_SQL)
            conn.commit()
            _apply_file(conn, SQL_035)
            conn.commit()
            _apply_file(conn, SQL_036)
            conn.commit()
            _apply_file(conn, SQL_037)
            conn.commit()

    def _wipe(self, conn) -> None:
        conn.execute(
            """
            TRUNCATE communication_rfc_ids, evidence, sources, people RESTART IDENTITY CASCADE
            """
        )
        conn.commit()

    def test_hold_reasons_long_thread_and_lineage(self) -> None:
        self._require_dsn()
        os.environ.pop("MEMORYBOX_I14_CENSUS_ALLOW_FLIGHTSIM", None)
        os.environ.pop("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB", None)
        with psycopg.connect(self.dsn, row_factory=dict_row, autocommit=False, connect_timeout=5) as conn:
            self._wipe(conn)
            assigned = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('mbox_import', 'household', 'file:household-mail.mbox', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]
            hold_a = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('mbox_import', 'tiny-a', 'file:synthetic-sample.mbox', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]
            hold_b = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('mbox_import', 'tiny-b', 'file:fixture-test.mbox', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]
            prev = None
            for i in range(1, 106):
                rfc = f"<c-{i}@example.test>"
                payload = _payload(
                    rfc=rfc,
                    body_text=f"Line {i}",
                    sent_at=f"2014-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00",
                    content_hash=_hash(rfc),
                    in_reply_to_ids=[prev] if prev else [],
                )
                eid = conn.execute(
                    """
                    INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                    VALUES ('communication', %s, 'c', %s::jsonb)
                    RETURNING id
                    """,
                    (assigned, json.dumps(payload)),
                ).fetchone()["id"]
                conn.execute(
                    """
                    INSERT INTO communication_rfc_ids (evidence_id, role, rfc_message_id)
                    VALUES (%s, 'own', %s)
                    """,
                    (eid, rfc),
                )
                prev = rfc
            extra = _payload(
                rfc="<c-1@example.test>",
                body_text="dup extract",
                content_hash=_hash("<c-1@example.test>"),
            )
            extra["rfc_message_id"] = "<c-1@example.test>"
            dup = conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'dup', %s::jsonb)
                RETURNING id
                """,
                (assigned, json.dumps(extra)),
            ).fetchone()["id"]
            conn.execute(
                """
                INSERT INTO communication_rfc_ids (evidence_id, role, rfc_message_id)
                VALUES (%s, 'own', '<c-1@example.test>')
                """,
                (dup,),
            )
            for i in range(5):
                p = _payload(rfc=f"<h-a-{i}@example.test>", body_text="hold a", content_hash=_hash(f"ha{i}"))
                conn.execute(
                    """
                    INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                    VALUES ('communication', %s, 'h', %s::jsonb)
                    """,
                    (hold_a, json.dumps(p)),
                )
            p1 = _payload(rfc="<h-b@example.test>", body_text="hold b", content_hash=_hash("hb"))
            conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'h', %s::jsonb)
                """,
                (hold_b, json.dumps(p1)),
            )
            conn.commit()
            report = run_census(
                conn,
                include_duplicate_audit=True,
                assign_threshold=10,
                batch_size=50,
                run_deadline_s=60,
                statement_timeout="15s",
            )
            conn.rollback()
            self.assertTrue(report["ok"])
            self.assertEqual(report["mbox_inventory"]["held_rows"], 6)
            self.assertEqual(report["mbox_inventory"]["held_unexplained_rows"], 0)
            reasons = {r["reason"]: r["rows"] for r in report["mbox_inventory"]["held_by_reason"]}
            self.assertEqual(sum(reasons.values()), 6)
            self.assertTrue(all("held_" in k for k in reasons))
            self.assertGreaterEqual(report["forecast"]["max_thread_size"], 100)
            self.assertGreaterEqual(report["forecast"]["threads_over_99"], 1)
            self.assertEqual(report["forecast"]["unexplained"], 0)
            self.assertGreaterEqual(report["forecast"]["identity_duplicates_omitted"], 1)
            self.assertEqual(
                report["forecast"]["omitted_with_survivor_lineage"],
                report["forecast"]["identity_duplicates_omitted"],
            )
            self.assertTrue(report["completeness"]["universe_check"])
            self.assertFalse(report["flightsim_writes"])
            self.assertEqual(report["duplicate_audit"]["ok"], True)

    def test_deadline_sanitized(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, autocommit=False, connect_timeout=5) as conn:
            self._wipe(conn)
            src = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('mbox_import', 'household', 'file:household-mail.mbox', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]
            conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'c', %s::jsonb)
                """,
                (src, json.dumps(_payload())),
            )
            conn.commit()
            import memorybox.ops.i14_preload_census as census
            from memorybox.ops.i14_duplicate_audit import failure_json

            original = census.load_messages_keyset

            def boom(*args, **kwargs):
                raise census.CensusError("run_deadline")

            census.load_messages_keyset = boom
            try:
                with self.assertRaises(CensusError) as ctx:
                    run_census(
                        conn,
                        include_duplicate_audit=False,
                        assign_threshold=1,
                        run_deadline_s=30,
                    )
                self.assertEqual(str(ctx.exception), "run_deadline")
            finally:
                census.load_messages_keyset = original
            fail = failure_json("run_deadline")
            self.assertFalse(fail["ok"])
            self.assertEqual(fail["error"], "run_deadline")
            self.assertEqual(list(fail.keys()), ["ok", "error"])
            conn.rollback()


if __name__ == "__main__":
    unittest.main()
