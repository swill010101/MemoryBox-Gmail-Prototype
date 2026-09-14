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
        list_person_threads,
        load_thread,
        new_ask_token,
    )

    pid = _ask_person_id(label)
    if not pid:
        return {"label": label, "ok": False, "error": "ask_person_unresolved"}
    token = new_ask_token()
    t0 = time.perf_counter()
    page1 = list_person_threads(conn, person_id=pid, token=token)
    first_page_ms = int((time.perf_counter() - t0) * 1000)
    years = page1.get("years") or []
    year_sum = sum(int(y.get("n") or 0) for y in years)
    undated = int(page1.get("undated_n") or 0)
    reachable = int(page1.get("reachable_total") or 0)
    histogram_covers = year_sum + undated == reachable
    page2_ms = None
    page2_n = 0
    disjoint = True
    ids1 = {str(i.get("display_id")) for i in page1.get("items") or []}
    if page1.get("has_more") and page1.get("next_cursor") and token:
        cur = page1["next_cursor"]
        t1 = time.perf_counter()
        page2 = list_person_threads(
            conn,
            person_id=pid,
            token=token,
            before_latest=cur.get("before_latest"),
            before_id=cur.get("before_id"),
        )
        page2_ms = int((time.perf_counter() - t1) * 1000)
        ids2 = {str(i.get("display_id")) for i in page2.get("items") or []}
        page2_n = len(ids2)
        disjoint = ids1.isdisjoint(ids2) and not page2.get("cancelled")
    year_page_ms = None
    year_page_n = 0
    year_walk_ok = None
    walkable = [y for y in years if 0 < int(y.get("n") or 0) <= 240]
    if walkable:
        y = int(walkable[-1]["year"])
        t2 = time.perf_counter()
        yp = list_person_threads(conn, person_id=pid, token=token, year=y)
        year_page_ms = int((time.perf_counter() - t2) * 1000)
        year_page_n = len(yp.get("items") or [])
        expected = int(walkable[-1]["n"])
        got = 0
        cursor = None
        guard = 0
        while guard < 40:
            guard += 1
            chunk = list_person_threads(
                conn,
                person_id=pid,
                token=token,
                year=y,
                before_latest=(cursor or {}).get("before_latest"),
                before_id=(cursor or {}).get("before_id"),
            )
            got += len(chunk.get("items") or [])
            if not chunk.get("has_more"):
                break
            cursor = chunk.get("next_cursor")
            if not cursor:
                break
        year_walk_ok = got == expected
    cancel_page = False
    if page1.get("next_cursor"):
        old = token
        new_ask_token()
        late = list_person_threads(
            conn,
            person_id=pid,
            token=old,
            before_id=page1["next_cursor"].get("before_id"),
            before_latest=page1["next_cursor"].get("before_latest"),
        )
        cancel_page = bool(late.get("cancelled"))
    token = new_ask_token()
    page1 = list_person_threads(conn, person_id=pid, token=token)
    attach_n = 0
    attach_unavail = 0
    originals = 0
    warnings = 0
    proof_ok = True
    sample = 0
    load_t0 = time.perf_counter()
    for card in page1.get("items") or []:
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
    match = (page1.get("person_match") or {}).get("status")
    return {
        "label": label,
        "ok": True,
        "ask_path": "find_ask_person_by_name",
        "ask_lazy_seed": False,
        "person_match": match,
        "first_comms_page_ms": first_page_ms,
        "query_ms": page1.get("query_ms"),
        "second_page_ms": page2_ms,
        "second_page_cards": page2_n,
        "pages_disjoint": disjoint,
        "year_page_ms": year_page_ms,
        "year_page_cards": year_page_n,
        "year_fully_walked_matches_histogram": year_walk_ok,
        "histogram_covers_reachable": histogram_covers,
        "year_count": len(years),
        "undated_n": undated,
        "cards_in_browser_window": len(page1.get("items") or []),
        "page_size": GALLERY_PAGE_SIZE,
        "reachable_show_by_default": reachable,
        "excluded": page1.get("excluded") or {},
        "cancel_stale_page_request": cancel_page,
        "thread_open_sample_ms": load_ms,
        "attachment_sample_threads": sample,
        "attachment_records_in_sample": attach_n,
        "attachment_unavailable_or_record_only": attach_unavail,
        "originals_in_sample_messages": originals,
        "messages_with_warnings_in_sample": warnings,
        "interaction_proof_ok": proof_ok,
        "browser_card_bound": GALLERY_PAGE_SIZE,
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
        "phase": "C2",
        "read_only": True,
        "database_kind": "memorybox" if dbname == "memorybox" else "other",
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "gallery_flag_default": "off",
        "flightsim_serve_flag_not_set_by_this_tool": True,
        "time_to_first_photo_video": "Find payload (photos/video) returns before prepared-comms fetch; not delayed by paging.",
        "people": people,
        "ask_unresolved": unresolved,
        "cancel_previous_ask_token": cancel_ok,
        "notes": [
            "reachable_show_by_default is every default-visible thread; browser shows one page (80).",
            "Year chips plus Load older page through the reachable set without loading all cards.",
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
