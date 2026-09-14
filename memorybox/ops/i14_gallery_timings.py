"""Read-only Phase C timings against the active household-email generation.

Does not enable Gallery on serve, activate, load, or migrate.
Counts-only JSON: no UUIDs, addresses, bodies, or generation ids.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any

from memorybox.ops.i14_dsn_guard import ProductionDSNError, refuse_live_dsn

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)


class TimingError(RuntimeError):
    pass


def _env_on(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def assert_counts_only(payload: dict[str, Any]) -> None:
    blob = json.dumps(payload, default=str)
    if UUID_RE.search(blob):
        raise TimingError("timing_output_contains_uuid")
    if EMAIL_RE.search(blob):
        raise TimingError("timing_output_contains_address")


def require_flags(conn: Any) -> str:
    row = conn.execute("SELECT current_database() AS d").fetchone()
    name = str(row["d"]).lower()
    info = getattr(conn, "info", None)
    host = str(getattr(info, "host", "") or "") if info is not None else ""
    allow_db = _env_on("MEMORYBOX_I14_AUDIT_ALLOW_MEMORYBOX_DB")
    allow_fs = _env_on("MEMORYBOX_I14_GALLERY_TIMING_ALLOW_FLIGHTSIM") or _env_on(
        "MEMORYBOX_I14_AUDIT_ALLOW_FLIGHTSIM"
    )
    try:
        refuse_live_dsn(host, None if allow_db else name, allow_flightsim=allow_fs)
    except ProductionDSNError as exc:
        raise TimingError(str(exc)) from None
    if name == "memorybox" and not allow_db:
        raise TimingError("refused_memorybox_dbname")
    return name


def _person_id(conn: Any, label: str) -> str | None:
    row = conn.execute(
        """
        SELECT p.id::text AS id
          FROM people p
          JOIN comms_prepared_participants pp ON pp.person_id = p.id
          JOIN comms_prepared_messages m ON m.id = pp.message_id
          JOIN comms_prepared_threads t ON t.id = m.thread_id
          JOIN comms_prepared_active_generations ag ON ag.id = t.generation_id
         WHERE p.status <> 'merged_away'
           AND ag.scope_key = 'household_email'
           AND (
             lower(coalesce(p.display_name, '')) = lower(%s)
             OR lower(coalesce(p.display_name, '')) LIKE lower(%s) || ' %%'
           )
         GROUP BY p.id
         ORDER BY COUNT(DISTINCT t.id) DESC
         LIMIT 1
        """,
        (label, label),
    ).fetchone()
    if not row:
        return None
    return str(row["id"])


def measure_label(conn: Any, label: str) -> dict[str, Any]:
    from memorybox.explore.prepared_comms import GALLERY_CARD_CAP, list_person_threads, load_thread, new_ask_token

    pid = _person_id(conn, label)
    if not pid:
        return {"label": label, "ok": False, "error": "person_not_found"}
    token = new_ask_token()
    t0 = time.perf_counter()
    listed = list_person_threads(conn, person_id=pid, token=token)
    wall_ms = int((time.perf_counter() - t0) * 1000)
    attach_n = 0
    attach_unavail = 0
    sample = 0
    load_t0 = time.perf_counter()
    for card in listed.get("items") or []:
        if sample >= 8:
            break
        did = str(card.get("display_id") or "")
        if not did:
            continue
        sample += 1
        loaded = load_thread(conn, did)
        for msg in loaded.get("messages") or []:
            for att in msg.get("attachments") or []:
                attach_n += 1
                if not att.get("available"):
                    attach_unavail += 1
    load_ms = int((time.perf_counter() - load_t0) * 1000)
    return {
        "label": label,
        "ok": True,
        "query_ms": listed.get("query_ms"),
        "wall_ms": wall_ms,
        "thread_open_sample_ms": load_ms,
        "cards_returned": len(listed.get("items") or []),
        "thread_total_show_by_default": listed.get("thread_total"),
        "card_cap": GALLERY_CARD_CAP,
        "excluded": listed.get("excluded") or {},
        "stale": bool(listed.get("stale")),
        "cancelled": bool(listed.get("cancelled")),
        "attachment_sample_threads": sample,
        "attachment_records_in_sample": attach_n,
        "attachment_unavailable_in_sample": attach_unavail,
    }


def run() -> dict[str, Any]:
    from memorybox.db import connection
    from memorybox.explore.prepared_comms import abandon_token, new_ask_token, token_live

    with connection() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        dbname = require_flags(conn)
        people = [measure_label(conn, name) for name in ("Peggy", "Sue", "Tom")]
        first = new_ask_token()
        second = new_ask_token()
        cancel_ok = (not token_live(first)) and token_live(second)
        abandon_token(second)
    report = {
        "ok": True,
        "phase": "C",
        "read_only": True,
        "database_kind": "memorybox" if dbname == "memorybox" else "other",
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "gallery_flag_default": "off",
        "flightsim_serve_flag_not_set_by_this_tool": True,
        "people": people,
        "cancel_previous_ask_token": cancel_ok,
        "notes": [
            "query_ms is SQL list_person_threads; photos-first Gallery TTFV is separate serve latency.",
            "thread_total_show_by_default is full Person match after commercial default filter.",
            "cards_returned is capped for founder-facing Gallery.",
        ],
    }
    assert_counts_only(report)
    return report


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        report = run()
    except TimingError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
