"""Disposable PostgreSQL proofs for the I14 duplicate-audit contract. Never uses production."""
from __future__ import annotations

import inspect
import json
import os
import unittest

import psycopg
from psycopg.rows import dict_row

from memorybox.ops import i14_duplicate_audit as audit
from memorybox.ops.i14_duplicate_audit import AuditError
from tests.test_p2_i14_lineage_pg import SQL_001, _DisposablePg, _apply_file

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_NEAR_1 = ("ab" * 31) + "aa"
HASH_NEAR_2 = ("ab" * 31) + "bb"
SECRET_URI = "synthetic:/private-mail-a.mbox"
SECRET_URI_B = "synthetic:/private-mail-b.mbox"
SECRET_ICS = "synthetic:/private-cal.ics"
SECRET_CSV = "synthetic:/private-sms.csv"
SECRET_SUBJECT = "CONFIDENTIAL_SUBJECT Re: family"
SECRET_BODY = "SECRET_BODY_TEXT do not emit"
SECRET_ADDR = "alice@example.test"
SECRET_RFC = "<same-secret@example.test>"

SNAP_SQL = """
SELECT
  (SELECT COUNT(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public') AS public_rels,
  (SELECT string_agg(c.relname, ',' ORDER BY c.relname)
     FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'i', 'S')) AS relnames,
  (SELECT COUNT(*) FROM sources) AS sources,
  (SELECT COUNT(*) FROM evidence) AS evidence,
  (SELECT COUNT(*) FROM communication_rfc_ids) AS rfc,
  (SELECT xmin::text FROM evidence ORDER BY id LIMIT 1) AS ev_xmin
"""


class DatabaseNameOverlay:
    """Disposable connection overlay so current_database() reports a forced name."""

    def __init__(self, conn, dbname: str):
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_dbname", dbname)
        object.__setattr__(self, "statements", [])

    def execute(self, query, params=None, **kwargs):
        text = query if isinstance(query, str) else str(query)
        self.statements.append(text)
        if params is None:
            cur = self._conn.execute(query, **kwargs)
        else:
            cur = self._conn.execute(query, params, **kwargs)
        if isinstance(query, str) and "current_database()" in query.lower():
            return _ForcedDbCursor(cur, self._dbname)
        return cur

    def commit(self):
        raise AssertionError("commit_called")

    def rollback(self):
        return self._conn.rollback()

    def __getattr__(self, name):
        return getattr(self._conn, name)


class _ForcedDbCursor:
    def __init__(self, cur, dbname: str):
        self._cur = cur
        self._dbname = dbname

    def fetchone(self):
        row = self._cur.fetchone()
        if isinstance(row, dict):
            out = dict(row)
            if "d" in out:
                out["d"] = self._dbname
            return out
        return (self._dbname,)

    def __getattr__(self, name):
        return getattr(self._cur, name)


class ExecuteSpy:
    def __init__(self, conn: psycopg.Connection):
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "statements", [])

    def execute(self, query, params=None, **kwargs):
        text = query if isinstance(query, str) else str(query)
        self.statements.append(text)
        if "commit" in text.lower() and text.strip().split()[0].lower() == "commit":
            raise AssertionError("commit_sql_issued")
        if params is None:
            return self._conn.execute(query, **kwargs)
        return self._conn.execute(query, params, **kwargs)

    def commit(self):
        raise AssertionError("commit_called")

    def rollback(self):
        return self._conn.rollback()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _snapshot(conn) -> dict:
    row = conn.execute(SNAP_SQL).fetchone()
    return dict(row)


