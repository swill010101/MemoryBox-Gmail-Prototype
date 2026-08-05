"""Versioned owner memories for MBD-001 (voice notes + artifact labels)."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=30000;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,              -- voice_note | artifact_label
    title TEXT,
    asset_ref TEXT,                  -- optional link (immich id, video id, path)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    current_version INTEGER NOT NULL DEFAULT 1,
    revoked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS memory_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    body_text TEXT NOT NULL,          -- transcript / story / label (searchable)
    audio_path TEXT,                 -- optional; kept per version, not deleted on text edit
    actor_key TEXT NOT NULL DEFAULT 'owner',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    note TEXT,                       -- optional edit note
    UNIQUE(memory_id, version)
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    body_text,
    title,
    memory_id UNINDEXED,
    version UNINDEXED
);

CREATE INDEX IF NOT EXISTS idx_mem_updated ON memories(updated_at DESC);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error:
        pass
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _row_memory(conn: sqlite3.Connection, memory_id: int) -> dict[str, Any] | None:
    m = conn.execute(
        "SELECT * FROM memories WHERE id=? AND revoked=0", (memory_id,)
    ).fetchone()
    if not m:
        return None
    ver = conn.execute(
        """
        SELECT * FROM memory_versions
        WHERE memory_id=? AND version=?
        """,
        (memory_id, m["current_version"]),
    ).fetchone()
    versions = conn.execute(
        """
        SELECT version, created_at, length(body_text) AS chars, note
        FROM memory_versions WHERE memory_id=? ORDER BY version
        """,
        (memory_id,),
    ).fetchall()
    return {
        "id": m["id"],
        "kind": m["kind"],
        "title": m["title"],
        "asset_ref": m["asset_ref"],
        "created_at": m["created_at"],
        "updated_at": m["updated_at"],
        "current_version": m["current_version"],
        "body_text": ver["body_text"] if ver else "",
        "audio_path": ver["audio_path"] if ver else None,
        "versions": [dict(v) for v in versions],
    }


def create_memory(
    conn: sqlite3.Connection,
    *,
    kind: str,
    body_text: str,
    title: str | None = None,
    asset_ref: str | None = None,
    audio_path: str | None = None,
) -> dict[str, Any]:
    body = (body_text or "").strip()
    if not body:
        raise ValueError("body_text required")
    kind = (kind or "voice_note").strip()
    cur = conn.execute(
        """
        INSERT INTO memories (kind, title, asset_ref, current_version)
        VALUES (?,?,?,1)
        """,
        (kind, (title or "").strip() or None, asset_ref),
    )
    mid = int(cur.lastrowid)
    conn.execute(
        """
        INSERT INTO memory_versions (memory_id, version, body_text, audio_path, note)
        VALUES (?,?,?,?,?)
        """,
        (mid, 1, body, audio_path, "initial"),
    )
    title_s = (title or "").strip()
    conn.execute(
        "INSERT INTO memory_fts (memory_id, version, body_text, title) VALUES (?,?,?,?)",
        (mid, 1, body, title_s),
    )
    conn.commit()
    out = _row_memory(conn, mid)
    assert out
    return out


def edit_memory_text(
    conn: sqlite3.Connection,
    memory_id: int,
    body_text: str,
    *,
    note: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Create a new version from edited text. Prior versions retained. Latest searchable."""
    body = (body_text or "").strip()
    if not body:
        raise ValueError("body_text required")
    m = conn.execute(
        "SELECT * FROM memories WHERE id=? AND revoked=0", (memory_id,)
    ).fetchone()
    if not m:
        raise KeyError("memory not found")
    prev = conn.execute(
        "SELECT * FROM memory_versions WHERE memory_id=? AND version=?",
        (memory_id, m["current_version"]),
    ).fetchone()
    new_v = int(m["current_version"]) + 1
    # Keep prior audio_path on text-only edits (Confirm A)
    audio_path = prev["audio_path"] if prev else None
    conn.execute(
        """
        INSERT INTO memory_versions (memory_id, version, body_text, audio_path, note)
        VALUES (?,?,?,?,?)
        """,
        (memory_id, new_v, body, audio_path, note or "text edit"),
    )
    new_title = title if title is not None else m["title"]
    conn.execute(
        """
        UPDATE memories SET current_version=?, title=?, updated_at=datetime('now')
        WHERE id=?
        """,
        (new_v, new_title, memory_id),
    )
    # FTS: remove old current rows for this memory, index latest only for Ask default
    conn.execute("DELETE FROM memory_fts WHERE memory_id=?", (memory_id,))
    conn.execute(
        "INSERT INTO memory_fts (memory_id, version, body_text, title) VALUES (?,?,?,?)",
        (memory_id, new_v, body, (new_title or "")),
    )
    conn.commit()
    out = _row_memory(conn, memory_id)
    assert out
    return out


def get_memory(conn: sqlite3.Connection, memory_id: int) -> dict[str, Any] | None:
    return _row_memory(conn, memory_id)


def get_version(
    conn: sqlite3.Connection, memory_id: int, version: int
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM memory_versions WHERE memory_id=? AND version=?",
        (memory_id, version),
    ).fetchone()
    if not row:
        return None
    m = conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
    return {
        "memory_id": memory_id,
        "version": row["version"],
        "body_text": row["body_text"],
        "audio_path": row["audio_path"],
        "created_at": row["created_at"],
        "note": row["note"],
        "is_current": bool(m and m["current_version"] == version),
        "title": m["title"] if m else None,
        "kind": m["kind"] if m else None,
    }


def list_memories(conn: sqlite3.Connection, *, limit: int = 100) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT m.id FROM memories m
        WHERE m.revoked=0
        ORDER BY m.updated_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    out = []
    for r in rows:
        item = _row_memory(conn, int(r["id"]))
        if item:
            out.append(item)
    return out


def search_memories(conn: sqlite3.Connection, q: str, *, limit: int = 40) -> list[dict[str, Any]]:
    q = (q or "").strip()
    if not q:
        return list_memories(conn, limit=limit)
    # Prefer FTS; fall back to LIKE for plain phrases / tokenizer quirks
    rows: list[Any] = []
    try:
        # Quote multi-word as AND tokens safely via LIKE fallback if MATCH fails
        rows = list(
            conn.execute(
                """
                SELECT memory_id FROM memory_fts
                WHERE memory_fts MATCH ?
                LIMIT ?
                """,
                (q, limit),
            ).fetchall()
        )
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        rows = list(
            conn.execute(
                """
                SELECT m.id AS memory_id FROM memories m
                JOIN memory_versions v ON v.memory_id=m.id AND v.version=m.current_version
                WHERE m.revoked=0 AND (v.body_text LIKE ? OR IFNULL(m.title,'') LIKE ?)
                ORDER BY m.updated_at DESC LIMIT ?
                """,
                (f"%{q}%", f"%{q}%", limit),
            ).fetchall()
        )
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        raw = r["memory_id"] if "memory_id" in r.keys() else r[0]
        if raw is None:
            continue
        mid = int(raw)
        if mid in seen:
            continue
        seen.add(mid)
        item = _row_memory(conn, mid)
        if item:
            out.append(item)
    return out
