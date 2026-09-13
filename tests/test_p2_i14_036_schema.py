"""Static and disposable-Postgres tests for I14 migration 036. Never uses dbname memorybox."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from memorybox.migrate import _migration_files
from memorybox.ops.i14_thread_review import message_sort_key
from tests.test_p2_i14_lineage_pg import (
    SQL_001,
    SQL_035,
    _DisposablePg,
    _apply_file,
    _expect_fail,
    _non_comms_column_fingerprint,
    _public_tables,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "memorybox" / "migrations"
SQL_036 = MIGRATIONS / "036_p2_i14_prepared_communications.sql"
FORBIDDEN = re.compile(
    r"(memorybox@|@gmail\.|@marvinbot|PRIVATEEMAIL|"
    r"P:\\photos|C:\\MemoryBox|\\\\media-server|"
    r"all mail including spam|"
    r"password=|oauth|Bearer |https?://)",
    re.I,
)
PREPARED_TABLES = {
    "comms_prepared_generations",
    "comms_prepared_threads",
    "comms_prepared_messages",
    "comms_prepared_participants",
    "comms_prepared_attachments",
}


def _sql() -> str:
    return SQL_036.read_text(encoding="utf-8")


class MigrationOrdering(unittest.TestCase):
    def test_036_follows_035_and_is_last(self) -> None:
        names = [p.name for p in _migration_files(MIGRATIONS)]
        self.assertLess(
            names.index("035_p2_i14_communications_lineage.sql"),
            names.index("036_p2_i14_prepared_communications.sql"),
        )
        self.assertEqual(names[-1], "036_p2_i14_prepared_communications.sql")

    def test_035_bytes_unchanged_marker(self) -> None:
        sql035 = (MIGRATIONS / "035_p2_i14_communications_lineage.sql").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("comms_prepared_generations", sql035)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS comms_prepared_", sql035)


class AdditiveSqlContract(unittest.TestCase):
    def test_additive_no_seeds_no_calendar_sms(self) -> None:
        sql = _sql()
        self.assertNotRegex(sql, r"(?i)alter table evidence\b")
        self.assertNotRegex(sql, r"(?i)drop table evidence\b")
        self.assertNotRegex(sql, r"(?i)\binsert\s+into\b")
        self.assertNotIn("CREATE TABLE person_contact_points", sql)
        self.assertNotIn("CREATE TABLE communication_rfc_ids", sql)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS comms_prepared_sms", sql)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS comms_prepared_calendar", sql)
        self.assertNotIn("ON DELETE SET NULL", sql)

    def test_integrity_clauses(self) -> None:
        sql = _sql()
        self.assertIn("UNIQUE (generation_id, evidence_id)", sql)
        self.assertIn("UNIQUE (thread_id, ordinal)", sql)
        self.assertIn("UNIQUE (message_id, attachment_ordinal)", sql)
        self.assertIn("REFERENCES evidence (id) ON DELETE RESTRICT", sql)
        self.assertIn("REFERENCES comms_record_identities (id) ON DELETE RESTRICT", sql)
        self.assertIn("REFERENCES people (id) ON DELETE RESTRICT", sql)
        self.assertIn("retain_life_evidence", sql)
        self.assertIn("suppress_default", sql)
        self.assertIn("quote_contamination_flagged", sql)
        self.assertIn("comms_prepared_activate_generation", sql)
        self.assertIn("uq_comms_prepared_one_active", sql)
        self.assertIn("CHECK (role IN ('from', 'to', 'cc'))", sql)

    def test_rollback_order_documented(self) -> None:
        comment = _sql().split("CREATE TABLE", 1)[0]
        markers = [
            "comms_prepared_active_generations",
            "comms_prepared_activate_generation",
            "comms_prepared_guard_activation",
            "comms_prepared_message_generation_guard",
            "comms_prepared_attachments",
            "comms_prepared_participants",
            "comms_prepared_messages",
            "comms_prepared_threads",
            "comms_prepared_generations",
        ]
        positions = [comment.find(m) for m in markers]
        self.assertTrue(all(p >= 0 for p in positions))
        self.assertEqual(positions, sorted(positions))

    def test_no_private_material_or_deploy_path(self) -> None:
        sql = _sql()
        self.assertIsNone(FORBIDDEN.search(sql))
        self.assertNotIn("MEMORYBOX_DATABASE_URL", sql)
        self.assertNotIn("i14_migration_035", sql)
        self.assertNotIn("Deploy-I14", sql)


class SortKeyContract(unittest.TestCase):
    def test_utc_instant_then_evidence_id(self) -> None:
        early = {
            "timestamp": "2025-12-18T14:57:13+00:00",
            "evidence_id": "b",
        }
        late = {
            "timestamp": "2025-12-18T09:13:25-06:00",
            "evidence_id": "a",
        }
        self.assertLess(message_sort_key(early), message_sort_key(late))
        tie_a = {"timestamp": "2025-01-01T00:00:00+00:00", "evidence_id": "aaa"}
        tie_b = {"timestamp": "2025-01-01T00:00:00+00:00", "evidence_id": "bbb"}
        self.assertLess(message_sort_key(tie_a), message_sort_key(tie_b))


class DisposablePg036(_DisposablePg):
    def test_036_contract_on_disposable_postgres(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            db = conn.execute("SELECT current_database() AS db").fetchone()["db"]
            self.assertNotEqual(db.lower(), "memorybox")
            self.assertNotIn("memorybox", self.dsn.lower().rsplit("/", 1)[-1])
            _apply_file(conn, SQL_001)
            conn.commit()
            src = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('mbox_import', 'synthetic-src', 'synthetic:mbox-036', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]
            ev1 = conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'e1', '{}'::jsonb)
                RETURNING id, updated_at
                """,
                (src,),
            ).fetchone()
            ev2 = conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'e2', '{}'::jsonb)
                RETURNING id
                """,
                (src,),
            ).fetchone()["id"]
            ev3 = conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'e3', '{}'::jsonb)
                RETURNING id
                """,
                (src,),
            ).fetchone()["id"]
            person_a = conn.execute(
                "INSERT INTO people (display_name, status) VALUES ('Alpha', 'confirmed') RETURNING id"
            ).fetchone()["id"]
            person_b = conn.execute(
                "INSERT INTO people (display_name, status) VALUES ('Beta', 'confirmed') RETURNING id"
            ).fetchone()["id"]
            conn.commit()
            _apply_file(conn, SQL_035)
            conn.commit()
            lineage_n = conn.execute(
                "SELECT COUNT(*) AS n FROM comms_logical_sources"
            ).fetchone()["n"]
            evidence_before = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(length(summary)),0) AS s FROM evidence"
            ).fetchone()
            fingerprint_before = _non_comms_column_fingerprint(conn)
            _apply_file(conn, SQL_036)
            conn.commit()
            evidence_after = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(length(summary)),0) AS s FROM evidence"
            ).fetchone()
            self.assertEqual(evidence_before, evidence_after)
            self.assertEqual(fingerprint_before, _non_comms_column_fingerprint(conn))
            self.assertEqual(
                lineage_n,
                conn.execute("SELECT COUNT(*) AS n FROM comms_logical_sources").fetchone()["n"],
            )
            still = conn.execute(
                "SELECT updated_at FROM evidence WHERE id = %s", (ev1["id"],)
            ).fetchone()["updated_at"]
            self.assertEqual(still, ev1["updated_at"])
            tables = _public_tables(conn)
            self.assertTrue(PREPARED_TABLES.issubset(tables))
            self.assertNotIn("comms_prepared_calendar", tables)
            self.assertNotIn("comms_prepared_sms", tables)
            for table in PREPARED_TABLES:
                n = conn.execute(
                    f"SELECT COUNT(*) AS n FROM {table}"  # noqa: S608
                ).fetchone()["n"]
                self.assertEqual(n, 0)

            defs = "\n".join(
                r["d"]
                for r in conn.execute(
                    """
                    SELECT pg_get_constraintdef(oid) AS d
                    FROM pg_constraint
                    WHERE conrelid::regclass::text LIKE 'comms_prepared_%'
                    """
                ).fetchall()
            ).replace(" ", "")
            self.assertIn("REFERENCESevidence(id)ONDELETERESTRICT", defs)
            self.assertNotIn("ONDELETESETNULL", defs)

            log_id = conn.execute(
                """
                INSERT INTO comms_logical_sources (logical_key, source_kind, label)
                VALUES ('stream_email', 'email', 'Synthetic stream') RETURNING id
                """
            ).fetchone()["id"]
            gen = conn.execute(
                """
                INSERT INTO comms_prepared_generations (algo_version, logical_source_id)
                VALUES ('i14-prepared-email-v1', %s)
                RETURNING id, published, is_active, status
                """,
                (log_id,),
            ).fetchone()
            conn.commit()
            self.assertFalse(gen["published"])
            self.assertFalse(gen["is_active"])
            self.assertEqual(gen["status"], "building")
            active = conn.execute(
                "SELECT COUNT(*) AS n FROM comms_prepared_active_generations"
            ).fetchone()["n"]
            self.assertEqual(active, 0)
            _expect_fail(
                conn,
                """
                INSERT INTO comms_prepared_generations (
                    algo_version, logical_source_id, published, is_active, status, checksum
                ) VALUES (
                    'i14-prepared-email-v1', %s, TRUE, TRUE, 'published', %s
                )
                """,
                (log_id, "a" * 64),
            )
            _expect_fail(
                conn,
                """
                UPDATE comms_prepared_generations
                SET published = TRUE, is_active = TRUE, status = 'published', checksum = %s
                WHERE id = %s
                """,
                ("a" * 64, gen["id"]),
            )

            conn.execute(
                """
                UPDATE comms_prepared_generations
                SET status = 'validated', checksum = %s, item_count = 2
                WHERE id = %s
                """,
                ("b" * 64, gen["id"]),
            )
            conn.commit()
            conn.execute("SELECT comms_prepared_activate_generation(%s)", (gen["id"],))
            conn.commit()
            live = conn.execute(
                "SELECT published, is_active, status FROM comms_prepared_generations WHERE id = %s",
                (gen["id"],),
            ).fetchone()
            self.assertTrue(live["published"])
            self.assertTrue(live["is_active"])
            self.assertEqual(live["status"], "published")
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM comms_prepared_active_generations"
                ).fetchone()["n"],
                1,
            )

            gen2 = conn.execute(
                """
                INSERT INTO comms_prepared_generations (algo_version, logical_source_id)
                VALUES ('i14-prepared-email-v1', %s)
                RETURNING id
                """,
                (log_id,),
            ).fetchone()["id"]
            conn.execute(
                """
                UPDATE comms_prepared_generations
                SET status = 'validated', checksum = %s
                WHERE id = %s
                """,
                ("c" * 64, gen2),
            )
            conn.commit()
            conn.execute("SELECT comms_prepared_activate_generation(%s)", (gen2,))
            conn.commit()
            rows = conn.execute(
                """
                SELECT id, status, is_active, published
                FROM comms_prepared_generations
                WHERE id IN (%s, %s)
                ORDER BY created_at
                """,
                (gen["id"], gen2),
            ).fetchall()
            by_id = {r["id"]: r for r in rows}
            self.assertEqual(by_id[gen["id"]]["status"], "superseded")
            self.assertFalse(by_id[gen["id"]]["is_active"])
            self.assertTrue(by_id[gen2]["is_active"])
            self.assertEqual(
                conn.execute(
                    "SELECT id FROM comms_prepared_active_generations"
                ).fetchone()["id"],
                gen2,
            )

            failed = conn.execute(
                """
                INSERT INTO comms_prepared_generations (algo_version, logical_source_id)
                VALUES ('i14-prepared-email-v1', %s)
                RETURNING id
                """,
                (log_id,),
            ).fetchone()["id"]
            conn.execute(
                "UPDATE comms_prepared_generations SET status = 'failed' WHERE id = %s",
                (failed,),
            )
            conn.commit()
            _expect_fail(
                conn,
                "SELECT comms_prepared_activate_generation(%s)",
                (failed,),
            )

            thread = conn.execute(
                """
                INSERT INTO comms_prepared_threads (
                    generation_id, thread_key, display_id, threading_confidence,
                    identity_confidence, gallery_eligibility, suppression_reason,
                    founder_review_state
                ) VALUES (
                    %s, 'rfc:one', 'T-0001', 'rfc', 'mixed', 'suppress_default',
                    'commercial_suppress_default', 'accept_thread'
                ) RETURNING id
                """,
                (gen2,),
            ).fetchone()["id"]
            conn.commit()
            other_gen = conn.execute(
                """
                INSERT INTO comms_prepared_generations (algo_version)
                VALUES ('i14-prepared-email-v1')
                RETURNING id
                """
            ).fetchone()["id"]
            conn.commit()
            _expect_fail(
                conn,
                """
                INSERT INTO comms_prepared_messages (
                    thread_id, generation_id, ordinal, evidence_id, evidence_ref,
                    sent_at, authorship, commercial_class, direction
                ) VALUES (
                    %s, %s, 1, %s, 'T-0001-M-01', '2025-12-18T14:57:13+00:00',
                    'unverified', 'not_commercial', 'unresolved'
                )
                """,
                (thread, other_gen, ev1["id"]),
            )

            msgs = [
                {
                    "timestamp": "2025-12-18T09:13:25-06:00",
                    "evidence_id": str(ev2),
                    "eid": ev2,
                },
                {
                    "timestamp": "2025-12-18T14:57:13+00:00",
                    "evidence_id": str(ev1["id"]),
                    "eid": ev1["id"],
                },
            ]
            ordered = sorted(msgs, key=message_sort_key)
            self.assertEqual(ordered[0]["eid"], ev1["id"])
            self.assertEqual(ordered[1]["eid"], ev2)
            for i, item in enumerate(ordered, start=1):
                conn.execute(
                    """
                    INSERT INTO comms_prepared_messages (
                        thread_id, generation_id, ordinal, evidence_id, evidence_ref,
                        sent_at, authorship, commercial_class, direction,
                        quote_quality, identity_quality, voice_corpus, urls_stripped,
                        forward_status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        'authenticated_other', 'not_commercial', 'sent_to_focal_other_author',
                        'clean', 'resolved', FALSE, TRUE, 'none'
                    )
                    """,
                    (
                        thread,
                        gen2,
                        i,
                        item["eid"],
                        f"T-0001-M-{i:02d}",
                        item["timestamp"],
                    ),
                )
            conn.commit()
            _expect_fail(
                conn,
                """
                INSERT INTO comms_prepared_messages (
                    thread_id, generation_id, ordinal, evidence_id, evidence_ref,
                    sent_at, authorship, commercial_class, direction
                ) VALUES (
                    %s, %s, 3, %s, 'T-0001-M-03', '2025-12-18T15:00:00+00:00',
                    'unverified', 'not_commercial', 'unresolved'
                )
                """,
                (thread, gen2, ev1["id"]),
            )
            _expect_fail(
                conn,
                """
                INSERT INTO comms_prepared_messages (
                    thread_id, generation_id, ordinal, evidence_id, evidence_ref,
                    sent_at, authorship, commercial_class, direction, voice_corpus,
                    quote_quality
                ) VALUES (
                    %s, %s, 3, %s, 'T-0001-M-03', '2025-12-18T16:00:00+00:00',
                    'authenticated_focal', 'not_commercial', 'sent_by_focal', TRUE,
                    'unresolved_contamination'
                )
                """,
                (thread, gen2, ev3),
            )
            flagged = conn.execute(
                """
                INSERT INTO comms_prepared_messages (
                    thread_id, generation_id, ordinal, evidence_id, evidence_ref,
                    sent_at, authorship, commercial_class, direction,
                    quote_quality, identity_quality, voice_corpus
                ) VALUES (
                    %s, %s, 3, %s, 'T-0001-M-03', '2025-12-18T16:00:00+00:00',
                    'authenticated_focal', 'retain_life_evidence', 'sent_by_focal',
                    'suspected_contamination', 'resolved', FALSE
                )
                RETURNING id, quote_contamination_flagged, voice_corpus
                """,
                (thread, gen2, ev3),
            ).fetchone()
            self.assertTrue(flagged["quote_contamination_flagged"])
            self.assertFalse(flagged["voice_corpus"])
            msg_id = conn.execute(
                """
                SELECT id FROM comms_prepared_messages
                WHERE generation_id = %s AND ordinal = 1
                """,
                (gen2,),
            ).fetchone()["id"]
            conn.execute(
                """
                INSERT INTO comms_prepared_participants (
                    message_id, role, display_name, address_normalized,
                    identity_confidence, person_id
                ) VALUES
                    (%s, 'from', 'Alpha', 'alpha@example.test', 'authenticated_other', %s),
                    (%s, 'to', 'Beta', 'beta@example.test', 'authenticated_other', %s)
                """,
                (msg_id, person_a, msg_id, person_b),
            )
            people_n = conn.execute(
                """
                SELECT COUNT(DISTINCT person_id) AS people,
                       COUNT(DISTINCT message_id) AS messages
                FROM comms_prepared_participants
                WHERE message_id = %s
                """,
                (msg_id,),
            ).fetchone()
            self.assertEqual(people_n["people"], 2)
            self.assertEqual(people_n["messages"], 1)
            self.assertEqual(
                conn.execute(
                    """
                    SELECT COUNT(*) AS n FROM comms_prepared_messages
                    WHERE generation_id = %s AND evidence_id = %s
                    """,
                    (gen2, ordered[0]["eid"]),
                ).fetchone()["n"],
                1,
            )
            conn.execute(
                """
                INSERT INTO comms_prepared_attachments (
                    message_id, evidence_id, attachment_ordinal, filename,
                    mime_type, disposition, gallery_action
                ) VALUES
                    (%s, %s, 1, 'photo.jpg', 'image/jpeg', 'inline', 'view_image'),
                    (%s, %s, 2, 'notes.bin', 'application/octet-stream', 'attachment', 'record_only')
                """,
                (msg_id, ev1["id"], msg_id, ev1["id"]),
            )
            conn.commit()
            _expect_fail(
                conn,
                """
                INSERT INTO comms_prepared_attachments (
                    message_id, evidence_id, attachment_ordinal, filename,
                    mime_type, disposition, gallery_action
                ) VALUES (%s, %s, 1, 'dup.jpg', 'image/jpeg', 'inline', 'view_image')
                """,
                (msg_id, ev1["id"]),
            )
            _expect_fail(
                conn,
                """
                UPDATE comms_prepared_messages
                SET commercial_class = 'commercial_suppress'
                WHERE id = %s
                """,
                (flagged["id"],),
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM comms_prepared_attachments WHERE message_id = %s",
                    (msg_id,),
                ).fetchone()["n"],
                2,
            )

            conn.execute("DROP VIEW IF EXISTS comms_prepared_active_generations")
            conn.execute(
                "DROP FUNCTION IF EXISTS comms_prepared_activate_generation(uuid)"
            )
            conn.execute(
                "DROP TRIGGER IF EXISTS trg_comms_prepared_guard_activation ON comms_prepared_generations"
            )
            conn.execute("DROP FUNCTION IF EXISTS comms_prepared_guard_activation()")
            conn.execute(
                "DROP TRIGGER IF EXISTS trg_comms_prepared_message_generation_guard ON comms_prepared_messages"
            )
            conn.execute(
                "DROP FUNCTION IF EXISTS comms_prepared_message_generation_guard()"
            )
            conn.execute("DROP TABLE comms_prepared_attachments")
            conn.execute("DROP TABLE comms_prepared_participants")
            conn.execute("DROP TABLE comms_prepared_messages")
            conn.execute("DROP TABLE comms_prepared_threads")
            conn.execute("DROP TABLE comms_prepared_generations")
            conn.commit()
            self.assertFalse(PREPARED_TABLES & _public_tables(conn))
            self.assertIn("comms_logical_sources", _public_tables(conn))
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"],
                evidence_after["n"],
            )


if __name__ == "__main__":
    unittest.main()
