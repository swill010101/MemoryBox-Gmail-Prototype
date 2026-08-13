"""P2-I4 Explore find — map real Ask (and optional Library) hits to Explore items.

Preserves the Explore UI item contract used by the accepted interaction reference.
Does not hard-code people or events into product logic.
"""
from __future__ import annotations

from typing import Any


def _date_prefix(raw: str | None) -> str:
    if not raw:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    # ISO or date-only
    return s[:10] if len(s) >= 10 else s


def _item_base(
    *,
    id: str,
    type_: str,
    title: str,
    date: str = "",
    preview: str = "",
    detail: str = "",
    **extra: Any,
) -> dict[str, Any]:
    undated = bool(extra.pop("undated", False) or not date)
    out: dict[str, Any] = {
        "id": id,
        "type": type_,
        "kind": type_,
        "title": title or type_,
        "date": "" if undated else date,
        "undated": undated,
        "preview": preview or detail or title,
        "detail": detail or preview or title,
    }
    out.update(extra)
    return out


def _ask_scoped_person_names(result: dict[str, Any]) -> list[str]:
    """People the Ask was about — attach to photo items when Immich omits tags."""
    names: list[str] = []

    def add(raw: Any) -> None:
        s = str(raw or "").strip()
        if not s or s.lower() == "unknown":
            return
        if s not in names:
            names.append(s)

    ctx = result.get("context") or {}
    slots = ctx.get("plan_slots") or {}
    plan = result.get("plan") or {}
    plan_slots = plan.get("slots") or {}
    for key in ("person",):
        for n in slots.get(key) or plan_slots.get(key) or []:
            add(n)
    for n in ctx.get("person_names") or plan.get("person_names") or []:
        add(n)
    status = result.get("provider_status") or {}
    for block in status.values():
        if not isinstance(block, dict):
            continue
        for n in block.get("mapped_person_names") or []:
            add(n)
    return names


