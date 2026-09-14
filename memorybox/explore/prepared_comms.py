"""I14 Phase C — Gallery reads of the active household-email generation.

Flag MEMORYBOX_I14_GALLERY_COMMS=1 (default off). Never parses raw mbox.
Never writes comms_* or evidence. Active generation only.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

DISPLAY_COMMERCIAL = frozenset({"not_commercial", "retain_life_evidence"})
HIDE_ELIGIBILITY = frozenset({"suppress_default", "hold_uncertain"})
GALLERY_CARD_CAP = 200
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


def list_person_threads(
    conn: Any,
    *,
    person_id: str,
    token: str,
    cap: int = GALLERY_CARD_CAP,
) -> dict[str, Any]:
    started = time.perf_counter()
    if token and not token_live(token):
        return {
            "ok": True,
            "cancelled": True,
            "items": [],
            "token": token,
            "query_ms": 0,
        }
    gid = active_generation_id(conn)
    if gid is None:
        cached = _last_complete.get(person_id) or {}
        return {
            "ok": True,
            "stale": True,
            "updated_through": cached.get("updated_through"),
            "items": list(cached.get("items") or []),
            "thread_total": int(cached.get("thread_total") or 0),
            "excluded": cached.get("excluded") or {},
            "token": token,
            "query_ms": int((time.perf_counter() - started) * 1000),
            "active_generation": False,
        }
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
    excl = {str(r["gallery_eligibility"]): int(r["n"]) for r in excluded}
    shown = int(excl.get("show_by_default") or 0)
    rows = conn.execute(
        """
        SELECT t.display_id, t.earliest_at, t.latest_at, t.message_count,
               t.identity_confidence, t.gallery_eligibility,
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
         WHERE t.generation_id = %s
           AND t.gallery_eligibility = 'show_by_default'
           AND EXISTS (
                 SELECT 1
                   FROM comms_prepared_messages m
                   JOIN comms_prepared_participants p ON p.message_id = m.id
                  WHERE m.thread_id = t.id AND p.person_id = %s
               )
         ORDER BY t.latest_at DESC NULLS LAST, t.display_id
         LIMIT %s
        """,
        (PREVIEW_CHARS, list(DISPLAY_COMMERCIAL), gid, person_id, cap),
    ).fetchall()
    if token and not token_live(token):
        return {
            "ok": True,
            "cancelled": True,
            "items": [],
            "token": token,
            "query_ms": int((time.perf_counter() - started) * 1000),
        }
    items = []
    seen: set[str] = set()
    for rec in rows:
        did = str(rec["display_id"])
        if did in seen:
            continue
        seen.add(did)
        earliest = _iso(rec["earliest_at"])
        latest = _iso(rec["latest_at"])
        date = latest or earliest
        title = str(rec["subject"] or "").strip() or "Email thread"
        who = str(rec.get("participants") or "").strip() or "Email"
        items.append(
            {
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
                "people": [],
            }
        )
    updated = datetime.now(timezone.utc).date().isoformat()
    payload = {
        "ok": True,
        "cancelled": False,
        "stale": False,
        "active_generation": True,
        "updated_through": updated,
        "items": items,
        "thread_total": shown,
        "excluded": {
            "suppress_default": int(excl.get("suppress_default") or 0),
            "hold_uncertain": int(excl.get("hold_uncertain") or 0),
            "show_by_default": shown,
        },
        "token": token,
        "query_ms": int((time.perf_counter() - started) * 1000),
        "card_cap": cap,
    }
    _last_complete[person_id] = {
        "updated_through": updated,
        "items": items,
        "thread_total": shown,
        "excluded": payload["excluded"],
    }
    return payload


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
                "evidence_id": str(msg["evidence_id"]),
                "subject": msg["subject"],
                "sent_at": msg["sent_at"].isoformat() if hasattr(msg["sent_at"], "isoformat") else str(msg["sent_at"]),
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
                        "parent_evidence_id": str(msg["evidence_id"]),
                        "attachment_evidence_id": str(a["attachment_evidence_id"])
                        if a["attachment_evidence_id"]
                        else None,
                        "available": bool(a["attachment_evidence_id"] or a["source_locator"]),
                    }
                    for a in atts
                ],
            }
        )
        if body.strip():
            who = from_p[0]["label"] if from_p else "Someone"
            story_parts.append(f"{who}: {body.strip()}")
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
    }
