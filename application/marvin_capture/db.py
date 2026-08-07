"""SQLite storage for Marvin Capture.

Design principle: derived fields are additive. Raw email path and attachment
binaries are the authoritative record.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
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
    subject TEXT,
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

CREATE TABLE IF NOT EXISTS mem_bank_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_tick_date TEXT,
    completed_at TEXT,
    completion_email_sent INTEGER NOT NULL DEFAULT 0,
    sends_enabled INTEGER,
    next_initial_date TEXT
);

CREATE TABLE IF NOT EXISTS mem_send_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    gmail_message_id TEXT,
    gmail_thread_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_mem_send_question ON mem_send_log(question_id, sent_at);
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
    _migrate(conn)
    conn.commit()
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(response)").fetchall()}
    if "subject" not in cols:
        conn.execute("ALTER TABLE response ADD COLUMN subject TEXT")
    state_cols = {row[1] for row in conn.execute("PRAGMA table_info(mem_bank_state)").fetchall()}
    if "sends_enabled" not in state_cols:
        # NULL = inherit from config; 0 = forced off; 1 = forced on
        conn.execute("ALTER TABLE mem_bank_state ADD COLUMN sends_enabled INTEGER")
    if "next_initial_date" not in state_cols:
        conn.execute("ALTER TABLE mem_bank_state ADD COLUMN next_initial_date TEXT")


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


def find_prompt_by_type(conn: sqlite3.Connection, prompt_type: str) -> dict[str, Any] | None:
    """Prefer canonical TYPE id (no token); fall back to newest typed prompt."""
    prompt_type = prompt_type.upper()
    row = conn.execute("SELECT * FROM prompt WHERE id = ?", (prompt_type,)).fetchone()
    if row:
        return dict(row)
    row = conn.execute(
        "SELECT * FROM prompt WHERE type = ? ORDER BY sent_date DESC LIMIT 1",
        (prompt_type,),
    ).fetchone()
    return dict(row) if row else None


def response_exists(conn: sqlite3.Connection, gmail_message_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM response WHERE gmail_message_id = ?",
        (gmail_message_id,),
    ).fetchone()
    return row is not None


def journal_sent_on_date(conn: sqlite3.Connection, day: date) -> bool:
    """True if a JRN prompt was already sent on the given local calendar day."""
    day_s = day.isoformat()
    row = conn.execute(
        """
        SELECT 1 FROM prompt
        WHERE type = 'JRN'
          AND sent_date IS NOT NULL
          AND substr(sent_date, 1, 10) = ?
        LIMIT 1
        """,
        (day_s,),
    ).fetchone()
    if row:
        return True
    # Also accept legacy JRN-YYYYMMDD prompt ids
    legacy = f"JRN-{day.strftime('%Y%m%d')}"
    row = conn.execute(
        "SELECT 1 FROM prompt WHERE id = ? AND gmail_message_id IS NOT NULL LIMIT 1",
        (legacy,),
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
    subject: str | None = None,
) -> dict[str, Any]:
    cur = conn.execute(
        """
        INSERT INTO response (
            prompt_id, received_date, response_text, raw_email_path, subject,
            gmail_message_id, gmail_thread_id, processed, reviewed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0)
        """,
        (
            prompt_id,
            received_date or utc_now_iso(),
            response_text,
            raw_email_path,
            subject,
            gmail_message_id,
            gmail_thread_id,
        ),
    )
    return get_response(conn, int(cur.lastrowid))  # type: ignore[return-value]


def update_response_text(conn: sqlite3.Connection, response_id: int, response_text: str) -> None:
    conn.execute(
        "UPDATE response SET response_text = ? WHERE id = ?",
        (response_text, response_id),
    )


def list_responses_by_type(conn: sqlite3.Connection, prompt_type: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT r.*, p.subject AS prompt_subject, p.body AS prompt_body, p.type AS prompt_type
        FROM response r
        JOIN prompt p ON p.id = r.prompt_id
        WHERE p.type = ?
        ORDER BY r.received_date ASC, r.id ASC
        """,
        (prompt_type.upper(),),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_responses_by_type(conn: sqlite3.Connection, prompt_type: str) -> dict[str, Any]:
    """Delete responses (and attachments) for a type. Also removes linked files.

    Explicit batch wipe for EVS workflow — originals for other types untouched.
    """
    prompt_type = prompt_type.upper()
    rows = list_responses_by_type(conn, prompt_type)
    removed_files: list[str] = []
    for resp in rows:
        atts = conn.execute(
            "SELECT * FROM attachment WHERE response_id = ?",
            (resp["id"],),
        ).fetchall()
        for att in atts:
            path = Path(att["storage_path"])
            if path.is_file():
                path.unlink()
                removed_files.append(str(path))
        raw = Path(resp["raw_email_path"]) if resp.get("raw_email_path") else None
        if raw and raw.is_file():
            raw.unlink()
            removed_files.append(str(raw))
        conn.execute("DELETE FROM attachment WHERE response_id = ?", (resp["id"],))
        conn.execute("DELETE FROM response WHERE id = ?", (resp["id"],))

    # Remove prompt rows for this type that have no remaining responses
    prompts = conn.execute("SELECT id FROM prompt WHERE type = ?", (prompt_type,)).fetchall()
    removed_prompts = 0
    for p in prompts:
        left = conn.execute(
            "SELECT 1 FROM response WHERE prompt_id = ? LIMIT 1",
            (p["id"],),
        ).fetchone()
        if not left:
            conn.execute("DELETE FROM prompt WHERE id = ?", (p["id"],))
            removed_prompts += 1

    return {
        "type": prompt_type,
        "responses_deleted": len(rows),
        "prompts_deleted": removed_prompts,
        "files_removed": len(removed_files),
    }


