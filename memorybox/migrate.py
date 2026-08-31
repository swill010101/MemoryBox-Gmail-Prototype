"""Apply SQL migrations in order. Idempotent via schema_migrations table."""
from __future__ import annotations

import re
from pathlib import Path

from memorybox.config import Settings, settings
from memorybox.db import connection


_BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    filename TEXT NOT NULL
);
"""


def _migration_files(migrations_dir: Path) -> list[Path]:
    files = sorted(migrations_dir.glob("*.sql"))
    return [f for f in files if re.match(r"^\d{3}_.+\.sql$", f.name)]


def _sql_statements(sql: str) -> list[str]:
    """Split a migration file into executable statements.

    psycopg3 execute() runs one statement. Dollar-quoted bodies stay intact.
    """
    out: list[str] = []
    buf: list[str] = []
    dollars = 0
    for line in sql.splitlines():
        dollars += line.count("$$")
        buf.append(line)
        if dollars % 2 == 0 and line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip()
            buf = []
            if stmt and any(
                part.strip() and not part.strip().startswith("--")
                for part in stmt.splitlines()
            ):
                out.append(stmt)
    tail = "\n".join(buf).strip()
    if tail and any(
        part.strip() and not part.strip().startswith("--")
        for part in tail.splitlines()
    ):
        out.append(tail)
    return out


def _apply_sql(conn, sql: str) -> None:
    try:
        conn.execute(sql)
        return
    except Exception:
        pass
    for stmt in _sql_statements(sql):
        conn.execute(stmt)


def pending(cfg: Settings | None = None) -> list[str]:
    s = cfg or settings
    with connection(s) as conn:
        conn.execute(_BOOTSTRAP)
        applied = {
            r["version"]
            for r in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
    out: list[str] = []
    for path in _migration_files(s.migrations_dir):
        version = path.name.split("_", 1)[0]
        if version not in applied:
            out.append(path.name)
    return out


def migrate(cfg: Settings | None = None) -> list[str]:
    """Apply all pending migrations. Returns filenames applied this run."""
    s = cfg or settings
    applied_now: list[str] = []
    with connection(s) as conn:
        conn.execute(_BOOTSTRAP)
        applied = {
            r["version"]
            for r in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for path in _migration_files(s.migrations_dir):
            version = path.name.split("_", 1)[0]
            if version in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            _apply_sql(conn, sql)
            if version == "028":
                from memorybox.ingest.rfc_lookup import backfill_communication_rfc_ids

                backfill_communication_rfc_ids(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version, filename) VALUES (%s, %s)",
                (version, path.name),
            )
            applied_now.append(path.name)
            applied.add(version)
    return applied_now


def applied_versions(cfg: Settings | None = None) -> list[dict]:
    s = cfg or settings
    with connection(s) as conn:
        conn.execute(_BOOTSTRAP)
        rows = conn.execute(
            "SELECT version, filename, applied_at FROM schema_migrations ORDER BY version"
        ).fetchall()
    return [dict(r) for r in rows]
