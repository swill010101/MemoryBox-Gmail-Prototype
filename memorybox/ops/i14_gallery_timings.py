"""Read-only Phase C timings against the active household-email generation.

Does not enable Gallery on serve, activate, load, or migrate.
Counts-only JSON: no UUIDs, addresses, bodies, or generation ids.
"""
from __future__ import annotations

import json
import os
import re
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


def _ask_person_id(label: str) -> str | None:
    from memorybox.person import find_ask_person_by_name

    view = find_ask_person_by_name(label, lazy_seed=False)
    if view is None or not getattr(view, "id", None):
        return None
    return str(view.id)


def measure_label(conn: Any, label: str) -> dict[str, Any]:
    from memorybox.explore.prepared_comms import (
        GALLERY_PAGE_SIZE,
        interaction_proof,
        list_person_buckets,
        list_person_threads,
        load_thread,
        new_ask_token,
    )

    pid = _ask_person_id(label)
    if not pid:
        return {"label": label, "ok": False, "error": "ask_person_unresolved"}
    token = new_ask_token()
    t0 = time.perf_counter()
    unbounded = list_person_buckets(conn, person_id=pid, token=token)
    unbounded_ms = int((time.perf_counter() - t0) * 1000)
    t1 = time.perf_counter()
    y2017 = list_person_buckets(
        conn,
        person_id=pid,
        token=token,
        date_from="2017-01-01",
        date_to="2017-12-31",
    )
    year_ms = int((time.perf_counter() - t1) * 1000)
    year_keys = [str(b.get("key") or "") for b in (y2017.get("buckets") or [])]
    off_year = [k for k in year_keys if not k.startswith("2017")]
    month_sum = sum(int(b.get("thread_n") or 0) for b in (y2017.get("buckets") or []))
    t2 = time.perf_counter()
    detail = list_person_threads(
        conn,
        person_id=pid,
        token=token,
        date_from="2017-01-01",
        date_to="2017-12-31",
        cap=GALLERY_PAGE_SIZE,
    )
    detail_ms = int((time.perf_counter() - t2) * 1000)
    cancel_page = False
    if detail.get("next_cursor"):
        old = token
        new_ask_token()
        late = list_person_threads(
            conn,
            person_id=pid,
            token=old,
            date_from="2017-01-01",
            date_to="2017-12-31",
            before_id=detail["next_cursor"].get("before_id"),
            before_latest=detail["next_cursor"].get("before_latest"),
        )
        cancel_page = bool(late.get("cancelled"))
        token = new_ask_token()
        detail = list_person_threads(
            conn,
            person_id=pid,
            token=token,
            date_from="2017-01-01",
            date_to="2017-12-31",
        )
    attach_n = 0
    attach_unavail = 0
    originals = 0
    warnings = 0
    proof_ok = True
    sample = 0
    load_t0 = time.perf_counter()
    for card in detail.get("items") or []:
        if sample >= 5:
            break
        did = str(card.get("display_id") or "")
        if not did:
            continue
        sample += 1
        loaded = load_thread(conn, did)
        proof = interaction_proof(loaded)
        proof_ok = proof_ok and all(proof.values())
        originals += sum(1 for m in loaded.get("messages") or [] if m.get("evidence_id"))
        warnings += sum(1 for m in loaded.get("messages") or [] if m.get("warnings"))
        for msg in loaded.get("messages") or []:
            for att in msg.get("attachments") or []:
                attach_n += 1
                if not att.get("available") or att.get("gallery_action") == "record_only":
                    attach_unavail += 1
    load_ms = int((time.perf_counter() - load_t0) * 1000)
    match = (unbounded.get("person_match") or {}).get("status")
    year_buckets = {
        str(b.get("key")): int(b.get("thread_n") or 0)
        for b in (unbounded.get("buckets") or [])
    }
    month_buckets = {
        str(b.get("key")): {
            "thread_n": int(b.get("thread_n") or 0),
            "message_n": int(b.get("message_n") or 0),
        }
        for b in (y2017.get("buckets") or [])
    }
    return {
        "label": label,
        "ok": True,
        "ask_path": "find_ask_person_by_name",
        "ask_lazy_seed": False,
        "person_match": match,
        "unbounded_bucket_ms": unbounded_ms,
        "unbounded_thread_total": int(unbounded.get("scoped_thread_total") or 0),
        "unbounded_year_buckets": year_buckets,
        "year_2017_bucket_ms": year_ms,
        "year_2017_thread_total": int(y2017.get("scoped_thread_total") or 0),
        "year_2017_month_bucket_sum": month_sum,
        "year_2017_month_buckets": month_buckets,
        "year_2017_off_scope_keys": off_year,
        "year_2017_grain": y2017.get("grain"),
        "detail_page_ms": detail_ms,
        "detail_page_cards": len(detail.get("items") or []),
        "page_size": GALLERY_PAGE_SIZE,
        "excluded": unbounded.get("excluded") or {},
        "cancel_stale_page_request": cancel_page,
        "thread_open_sample_ms": load_ms,
        "attachment_sample_threads": sample,
        "attachment_records_in_sample": attach_n,
        "attachment_unavailable_or_record_only": attach_unavail,
        "originals_in_sample_messages": originals,
        "messages_with_warnings_in_sample": warnings,
        "interaction_proof_ok": proof_ok,
        "browser_card_bound": GALLERY_PAGE_SIZE,
        "query_ms": unbounded.get("query_ms"),
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
    unresolved = [p["label"] for p in people if p.get("error") == "ask_person_unresolved"]
    report = {
        "ok": True,
        "phase": "C3",
        "read_only": True,
        "database_kind": "memorybox" if dbname == "memorybox" else "other",
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "gallery_flag_default": "off",
        "flightsim_serve_flag_not_set_by_this_tool": True,
        "time_to_first_photo_video": "Find payload (photos/video) returns before prepared-comms buckets; mixed Gallery stays usable.",
        "people": people,
        "ask_unresolved": unresolved,
        "cancel_previous_ask_token": cancel_ok,
        "notes": [
            "Bucket counts are the full Ask-scoped set. The 80-row bound is thread-detail only.",
            "Year-precision Asks use month buckets; person-only Asks use year buckets.",
            "Ask path is find_ask_person_by_name(lazy_seed=False), same resolver as Person Ask.",
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
