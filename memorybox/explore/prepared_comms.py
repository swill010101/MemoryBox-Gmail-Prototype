"""I14 Phase C — Gallery reads of the active household-email generation.

Flag MEMORYBOX_I14_GALLERY_COMMS=1 (default off). Never parses raw mbox.
Never writes comms_* or evidence. Active generation only.

Date-bucket counts are complete and scoped to the Ask. The 80-row bound
applies only when opening a month/year communication bucket.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from memorybox.explore.gallery_scope import (
    CommsAskScope,
    attachment_state_copy,
    comms_ask_scope,
    empty_prepared_body_notice,
)

DISPLAY_COMMERCIAL = frozenset({"not_commercial", "retain_life_evidence"})
HIDE_ELIGIBILITY = frozenset({"suppress_default", "hold_uncertain"})
GALLERY_PAGE_SIZE = 80
GALLERY_CARD_CAP = GALLERY_PAGE_SIZE
PREVIEW_CHARS = 180

_lock = threading.Lock()
_tokens: dict[str, float] = {}
_last_complete: dict[str, dict[str, Any]] = {}


def gallery_comms_enabled() -> bool:
    return os.environ.get("MEMORYBOX_I14_GALLERY_COMMS", "").strip() == "1"


def new_ask_token() -> str:
    token = uuid.uuid4().hex
    with _lock:
        _tokens.clear()
        _tokens[token] = time.monotonic()
    return token


def token_live(token: str) -> bool:
    if not token:
        return False
    with _lock:
        return token in _tokens


def abandon_token(token: str) -> None:
    with _lock:
        _tokens.pop(token, None)


def _iso(raw: Any) -> str:
    if raw is None:
        return ""
    if hasattr(raw, "isoformat"):
        dt = raw
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).date().isoformat()
    text = str(raw)
    return text[:10] if len(text) >= 10 else text


def _party_label(row: dict[str, Any]) -> dict[str, Any]:
    conf = str(row.get("identity_confidence") or "")
    name = str(row.get("display_name") or "").strip()
    authenticated = conf in {"authenticated_focal", "authenticated_other"} and row.get("person_id")
    if authenticated and name:
        return {"label": name, "trusted": True, "role": row.get("role")}
    if name:
        return {"label": name, "trusted": False, "role": row.get("role")}
    return {"label": "Unknown participant", "trusted": False, "role": row.get("role")}


def active_generation_id(conn: Any) -> Any | None:
    row = conn.execute(
        """
        SELECT id FROM comms_prepared_active_generations
         WHERE scope_key = 'household_email'
         LIMIT 1
        """
    ).fetchone()
    if not row:
        return None
    return row["id"]


def _item_from_row(rec: dict[str, Any]) -> dict[str, Any]:
    did = str(rec["display_id"])
    earliest = _iso(rec["earliest_at"])
    latest = _iso(rec["latest_at"])
    date = latest or earliest
    title = str(rec["subject"] or "").strip() or "Email thread"
    who = str(rec.get("participants") or "").strip() or "Email"
    return {
        "id": f"prepared:{did}",
        "type": "email",
        "kind": "email",
        "media_type": "email",
        "title": title[:120],
        "date": date,
        "date_end": latest if latest and earliest and latest != earliest else "",
        "undated": not date,
        "preview": str(rec["preview"] or "").strip(),
        "detail": str(rec["preview"] or "").strip(),
        "from": who,
        "to": "",
        "display_id": did,
        "prepared": True,
        "gallery_default_hidden": False,
        "attachment_count": int(rec["attachment_count"] or 0),
        "message_count": int(rec["message_count"] or 0),
        "identity_confidence": rec["identity_confidence"],
        "latest_at": rec["latest_at"].isoformat()
        if hasattr(rec.get("latest_at"), "isoformat")
        else (str(rec["latest_at"]) if rec.get("latest_at") else None),
        "people": [],
    }


def _cancelled(token: str, started: float) -> dict[str, Any]:
    return {
        "ok": True,
        "cancelled": True,
        "items": [],
        "buckets": [],
        "token": token,
        "query_ms": int((time.perf_counter() - started) * 1000),
    }


def _scope_kwargs(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    year: int | None = None,
    month: int | None = None,
) -> CommsAskScope:
    if date_from or date_to:
        return comms_ask_scope(date_from, date_to)
    if year is not None and month is not None:
        mo = int(month)
        last = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
        return CommsAskScope(
            f"{int(year):04d}-{mo:02d}-01",
            f"{int(year):04d}-{mo:02d}-{last:02d}",
            "month",
            int(year),
        )
    if year is not None:
        y = int(year)
        return CommsAskScope(f"{y:04d}-01-01", f"{y:04d}-12-31", "month", y)
    return comms_ask_scope(None, None)


def _match_status(excl: dict[str, int]) -> dict[str, Any]:
    shown = int(excl.get("show_by_default") or 0)
    any_n = sum(int(v) for v in excl.values())
    if any_n == 0:
        return {"status": "no_prepared_participant", "reachable_show_by_default": 0}
    if shown == 0:
        return {"status": "linked_but_filtered", "reachable_show_by_default": 0}
    return {"status": "linked", "reachable_show_by_default": shown}


def _eligibility_counts(conn: Any, gid: Any, person_id: str) -> dict[str, int]:
    excluded = conn.execute(
        """
        SELECT t.gallery_eligibility, COUNT(DISTINCT t.id)::int AS n
          FROM comms_prepared_threads t
          JOIN comms_prepared_messages m ON m.thread_id = t.id
          JOIN comms_prepared_participants p ON p.message_id = m.id
         WHERE t.generation_id = %s AND p.person_id = %s
         GROUP BY t.gallery_eligibility
        """,
        (gid, person_id),
    ).fetchall()
    return {str(r["gallery_eligibility"]): int(r["n"]) for r in excluded}


def list_person_buckets(
    conn: Any,
    *,
    person_id: str,
    token: str,
    date_from: str | None = None,
    date_to: str | None = None,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    """Full date-bucket counts for the Ask. Never limited to 80 threads."""
    started = time.perf_counter()
    if token and not token_live(token):
        return _cancelled(token, started)
    scope = _scope_kwargs(date_from=date_from, date_to=date_to, year=year, month=month)
    gid = active_generation_id(conn)
    if gid is None:
        cached = _last_complete.get(person_id) or {}
        return {
            "ok": True,
            "stale": True,
            "view": "buckets",
            "updated_through": cached.get("updated_through"),
            "items": [],
            "buckets": list(cached.get("buckets") or []),
            "grain": cached.get("grain") or scope.grain,
            "scoped_thread_total": int(cached.get("scoped_thread_total") or 0),
            "scoped_message_total": int(cached.get("scoped_message_total") or 0),
            "thread_total": int(cached.get("thread_total") or 0),
            "reachable_total": int(cached.get("scoped_thread_total") or cached.get("thread_total") or 0),
            "excluded": cached.get("excluded") or {},
            "person_match": cached.get("person_match")
            or {"status": "no_active_generation"},
            "token": token,
            "query_ms": int((time.perf_counter() - started) * 1000),
            "active_generation": False,
            "undated_n": 0,
            "scope_year": scope.calendar_year,
            "date_from": scope.date_from,
            "date_to": scope.date_to,
        }
    excl = _eligibility_counts(conn, gid, person_id)
    match = _match_status(excl)
    if token and not token_live(token):
        return _cancelled(token, started)
    grain_month = scope.grain == "month"
    rows = conn.execute(
        """
        -- gallery_buckets
        WITH scoped AS (
          SELECT t.id AS thread_id,
                 MAX(m.sent_at) AS in_scope_latest,
                 COUNT(m.id)::int AS message_n
            FROM comms_prepared_threads t
            JOIN comms_prepared_messages m ON m.thread_id = t.id
           WHERE t.generation_id = %s
             AND t.gallery_eligibility = 'show_by_default'
             AND m.sent_at IS NOT NULL
             AND (%s::date IS NULL OR m.sent_at::date >= %s::date)
             AND (%s::date IS NULL OR m.sent_at::date <= %s::date)
             AND EXISTS (
                   SELECT 1
                     FROM comms_prepared_participants p
                    WHERE p.message_id = m.id AND p.person_id = %s
                 )
           GROUP BY t.id
        )
        SELECT EXTRACT(YEAR FROM in_scope_latest)::int AS y,
               EXTRACT(MONTH FROM in_scope_latest)::int AS mo,
               COUNT(*)::int AS thread_n,
               SUM(message_n)::int AS message_n
          FROM scoped
         GROUP BY 1, 2
         ORDER BY 1 DESC, 2 DESC
        """,
        (
            gid,
            scope.date_from,
            scope.date_from,
            scope.date_to,
            scope.date_to,
            person_id,
        ),
    ).fetchall()
    buckets: list[dict[str, Any]] = []
    if grain_month:
        for r in rows:
            y, mo = r.get("y"), r.get("mo")
            if y is None or mo is None:
                continue
            buckets.append(
                {
                    "key": f"{int(y):04d}-{int(mo):02d}",
                    "year": int(y),
                    "month": int(mo),
                    "thread_n": int(r["thread_n"]),
                    "message_n": int(r["message_n"]),
                }
            )
    else:
        by_year: dict[int, dict[str, int]] = {}
        for r in rows:
            y = r.get("y")
            if y is None:
                continue
            yi = int(y)
            slot = by_year.setdefault(yi, {"thread_n": 0, "message_n": 0})
            slot["thread_n"] += int(r["thread_n"])
            slot["message_n"] += int(r["message_n"])
        for yi in sorted(by_year, reverse=True):
            slot = by_year[yi]
            buckets.append(
                {
                    "key": f"{yi:04d}",
                    "year": yi,
                    "month": None,
                    "thread_n": slot["thread_n"],
                    "message_n": slot["message_n"],
                }
            )
    scoped_threads = sum(int(b["thread_n"]) for b in buckets)
    scoped_msgs = sum(int(b["message_n"]) for b in buckets)
    updated = datetime.now(timezone.utc).date().isoformat()
    payload = {
        "ok": True,
        "cancelled": False,
        "stale": False,
        "view": "buckets",
        "active_generation": True,
        "updated_through": updated,
        "items": [],
        "buckets": buckets,
        "grain": scope.grain,
        "scoped_thread_total": scoped_threads,
        "scoped_message_total": scoped_msgs,
        "thread_total": int(excl.get("show_by_default") or 0),
        "reachable_total": scoped_threads,
        "excluded": {
            "suppress_default": int(excl.get("suppress_default") or 0),
            "hold_uncertain": int(excl.get("hold_uncertain") or 0),
            "show_by_default": int(excl.get("show_by_default") or 0),
        },
        "person_match": match,
        "undated_n": 0,
        "has_more": False,
        "next_cursor": None,
        "page_size": GALLERY_PAGE_SIZE,
        "token": token,
        "query_ms": int((time.perf_counter() - started) * 1000),
        "scope_year": scope.calendar_year,
        "date_from": scope.date_from,
        "date_to": scope.date_to,
        "card_cap": GALLERY_PAGE_SIZE,
    }
    _last_complete[person_id] = {
        "updated_through": updated,
        "buckets": buckets,
        "grain": scope.grain,
        "scoped_thread_total": scoped_threads,
        "scoped_message_total": scoped_msgs,
        "thread_total": payload["thread_total"],
        "excluded": payload["excluded"],
        "person_match": match,
    }
    return payload


def list_person_threads(
    conn: Any,
    *,
    person_id: str,
    token: str,
    cap: int | None = None,
    year: int | None = None,
    month: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    before_latest: str | None = None,
    before_id: str | None = None,
) -> dict[str, Any]:
    """Bounded thread page for one opened date bucket. Not Gallery card counts."""
    started = time.perf_counter()
    limit = GALLERY_PAGE_SIZE if cap is None else max(1, min(int(cap), GALLERY_PAGE_SIZE))
    if token and not token_live(token):
        return _cancelled(token, started)
    scope = _scope_kwargs(date_from=date_from, date_to=date_to, year=year, month=month)
    gid = active_generation_id(conn)
    if gid is None:
        return {
            "ok": True,
            "stale": True,
            "view": "threads",
            "items": [],
            "has_more": False,
            "next_cursor": None,
            "page_size": limit,
            "token": token,
            "query_ms": int((time.perf_counter() - started) * 1000),
            "active_generation": False,
        }
    excl = _eligibility_counts(conn, gid, person_id)
    match = _match_status(excl)
    if token and not token_live(token):
        return _cancelled(token, started)
    rows = conn.execute(
        """
        -- gallery_threads
        SELECT t.display_id, t.earliest_at, t.latest_at, t.message_count,
               t.identity_confidence, t.gallery_eligibility,
               scoped.in_scope_latest,
               (
                 SELECT m.subject FROM comms_prepared_messages m
                  WHERE m.thread_id = t.id ORDER BY m.ordinal LIMIT 1
               ) AS subject,
               (
                 SELECT left(m.cleaned_authored_text, %s)
                   FROM comms_prepared_messages m
                  WHERE m.thread_id = t.id
                    AND m.commercial_class = ANY(%s)
                    AND coalesce(m.cleaned_authored_text, '') <> ''
                  ORDER BY m.ordinal LIMIT 1
               ) AS preview,
               (
                 SELECT COUNT(*)::int FROM comms_prepared_attachments a
                   JOIN comms_prepared_messages m ON m.id = a.message_id
                  WHERE m.thread_id = t.id
               ) AS attachment_count,
               (
                 SELECT string_agg(nm, ', ')
                   FROM (
                     SELECT DISTINCT p.display_name AS nm
                       FROM comms_prepared_messages m
                       JOIN comms_prepared_participants p ON p.message_id = m.id
                      WHERE m.thread_id = t.id
                        AND p.person_id IS NOT NULL
                        AND coalesce(p.display_name, '') <> ''
                      LIMIT 4
                   ) names
               ) AS participants
          FROM comms_prepared_threads t
          JOIN (
            SELECT t2.id AS thread_id, MAX(m2.sent_at) AS in_scope_latest
              FROM comms_prepared_threads t2
              JOIN comms_prepared_messages m2 ON m2.thread_id = t2.id
             WHERE t2.generation_id = %s
               AND t2.gallery_eligibility = 'show_by_default'
               AND m2.sent_at IS NOT NULL
               AND (%s::date IS NULL OR m2.sent_at::date >= %s::date)
               AND (%s::date IS NULL OR m2.sent_at::date <= %s::date)
               AND EXISTS (
                     SELECT 1 FROM comms_prepared_participants p2
                      WHERE p2.message_id = m2.id AND p2.person_id = %s
                   )
             GROUP BY t2.id
          ) scoped ON scoped.thread_id = t.id
         WHERE (
                 %s::text IS NULL
                 OR (COALESCE(scoped.in_scope_latest, '-infinity'::timestamptz), t.display_id)
                    < (COALESCE(%s::timestamptz, '-infinity'::timestamptz), %s)
               )
         ORDER BY COALESCE(scoped.in_scope_latest, '-infinity'::timestamptz) DESC,
                  t.display_id DESC
         LIMIT %s
        """,
        (
            PREVIEW_CHARS,
            list(DISPLAY_COMMERCIAL),
            gid,
            scope.date_from,
            scope.date_from,
            scope.date_to,
            scope.date_to,
            person_id,
            before_id,
            before_latest,
            before_id,
            limit + 1,
        ),
    ).fetchall()
    if token and not token_live(token):
        return _cancelled(token, started)
    has_more = len(rows) > limit
    page = rows[:limit]
    items = []
    seen: set[str] = set()
    for rec in page:
        did = str(rec["display_id"])
        if did in seen:
            continue
        seen.add(did)
        item = _item_from_row(rec)
        in_scope = rec.get("in_scope_latest")
        if in_scope is not None:
            item["date"] = _iso(in_scope)
            item["undated"] = False
            item["latest_at"] = (
                in_scope.isoformat()
                if hasattr(in_scope, "isoformat")
                else str(in_scope)
            )
        items.append(item)
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = {
            "before_latest": last.get("latest_at"),
            "before_id": last["display_id"],
        }
    return {
        "ok": True,
        "cancelled": False,
        "stale": False,
        "view": "threads",
        "active_generation": True,
        "items": items,
        "has_more": has_more,
        "next_cursor": next_cursor,
        "person_match": match,
        "excluded": {
            "suppress_default": int(excl.get("suppress_default") or 0),
            "hold_uncertain": int(excl.get("hold_uncertain") or 0),
            "show_by_default": int(excl.get("show_by_default") or 0),
        },
        "page_size": limit,
        "card_cap": limit,
        "token": token,
        "query_ms": int((time.perf_counter() - started) * 1000),
        "date_from": scope.date_from,
        "date_to": scope.date_to,
        "year": scope.calendar_year if month or year else year,
        "month": month,
    }


def load_thread(conn: Any, display_id: str) -> dict[str, Any]:
    gid = active_generation_id(conn)
    if gid is None:
        return {"ok": False, "error": "no_active_generation"}
    trow = conn.execute(
        """
        SELECT * FROM comms_prepared_threads
         WHERE generation_id = %s AND display_id = %s
        """,
        (gid, display_id),
    ).fetchone()
    if not trow:
        return {"ok": False, "error": "thread_not_in_active_generation"}
    msgs = conn.execute(
        """
        SELECT * FROM comms_prepared_messages
         WHERE thread_id = %s ORDER BY ordinal
        """,
        (trow["id"],),
    ).fetchall()
    packed = []
    story_parts = []
    for msg in msgs:
        parties = conn.execute(
            """
            SELECT role, display_name, identity_confidence, person_id
              FROM comms_prepared_participants
             WHERE message_id = %s
             ORDER BY role, display_name
            """,
            (msg["id"],),
        ).fetchall()
        from_p = [_party_label(p) for p in parties if p["role"] == "from"]
        to_p = [_party_label(p) for p in parties if p["role"] == "to"]
        cc_p = [_party_label(p) for p in parties if p["role"] == "cc"]
        atts = conn.execute(
            """
            SELECT filename, mime_type, byte_size, gallery_action,
                   attachment_evidence_id, source_locator, attachment_ordinal
              FROM comms_prepared_attachments
             WHERE message_id = %s
             ORDER BY attachment_ordinal
            """,
            (msg["id"],),
        ).fetchall()
        warnings = []
        if str(msg.get("quote_quality") or "") != "clean":
            warnings.append("quote_quality_uncertain")
        if str(msg.get("identity_quality") or "") in {"uncertain", "unverified"}:
            warnings.append("participant_identity_uncertain")
        body = str(msg.get("cleaned_authored_text") or "")
        packed.append(
            {
                "ordinal": msg["ordinal"],
                "evidence_ref": msg["evidence_ref"],
                "evidence_id": str(msg["evidence_id"]) if msg.get("evidence_id") else None,
                "empty_prepared_text": not bool(body.strip()),
                "empty_body_notice": empty_prepared_body_notice()
                if not body.strip()
                else None,
                "original_href": (
                    "/explore/api/email/" + str(msg["evidence_id"])
                    if msg.get("evidence_id")
                    else None
                ),
                "subject": msg["subject"],
                "sent_at": msg["sent_at"].isoformat()
                if hasattr(msg["sent_at"], "isoformat")
                else str(msg["sent_at"]),
                "from": from_p,
                "to": to_p,
                "cc": cc_p,
                "cleaned_authored_text": body,
                "quote_quality": msg["quote_quality"],
                "identity_quality": msg["identity_quality"],
                "voice_corpus": bool(msg["voice_corpus"]),
                "commercial_class": msg["commercial_class"],
                "warnings": warnings,
                "attachments": [
                    {
                        "filename": a["filename"],
                        "mime_type": a["mime_type"],
                        "byte_size": a["byte_size"],
                        "gallery_action": a["gallery_action"],
                        "attachment_ordinal": a["attachment_ordinal"],
                        "parent_evidence_id": str(msg["evidence_id"])
                        if msg.get("evidence_id")
                        else None,
                        "attachment_evidence_id": str(a["attachment_evidence_id"])
                        if a["attachment_evidence_id"]
                        else None,
                        "available": bool(a["attachment_evidence_id"] or a["source_locator"]),
                        "state_label": attachment_state_copy(
                            action=a["gallery_action"],
                            available=bool(
                                a["attachment_evidence_id"] or a["source_locator"]
                            ),
                            mime=str(a["mime_type"] or ""),
                            filename=str(a["filename"] or ""),
                        ),
                    }
                    for a in atts
                ],
            }
        )
        who = from_p[0]["label"] if from_p else "Someone"
        story_parts.append(f"{who}: {body.strip()}" if body.strip() else f"{who}:")
    return {
        "ok": True,
        "display_id": display_id,
        "identity_confidence": trow["identity_confidence"],
        "messages": packed,
        "story_body": "\n\n".join(story_parts),
        "story_memory": {
            "source_kind": "email_thread",
            "source_id": display_id,
            "label_snapshot": str((msgs[0]["subject"] if msgs else "") or display_id),
        },
        "attachments_copied_into_story": False,
    }


def interaction_proof(thread: dict[str, Any]) -> dict[str, Any]:
    """Deterministic checks for original, attachments, story, warnings."""
    msgs = list(thread.get("messages") or [])
    authored = [m for m in msgs if str(m.get("cleaned_authored_text") or "").strip()]
    story = str(thread.get("story_body") or "")
    atts = [a for m in msgs for a in (m.get("attachments") or [])]
    mem = thread.get("story_memory") or {}
    return {
        "original_on_demand": all(bool(m.get("evidence_id")) for m in msgs) if msgs else False,
        "story_covers_authored": all(
            str(m.get("cleaned_authored_text") or "").strip() in story for m in authored
        ),
        "story_kind_email_thread": mem.get("source_kind") == "email_thread",
        "story_source_is_display_id": mem.get("source_id") == thread.get("display_id"),
        "attachments_linked_not_copied": all("bytes" not in a for a in atts)
        and thread.get("attachments_copied_into_story") is False,
        "quote_or_identity_warnings": any(bool(m.get("warnings")) for m in msgs)
        or not msgs
        or all(
            str(m.get("quote_quality") or "") == "clean"
            and str(m.get("identity_quality") or "") not in {"uncertain", "unverified"}
            for m in msgs
        ),
        "viewable_attachments_have_parent": all(
            bool(a.get("parent_evidence_id"))
            for a in atts
            if a.get("available") and a.get("gallery_action") != "record_only"
        ),
    }