def _temp_audit_tables(conn) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname LIKE 'pg_temp%'
           AND c.relname LIKE 'i14_audit%'
        """
    ).fetchone()
    return int(row["n"] if isinstance(row, dict) else row[0])


class DuplicateAuditUnits(unittest.TestCase):
    def test_uri_class_and_hash_shape(self) -> None:
        self.assertEqual(audit.uri_class(r"P:\photos\x.mbox"), "mbox")
        self.assertEqual(audit.classify_hash("  " + HASH_A.upper() + "  "), (HASH_A, "ok"))
        self.assertEqual(audit.classify_hash(""), ("", "missing"))
        self.assertEqual(audit.classify_hash("not-a-hash"), ("not-a-hash", "invalid"))

    def test_counts_only_rejects_hex_uuid_and_address(self) -> None:
        with self.assertRaises(AuditError):
            audit.assert_counts_only({"x": HASH_A})
        with self.assertRaises(AuditError):
            audit.assert_counts_only({"x": HASH_A[:16]})
        with self.assertRaises(AuditError):
            audit.assert_counts_only({"id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"})
        with self.assertRaises(AuditError):
            audit.assert_counts_only({"from": SECRET_ADDR})

    def test_load_sql_compares_full_hash_without_hashtext_or_prefix(self) -> None:
        load = audit._LOAD_SQL.lower()
        self.assertIn("payload_json->>'content_hash'", load)
        self.assertNotIn("hashtext", load)
        self.assertNotIn("left(", load)
        self.assertNotIn("substr(", load)
        self.assertNotIn("substring(", load)
        self.assertIn("limit %s offset %s", load)
        grouping = "\n".join(
            inspect.getsource(fn)
            for fn in (audit._within_source, audit._cross_source_in_cluster, audit._cross_cluster_or_stream)
        ).lower()
        self.assertNotIn("hashtext(", grouping)
        self.assertNotIn("left(content_hash", grouping)


class DuplicateAuditPg(_DisposablePg):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if cls.boot_error or not cls.dsn:
            return
        with psycopg.connect(cls.dsn, row_factory=dict_row, autocommit=False, connect_timeout=5) as conn:
            db = conn.execute("SELECT current_database() AS db").fetchone()["db"]
            if str(db).lower() == "memorybox":
                cls.boot_error = "refused_memorybox_on_fixture_dsn"
                return
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
            conn.commit()

    def _conn(self):
        self._require_dsn()
        return psycopg.connect(self.dsn, row_factory=dict_row, autocommit=False, connect_timeout=5)

    def _snap(self) -> dict:
        with self._conn() as conn:
            return _snapshot(conn)

    def _temp_count(self) -> int:
        with self._conn() as conn:
            return _temp_audit_tables(conn)

    def _truncate(self, conn) -> None:
        conn.execute("TRUNCATE communication_rfc_ids, evidence, sources CASCADE")
        conn.commit()

    def _seed(self, conn) -> dict:
        src_a = conn.execute(
            """
            INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
            VALUES ('mbox_import', 'a', %s, 'referenced')
            RETURNING id
            """,
            (SECRET_URI,),
        ).fetchone()["id"]
        src_b = conn.execute(
            """
            INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
            VALUES ('mbox_import', 'b', %s, 'referenced')
            RETURNING id
            """,
            (SECRET_URI_B,),
        ).fetchone()["id"]
        src_c = conn.execute(
            """
            INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
            VALUES ('ics_import', 'c', %s, 'referenced')
            RETURNING id
            """,
            (SECRET_ICS,),
        ).fetchone()["id"]
        src_sms = conn.execute(
            """
            INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
            VALUES ('sms_csv', 'sms', %s, 'referenced')
            RETURNING id
            """,
            (SECRET_CSV,),
        ).fetchone()["id"]

        def ev(source_id, kind, payload):
            return conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES (%s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    kind,
                    source_id,
                    SECRET_SUBJECT,
                    json.dumps(
                        {
                            **payload,
                            "subject": SECRET_SUBJECT,
                            "body": SECRET_BODY,
                            "from": SECRET_ADDR,
                        }
                    ),
                ),
            ).fetchone()["id"]

        e1 = ev(src_a, "communication", {"content_hash": HASH_A})
        ev(src_a, "communication", {"content_hash": HASH_A})
        e3 = ev(src_b, "communication", {"content_hash": HASH_A})
        ev(src_c, "calendar_event", {"content_hash": HASH_A})
        ev(src_a, "communication", {"content_hash": HASH_B})
        ev(src_a, "communication", {})
        ev(src_a, "communication", {"content_hash": "nope"})
        ev(src_sms, "communication", {"content_hash": HASH_B})
        ev(src_a, "communication", {"content_hash": HASH_NEAR_1})
        ev(src_sms, "communication", {"content_hash": HASH_NEAR_2})
        conn.execute(
            """
            INSERT INTO communication_rfc_ids (evidence_id, role, rfc_message_id)
            VALUES (%s, 'own', %s), (%s, 'own', %s)
            """,
            (e1, SECRET_RFC, e3, SECRET_RFC),
        )
        conn.commit()
        return {"src_a": src_a, "src_b": src_b, "src_c": src_c, "src_sms": src_sms, "e1": e1, "e3": e3}

    def _assert_private_absent(self, blob: str, ids: dict) -> None:
        for secret in (
            HASH_A,
            HASH_B,
            HASH_NEAR_1,
            HASH_NEAR_2,
            HASH_A[:16],
            HASH_NEAR_1[:32],
            SECRET_URI,
            SECRET_URI_B,
            SECRET_ICS,
            SECRET_CSV,
            SECRET_SUBJECT,
            SECRET_BODY,
            SECRET_ADDR,
            SECRET_RFC,
            "private-mail-a.mbox",
            str(ids["src_a"]),
            str(ids["e1"]),
        ):
            self.assertNotIn(secret, blob)

    def test_full_hash_compare_without_python_private_values(self) -> None:
        with self._conn() as conn:
            self._truncate(conn)
            ids = self._seed(conn)
            before = self._snap()
            spy = ExecuteSpy(conn)
            report = audit.run_audit(spy, batch_size=3)
            sql_blob = "\n".join(spy.statements).lower()
            self.assertNotIn("hashtext", sql_blob)
            self.assertNotIn("select distinct source_id", sql_blob)
            self.assertIn("limit %s offset %s", sql_blob)
            self.assertNotRegex(sql_blob, r"left\s*\(\s*lower\s*\(\s*btrim")
            self.assertNotRegex(sql_blob, r"substr(ing)?\s*\(")
            self.assertTrue(any("payload_json->>'content_hash'" in s.lower() for s in spy.statements))
            grouped = [s for s in spy.statements if "group by" in s.lower() and "content_hash" in s.lower()]
            self.assertTrue(grouped)
            for stmt in grouped:
                self.assertNotIn("left(", stmt.lower())
            self.assertEqual(report["within_source_duplicates"]["colliding_hashes"], 1)
            self.assertEqual(report["within_source_duplicates"]["extra_rows"], 1)
            self.assertEqual(report["missing_hash"], 1)
            self.assertEqual(report["invalid_hash"], 1)
            conn.rollback()
            self._assert_private_absent(json.dumps(report), ids)
            self.assertEqual(self._snap(), before)

    def test_counts_only_output_has_no_private_identifiers(self) -> None:
        with self._conn() as conn:
            self._truncate(conn)
            ids = self._seed(conn)
            report = audit.run_audit(conn)
            blob = json.dumps(report, sort_keys=True)
            conn.rollback()
            self.assertTrue(report["ok"])
            self.assertEqual(report["statement_timeout"], "30s")
            audit.assert_counts_only(report)
            self._assert_private_absent(blob, ids)
            self.assertNotIn("CONFIDENTIAL", blob)
            self.assertNotIn("SECRET_", blob)

    def test_missing_and_malformed_hashes_counted_separately(self) -> None:
        with self._conn() as conn:
            self._truncate(conn)
            self._seed(conn)
            report = audit.run_audit(conn)
            conn.rollback()
            self.assertEqual(report["missing_hash"], 1)
            self.assertEqual(report["invalid_hash"], 1)
            self.assertNotEqual(report["missing_hash"], report["invalid_hash"] + 10)
            within = report["within_source_duplicates"]
            self.assertEqual(within["colliding_hashes"], 1)
            self.assertEqual(within["extra_rows"], 1)

    def test_within_source_and_cross_source_groups_distinguished(self) -> None:
        with self._conn() as conn:
            self._truncate(conn)
            ids = self._seed(conn)
            report = audit.run_audit(conn)
            conn.rollback()
            within = report["within_source_duplicates"]
            cross = report["cross_source_same_stream_or_cluster"]
            spread = report["same_hash_different_streams_or_clusters"]
            self.assertEqual(within["colliding_hashes"], 1)
            self.assertEqual(within["extra_rows"], 1)
            self.assertEqual(within["sources_affected"], 1)
            self.assertEqual(cross["mode"], "unassigned_cluster")
            self.assertEqual(cross["colliding_hashes"], 1)
            self.assertEqual(cross["extra_rows"], 1)
            self.assertGreaterEqual(spread["colliding_hashes"], 2)
            mapped = audit.run_audit(
                conn,
                stream_map={
                    str(ids["src_a"]): "household_email",
                    str(ids["src_b"]): "household_email",
                    str(ids["src_c"]): "household_calendar",
                    str(ids["src_sms"]): "household_sms",
                },
            )
            conn.rollback()
            self.assertEqual(mapped["cross_source_same_stream_or_cluster"]["mode"], "assigned_stream")
            self.assertGreaterEqual(mapped["cross_source_same_stream_or_cluster"]["colliding_hashes"], 1)
            self.assertGreaterEqual(mapped["same_hash_different_streams_or_clusters"]["colliding_hashes"], 1)

    def test_production_name_refused_without_override(self) -> None:
        os.environ.pop("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB", None)
        with self._conn() as conn:
            self._truncate(conn)
            self._seed(conn)
            real_name = conn.execute("SELECT current_database() AS d").fetchone()["d"]
            conn.rollback()
            self.assertNotEqual(str(real_name).lower(), "memorybox")
            before = self._snap()
            overlay = DatabaseNameOverlay(conn, "memorybox")
            with self.assertRaises(AuditError) as ctx:
                audit.run_audit(overlay)
            self.assertEqual(str(ctx.exception), "refused_memorybox_dbname")
            self.assertFalse(audit.failure_json(str(ctx.exception))["ok"])
            sql_blob = "\n".join(overlay.statements).lower()
            self.assertIn("current_database()", sql_blob)
            self.assertNotIn("create temp table", sql_blob)
            conn.rollback()
            self.assertEqual(self._snap(), before)
            self.assertEqual(self._temp_count(), 0)

    def test_permitted_path_temp_only_no_commit_rollback_cleanup(self) -> None:
        with self._conn() as conn:
            self._truncate(conn)
            self._seed(conn)
            self.assertFalse(conn.autocommit)
            before = self._snap()
            self.assertEqual(self._temp_count(), 0)
            spy = ExecuteSpy(conn)
            report = audit.run_audit(spy)
            self.assertTrue(report["ok"])
            self.assertTrue(report["read_only_production_tables"])
            self.assertTrue(report["persistent_write_gate"])
            self.assertEqual(report["statement_timeout"], "30s")
            sql_blob = "\n".join(spy.statements).lower()
            self.assertNotIn("\ncommit", "\n" + sql_blob)
            self.assertFalse(any(s.strip().lower().startswith("commit") for s in spy.statements))
            self.assertTrue(any("create temp table i14_audit_hash_rows" in s.lower() for s in spy.statements))
            with self.assertRaises(AuditError):
                audit.catalog_execute(
                    spy,
                    "INSERT INTO evidence (evidence_kind, summary, payload_json) VALUES ('x', 'y', '{}'::jsonb)",
                )
            conn.rollback()
            self.assertEqual(self._snap(), before)
            self.assertEqual(self._temp_count(), 0)
            with self.assertRaises(AuditError) as ctx:
                audit.catalog_execute(conn, "CREATE TABLE i14_should_not_exist (id int)")
            self.assertEqual(str(ctx.exception), "persistent_write_refused")
            conn.rollback()

    def test_timeout_sanitized_failure_not_complete_data(self) -> None:
        with self._conn() as conn:
            self._truncate(conn)
            self._seed(conn)
            before = self._snap()
            original = audit._load_rows

            def sleepy(inner_conn, **kwargs):
                audit.catalog_execute(inner_conn, "SELECT pg_sleep(1)")
                return original(inner_conn, **kwargs)

            audit._load_rows = sleepy
            try:
                with self.assertRaises(AuditError) as ctx:
                    audit.run_audit(conn, statement_timeout="1ms")
            finally:
                audit._load_rows = original
            self.assertEqual(str(ctx.exception), "statement_timeout")
            fail = audit.failure_json(str(ctx.exception))
            self.assertEqual(fail, {"ok": False, "error": "statement_timeout"})
            self.assertNotIn(HASH_A, json.dumps(fail))
            conn.rollback()
            self.assertEqual(self._snap(), before)
            self.assertEqual(self._temp_count(), 0)

    def test_error_and_success_leave_persistent_relations_unchanged(self) -> None:
        with self._conn() as conn:
            self._truncate(conn)
            self._seed(conn)
            before = self._snap()
            report = audit.run_audit(conn)
            self.assertTrue(report["ok"])
            conn.rollback()
            after_ok = self._snap()
            self.assertEqual(after_ok, before)
            original = audit._create_temp

            def boom(inner_conn):
                original(inner_conn)
                raise AuditError("injected_failure")

            audit._create_temp = boom
            try:
                with self.assertRaises(AuditError):
                    audit.run_audit(conn)
            finally:
                audit._create_temp = original
            conn.rollback()
            self.assertEqual(self._snap(), before)
            self.assertEqual(self._temp_count(), 0)

    def test_postgres_rejects_temp_in_read_only_so_rollback_temp_is_used(self) -> None:
        with self._conn() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            with self.assertRaises(psycopg.errors.ReadOnlySqlTransaction):
                conn.execute("CREATE TEMP TABLE i14_should_fail (x int)")
            conn.rollback()


if __name__ == "__main__":
    unittest.main()