def format_evs_export(items: list[dict[str, Any]]) -> str:
    """Plain-text batch export for MemoryBox EVS processing."""
    blocks: list[str] = []
    for i, item in enumerate(items, start=1):
        subject = item.get("subject") or item.get("prompt_subject") or ""
        header = (
            f"=== EVS {i} ===\n"
            f"received: {item.get('received_date') or ''}\n"
            f"subject: {subject}\n"
            f"id: {item.get('id')}\n"
            f"---\n"
        )
        body = (item.get("response_text") or "").strip()
        blocks.append(header + body)
    if not blocks:
        return "=== EVS export ===\n(no EVS responses)\n"
    return "\n\n".join(blocks) + "\n"


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


def find_response_by_normalized_text(
    conn: sqlite3.Connection,
    *,
    prompt_id: str,
    normalized_text: str,
) -> dict[str, Any] | None:
    """Return first response whose collapsed text matches (Python-side normalize)."""
    if not normalized_text:
        return None
    rows = conn.execute(
        """
        SELECT id, response_text FROM response
        WHERE prompt_id = ? AND length(trim(response_text)) > 0
        ORDER BY id ASC
        """,
        (prompt_id,),
    ).fetchall()
    # Import locally to keep db free of reply_extract cycles at module load
    from .reply_extract import normalize_for_dedupe

    for row in rows:
        if normalize_for_dedupe(row["response_text"]) == normalized_text:
            return dict(row)
    return None


def auto_review_duplicate_bodies(
    conn: sqlite3.Connection,
    *,
    similarity_threshold: float = 0.88,
) -> int:
    """Mark newer unreviewed rows reviewed when an older twin exists.

    Match rules (same prompt_id):
      1. Exact normalized body
      2. High similarity (SequenceMatcher on normalized body)

    Keeps raw email + both DB rows (additive). Clears Inbox clutter for
    accidental double-captures of the same journal/MEM body.
    """
    import difflib

    from .reply_extract import normalize_for_dedupe

    rows = conn.execute(
        """
        SELECT id, prompt_id, response_text, reviewed, received_date
        FROM response
        WHERE length(trim(response_text)) > 0
        ORDER BY id ASC
        """
    ).fetchall()

    # Keep first (oldest) keeper per prompt_id as list of (norm, id)
    keepers: dict[str, list[tuple[str, int]]] = {}
    marked = 0
    for row in rows:
        pid = row["prompt_id"]
        norm = normalize_for_dedupe(row["response_text"])
        if not norm:
            continue
        prior = keepers.setdefault(pid, [])
        is_dupe = False
        for prev_norm, _prev_id in prior:
            if prev_norm == norm:
                is_dupe = True
                break
            # Long journals: require solid overlap; short notes need near-exact
            ratio = difflib.SequenceMatcher(None, prev_norm, norm).ratio()
            need = similarity_threshold if min(len(prev_norm), len(norm)) >= 80 else 0.97
            if ratio >= need:
                is_dupe = True
                break
            # One body fully contains the other (truncated / extended resend)
            if len(prev_norm) >= 40 and len(norm) >= 40:
                if prev_norm in norm or norm in prev_norm:
                    is_dupe = True
                    break
        if is_dupe:
            if not row["reviewed"]:
                mark_reviewed(conn, row["id"], reviewed=True)
                marked += 1
            continue
        prior.append((norm, row["id"]))
    return marked


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


def prompt_has_response(conn: sqlite3.Connection, prompt_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM response WHERE prompt_id = ? LIMIT 1",
        (prompt_id,),
    ).fetchone()
    return row is not None


