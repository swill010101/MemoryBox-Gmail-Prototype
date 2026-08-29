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
    if not (q or "").strip() and not (person_id or "").strip():
        return {
            "ok": True,
            "total": 0,
            "truncated": False,
            "offset": offset,
            "limit": limit,
            "items": [],
            "matched_person_id": None,
        }

    resolved_person = (person_id or "").strip() or None
    if not resolved_person and (q or "").strip():
        try:
            from memorybox.person import find_ask_person_by_name

            view = find_ask_person_by_name((q or "").strip(), lazy_seed=False)
            if view:
                resolved_person = view.id
        except Exception:
            resolved_person = resolved_person

    items: list[dict[str, Any]] = []
    truncated = False
    try:
        from memorybox.planner import plan_ask
        from memorybox.context import AskContext

        plan = plan_ask((q or "").strip() or "show me memories", AskContext.empty())
        if resolved_person:
            from dataclasses import replace

            plan = replace(
                plan,
                person_ids=tuple({*plan.person_ids, resolved_person}),
                want_photo=True,
                want_still=True,
            )
    except Exception:
        plan = None

    if "photo" in wanted:
        photos, more = _photos(plan, q, person_id=resolved_person, limit=limit)
        items.extend(photos)
        truncated = truncated or more
    if "video" in wanted:
        videos, more = _videos(plan, limit=limit)
        items.extend(videos)
        truncated = truncated or more
    if "email_thread" in wanted or "sms_conversation" in wanted:
        comms, more = _comms(
            wanted, q, resolved_person, time_start, time_end, limit=limit
        )
        items.extend(comms)
        truncated = truncated or more
    if "calendar_event" in wanted:
        cals, more = _calendar(q, time_start, time_end, place, limit=limit)
        items.extend(cals)
        truncated = truncated or more
    if "artifact" in wanted:
        arts, more = _artifacts(q, resolved_person, limit=limit)
        items.extend(arts)
        truncated = truncated or more
    if "journal" in wanted:
        journals, more = _journals(q, resolved_person, limit=limit)
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
        "matched_person_id": resolved_person,
    }


def _photo_item(d: dict[str, Any]) -> dict[str, Any] | None:
    eid = str(d.get("external_id") or d.get("id") or "")
    if not eid:
        return None
    people = _people_on_photo(d)
    names = [str(p.get("display_name") or "").strip() for p in people if p.get("display_name")]
    raw_title = (d.get("original_filename") or d.get("title") or "").strip()
    when = str(d.get("taken_at") or "")[:10]
    if not raw_title or raw_title.lower() in {"photo", "image", "img"}:
        raw_title = when or (names[0] if names else "Untitled photo")
    return {
        "source_kind": "photo",
        "source_id": eid,
        "title": raw_title,
        "occurred_on": d.get("taken_at"),
        "thumb_url": d.get("thumb_url") or f"/library/media/photo/{eid}",
        "people": people,
        "context": ", ".join(names) if names else (when or ""),
    }


_PERSON_NAME_CACHE: dict[str, dict[str, str] | None] = {}


def _people_on_photo(d: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(pid: str | None, name: str | None) -> None:
        key = (pid or "").strip()
        label = (name or "").strip()
        if key and key in seen:
            return
        if key:
            seen.add(key)
            out.append({"id": key, "display_name": label, "portrait_url": f"/people/{key}/portrait"})
        elif label and label.lower() not in {x.get("display_name", "").lower() for x in out}:
            resolved = _resolve_person_name(label)
            if resolved:
                _add(resolved.get("id"), resolved.get("display_name") or label)
            else:
                out.append({"id": "", "display_name": label})

    mid = str(d.get("mb_person_id") or "").strip()
    if mid:
        _add(mid, d.get("mb_person_name"))
    for p in d.get("people") or []:
        if isinstance(p, dict):
            _add(str(p.get("id") or p.get("person_id") or ""), p.get("display_name") or p.get("name"))
        else:
            _add(None, str(p))
    for f in d.get("faces") or []:
        if isinstance(f, dict):
            _add(str(f.get("person_id") or ""), f.get("display_name") or f.get("name"))
    return out


def _resolve_person_name(name: str) -> dict[str, str] | None:
    key = (name or "").strip().lower()
    if not key:
        return None
    if key in _PERSON_NAME_CACHE:
        return _PERSON_NAME_CACHE[key]
    try:
        from memorybox.person import find_ask_person_by_name

        view = find_ask_person_by_name(name.strip(), lazy_seed=False)
        if view:
            _PERSON_NAME_CACHE[key] = {"id": view.id, "display_name": view.display_name or name}
            return _PERSON_NAME_CACHE[key]
    except Exception:
        pass
    _PERSON_NAME_CACHE[key] = None
    return None


def _photos(
    plan: Any, q: str, *, person_id: str | None, limit: int
) -> tuple[list[dict[str, Any]], bool]:
    out: list[dict[str, Any]] = []
    try:
        from memorybox.ask import retrieve as R
        from memorybox.ask.deps import build_photo

        photo = build_photo()
        if plan is not None:
            hits, _status = R.search_photos(plan, photo, limit=max(limit, 24))
            for h in hits:
                d = h.to_dict() if hasattr(h, "to_dict") else dict(h)
                item = _photo_item(d)
                if item:
                    out.append(item)
        if not out and not (q or "").strip() and not person_id:
            return [], False
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
              AND coalesce(payload_json->>'mailbox_skip', '') NOT IN ('spam', 'trash')
              AND coalesce(payload_json->>'skip_reason', '') NOT IN ('spam', 'trash')
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
        if _is_spam_or_trash(payload):
            continue
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
                str(payload.get("from_name") or ""),
                str(payload.get("to") or ""),
                str(r.get("summary") or ""),
            ]
        ).lower()
        if needle and needle not in blob:
            tokens = [t for t in needle.split() if len(t) > 1]
            if not tokens or not any(t in blob for t in tokens):
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
        frm = payload.get("from") or payload.get("from_name") or payload.get("from_email")
        to = payload.get("to") or payload.get("to_name")
        channel_label = "Email" if kind == "email_thread" else "Text"
        who = ", ".join(str(x) for x in (frm, to) if x)
        out.append(
            {
                "source_kind": kind,
                "source_id": str(r["id"]),
                "title": payload.get("subject")
                or payload.get("title")
                or (r.get("summary") or "Message"),
                "occurred_on": payload.get("sent_at") or payload.get("date"),
                "thumb_url": None,
                "context": " · ".join(x for x in (channel_label, who) if x) or channel_label,
                "attributes_json": {
                    "from": frm,
                    "to": to,
                    "channel": ch,
                },
            }
        )
        if len(out) >= limit:
            return out, True
    return out, False


def _is_spam_or_trash(payload: dict[str, Any]) -> bool:
    skip = str(
        payload.get("mailbox_skip") or payload.get("skip_reason") or ""
    ).strip().lower()
    if skip in {"spam", "trash", "junk"}:
        return True
    labels = payload.get("gmail_labels") or payload.get("labels") or payload.get("label")
    if isinstance(labels, str):
        tokens = [t.strip().lower() for t in labels.replace(";", ",").split(",")]
    elif isinstance(labels, list):
        tokens = [str(t).strip().lower() for t in labels]
    else:
        tokens = []
    return any(t in {"spam", "trash", "junk"} for t in tokens)


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
        attendees = payload.get("attendees") or payload.get("participants") or ""
        if isinstance(attendees, list):
            attendees = " ".join(str(a) for a in attendees)
        blob = f"{title} {loc} {attendees}".lower()
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
