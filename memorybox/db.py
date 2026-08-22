"""PostgreSQL access helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from memorybox.config import Settings, settings


def connect(cfg: Settings | None = None) -> psycopg.Connection:
    s = cfg or settings
    return psycopg.connect(s.database_url, row_factory=dict_row)


@contextmanager
def connection(cfg: Settings | None = None) -> Iterator[psycopg.Connection]:
    conn = connect(cfg)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ping(cfg: Settings | None = None) -> dict:
    """Return a small status dict or raise."""
    with connection(cfg) as conn:
        row = conn.execute("SELECT 1 AS ok, current_database() AS database").fetchone()
        assert row is not None
        return {"ok": bool(row["ok"]), "database": row["database"]}
