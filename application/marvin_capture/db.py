"""SQLite storage for Marvin Capture.

Design principle: derived fields are additive. Raw email path and attachment
binaries are the authoritative record.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS prompt (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    sent_date TEXT,
    gmail_message_id TEXT,
    gmail_thread_id TEXT
);

CREATE TABLE IF NOT EXISTS response (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id TEXT NOT NULL REFERENCES prompt(id),
    received_date TEXT NOT NULL,
    response_text TEXT NOT NULL DEFAULT '',
    raw_email_path TEXT NOT NULL,
    gmail_message_id TEXT UNIQUE,
    gmail_thread_id TEXT,
    processed INTEGER NOT NULL DEFAULT 1,
    reviewed INTEGER NOT NULL DEFAULT 0,
    reviewed_at TEXT,
    FOREIGN KEY (prompt_id) REFERENCES prompt(id)
);

CREATE TABLE IF NOT EXISTS attachment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES response(id),
    filename TEXT NOT NULL,
    mime_type TEXT,
    storage_path TEXT NOT NULL,
    is_audio INTEGER NOT NULL DEFAULT 0,
    transcript TEXT,
    transcript_status TEXT NOT NULL DEFAULT 'none'
);

CREATE INDEX IF NOT EXISTS idx_response_prompt ON response(prompt_id);
CREATE INDEX IF NOT EXISTS idx_response_reviewed ON response(reviewed);
CREATE INDEX IF NOT EXISTS idx_attachment_response ON attachment(response_id);
CREATE INDEX IF NOT EXISTS idx_attachment_transcript ON attachment(transcript_status);
"""

AUDIO_MIME_PREFIXES = ("audio/",)
AUDIO_EXTENSIONS = {".m4a", ".wav", ".mp3", ".ogg", ".flac", ".aac", ".webm"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI serves requests on worker threads;
    # single-user PoC with short SQLite ops.
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path) -> sqlite3.Connection:
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


@contextmanager
def db_session(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    conn = init_db(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def is_audio(filename: str, mime_type: str | None) -> bool:
    if mime_type and any(mime_type.lower().startswith(p) for p in AUDIO_MIME_PREFIXES):
        return True
    return Path(filename).suffix.lower() in AUDIO_EXTENSIONS


def insert_prompt(
    conn: sqlite3.Connection,
    *,
    prompt_id: str,
    prompt_type: str,
    subject: str,
    body: str,
    sent_date: str | None = None,
    gmail_message_id: str | None = None,
    gmail_thread_id: str | None = None,
) -> dict[str, Any]:
    conn.execute(
        """
        INSERT INTO prompt (id, type, subject, body, sent_date, gmail_message_id, gmail_thread_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            subject=excluded.subject,
            body=excluded.body,
            sent_date=COALESCE(excluded.sent_date, prompt.sent_date),
            gmail_message_id=COALESCE(excluded.gmail_message_id, prompt.gmail_message_id),
            gmail_thread_id=COALESCE(excluded.gmail_thread_id, prompt.gmail_thread_id)
        """,
        (
            prompt_id,
            prompt_type,
            subject,
            body,
            sent_date or utc_now_iso(),
            gmail_message_id,
            gmail_thread_id,
        ),
    )
    return get_prompt(conn, prompt_id)  # type: ignore[return-value]


def get_prompt(conn: sqlite3.Connection, prompt_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM prompt WHERE id = ?", (prompt_id,)).fetchone()
    return dict(row) if row else None


def find_prompt_by_thread(conn: sqlite3.Connection, thread_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM prompt WHERE gmail_thread_id = ? ORDER BY sent_date DESC LIMIT 1",
        (thread_id,),
    ).fetchone()
    return dict(row) if row else None


def response_exists(conn: sqlite3.Connection, gmail_message_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM response WHERE gmail_message_id = ?",
        (gmail_message_id,),
    ).fetchone()
    return row is not None


def insert_response(
    conn: sqlite3.Connection,
    *,
    prompt_id: str,
    response_text: str,
    raw_email_path: str,
    received_date: str | None = None,
    gmail_message_id: str | None = None,
    gmail_thread_id: str | None = None,
) -> dict[str, Any]:
    cur = conn.execute(
        """
        INSERT INTO response (
            prompt_id, received_date, response_text, raw_email_path,
            gmail_message_id, gmail_thread_id, processed, reviewed
        ) VALUES (?, ?, ?, ?, ?, ?, 1, 0)
        """,
        (
            prompt_id,
            received_date or utc_now_iso(),
            response_text,
            raw_email_path,
            gmail_message_id,
            gmail_thread_id,
        ),
    )
    return get_response(conn, int(cur.lastrowid))  # type: ignore[return-value]


def get_response(conn: sqlite3.Connection, response_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM response WHERE id = ?", (response_id,)).fetchone()
    return dict(row) if row else None


def insert_attachment(
    conn: sqlite3.Connection,
    *,
    response_id: int,
    filename: str,
    mime_type: str | None,
    storage_path: str,
) -> dict[str, Any]:
    audio = is_audio(filename, mime_type)
    status = "pending" if audio else "none"
    cur = conn.execute(
        """
        INSERT INTO attachment (
            response_id, filename, mime_type, storage_path, is_audio, transcript_status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (response_id, filename, mime_type, storage_path, 1 if audio else 0, status),
    )
    row = conn.execute("SELECT * FROM attachment WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def list_responses(
    conn: sqlite3.Connection,
    *,
    reviewed: bool | None = None,
) -> list[dict[str, Any]]:
    if reviewed is None:
        rows = conn.execute(
            """
            SELECT r.*, p.subject AS prompt_subject, p.body AS prompt_body, p.type AS prompt_type
            FROM response r
            JOIN prompt p ON p.id = r.prompt_id
            ORDER BY r.received_date DESC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT r.*, p.subject AS prompt_subject, p.body AS prompt_body, p.type AS prompt_type
            FROM response r
            JOIN prompt p ON p.id = r.prompt_id
            WHERE r.reviewed = ?
            ORDER BY r.received_date DESC
            """,
            (1 if reviewed else 0,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_response_detail(conn: sqlite3.Connection, response_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT r.*, p.subject AS prompt_subject, p.body AS prompt_body,
               p.type AS prompt_type, p.sent_date AS prompt_sent_date
        FROM response r
        JOIN prompt p ON p.id = r.prompt_id
        WHERE r.id = ?
        """,
        (response_id,),
    ).fetchone()
    if not row:
        return None
    detail = dict(row)
    atts = conn.execute(
        "SELECT * FROM attachment WHERE response_id = ? ORDER BY id",
        (response_id,),
    ).fetchall()
    detail["attachments"] = [dict(a) for a in atts]
    return detail


def mark_reviewed(conn: sqlite3.Connection, response_id: int, reviewed: bool = True) -> dict[str, Any] | None:
    conn.execute(
        "UPDATE response SET reviewed = ?, reviewed_at = ? WHERE id = ?",
        (1 if reviewed else 0, utc_now_iso() if reviewed else None, response_id),
    )
    return get_response_detail(conn, response_id)


def list_pending_transcriptions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM attachment
        WHERE is_audio = 1 AND transcript_status IN ('pending', 'error')
        ORDER BY id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def update_transcript(
    conn: sqlite3.Connection,
    attachment_id: int,
    *,
    transcript: str | None,
    status: str,
) -> None:
    conn.execute(
        """
        UPDATE attachment
        SET transcript = COALESCE(?, transcript), transcript_status = ?
        WHERE id = ?
        """,
        (transcript, status, attachment_id),
    )
