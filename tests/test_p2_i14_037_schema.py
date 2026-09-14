"""Disposable PostgreSQL proofs for migration 037 evidence_ref scale. Never dbname memorybox."""
from __future__ import annotations

import unittest
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from tests.test_p2_i14_036_schema import SQL_036
from tests.test_p2_i14_lineage_pg import (
    SQL_001,
    SQL_035,
    _DisposablePg,
    _apply_file,
    _expect_fail,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_037 = ROOT / "memorybox" / "migrations" / "037_p2_i14_prepared_evidence_ref_scale.sql"


class DisposablePg037(_DisposablePg):
    def test_036_rejects_m100_037_accepts_and_keeps_m01(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            db = conn.execute("SELECT current_database() AS db").fetchone()["db"]
            self.assertNotEqual(str(db).lower(), "memorybox")
            _apply_file(conn, SQL_001)
            conn.commit()
            src = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('mbox_import', 'synthetic-src', 'synthetic:mbox-037', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]
            ev = conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'synthetic', '{}'::jsonb)
                RETURNING id
                """,
                (src,),
            ).fetchone()["id"]
            ev2 = conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'synthetic-2', '{}'::jsonb)
                RETURNING id
                """,
                (src,),
            ).fetchone()["id"]
            conn.commit()
            _apply_file(conn, SQL_035)
            conn.commit()
            _apply_file(conn, SQL_036)
            conn.commit()
            gen = conn.execute(
                """
                INSERT INTO comms_prepared_generations (algo_version)
                VALUES ('i14-prepared-email-v1')
                RETURNING id
                """
            ).fetchone()["id"]
            thread = conn.execute(
                """
                INSERT INTO comms_prepared_threads (
                    generation_id, thread_key, display_id, threading_confidence,
                    identity_confidence, gallery_eligibility, founder_review_state
                ) VALUES (
                    %s, 'rfc:long', 'T-0001', 'rfc', 'mixed', 'show_by_default', 'unreviewed'
                ) RETURNING id
                """,
                (gen,),
            ).fetchone()["id"]
            conn.commit()
            _expect_fail(
                conn,
                """
                INSERT INTO comms_prepared_messages (
                    thread_id, generation_id, ordinal, evidence_id, evidence_ref,
                    sent_at, authorship, commercial_class, direction
                ) VALUES (
                    %s, %s, 100, %s, 'T-0001-M-100', '2013-01-01T00:00:00+00:00',
                    'unverified', 'not_commercial', 'unresolved'
                )
                """,
                (thread, gen, ev),
            )
            _apply_file(conn, SQL_037)
            conn.commit()
            conn.execute(
                """
                INSERT INTO comms_prepared_messages (
                    thread_id, generation_id, ordinal, evidence_id, evidence_ref,
                    sent_at, authorship, commercial_class, direction
                ) VALUES (
                    %s, %s, 1, %s, 'T-0001-M-01', '2013-01-01T00:00:00+00:00',
                    'unverified', 'not_commercial', 'unresolved'
                )
                """,
                (thread, gen, ev),
            )
            conn.execute(
                """
                INSERT INTO comms_prepared_messages (
                    thread_id, generation_id, ordinal, evidence_id, evidence_ref,
                    sent_at, authorship, commercial_class, direction
                ) VALUES (
                    %s, %s, 100, %s, 'T-0001-M-100', '2013-01-01T00:01:00+00:00',
                    'unverified', 'not_commercial', 'unresolved'
                )
                """,
                (thread, gen, ev2),
            )
            conn.commit()
            ev3 = conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'synthetic-3', '{}'::jsonb)
                RETURNING id
                """,
                (src,),
            ).fetchone()["id"]
            conn.commit()
            _expect_fail(
                conn,
                """
                INSERT INTO comms_prepared_messages (
                    thread_id, generation_id, ordinal, evidence_id, evidence_ref,
                    sent_at, authorship, commercial_class, direction
                ) VALUES (
                    %s, %s, 2, %s, 'T-0001-M-1', '2013-01-01T00:02:00+00:00',
                    'unverified', 'not_commercial', 'unresolved'
                )
                """,
                (thread, gen, ev3),
            )


if __name__ == "__main__":
    unittest.main()