def items_from_ask_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert AskResult.to_dict() (or equivalent) into Explore gallery items."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    ask_people = _ask_scoped_person_names(result)

    def add(it: dict[str, Any]) -> None:
        iid = str(it.get("id") or "")
        if not iid or iid in seen:
            return
        seen.add(iid)
        items.append(it)

    for p in result.get("photo_hits") or []:
        eid = str(p.get("external_id") or "")
        if not eid:
            continue
        taken = _date_prefix(p.get("taken_at"))
        people: list[str] = []
        for n in list(p.get("people") or []):
            s = str(n or "").strip()
            if s and s.lower() != "unknown" and s not in people:
                people.append(s)
        mb_name = str(p.get("mb_person_name") or "").strip() or None
        if mb_name and mb_name.lower() != "unknown" and mb_name not in people:
            people.insert(0, mb_name)
        for face in p.get("faces") or []:
            if not isinstance(face, dict):
                continue
            fn = str(face.get("name") or "").strip()
            if fn and fn.lower() != "unknown" and fn not in people:
                people.append(fn)
        for n in ask_people:
            if n not in people:
                people.append(n)
        name = mb_name or (people[0] if people else None)
        title = name or "Photo"
        place = p.get("place") or None
        loc_str = p.get("location") or None
        if place and not loc_str:
            loc_str = str(place)
        if loc_str and not place:
            place = str(loc_str).split(",")[0].strip() or loc_str
        if place:
            title = f"{title} · {place}"
        elif p.get("location"):
            title = f"{title} · {p.get('location')}"
        thumb = f"/library/media/photo/{eid}"
        face_box = p.get("face_box")
        lat = p.get("latitude")
        lng = p.get("longitude")
        try:
            lat_f = float(lat) if lat is not None else None
            lng_f = float(lng) if lng is not None else None
        except (TypeError, ValueError):
            lat_f = lng_f = None
        if lat_f is not None and (lat_f < -90 or lat_f > 90):
            lat_f = None
        if lng_f is not None and (lng_f < -180 or lng_f > 180):
            lng_f = None
        extra: dict[str, Any] = {
            "people": people,
            "mb_person_id": p.get("mb_person_id"),
            "mb_person_name": mb_name or (people[0] if people else None),
            "provider_key": p.get("provider_key") or "immich",
            "external_id": eid,
            "media_url": thumb,
            "thumb_url": thumb,
            "teachable": True,
            "face_identity": mb_name or (people[0] if people else None) or "Unknown",
            "place": place,
            "location": loc_str,
            "city": p.get("city"),
            "state": p.get("state"),
            "country": p.get("country"),
            "original_filename": p.get("original_filename"),
            "exif": p.get("exif") if isinstance(p.get("exif"), dict) else None,
            "faces": list(p.get("faces") or []) if isinstance(p.get("faces"), list) else [],
        }
        if lat_f is not None and lng_f is not None:
            extra["lat"] = lat_f
            extra["lng"] = lng_f
            extra["latitude"] = lat_f
            extra["longitude"] = lng_f
        # Only attach real geometry — never invent a placeholder box.
        if isinstance(face_box, dict) and all(
            isinstance(face_box.get(k), (int, float)) for k in ("x", "y", "w", "h")
        ):
            extra["face_box"] = {
                "x": float(face_box["x"]),
                "y": float(face_box["y"]),
                "w": float(face_box["w"]),
                "h": float(face_box["h"]),
            }
        add(
            _item_base(
                id=f"photo:{p.get('provider_key') or 'immich'}:{eid}",
                type_="photo",
                title=str(title)[:80],
                date=taken,
                undated=not taken,
                preview=str(p.get("attribution") or name or "Photo"),
                detail=str(p.get("attribution") or ""),
                **extra,
            )
        )

    video_raw: list[dict[str, Any]] = []
    for v in result.get("video_hits") or []:
        vid = str(v.get("video_external_id") or v.get("external_id") or "")
        if not vid:
            continue
        t0 = float(v.get("start_sec") or 0)
        t1 = v.get("end_sec")
        face = v.get("face_external_id")
        play = v.get("play_url") or (
            f"/review/ui?video={vid}&t={t0}"
            + (f"&face={face}" if face else "")
        )
        poster = f"/library/media/video-poster?video={vid}&t={t0:.3f}"
        # Appearance moments are in-video spans — calendar undated unless known
        label = v.get("label") or v.get("mb_person_name") or "Video moment"
        if label == "face-appearance-moment":
            label = v.get("mb_person_name") or "Video moment"
        face_box = v.get("face_box")
        item = _item_base(
            id=f"video:{v.get('provider_key') or 'hvrt'}:{v.get('external_id') or vid}:{t0}",
            type_="video",
            title=str(label)[:80],
            date="",
            undated=True,
            preview=f"Moment @ {t0:.1f}s",
            detail=f"{t0:.1f}s" + (f"–{float(t1):.1f}s" if t1 is not None else ""),
            people=[v["mb_person_name"]] if v.get("mb_person_name") else [],
            mb_person_id=v.get("mb_person_id"),
            mb_person_name=v.get("mb_person_name"),
            provider_key=v.get("provider_key") or "hvrt",
            video_provider_key=v.get("provider_key") or "hvrt",
            video_external_id=vid,
            external_id=v.get("external_id"),
            face_external_id=face,
            t=t0,
            start_sec=t0,
            end_sec=t1,
            duration_sec=(float(t1) - t0) if t1 is not None else None,
            play_url=play,
            media_url=poster,
            thumb_url=poster,
            teachable=True,
            paused_frame=True,
            face_identity=v.get("mb_person_name") or "Unknown",
        )
        if isinstance(face_box, dict) and all(
            isinstance(face_box.get(k), (int, float)) for k in ("x", "y", "w", "h")
        ):
            item["face_box"] = {
                "x": float(face_box["x"]),
                "y": float(face_box["y"]),
                "w": float(face_box["w"]),
                "h": float(face_box["h"]),
            }
        video_raw.append(item)

    # Collapse near-duplicate video moments (same clip / ~same seek)
    video_kept: list[dict[str, Any]] = []
    video_slots: set[tuple[str, int]] = set()
    for it in video_raw:
        vid = str(it.get("video_external_id") or "")
        slot = int(float(it.get("start_sec") or 0) // 2.5)
        key = (vid, slot)
        if key in video_slots:
            continue
        video_slots.add(key)
        video_kept.append(it)
    for it in video_kept:
        add(it)

    for e in result.get("evidence_hits") or []:
        kind = str(e.get("evidence_kind") or "document").lower()
        # Map communication-ish kinds to email for Explore filters
        type_ = "email" if kind in ("email", "sms", "text", "communication", "comms") else (
            "document" if kind in ("document", "file") else kind
        )
        if type_ not in ("email", "sms", "text", "document", "calendar", "recipe"):
            # Keep as email/text bucket for unknown communication evidence
            if "mail" in kind or "sms" in kind or "message" in kind:
                type_ = "email"
            else:
                type_ = "document"
        eid = str(e.get("evidence_id") or "")
        if not eid:
            continue
        add(
            _item_base(
                id=f"evidence:{eid}",
                type_=type_ if type_ != "communication" else "email",
                title=(e.get("summary") or kind or "Evidence")[:80],
                date="",  # evidence often lacks browse date in Ask hit
                undated=True,
                preview=str(e.get("excerpt") or e.get("summary") or ""),
                detail=str(e.get("excerpt") or e.get("summary") or ""),
                evidence_id=eid,
                evidence_kind=kind,
                score=e.get("score"),
            )
        )

    for a in result.get("artifact_hits") or []:
        aid = str(a.get("artifact_id") or a.get("id") or "")
        if not aid:
            continue
        add(
            _item_base(
                id=f"artifact:{aid}",
                type_="artifact",
                title=str(a.get("label") or a.get("title") or "Artifact")[:80],
                date=_date_prefix(a.get("created_at") or a.get("date")),
                undated=not _date_prefix(a.get("created_at") or a.get("date")),
                preview=str(a.get("summary") or a.get("label") or ""),
                detail=str(a.get("summary") or ""),
                artifact_id=aid,
            )
        )

    for s in result.get("story_hits") or []:
        sid = str(s.get("story_id") or "")
        if not sid:
            continue
        add(
            _item_base(
                id=f"story:{sid}",
                type_="story",
                title=str(s.get("title") or "Story")[:80],
                date="",  # stories are not calendar-primary
                undated=True,
                preview=str(s.get("excerpt") or s.get("attribution") or ""),
                detail=str(s.get("excerpt") or ""),
                story_id=sid,
                version=s.get("version"),
                attribution=s.get("attribution"),
            )
        )

    return items


def chips_from_ask_result(result: dict[str, Any]) -> list[dict[str, str]]:
    chips: list[dict[str, str]] = []
    ctx = result.get("context") or {}
    slots = ctx.get("plan_slots") or {}
    for name in slots.get("person") or ctx.get("person_names") or []:
        chips.append({"kind": "person", "label": str(name)})
    for ev in slots.get("event") or ctx.get("event_labels") or []:
        chips.append({"kind": "event", "label": str(ev)})
    for pl in slots.get("place") or ctx.get("place_names") or []:
        chips.append({"kind": "place", "label": str(pl)})
    # Range chip from dated items only
    return chips


def curator_from_items(
    ask_text: str,
    items: list[dict[str, Any]],
    answer_text: str | None,
    *,
    provider_status: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Title + summary for Explore curator."""
    title = (ask_text or "Memories").strip()
    if len(title) > 64:
        title = title[:61] + "…"
    if answer_text and str(answer_text).strip():
        summary = str(answer_text).strip()
    else:
        counts = {
            "photo": sum(1 for i in items if i.get("type") == "photo"),
            "video": sum(1 for i in items if i.get("type") == "video"),
            "email": sum(1 for i in items if i.get("type") in ("email", "sms", "text")),
            "artifact": sum(1 for i in items if i.get("type") == "artifact"),
            "story": sum(1 for i in items if i.get("type") == "story"),
        }
        parts = []
        if counts["photo"]:
            parts.append(f"{counts['photo']} photo{'s' if counts['photo'] != 1 else ''}")
        if counts["video"]:
            parts.append(
                f"{counts['video']} video moment{'s' if counts['video'] != 1 else ''}"
            )
        if counts["email"]:
            parts.append(f"{counts['email']} email/text")
        if counts["artifact"]:
            parts.append(
                f"{counts['artifact']} artifact{'s' if counts['artifact'] != 1 else ''}"
            )
        if counts["story"]:
            parts.append(f"{counts['story']} stor{'y' if counts['story'] == 1 else 'ies'}")
        undated = sum(1 for i in items if i.get("undated"))
        summary = f"I found {len(items)} memories"
        if parts:
            summary += ", including " + ", ".join(parts)
        summary += "."
        if undated:
            summary += f" {undated} undated (not placed on the Timeline axis)."
    # Honest photo-provider disclosure when Ask resolved a person but Immich returned none.
    # Orchestrator stores health under "photo" and search outcome under "photo_search".
    photos = sum(1 for i in items if i.get("type") == "photo")
    if photos == 0 and provider_status:
        photo_health = provider_status.get("photo") or {}
        photo_search = provider_status.get("photo_search") or {}
        if not isinstance(photo_health, dict):
            photo_health = {}
        if not isinstance(photo_search, dict):
            photo_search = {}
        if photo_search.get("unavailable") or (
            photo_health and photo_health.get("ok") is False
        ):
            detail = str(
                photo_search.get("detail") or photo_health.get("detail") or ""
            ).strip()
            summary += f" Photos unavailable from Immich ({detail or 'provider unhealthy'})."
        else:
            detail = str(photo_search.get("detail") or "").strip()
            if detail and detail not in ("not_requested",):
                summary += f" Immich photos: {detail}."
    return title, summary


def range_chip_for_items(items: list[dict[str, Any]]) -> dict[str, str] | None:
    dates = sorted(
        {
            str(i.get("date"))[:4]
            for i in items
            if i.get("date") and not i.get("undated") and len(str(i.get("date"))) >= 4
        }
    )
    if not dates:
        return None
    if dates[0] == dates[-1]:
        return {"kind": "range", "label": dates[0]}
    return {"kind": "range", "label": f"{dates[0]}–{dates[-1]}"}


def build_explore_find(
    *,
    ask_text: str,
    session_id: str | None = None,
    orchestrator: Any | None = None,
) -> dict[str, Any]:
    """Run Ask and return an Explore-ready payload (same shape as demo_payload)."""
    text = (ask_text or "").strip()
    if not text:
        return {
            "ok": True,
            "demo": False,
            "live": True,
            "ask_text": "",
            "title": "What would you like to see?",
            "summary": "Ask MemoryBox about a person, place, time, or kind of memory.",
            "chips": [],
            "items": [],
            "counts": {},
            "session_id": session_id,
            "provider_status": {},
        }

    if orchestrator is None:
        from memorybox.ask.orchestrator import AskOrchestrator
        from memorybox.context import default_context_store

        orchestrator = AskOrchestrator(store=default_context_store)

    result_obj = orchestrator.ask(text, session_id=session_id)
    result = result_obj.to_dict() if hasattr(result_obj, "to_dict") else dict(result_obj)
    items = items_from_ask_result(result)
    title, summary = curator_from_items(
        text,
        items,
        result.get("answer_text"),
        provider_status=result.get("provider_status") or {},
    )
    chips = chips_from_ask_result(result)
    rc = range_chip_for_items(items)
    if rc:
        chips.append(rc)

    counts: dict[str, int] = {}
    for i in items:
        t = str(i.get("type") or "other")
        counts[t] = counts.get(t, 0) + 1
    counts["undated"] = sum(1 for i in items if i.get("undated"))

    return {
        "ok": True,
        "demo": False,
        "live": True,
        "fixture_id": None,
        "ask_text": text,
        "title": title,
        "summary": summary,
        "chips": chips,
        "items": items,
        "counts": counts,
        "session_id": result.get("session_id") or session_id,
        "answer_kind": result.get("answer_kind"),
        "missing_disclosure": result.get("missing_disclosure"),
        "provider_status": result.get("provider_status") or {},
        "plan": result.get("plan"),
        "context": result.get("context"),
    }
