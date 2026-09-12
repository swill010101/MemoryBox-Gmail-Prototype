"""Disposable PostgreSQL tests for I14 migration 035. Never uses the memorybox DB."""
from __future__ import annotations

import socket
import subprocess
import time
import unittest
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from memorybox.migrate import _BOOTSTRAP, _migration_files, _sql_statements

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "memorybox" / "migrations"
SQL_001 = MIGRATIONS / "001_domain_v0.sql"
SQL_035 = MIGRATIONS / "035_p2_i14_communications_lineage.sql"

ADMIN_DSN = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
_DOCKER_PROBE: tuple[bool, str] | None = None
COMMS_TABLES = {
    "comms_logical_sources",
    "comms_source_memberships",
    "comms_extract_instances",
    "comms_source_checkpoint",
    "comms_record_identities",
    "comms_record_identity_aliases",
}


def docker_ok() -> tuple[bool, str]:
    global _DOCKER_PROBE
    if _DOCKER_PROBE is not None:
        return _DOCKER_PROBE
    try:
        proc = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=12,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        _DOCKER_PROBE = (False, type(exc).__name__)
        return _DOCKER_PROBE
    if proc.returncode != 0:
        _DOCKER_PROBE = (False, "docker_info_failed")
        return _DOCKER_PROBE
    _DOCKER_PROBE = (True, "ok")
    return _DOCKER_PROBE


def _start_docker() -> tuple[str, str]:
    ok, reason = docker_ok()
    if not ok:
        return "", reason
    port = _free_port()
    container = "i14-035-" + uuid4().hex[:10]
    user = "i14test"
    password = "i14test"
    dbname = "i14_035"
    run = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            container,
            "-e",
            f"POSTGRES_USER={user}",
            "-e",
            f"POSTGRES_PASSWORD={password}",
            "-e",
            f"POSTGRES_DB={dbname}",
            "-p",
            f"127.0.0.1:{port}:5432",
            "postgres:16-alpine",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if run.returncode != 0:
        return "", "docker_run_failed"
    dsn = f"postgresql://{user}:{password}@127.0.0.1:{port}/{dbname}"
    deadline = time.time() + 45
    while time.time() < deadline:
        try:
            with psycopg.connect(dsn, connect_timeout=2) as conn:
                conn.execute("SELECT 1")
            return dsn, container
        except Exception:
            time.sleep(0.4)
    subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=30)
    return "", "postgres_not_ready"


def _start_local_db() -> tuple[str, str]:
    name = "i14_035_" + uuid4().hex[:12]
    if not name.replace("_", "").isalnum() or name.lower() == "memorybox":
        return "", "invalid_db_name"
    try:
        with psycopg.connect(ADMIN_DSN, autocommit=True, connect_timeout=3) as admin:
            db = admin.execute("SELECT current_database() AS d").fetchone()[0]
            if str(db).lower() == "memorybox":
                return "", "refused_memorybox_admin"
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    except Exception as exc:
        return "", type(exc).__name__
    dsn = "postgresql://postgres:postgres@127.0.0.1:5432/" + name
    return dsn, name


