"""Deterministic candidate discovery. Model proposals stay candidate and I7A-traced."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from memorybox.db import connection
from memorybox.occurrence.store import (
    evidence_key,
    link_place,
    rejected_keys,
    upsert_membership,
)

_STOP = frozenset(
    {
        "the",
        "our",
        "a",
        "an",
        "to",
        "of",
        "and",
        "trip",
        "event",
        "show",
        "me",
        "my",
        "we",
        "us",
        "in",
        "on",
        "at",
        "from",
    }
)
_TOKEN = re.compile(r"[a-z0-9']{3,}")


def tokens_from_label(label: str) -> list[str]:
    parts = _TOKEN.findall((label or "").lower())
    return [p for p in parts if p not in _STOP]


def _payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _day(value: Any) -> str:
    s = str(value or "")[:10]
    return s if len(s) == 10 and s[0].isdigit() else ""


def _in_window(day: str, start: str | None, end: str | None) -> bool:
    if not day:
        return False
    if start and day < str(start)[:10]:
        return False
    if end and day > str(end)[:10]:
        return False
    return True


def _blob_match(blob: str, tokens: list[str]) -> bool:
    if not tokens:
        return False
    b = blob.lower()
    return any(t in b for t in tokens)


def _trace_model_proposal(detail: dict[str, Any]) -> None:
    try:
        from memorybox.ai_trace import context as ai_ctx
        from memorybox.ai_trace import store as ai_store

        tid = ai_ctx.current_trace_id()
        if not tid:
            return
        ai_store.insert_span(
            trace_id=tid,
            stage="occurrence_discovery",
            component="occurrence.discover",
            operation="model_proposal",
            assembled_context=detail,
            disposition={"status": "candidate", "auto_confirm": False},
        )
    except Exception:
        return


def propose_model_candidate(
    *,
    occurrence_id: str,
    evidence_kind: str,
    evidence_ref: dict[str, Any],
    reason: str,
    confidence: float | None = None,
) -> dict[str, Any]:
    """Model assistance may propose only. Never owner-confirms."""
    _trace_model_proposal(
        {
            "occurrence_id": occurrence_id,
            "evidence_kind": evidence_kind,
            "reason": reason,
            "join_method": "model_proposal",
        }
    )
    return upsert_membership(
        occurrence_id=occurrence_id,
        evidence_kind=evidence_kind,
        evidence_ref=evidence_ref,
        join_method="model_proposal",
        status="candidate",
        confidence=confidence,
        actor_key="model",
        provenance={"reason": reason, "i7a": True},
    )


def discover_candidates(
    occ: dict[str, Any],
    *,
    include_sms: bool = False,
    photo_hits: list[Any] | None = None,
    limit_each: int = 40,
) -> dict[str, Any]:
    """Deterministic proposals from date window, Place, calendar identity, tokens."""
    oid = str(occ["id"])
    tokens = tokens_from_label(str(occ.get("label") or ""))
    t0 = str(occ.get("time_start") or "")[:10] or None
    t1 = str(occ.get("time_end") or "")[:10] or None
    blocked = rejected_keys(oid)
    added = 0
    skipped_rejected = 0

    def _allow(kind: str, ref: dict[str, Any]) -> bool:
        key = f"{kind}|{evidence_key(kind, ref)}"
        if kind in ("email", "sms", "calendar", "communication"):
            key = f"{kind}|{evidence_key(kind, ref)}"
        if key in blocked or f"communication|{evidence_key('communication', ref)}" in blocked:
            nonlocal skipped_rejected
            skipped_rejected += 1
            return False
        return True

    with connection() as conn:
        cal_rows = conn.execute(
            """
            SELECT id, summary, payload_json
            FROM evidence
            WHERE evidence_kind = 'calendar_event'
            ORDER BY created_at DESC
            LIMIT 4000
            """
        ).fetchall()
        comm_rows = conn.execute(
            """
            SELECT id, summary, payload_json
            FROM evidence
            WHERE evidence_kind = 'communication'
            ORDER BY created_at DESC
            LIMIT 8000
            """
        ).fetchall()
        spoken_rows = conn.execute(
            """
            SELECT id::text AS id, video_provider_key, video_external_id,
                   t_start, t_end, text, person_id
            FROM speech_spoken_moments
            WHERE COALESCE(status, 'accepted') <> 'withdrawn'
            ORDER BY t_start
            LIMIT 4000
            """
        ).fetchall()
        face_rows = conn.execute(
            """
            SELECT id::text AS id, video_provider_key, video_external_id,
                   start_sec, end_sec, person_id
            FROM face_appearance_moments
            WHERE COALESCE(status, 'accepted') <> 'withdrawn'
            LIMIT 2000
            """
        ).fetchall()

    for r in cal_rows:
        payload = _payload(r["payload_json"])
        title = str(payload.get("title") or r.get("summary") or "")
        loc = str(payload.get("location") or "")
        start = str(payload.get("start") or "")
        day = _day(start)
        token_hit = _blob_match(f"{title} {loc}", tokens)
        date_hit = bool(t0 and t1 and day and _in_window(day, t0, t1))
        if not (token_hit or date_hit):
            continue
        if date_hit and not token_hit and not loc:
            # Date-only calendar rows are supporting, not strong, unless token matches.
            if not include_sms:
                join = "date_overlap"
            else:
                join = "date_overlap"
        join = "calendar_uid" if payload.get("event_uid") and token_hit else (
            "exact_place" if loc and token_hit else (
                "date_overlap" if date_hit and token_hit else (
                    "filename_context" if token_hit else "date_overlap"
                )
            )
        )
        ref = {
            "kind": "calendar_event",
            "evidence_id": str(r["id"]),
            "event_uid": payload.get("event_uid"),
            "title": title,
            "start": start,
            "location": loc,
        }
        if not _allow("calendar", ref):
            continue
        upsert_membership(
            occurrence_id=oid,
            evidence_kind="calendar",
            evidence_ref=ref,
            join_method=join,
            status="candidate",
            confidence=0.8 if token_hit and date_hit else 0.55,
            actor_key="system",
        )
        added += 1
        if loc:
            link_place(oid, loc)
        if added >= limit_each:
            break

    comm_added = 0
    for r in comm_rows:
        payload = _payload(r["payload_json"])
        channel = str(payload.get("channel") or payload.get("source") or "").lower()
        kind = "sms" if channel in ("sms", "imessage", "mms", "rcs") else "email"
        if kind == "sms" and not include_sms and not tokens:
            continue
        sent = str(payload.get("sent_at") or payload.get("date") or "")
        day = _day(sent)
        blob = " ".join(
            [
                str(r.get("summary") or ""),
                str(payload.get("subject") or ""),
                str(payload.get("body_text") or "")[:800],
                str(payload.get("thread_id") or ""),
            ]
        )
        token_hit = _blob_match(blob, tokens)
        date_hit = bool(t0 and t1 and day and _in_window(day, t0, t1))
        if kind == "sms" and include_sms:
            if not date_hit and not token_hit:
                continue
        elif not token_hit:
            continue
        elif t0 and t1 and day and not date_hit:
            # Token match outside the occurrence window stays out unless no window.
            continue
        join = "date_overlap" if date_hit and token_hit else (
            "subject_thread" if token_hit else "date_overlap"
        )
        ref = {
            "kind": "communication",
            "evidence_id": str(r["id"]),
            "channel": kind,
            "sent_at": sent,
            "subject": payload.get("subject"),
        }
        if not _allow(kind, ref):
            continue
        upsert_membership(
            occurrence_id=oid,
            evidence_kind=kind,
            evidence_ref=ref,
            join_method=join,
            status="candidate",
            confidence=0.7 if date_hit and token_hit else 0.45,
            actor_key="system",
        )
        comm_added += 1
        added += 1
        if comm_added >= limit_each:
            break

    spoken_added = 0
    for r in spoken_rows:
        text = str(r.get("text") or "")
        if not _blob_match(text, tokens):
            continue
        ref = {
            "kind": "spoken_moment",
            "spoken_moment_id": str(r["id"]),
            "video_provider_key": r.get("video_provider_key"),
            "video_external_id": r.get("video_external_id"),
            "t_start": float(r["t_start"]),
            "t_end": float(r["t_end"]),
            "text": text[:400],
        }
        if not _allow("spoken_moment", ref):
            continue
        upsert_membership(
            occurrence_id=oid,
            evidence_kind="spoken_moment",
            evidence_ref=ref,
            join_method="subject_thread",
            status="candidate",
            confidence=0.6,
            actor_key="system",
        )
        spoken_added += 1
        added += 1
        if spoken_added >= limit_each:
            break

    face_added = 0
    if t0 and t1:
        for r in face_rows:
            ref = {
                "kind": "face_range",
                "appearance_moment_id": str(r["id"]),
                "video_provider_key": r.get("video_provider_key"),
                "video_external_id": r.get("video_external_id"),
                "start_sec": float(r["start_sec"] or 0),
                "end_sec": float(r["end_sec"] or 0),
            }
            # Face ranges need supporting overlap; skip unless caller tagged provenance.
            continue

    photo_added = 0
    for p in photo_hits or []:
        taken = getattr(p, "taken_at", None) if not isinstance(p, dict) else p.get("taken_at")
        place = getattr(p, "place", None) if not isinstance(p, dict) else p.get("place")
        loc = getattr(p, "location", None) if not isinstance(p, dict) else p.get("location")
        eid = getattr(p, "external_id", None) if not isinstance(p, dict) else p.get("external_id")
        pk = getattr(p, "provider_key", None) if not isinstance(p, dict) else p.get("provider_key")
        day = _day(taken)
        place_s = f"{place or ''} {loc or ''}"
        token_hit = _blob_match(place_s + " " + str(eid or ""), tokens)
        date_hit = bool(t0 and t1 and day and _in_window(day, t0, t1))
        gps = None
        lat = getattr(p, "latitude", None) if not isinstance(p, dict) else p.get("latitude")
        lng = getattr(p, "longitude", None) if not isinstance(p, dict) else p.get("longitude")
        if lat is not None and lng is not None:
            gps = True
        if not (date_hit or token_hit or gps):
            continue
        join = "exact_place" if gps or token_hit else "date_overlap"
        ref = {
            "kind": "photo",
            "provider_key": pk or "immich",
            "external_id": str(eid),
            "taken_at": taken,
            "place": place or loc,
            "latitude": lat,
            "longitude": lng,
        }
        if not _allow("photo", ref):
            continue
        upsert_membership(
            occurrence_id=oid,
            evidence_kind="photo",
            evidence_ref=ref,
            join_method=join,
            status="candidate",
            confidence=0.75 if gps else 0.5,
            actor_key="system",
        )
        photo_added += 1
        added += 1
        if place or loc:
            link_place(
                oid,
                str(place or loc),
                latitude=float(lat) if lat is not None else None,
                longitude=float(lng) if lng is not None else None,
            )
        if photo_added >= limit_each:
            break

    return {
        "added": added,
        "skipped_rejected": skipped_rejected,
        "tokens": tokens,
        "spoken": spoken_added,
        "photos": photo_added,
        "communications": comm_added,
        "faces_considered": face_added,
    }


def expand_window(start: str | None, end: str | None, days: int = 2) -> tuple[str | None, str | None]:
    if not start or not end:
        return start, end
    try:
        a = datetime.fromisoformat(str(start)[:10]).replace(tzinfo=timezone.utc)
        b = datetime.fromisoformat(str(end)[:10]).replace(tzinfo=timezone.utc)
        return (a - timedelta(days=days)).date().isoformat(), (b + timedelta(days=days)).date().isoformat()
    except ValueError:
        return start, end
