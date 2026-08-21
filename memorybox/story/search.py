"""I10A mixed-evidence search for the Add memories picker."""
from __future__ import annotations

from typing import Any

from memorybox.db import connection
from memorybox.story import SOURCE_KINDS, StoryServiceError


def evidence_search(
    *,
    q: str = "",
    person_id: str | None = None,
    types: list[str] | None = None,
    time_start: str | None = None,
    time_end: str | None = None,
    place: str | None = None,
    limit: int = 48,
    offset: int = 0,
) -> dict[str, Any]:
    wanted = [t for t in (types or []) if t and t != "story"]
    if not wanted:
        wanted = [
            "photo",
            "video",
            "email_thread",
            "sms_conversation",
            "calendar_event",
            "artifact",
            "journal",
            "audio",
        ]
    for t in wanted:
        if t not in SOURCE_KINDS:
            raise StoryServiceError(f"unsupported type {t!r}")
    items: list[dict[str, Any]] = []
    truncated = False
    try:
        from memorybox.planner import plan_ask
        from memorybox.context import AskContext

        plan = plan_ask((q or "").strip() or "show me memories", AskContext.empty())
        if person_id:
            from dataclasses import replace

            plan = replace(
                plan,
                person_ids=tuple({*plan.person_ids, person_id}),
            )
    except Exception:
        plan = None

    if "photo" in wanted:
        photos, more = _photos(plan, q, limit=limit)
        items.extend(photos)
        truncated = truncated or more
    if "video" in wanted:
        videos, more = _videos(plan, limit=limit)
        items.extend(videos)
        truncated = truncated or more
    if "email_thread" in wanted or "sms_conversation" in wanted:
        comms, more = _comms(
            wanted, q, person_id, time_start, time_end, limit=limit
        )
        items.extend(comms)
        truncated = truncated or more
    if "calendar_event" in wanted:
        cals, more = _calendar(q, time_start, time_end, place, limit=limit)
        items.extend(cals)
        truncated = truncated or more
    if "artifact" in wanted:
        arts, more = _artifacts(q, person_id, limit=limit)
        items.extend(arts)
        truncated = truncated or more
    if "journal" in wanted:
        journals, more = _journals(q, person_id, limit=limit)
        items.extend(journals)
        truncated = truncated or more
    if "audio" in wanted:
        aud, more = _audio(q, limit=limit)
        items.extend(aud)
        truncated = truncated or more

    total = len(items)
    page = items[offset : offset + limit]
    return {
        "ok": True,
        "total": total,
        "truncated": truncated,
        "offset": offset,
        "limit": limit,
        "items": page,
    }


def _photos(plan: Any, q: str, *, limit: int) -> tuple[list[dict[str, Any]], bool]:
    out: list[dict[str, Any]] = []
    try:
        from memorybox.ask import retrieve as R
        from memorybox.ask.deps import build_photo

        if plan is not None:
            hits, _status = R.search_photos(plan, build_photo(), limit=max(limit, 24))
            for h in hits:
                d = h.to_dict() if hasattr(h, "to_dict") else dict(h)
                eid = str(d.get("external_id") or d.get("id") or "")
                if not eid:
                    continue
                out.append(
                    {
                        "source_kind": "photo",
                        "source_id": eid,
                        "title": d.get("original_filename")
                        or d.get("title")
                        or "Photo",
                        "occurred_on": d.get("taken_at"),
                        "thumb_url": d.get("thumb_url")
                        or f"/library/media/photo/{eid}",
                        "people": d.get("people") or [],
                    }
                )
    except Exception:
        return out, False
    return out, len(out) >= limit


def _videos(plan: Any, *, limit: int) -> tuple[list[dict[str, Any]], bool]:
    out: list[dict[str, Any]] = []
    try:
        from memorybox.ask import retrieve as R
        from memorybox.ask.deps import build_video, build_photo

        if plan is None:
            return out, False
        hits, _status = R.search_videos(plan, build_video(), photo=build_photo())
        for h in hits[:limit]:
            d = h.to_dict() if hasattr(h, "to_dict") else dict(h)
            eid = str(d.get("external_id") or d.get("video_external_id") or "")
            if not eid:
                continue
            out.append(
                {
                    "source_kind": "video",
                    "source_id": eid,
                    "title": d.get("label") or "Video",
                    "occurred_on": None,
                    "thumb_url": d.get("play_url") or None,
                    "attributes_json": {
                        "start_sec": d.get("start_sec"),
                        "end_sec": d.get("end_sec"),
                    },
                }
            )
    except Exception:
        return out, False
    return out, len(out) >= limit