def _drop_local_db(name: str) -> None:
    if not name.startswith("i14_035_"):
        return
    with psycopg.connect(ADMIN_DSN, autocommit=True, connect_timeout=3) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _apply_file(conn: psycopg.Connection, path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    try:
        conn.execute(text)
        return
    except Exception:
        conn.rollback()
    for stmt in _sql_statements(text):
        conn.execute(stmt)


def _expect_fail(conn: psycopg.Connection, sql_text: str, params: tuple) -> None:
    try:
        conn.execute(sql_text, params)
        conn.commit()
    except psycopg.Error:
        conn.rollback()
        return
    conn.rollback()
    raise AssertionError("expected_constraint_failure")


def _public_tables(conn: psycopg.Connection) -> set[str]:
    return {
        r["t"]
        for r in conn.execute(
            "SELECT tablename AS t FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    }


def _non_comms_column_fingerprint(conn: psycopg.Connection) -> str:
    row = conn.execute(
        """
        SELECT md5(string_agg(table_name || '.' || column_name || ':' || data_type, ','
                              ORDER BY table_name, ordinal_position)) AS h
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name NOT LIKE 'comms_%'
        """
    ).fetchone()
    return str(row["h"] if isinstance(row, dict) else row[0])


class _DisposablePg(unittest.TestCase):
    container = ""
    local_db = ""
    dsn = ""
    boot_error = ""

    @classmethod
    def setUpClass(cls) -> None:
        dsn, token = _start_docker()
        if dsn:
            cls.dsn = dsn
            cls.container = token
            return
        dsn, name = _start_local_db()
        if dsn:
            cls.dsn = dsn
            cls.local_db = name
            return
        cls.boot_error = token or name or "no_disposable_postgres"

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.container:
            subprocess.run(["docker", "rm", "-f", cls.container], capture_output=True, timeout=30)
        if cls.local_db:
            _drop_local_db(cls.local_db)

    def _require_dsn(self) -> None:
        if self.boot_error or not self.dsn:
            self.fail(
                "Disposable PostgreSQL is unavailable ("
                + (self.boot_error or "no_dsn")
                + "). Static SQL tests are not sufficient for migration 035."
            )


class DisposablePg035(_DisposablePg):
    def test_035_constraints_on_disposable_postgres(self) -> None:
        self._require_dsn()
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            db = conn.execute("SELECT current_database() AS db").fetchone()["db"]
            self.assertNotEqual(db.lower(), "memorybox")
            _apply_file(conn, SQL_001)
            conn.commit()
            src_a = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('mbox_import', 'synthetic-a', 'synthetic:mbox-a', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]
            ev_keep = conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'keep', '{}'::jsonb)
                RETURNING id, updated_at
                """,
                (src_a,),
            ).fetchone()
            before = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(length(summary)),0) AS s FROM evidence"
            ).fetchone()
            conn.commit()
            _apply_file(conn, SQL_035)
            conn.commit()
            after = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(length(summary)),0) AS s FROM evidence"
            ).fetchone()
            self.assertEqual(before["n"], after["n"])
            self.assertEqual(before["s"], after["s"])
            still = conn.execute(
                "SELECT id, updated_at FROM evidence WHERE id = %s",
                (ev_keep["id"],),
            ).fetchone()
            self.assertEqual(still["updated_at"], ev_keep["updated_at"])

            nullable = conn.execute(
                """
                SELECT is_nullable FROM information_schema.columns
                WHERE table_name = 'comms_record_identities' AND column_name = 'evidence_id'
                """
            ).fetchone()["is_nullable"]
            self.assertEqual(nullable, "NO")

            defs = [
                r["d"]
                for r in conn.execute(
                    """
                    SELECT pg_get_constraintdef(oid) AS d
                    FROM pg_constraint
                    WHERE conrelid::regclass::text LIKE 'comms_%'
                    """
                ).fetchall()
            ]
            compact = "\n".join(defs).replace(" ", "")
            self.assertIn("REFERENCESevidence(id)ONDELETERESTRICT", compact)
            self.assertIn("REFERENCESsources(id)ONDELETERESTRICT", compact)
            self.assertIn("REFERENCEScomms_source_memberships(source_id,logical_source_id)ONDELETERESTRICT", compact)
            self.assertNotIn("ONDELETESETNULL", compact)

            uniq_source = conn.execute(
                """
                SELECT pg_get_constraintdef(oid) AS d
                FROM pg_constraint
                WHERE conrelid = 'comms_extract_instances'::regclass
                  AND contype = 'u'
                  AND replace(pg_get_constraintdef(oid), ' ', '') = 'UNIQUE(source_id)'
                """
            ).fetchone()
            self.assertIsNone(uniq_source)

            idx = conn.execute(
                """
                SELECT i.indisunique AS u
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                WHERE c.relname = 'idx_comms_extract_instances_source'
                """
            ).fetchone()
            self.assertIsNotNone(idx)
            self.assertFalse(idx["u"])

            log_a = conn.execute(
                """
                INSERT INTO comms_logical_sources (logical_key, source_kind, label)
                VALUES ('family', 'email', 'Family email') RETURNING id
                """
            ).fetchone()["id"]
            log_b = conn.execute(
                """
                INSERT INTO comms_logical_sources (logical_key, source_kind, label)
                VALUES ('family', 'calendar', 'Family calendar') RETURNING id
                """
            ).fetchone()["id"]
            conn.commit()
            _expect_fail(
                conn,
                """
                INSERT INTO comms_logical_sources (logical_key, source_kind, label)
                VALUES ('family', 'email', 'dup')
                """,
                (),
            )

            conn.execute(
                """
                INSERT INTO comms_source_memberships (source_id, logical_source_id)
                VALUES (%s, %s)
                """,
                (src_a, log_a),
            )
            conn.commit()
            _expect_fail(
                conn,
                """
                INSERT INTO comms_source_memberships (source_id, logical_source_id)
                VALUES (%s, %s)
                """,
                (src_a, log_b),
            )

            fp_a = "a" * 64
            fp_b = "b" * 64
            ext_a = conn.execute(
                """
                INSERT INTO comms_extract_instances (
                    logical_source_id, source_id, fingerprint, landing_alias, landing_basename
                ) VALUES (%s, %s, %s, 'family', 'export-a.mbox') RETURNING id
                """,
                (log_a, src_a, fp_a),
            ).fetchone()["id"]
            ext_a_later = conn.execute(
                """
                INSERT INTO comms_extract_instances (
                    logical_source_id, source_id, fingerprint, landing_alias, landing_basename
                ) VALUES (%s, %s, %s, 'family', 'export-b.mbox') RETURNING id
                """,
                (log_a, src_a, fp_b),
            ).fetchone()["id"]
            same_source = conn.execute(
                """
                SELECT COUNT(*) AS n FROM comms_extract_instances
                WHERE source_id = %s AND logical_source_id = %s
                """,
                (src_a, log_a),
            ).fetchone()["n"]
            self.assertEqual(same_source, 2)
            self.assertNotEqual(ext_a, ext_a_later)
            conn.commit()
            _expect_fail(
                conn,
                """
                INSERT INTO comms_extract_instances (
                    logical_source_id, source_id, fingerprint, landing_alias, landing_basename
                ) VALUES (%s, %s, %s, 'family', 'export-a-again.mbox')
                """,
                (log_a, src_a, fp_a),
            )
            _expect_fail(
                conn,
                """
                INSERT INTO comms_extract_instances (
                    logical_source_id, source_id, fingerprint, landing_alias, landing_basename
                ) VALUES (%s, %s, %s, 'family', 'export-wrong-lineage.mbox')
                """,
                (log_b, src_a, "c" * 64),
            )

            src_cal = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('ics_import', 'synthetic-cal', 'synthetic:ics-a', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]
            conn.execute(
                """
                INSERT INTO comms_source_memberships (source_id, logical_source_id)
                VALUES (%s, %s)
                """,
                (src_cal, log_b),
            )
            ext_b = conn.execute(
                """
                INSERT INTO comms_extract_instances (
                    logical_source_id, source_id, fingerprint, landing_alias, landing_basename
                ) VALUES (%s, %s, %s, 'family', 'export-a.ics') RETURNING id
                """,
                (log_b, src_cal, fp_a),
            ).fetchone()["id"]
            conn.commit()
            _expect_fail(
                conn,
                """
                INSERT INTO comms_source_checkpoint
                    (logical_source_id, current_extract_instance_id)
                VALUES (%s, %s)
                """,
                (log_a, ext_b),
            )
            conn.execute(
                """
                INSERT INTO comms_source_checkpoint
                    (logical_source_id, current_extract_instance_id)
                VALUES (%s, %s)
                """,
                (log_a, ext_a),
            )
            conn.commit()

            ck_del = conn.execute(
                """
                SELECT c.confdeltype AS d
                FROM pg_constraint c
                WHERE c.conrelid = 'comms_source_checkpoint'::regclass
                  AND c.contype = 'f'
                  AND pg_get_constraintdef(c.oid) LIKE '%current_extract_instance_id%'
                """
            ).fetchone()["d"]
            self.assertEqual(ck_del, "r")
            _expect_fail(
                conn,
                "DELETE FROM comms_extract_instances WHERE id = %s",
                (ext_a,),
            )
            still_ck = conn.execute(
                """
                SELECT logical_source_id, current_extract_instance_id
                FROM comms_source_checkpoint
                WHERE logical_source_id = %s
                """,
                (log_a,),
            ).fetchone()
            self.assertEqual(still_ck["logical_source_id"], log_a)
            self.assertEqual(still_ck["current_extract_instance_id"], ext_a)
            conn.execute("DELETE FROM comms_extract_instances WHERE id = %s", (ext_a_later,))
            conn.commit()
            after_unreferenced = conn.execute(
                """
                SELECT current_extract_instance_id
                FROM comms_source_checkpoint WHERE logical_source_id = %s
                """,
                (log_a,),
            ).fetchone()
            self.assertEqual(after_unreferenced["current_extract_instance_id"], ext_a)
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM comms_extract_instances WHERE id = %s",
                    (ext_a,),
                ).fetchone()["n"],
                1,
            )

            ev2 = conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'mapped', '{}'::jsonb) RETURNING id
                """,
                (src_a,),
            ).fetchone()["id"]
            rec = conn.execute(
                """
                INSERT INTO comms_record_identities (
                    logical_source_id, evidence_id, source_kind, first_extract_instance_id
                ) VALUES (%s, %s, 'email', %s) RETURNING id
                """,
                (log_a, ev2, ext_a),
            ).fetchone()["id"]
            conn.execute(
                """
                INSERT INTO comms_record_identity_aliases (
                    canonical_record_id, logical_source_id, identity_method, record_key
                ) VALUES (%s, %s, 'email_rfc_message_id', 'rfc:<one@example.test>')
                """,
                (rec, log_a),
            )
            conn.commit()
            _expect_fail(
                conn,
                """
                INSERT INTO comms_record_identity_aliases (
                    canonical_record_id, logical_source_id, identity_method, record_key
                ) VALUES (%s, %s, 'email_rfc_message_id', 'rfc:<one@example.test>')
                """,
                (rec, log_a),
            )
            _expect_fail(
                conn,
                """
                INSERT INTO comms_record_identities (
                    logical_source_id, evidence_id, source_kind, first_extract_instance_id
                ) VALUES (%s, %s, 'email', %s)
                """,
                (log_a, ev2, ext_a),
            )
            _expect_fail(
                conn,
                """
                INSERT INTO comms_record_identities (
                    logical_source_id, evidence_id, source_kind, first_extract_instance_id
                ) VALUES (%s, %s, 'email', %s)
                """,
                (log_a, ev2, ext_b),
            )

            ev3 = conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('calendar_event', %s, 'cal', '{}'::jsonb) RETURNING id
                """,
                (src_cal,),
            ).fetchone()["id"]
            rec_b = conn.execute(
                """
                INSERT INTO comms_record_identities (
                    logical_source_id, evidence_id, source_kind, first_extract_instance_id
                ) VALUES (%s, %s, 'calendar', %s) RETURNING id
                """,
                (log_b, ev3, ext_b),
            ).fetchone()["id"]
            conn.execute(
                """
                INSERT INTO comms_record_identity_aliases (
                    canonical_record_id, logical_source_id, identity_method, record_key
                ) VALUES (%s, %s, 'email_rfc_message_id', 'rfc:<one@example.test>')
                """,
                (rec_b, log_b),
            )
            conn.commit()

            conn.execute("DROP TABLE comms_record_identity_aliases")
            conn.execute("DROP TABLE comms_record_identities")
            conn.execute("DROP TABLE comms_source_checkpoint")
            conn.execute("DROP TABLE comms_extract_instances")
            conn.execute("DROP TABLE comms_source_memberships")
            conn.execute("DROP TABLE comms_logical_sources")
            conn.commit()
            self.assertIsNone(
                conn.execute(
                    "SELECT to_regclass('public.comms_logical_sources') AS r"
                ).fetchone()["r"]
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM evidence WHERE id = %s",
                    (ev_keep["id"],),
                ).fetchone()["n"],
                1,
            )


class DisposablePgFullChain(_DisposablePg):
    def test_001_through_034_then_035_on_ephemeral_postgres(self) -> None:
        self._require_dsn()
        chain = [
            p
            for p in _migration_files(MIGRATIONS)
            if int(p.name.split("_", 1)[0]) <= 34
        ]
        versions = [int(p.name.split("_", 1)[0]) for p in chain]
        self.assertEqual(versions, sorted(versions))
        self.assertEqual(versions[0], 1)
        self.assertEqual(versions[-1], 34)
        self.assertNotIn(35, versions)

        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            db = conn.execute("SELECT current_database() AS db").fetchone()["db"]
            self.assertNotEqual(db.lower(), "memorybox")
            conn.execute(_BOOTSTRAP)
            applied: list[str] = []
            for path in chain:
                _apply_file(conn, path)
                version = path.name.split("_", 1)[0]
                conn.execute(
                    "INSERT INTO schema_migrations (version, filename) VALUES (%s, %s)",
                    (version, path.name),
                )
                applied.append(path.name)
                conn.commit()
            self.assertEqual(applied, [p.name for p in chain])
            ledger = [
                r["filename"]
                for r in conn.execute(
                    "SELECT filename FROM schema_migrations ORDER BY version"
                ).fetchall()
            ]
            self.assertEqual(ledger, applied)

            src = conn.execute(
                """
                INSERT INTO sources (source_kind, label, uri, authoritative_original_mode)
                VALUES ('mbox_import', 'pre035', 'synthetic:pre035', 'referenced')
                RETURNING id
                """
            ).fetchone()["id"]
            ev = conn.execute(
                """
                INSERT INTO evidence (evidence_kind, source_id, summary, payload_json)
                VALUES ('communication', %s, 'pre035-keep', '{}'::jsonb)
                RETURNING id, updated_at
                """,
                (src,),
            ).fetchone()
            tables_before = _public_tables(conn)
            cols_before = _non_comms_column_fingerprint(conn)
            ledger_before = [
                (r["version"], r["filename"], r["applied_at"])
                for r in conn.execute(
                    "SELECT version, filename, applied_at FROM schema_migrations ORDER BY version"
                ).fetchall()
            ]
            ev_count_before = conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"]
            conn.commit()

            self.assertNotIn("comms_logical_sources", tables_before)
            _apply_file(conn, SQL_035)
            conn.execute(
                "INSERT INTO schema_migrations (version, filename) VALUES (%s, %s)",
                ("035", SQL_035.name),
            )
            conn.commit()

            tables_after = _public_tables(conn)
            self.assertEqual(tables_after - tables_before, COMMS_TABLES)
            self.assertTrue(COMMS_TABLES.issubset(tables_after))
            self.assertEqual(tables_before, tables_after - COMMS_TABLES)
            self.assertEqual(cols_before, _non_comms_column_fingerprint(conn))
            still = conn.execute(
                "SELECT id, updated_at, summary FROM evidence WHERE id = %s",
                (ev["id"],),
            ).fetchone()
            self.assertEqual(still["updated_at"], ev["updated_at"])
            self.assertEqual(still["summary"], "pre035-keep")
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM evidence").fetchone()["n"],
                ev_count_before,
            )
            ledger_after = [
                (r["version"], r["filename"], r["applied_at"])
                for r in conn.execute(
                    "SELECT version, filename, applied_at FROM schema_migrations ORDER BY version"
                ).fetchall()
            ]
            self.assertEqual(ledger_after[:-1], ledger_before)
            self.assertEqual(ledger_after[-1][0], "035")
            self.assertEqual(ledger_after[-1][1], SQL_035.name)

            nullable = conn.execute(
                """
                SELECT is_nullable FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'comms_record_identities'
                  AND column_name = 'evidence_id'
                """
            ).fetchone()["is_nullable"]
            self.assertEqual(nullable, "NO")
            defs = "\n".join(
                r["d"]
                for r in conn.execute(
                    """
                    SELECT pg_get_constraintdef(oid) AS d
                    FROM pg_constraint
                    WHERE conrelid::regclass::text LIKE 'comms_%'
                    """
                ).fetchall()
            ).replace(" ", "")
            self.assertIn("REFERENCESevidence(id)ONDELETERESTRICT", defs)
            self.assertIn("UNIQUEevidence_id", defs.replace("UNIQUE(evidence_id)", "UNIQUEevidence_id"))
            self.assertIn("UNIQUE(evidence_id)", defs)
            self.assertIn("UNIQUE(logical_source_id,fingerprint)", defs)
            self.assertIn("REFERENCEScomms_source_memberships(source_id,logical_source_id)ONDELETERESTRICT", defs)
            self.assertNotIn("ONDELETESETNULL", defs)
            ck_del = conn.execute(
                """
                SELECT c.confdeltype AS d
                FROM pg_constraint c
                WHERE c.conrelid = 'comms_source_checkpoint'::regclass
                  AND c.contype = 'f'
                  AND pg_get_constraintdef(c.oid) LIKE '%current_extract_instance_id%'
                """
            ).fetchone()["d"]
            self.assertEqual(ck_del, "r")
            uniq_extract_source = conn.execute(
                """
                SELECT pg_get_constraintdef(oid) AS d
                FROM pg_constraint
                WHERE conrelid = 'comms_extract_instances'::regclass
                  AND contype = 'u'
                  AND replace(pg_get_constraintdef(oid), ' ', '') = 'UNIQUE(source_id)'
                """
            ).fetchone()
            self.assertIsNone(uniq_extract_source)
            idx = conn.execute(
                """
                SELECT i.indisunique AS u
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                WHERE c.relname = 'idx_comms_extract_instances_source'
                """
            ).fetchone()
            self.assertIsNotNone(idx)
            self.assertFalse(idx["u"])


if __name__ == "__main__":
    unittest.main()
