"""Guarded activation of the unpublished 038 household-email generation.

Calls comms_prepared_activate_generation once. Never updates published flags
row-by-row. Never mutates evidence, Gallery, Ask, or I11A.
"""
from __future__ import annotations

import json
import os
from typing import Any

from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn
from memorybox.ops.i14_duplicate_audit import assert_counts_only, failure_json

CONFIRM = "activate-unpublished-voice-038-v1"
REQUIRED_LEDGER = 38
LEDGER_LAST = "038_p2_i14_voice_without_recipient_identity.sql"
EXPECTED = {
    "threads": 40996,
    "messages": 91247,
    "participants": 294061,
    "attachments": 28467,
    "evidence": 188656,
    "sources": 27,
    "communication_rfc_ids": 287010,
    "voice_tom": 12071,
    "voice_peggy": 1368,
    "voice_sue": 307,
}


class ActivateError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _env_on(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def require_flags() -> None:
    if not _env_on("MEMORYBOX_I14_ACTIVATE_ALLOW_FLIGHTSIM"):
        raise ActivateError("activate_flightsim_not_allowed")
    if not _env_on("MEMORYBOX_I14_ACTIVATE_ALLOW_MEMORYBOX_DB"):
        raise ActivateError("activate_memorybox_db_not_allowed")
    if os.environ.get("MEMORYBOX_I14_ACTIVATE_CONFIRM", "").strip() != CONFIRM:
        raise ActivateError("activate_confirm_mismatch")


def _n(conn: Any, sql: str, params: tuple | None = None) -> int:
    row = conn.execute(sql, params).fetchone() if params else conn.execute(sql).fetchone()
    return int(row["n"])


def _voice(conn: Any, gid: Any) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT split_part(pe.display_name, ' ', 1) AS who, COUNT(*)::int AS n
          FROM comms_prepared_messages m
          JOIN comms_prepared_threads t ON t.id = m.thread_id
          JOIN comms_prepared_participants p ON p.message_id = m.id AND p.role = 'from'
          JOIN people pe ON pe.id = p.person_id
         WHERE t.generation_id = %s AND m.voice_corpus
         GROUP BY 1
        """,
        (gid,),
    ).fetchall()
    out = {"voice_tom": 0, "voice_peggy": 0, "voice_sue": 0}
    extra = 0
    for row in rows:
        who = str(row["who"] or "")
        n = int(row["n"])
        if who == "Tom":
            out["voice_tom"] = n
        elif who == "Peggy":
            out["voice_peggy"] = n
        elif who == "Sue":
            out["voice_sue"] = n
        else:
            extra += n
    if extra:
        raise ActivateError("unexpected_from_voice")
    return out


def _snapshot(conn: Any, gid: Any) -> dict[str, int]:
    out = {
        "threads": _n(
            conn,
            "SELECT COUNT(*) AS n FROM comms_prepared_threads WHERE generation_id = %s",
            (gid,),
        ),
        "messages": _n(
            conn,
            "SELECT COUNT(*) AS n FROM comms_prepared_messages WHERE generation_id = %s",
            (gid,),
        ),
        "participants": _n(
            conn,
            """
            SELECT COUNT(*) AS n FROM comms_prepared_participants p
              JOIN comms_prepared_messages m ON m.id = p.message_id
             WHERE m.generation_id = %s
            """,
            (gid,),
        ),
        "attachments": _n(
            conn,
            """
            SELECT COUNT(*) AS n FROM comms_prepared_attachments a
              JOIN comms_prepared_messages m ON m.id = a.message_id
             WHERE m.generation_id = %s
            """,
            (gid,),
        ),
        "evidence": _n(conn, "SELECT COUNT(*) AS n FROM evidence"),
        "sources": _n(conn, "SELECT COUNT(*) AS n FROM sources"),
        "communication_rfc_ids": _n(conn, "SELECT COUNT(*) AS n FROM communication_rfc_ids"),
    }
    out.update(_voice(conn, gid))
    return out


def _agree(actual: dict[str, int]) -> None:
    diffs = [f"{k}:{actual.get(k)}!={v}" for k, v in EXPECTED.items() if int(actual.get(k) or 0) != v]
    if diffs:
        raise ActivateError("precondition_count_mismatch")


def select_target(conn: Any) -> Any:
    published = _n(conn, "SELECT COUNT(*) AS n FROM comms_prepared_generations WHERE published")
    active = _n(conn, "SELECT COUNT(*) AS n FROM comms_prepared_active_generations")
    failed = _n(
        conn,
        "SELECT COUNT(*) AS n FROM comms_prepared_generations WHERE status = 'failed'",
    )
    if published or active or failed:
        raise ActivateError("generation_state_not_pre_activate")
    rows = conn.execute(
        """
        SELECT id, status, published, is_active, checksum, scope_key
          FROM comms_prepared_generations
         WHERE status = 'validated' AND NOT published AND NOT is_active
         ORDER BY created_at
        """
    ).fetchall()
    if len(rows) != 1:
        raise ActivateError("eligible_unpublished_not_one")
    rec = rows[0]
    if rec["scope_key"] != "household_email":
        raise ActivateError("scope_not_household_email")
    if not rec["checksum"]:
        raise ActivateError("checksum_required")
    return rec["id"]


def assert_ledger(conn: Any) -> None:
    rows = list(
        conn.execute("SELECT version, filename FROM schema_migrations ORDER BY version").fetchall()
    )
    if len(rows) != REQUIRED_LEDGER:
        raise ActivateError("ledger_not_001_038")
    if str(rows[-1]["filename"]) != LEDGER_LAST:
        raise ActivateError("ledger_last_not_038")


def assert_voice_check(conn: Any) -> None:
    row = conn.execute(
        """
        SELECT pg_get_constraintdef(oid) AS def
          FROM pg_constraint
         WHERE conname = 'comms_prepared_messages_voice_corpus_ck'
        """
    ).fetchone()
    text = str(row["def"] if row else "")
    if "quote_quality = 'clean'" not in text or "authorship = 'authenticated_focal'" not in text:
        raise ActivateError("voice_check_mismatch")
    if "identity_quality" in text:
        raise ActivateError("voice_check_still_requires_identity")


def run_activation(conn: Any, *, dry_run: bool) -> dict[str, Any]:
    assert_ledger(conn)
    assert_voice_check(conn)
    gid = select_target(conn)
    before = _snapshot(conn, gid)
    _agree(before)
    conn.execute("SELECT comms_prepared_assert_generation_ready(%s)", (gid,))
    if dry_run:
        return {
            "ok": True,
            "kind": "household_email_activation",
            "dry_run": True,
            "activation_called": False,
            "published": 0,
            "active": 0,
            "eligible_unpublished": 1,
            "failed": 0,
            "gallery_changed": False,
            "i11a_changed": False,
            **before,
        }
    conn.execute("SELECT comms_prepared_activate_generation(%s)", (gid,))
    after = _snapshot(conn, gid)
    _agree(after)
    published = _n(conn, "SELECT COUNT(*) AS n FROM comms_prepared_generations WHERE published")
    active = _n(conn, "SELECT COUNT(*) AS n FROM comms_prepared_active_generations")
    failed = _n(
        conn,
        "SELECT COUNT(*) AS n FROM comms_prepared_generations WHERE status = 'failed'",
    )
    eligible = _n(
        conn,
        """
        SELECT COUNT(*) AS n FROM comms_prepared_generations
         WHERE status = 'validated' AND NOT published AND NOT is_active
        """,
    )
    status = conn.execute(
        """
        SELECT status, published, is_active
          FROM comms_prepared_generations
         WHERE id = %s
        """,
        (gid,),
    ).fetchone()
    if (
        str(status["status"]) != "published"
        or not status["published"]
        or not status["is_active"]
        or published != 1
        or active != 1
        or failed != 0
        or eligible != 0
    ):
        raise ActivateError("post_activate_state_mismatch")
    return {
        "ok": True,
        "kind": "household_email_activation",
        "dry_run": False,
        "activation_called": True,
        "published": published,
        "active": active,
        "eligible_unpublished": eligible,
        "failed": failed,
        "gallery_changed": False,
        "i11a_changed": False,
        **after,
    }


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        require_flags()
        dsn = os.environ.get("MEMORYBOX_DATABASE_URL")
        if not dsn:
            raise ActivateError("MEMORYBOX_DATABASE_URL_missing")
        try:
            refuse_live_dsn(dsn, None, allow_flightsim=True)
        except ProductionDSNError as exc:
            raise ActivateError(str(exc)) from None
        dry_run = _env_on("MEMORYBOX_I14_ACTIVATE_DRY_RUN")
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(dsn, row_factory=dict_row, autocommit=False, connect_timeout=10) as conn:
            public = run_activation(conn, dry_run=dry_run)
            if dry_run:
                conn.rollback()
            else:
                conn.commit()
        assert_counts_only(public)
        print(json.dumps(public, indent=2, sort_keys=True))
        return 0
    except ActivateError as exc:
        print(json.dumps(failure_json(str(exc))))
        return 2