def _comms(
    wanted: list[str],
    q: str,
    person_id: str | None,
    t0: str | None,
    t1: str | None,
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], bool]:
    kinds = []
    if "email_thread" in wanted:
        kinds.append("email")
    if "sms_conversation" in wanted:
        kinds.extend(["sms", "imessage", "mms", "rcs", "text"])
    out: list[dict[str, Any]] = []
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, evidence_kind, summary, payload_json
            FROM evidence
            WHERE evidence_kind = 'communication'
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (max(limit * 4, 80),),
        ).fetchall()
    needle = (q or "").lower()
    for r in rows:
        payload = r["payload_json"] or {}
        if isinstance(payload, str):
            import json

            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        ch = str(payload.get("channel") or payload.get("source_channel") or "").lower()
        if kinds and ch and ch not in kinds and not (
            "email" in kinds and "mail" in ch
        ):
            if "email" in kinds and ch in {"", "email", "gmail", "mbox"}:
                pass
            elif "sms" in kinds and ch in {"sms", "imessage", "text", "mms"}:
                pass
            elif not ch:
                pass
            else:
                continue
        blob = " ".join(
            [
                str(payload.get("subject") or ""),
                str(payload.get("body_text") or ""),
                str(payload.get("from") or ""),
                str(r.get("summary") or ""),
            ]
        ).lower()
        if needle and needle not in blob:
            continue
        kind = (
            "email_thread"
            if (ch in {"email", "gmail", "mbox", ""} or "mail" in ch)
            else "sms_conversation"
        )
        if kind not in wanted and not (
            kind == "email_thread" and "email_thread" in wanted
        ):
            if kind == "sms_conversation" and "sms_conversation" not in wanted:
                continue
        out.append(
            {
                "source_kind": kind,
                "source_id": str(r["id"]),
                "title": payload.get("subject")
                or payload.get("title")
                or (r.get("summary") or "Message"),
                "occurred_on": payload.get("sent_at") or payload.get("date"),
                "thumb_url": None,
                "attributes_json": {
                    "from": payload.get("from") or payload.get("from_name"),
                    "to": payload.get("to"),
                    "channel": ch,
                },
            }
        )
        if len(out) >= limit:
            return out, True
    return out, False


def _calendar(
    q: str, t0: str | None, t1: str | None, place: str | None, *, limit: int
) -> tuple[list[dict[str, Any]], bool]:
    out: list[dict[str, Any]] = []
    needle = (q or "").lower()
    pl = (place or "").lower()
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, summary, payload_json
            FROM evidence
            WHERE evidence_kind = 'calendar_event'
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (max(limit * 2, 40),),
        ).fetchall()
    for r in rows:
        payload = r["payload_json"] or {}
        if isinstance(payload, str):
            import json

            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        title = str(payload.get("summary") or payload.get("title") or r.get("summary") or "Event")
        loc = str(payload.get("location") or "")
        blob = f"{title} {loc}".lower()
        if needle and needle not in blob:
            continue
        if pl and pl not in loc.lower() and pl not in blob:
            continue
        out.append(
            {
                "source_kind": "calendar_event",
                "source_id": str(r["id"]),
                "title": title,
                "occurred_on": payload.get("start") or payload.get("dtstart"),
                "thumb_url": None,
                "attributes_json": {"location": loc},
            }
        )
        if len(out) >= limit:
            return out, True
    return out, False


def _artifacts(
    q: str, person_id: str | None, *, limit: int
) -> tuple[list[dict[str, Any]], bool]:
    try:
        from memorybox.artifact import list_artifacts

        rows = list_artifacts(limit=limit, person_id=person_id, query=q or None)
    except Exception:
        return [], False
    out = []
    for a in rows:
        d = a.to_dict() if hasattr(a, "to_dict") else dict(a)
        out.append(
            {
                "source_kind": "artifact",
                "source_id": str(d.get("id") or d.get("artifact_id")),
                "title": d.get("label") or d.get("title") or "Artifact",
                "occurred_on": d.get("created_at"),
                "thumb_url": None,
            }
        )
    return out, len(out) >= limit


def _journals(
    q: str, person_id: str | None, *, limit: int
) -> tuple[list[dict[str, Any]], bool]:
    out: list[dict[str, Any]] = []
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, described_start_date
            FROM journal_entries
            WHERE status = 'active'
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (max(limit, 24),),
        ).fetchall()
    needle = (q or "").lower()
    for r in rows:
        title = r.get("title") or "Journal"
        if needle and needle not in str(title).lower():
            continue
        out.append(
            {
                "source_kind": "journal",
                "source_id": str(r["id"]),
                "title": title,
                "occurred_on": str(r["described_start_date"])
                if r.get("described_start_date")
                else None,
                "thumb_url": None,
            }
        )
        if len(out) >= limit:
            return out, True
    return out, False


def _audio(q: str, *, limit: int) -> tuple[list[dict[str, Any]], bool]:
    out: list[dict[str, Any]] = []
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, story_id, version, audio_uri, title
            FROM story_versions
            WHERE audio_uri IS NOT NULL AND audio_uri <> ''
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    for r in rows:
        out.append(
            {
                "source_kind": "audio",
                "source_id": str(r["id"]),
                "title": r.get("title") or "Audio",
                "occurred_on": None,
                "thumb_url": None,
            }
        )
    return out, False