def get_mem_bank_state(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM mem_bank_state WHERE id = 1").fetchone()
    if not row:
        conn.execute("INSERT INTO mem_bank_state (id) VALUES (1)")
        row = conn.execute("SELECT * FROM mem_bank_state WHERE id = 1").fetchone()
    return dict(row)


def set_mem_bank_state(
    conn: sqlite3.Connection,
    *,
    last_tick_date: str | None = None,
    completed_at: str | None = None,
    completion_email_sent: int | None = None,
    sends_enabled: int | None = None,
    next_initial_date: str | None = None,
) -> dict[str, Any]:
    get_mem_bank_state(conn)
    if last_tick_date is not None:
        conn.execute(
            "UPDATE mem_bank_state SET last_tick_date = ? WHERE id = 1",
            (last_tick_date,),
        )
    if completed_at is not None:
        conn.execute(
            "UPDATE mem_bank_state SET completed_at = ? WHERE id = 1",
            (completed_at,),
        )
    if completion_email_sent is not None:
        conn.execute(
            "UPDATE mem_bank_state SET completion_email_sent = ? WHERE id = 1",
            (completion_email_sent,),
        )
    if sends_enabled is not None:
        conn.execute(
            "UPDATE mem_bank_state SET sends_enabled = ? WHERE id = 1",
            (1 if sends_enabled else 0,),
        )
    if next_initial_date is not None:
        conn.execute(
            "UPDATE mem_bank_state SET next_initial_date = ? WHERE id = 1",
            (next_initial_date,),
        )
    return get_mem_bank_state(conn)


def arm_mem_sends(conn: sqlite3.Connection, *, enabled: bool, now: datetime | None = None) -> dict[str, Any]:
    """Turn sends on/off. When turning on, first new question is tomorrow."""
    now = now or datetime.now()
    if enabled:
        tomorrow = (now.date() + timedelta(days=1)).isoformat()
        return set_mem_bank_state(conn, sends_enabled=1, next_initial_date=tomorrow)
    return set_mem_bank_state(conn, sends_enabled=0)


def mem_sends_are_enabled(conn: sqlite3.Connection, cfg: dict[str, Any]) -> bool:
    """UI/DB toggle overrides config when sends_enabled is 0 or 1."""
    state = get_mem_bank_state(conn)
    flag = state.get("sends_enabled")
    if flag is None:
        return bool((cfg.get("mem_bank") or {}).get("enabled"))
    return bool(flag)


def log_mem_send(
    conn: sqlite3.Connection,
    *,
    question_id: int,
    kind: str,
    sent_at: str,
    gmail_message_id: str | None = None,
    gmail_thread_id: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO mem_send_log (question_id, kind, sent_at, gmail_message_id, gmail_thread_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (question_id, kind, sent_at, gmail_message_id, gmail_thread_id),
    )


def count_mem_sends(conn: sqlite3.Connection, question_id: int, kind: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM mem_send_log WHERE question_id = ? AND kind = ?",
        (question_id, kind),
    ).fetchone()
    return int(row["n"] if row else 0)


def first_mem_send(conn: sqlite3.Connection, question_id: int, kind: str = "initial") -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM mem_send_log
        WHERE question_id = ? AND kind = ?
        ORDER BY sent_at ASC, id ASC
        LIMIT 1
        """,
        (question_id, kind),
    ).fetchone()
    return dict(row) if row else None


def last_mem_send(conn: sqlite3.Connection, question_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM mem_send_log
        WHERE question_id = ?
        ORDER BY sent_at DESC, id DESC
        LIMIT 1
        """,
        (question_id,),
    ).fetchone()
    return dict(row) if row else None


def list_mem_bank_qa(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Responses for prompt ids MEM-<digits>, oldest first, with attachments."""
    rows = conn.execute(
        """
        SELECT r.*, p.subject AS prompt_subject, p.body AS prompt_body, p.type AS prompt_type
        FROM response r
        JOIN prompt p ON p.id = r.prompt_id
        WHERE p.type = 'MEM' AND r.prompt_id GLOB 'MEM-[0-9]*'
        ORDER BY CAST(substr(r.prompt_id, 5) AS INTEGER) ASC, r.received_date ASC, r.id ASC
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        atts = conn.execute(
            "SELECT * FROM attachment WHERE response_id = ? ORDER BY id",
            (item["id"],),
        ).fetchall()
        item["attachments"] = [dict(a) for a in atts]
        out.append(item)
    return out


def maybe_promote_transcript_to_answer(conn: sqlite3.Connection, attachment_id: int, transcript: str) -> bool:
    """If the parent response has empty text, use Whisper transcript as the answer."""
    row = conn.execute(
        """
        SELECT r.id, r.response_text
        FROM attachment a
        JOIN response r ON r.id = a.response_id
        WHERE a.id = ?
        """,
        (attachment_id,),
    ).fetchone()
    if not row:
        return False
    if (row["response_text"] or "").strip():
        return False
    conn.execute(
        "UPDATE response SET response_text = ? WHERE id = ?",
        (transcript.strip(), row["id"]),
    )
    return True

