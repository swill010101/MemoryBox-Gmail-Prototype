"""P2-I4 Explore find — map real Ask (and optional Library) hits to Explore items.

Preserves the Explore UI item contract used by the accepted interaction reference.
Does not hard-code people or events into product logic.
"""
from __future__ import annotations

import re
from typing import Any

_SMS_ITEM_TYPES = frozenset({"sms", "text", "imessage", "mms", "rcs"})
_SMS_ASK_RE = re.compile(
    r"(?i)\b("
    r"sms|imessage|i-?message|mms|rcs|"
    r"text(?:s|ed|ing)?(?:\s+messages?)?|"
    r"messages?\s+(?:from|to|between|with)|"
    r"from\s+and\s+to|last\s+\d+\s+messages?"
    r")\b"
)
# All-ask: small hidden sample so Email/Text works. Count is the real archive.
# Explicit text ask / Add texts: year-fair slice up to this cap (90k is too many cards).
_HIDDEN_SMS_CARD_SAMPLE = 800
_VISIBLE_SMS_GALLERY_CAP = 10000
_HOLIDAY_WINDOW_MARKERS = (
    "christmas",
    "xmas",
    "thanksgiving",
    "easter",
    "halloween",
    "holiday",
    "nye",
    "nyd",
    "memorial",
    "labor",
    "juneteenth",
)


def _is_sms_type(type_: str) -> bool:
    return str(type_ or "").lower() in _SMS_ITEM_TYPES


def explicit_text_gallery(result: dict[str, Any] | None, ask_text: str | None = None) -> bool:
    """True when the ask itself requested texts (not a broad memory query)."""
    plan = (result or {}).get("plan") or {}
    notes = plan.get("notes") or ()
    if "want_sms_modality" in notes:
        return True
    blob = " ".join(
        [
            ask_text or "",
            str(plan.get("original_ask") or ""),
            str((result or {}).get("ask") or ""),
        ]
    )
    return bool(_SMS_ASK_RE.search(blob))


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
        if mb_name and people:
            from memorybox.person import asked_name_matches_person

            if not any(asked_name_matches_person(mb_name, n) for n in people):
                mb_name = None
        if not people:
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
        exif_d = p.get("exif") if isinstance(p.get("exif"), dict) else {}
        photo_type = (
            "video"
            if str((exif_d or {}).get("media") or "").lower() == "video"
            else "photo"
        )
        add(
            _item_base(
                id=f"photo:{p.get('provider_key') or 'immich'}:{eid}",
                type_=photo_type,
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
        poster = ""
        if not str(vid).startswith(("video-peggy-", "video-library-")):
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
        channel = str(e.get("channel") or "").lower()
        sms_channels = {"sms", "text", "imessage", "mms", "rcs"}
        # Map communication-ish kinds to email/sms for existing Explore filters
        if channel in sms_channels or e.get("source") == "sms_export":
            type_ = "sms"
        elif kind in ("email", "sms", "text", "communication", "comms"):
            type_ = "sms" if kind in ("sms", "text") else "email"
        else:
            type_ = "document" if kind in ("document", "file") else kind
        if type_ not in ("email", "sms", "text", "document", "calendar", "recipe"):
            # Keep as email/text bucket for unknown communication evidence
            if "mail" in kind or "sms" in kind or "message" in kind:
                type_ = "email"
            else:
                type_ = "document"
        eid = str(e.get("evidence_id") or "")
        if not eid:
            continue
        sent = _date_prefix(e.get("sent_at"))
        people = [str(p) for p in (e.get("people") or []) if str(p).strip()]
        item = _item_base(
            id=f"evidence:{eid}",
            type_=type_ if type_ != "communication" else "email",
            title=(e.get("summary") or kind or "Evidence")[:80],
            date=sent,
            undated=not sent,
            preview=str(e.get("excerpt") or e.get("summary") or ""),
            detail=str(e.get("excerpt") or e.get("summary") or ""),
            evidence_id=eid,
            evidence_kind=kind,
            score=e.get("score"),
            people=people or None,
            attachments=e.get("attachments") or None,
            thread_id=e.get("thread_id"),
            direction=e.get("direction"),
        )
        item["from"] = people[0] if people else (e.get("thread_id") or "Message")
        atts = e.get("attachments") or item.get("attachments") or []
        item["attachments"] = atts
        item["attachment_count"] = len(atts) if isinstance(atts, list) else 0
        if e.get("identity_mapped"):
            item["identity_mapped"] = e.get("identity_mapped")
        if e.get("match_total") is not None:
            item["match_total"] = e.get("match_total")
            item["truncated"] = bool(e.get("truncated"))
        if _is_sms_type(item.get("type") or type_):
            item["gallery_default_hidden"] = not explicit_text_gallery(result)
        add(item)

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
    seen: set[str] = set()

    def add(kind: str, label: str) -> None:
        s = str(label or "").strip()
        if not s:
            return
        key = f"{kind}:{s.lower()}"
        if key in seen:
            return
        seen.add(key)
        chips.append({"kind": kind, "label": s})

    ctx = result.get("context") or {}
    slots = ctx.get("plan_slots") or {}
    plan = result.get("plan") or {}
    for name in slots.get("person") or ctx.get("person_names") or plan.get("person_names") or []:
        add("person", str(name))
    for pl in slots.get("place") or ctx.get("place_names") or plan.get("place_names") or []:
        add("place", str(pl))
    for ev in slots.get("event") or ctx.get("event_labels") or plan.get("event_labels") or []:
        add("event", str(ev))
    for tr in slots.get("trip") or plan.get("trip_labels") or []:
        add("trip", str(tr))
    # Temporal chip — prefer holiday/season label over raw year range chip later
    tlabel = plan.get("temporal_label") or slots.get("time_label")
    if tlabel:
        add("time", str(tlabel))
    elif plan.get("time_start") and plan.get("time_end"):
        a = str(plan["time_start"])[:4]
        b = str(plan["time_end"])[:4]
        add("time", a if a == b else f"{a}–{b}")
    return chips


def _immich_diag_line(provider_status: dict[str, Any] | None) -> str:
    photo_search = (provider_status or {}).get("photo_search") or {}
    if not isinstance(photo_search, dict):
        return ""
    diag = photo_search.get("immich_diag") or {}
    if not isinstance(diag, dict) or not diag:
        return ""
    last = (diag.get("last") or [{}])[-1] if diag.get("last") else {}
    if not isinstance(last, dict):
        last = {}
    bits = [
        f"{int(diag.get('calls') or 0)} calls",
        f"{int(diag.get('fails') or 0)} fail",
        f"{int(diag.get('total_ms') or 0)}ms",
    ]
    if diag.get("circuit"):
        bits.append("circuit open")
    if diag.get("source"):
        bits.append(f"src={diag.get('source')}")
    if last.get("path"):
        bits.append(
            f"last {last.get('method') or 'GET'} {last.get('path')} "
            f"{last.get('err') or last.get('status')}"
        )
    return " Immich diag: " + ", ".join(bits) + "."


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
            "sms": sum(1 for i in items if _is_sms_type(i.get("type"))),
            "email": sum(1 for i in items if i.get("type") == "email"),
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
        if counts["sms"]:
            parts.append(f"{counts['sms']} text{'s' if counts['sms'] != 1 else ''}")
        if counts["email"]:
            parts.append(f"{counts['email']} email{'s' if counts['email'] != 1 else ''}")
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
        search_detail = str(photo_search.get("detail") or "").strip()
        health_detail = str(photo_health.get("detail") or "").strip()
        if photo_search.get("unavailable"):
            summary += (
                f" Photos unavailable from Immich "
                f"({search_detail or health_detail or 'provider unhealthy'})."
            )
        elif search_detail and search_detail not in ("not_requested",):
            # Ping can fail while /people still works — don't hide the search detail.
            summary += f" Immich photos: {search_detail}."
        elif photo_health and photo_health.get("ok") is False:
            summary += (
                f" Photos unavailable from Immich "
                f"({health_detail or 'provider unhealthy'})."
            )
        summary += _immich_diag_line(provider_status)
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


def _sms_attach_windows(plan: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Prefer holiday/event windows. Never treat a lifetime span as the SMS set."""
    raw = plan.get("temporal_windows") or ()
    out: list[tuple[str, str]] = []
    for w in raw:
        if not isinstance(w, (list, tuple)) or len(w) < 2:
            continue
        a, b = str(w[0] or "")[:10], str(w[1] or "")[:10]
        if a and b:
            out.append((a, b))
    if out:
        return tuple(out)
    blob = " ".join(
        [
            str(plan.get("temporal_label") or ""),
            " ".join(str(x) for x in (plan.get("notes") or ())),
            str(plan.get("original_ask") or ""),
            str(plan.get("effective_ask") or ""),
        ]
    ).lower()
    if any(m in blob for m in _HOLIDAY_WINDOW_MARKERS):
        return ()
    t0, t1 = plan.get("time_start"), plan.get("time_end")
    if t0 and t1:
        return ((str(t0)[:10], str(t1)[:10]),)
    return ()


def _attach_hidden_sms(
    items: list[dict[str, Any]],
    result: dict[str, Any],
    *,
    ask_text: str,
    show_sms: bool,
) -> tuple[list[dict[str, Any]], int, int]:
    """Keep SMS eligible for Add texts without dumping cards on broad memory asks.

    Gallery visibility is not evidence exclusion. Caps hidden cards so Explore
    stays usable; full retrieve/count remains on the SMS Ask path.
    """
    existing_ids = {str(i.get("evidence_id") or "") for i in items if i.get("evidence_id")}
    sms_already = [i for i in items if _is_sms_type(i.get("type"))]
    if show_sms and sms_already:
        for i in sms_already:
            i["gallery_default_hidden"] = False
        return items, len(sms_already), 0

    plan = result.get("plan") or {}
    people = list(plan.get("person_names") or [])
    pids = list(plan.get("person_ids") or [])
    if not people and not pids and not sms_already:
        hidden = sum(1 for i in sms_already if i.get("gallery_default_hidden"))
        return items, len(sms_already), hidden

    tw = _sms_attach_windows(plan)
    holiday_blob = " ".join(
        [
            ask_text or "",
            str(plan.get("temporal_label") or ""),
            " ".join(str(x) for x in (plan.get("notes") or ())),
        ]
    ).lower()
    holiday_ask = any(m in holiday_blob for m in _HOLIDAY_WINDOW_MARKERS)
    # Retrieve already scoped holiday SMS. Do not pad with the person-wide cap
    # (Peggy Christmas curator was 500 all-time texts).
    if sms_already and (tw or holiday_ask):
        for i in sms_already:
            i["gallery_default_hidden"] = True
        return items, len(sms_already), len(sms_already)
    if holiday_ask and not tw:
        for i in sms_already:
            i["gallery_default_hidden"] = True
        hidden = sum(1 for i in sms_already if i.get("gallery_default_hidden"))
        return items, len(sms_already), hidden

    extra: list[dict[str, Any]] = []
    match_total = 0
    try:
        from memorybox.ask.retrieve import search_sms_messages
        from memorybox.planner import QueryPlan

        t0 = tw[0][0] if tw else plan.get("time_start")
        t1 = tw[-1][1] if tw else plan.get("time_end")
        sms_plan = QueryPlan(
            original_ask=ask_text or plan.get("original_ask") or "",
            effective_ask=plan.get("effective_ask") or ask_text or "",
            is_followup=False,
            want_photo=False,
            want_communication=True,
            want_calendar=False,
            person_names=tuple(people),
            person_ids=tuple(pids),
            time_start=t0,
            time_end=t1,
            temporal_windows=tw,
            notes=("gallery_sms_eligible",),
        )
        cap = _VISIBLE_SMS_GALLERY_CAP if show_sms else _HIDDEN_SMS_CARD_SAMPLE
        hits = search_sms_messages(sms_plan, limit=cap)
        if hits:
            match_total = int(getattr(hits[0], "match_total", None) or len(hits))
        mapped = items_from_ask_result(
            {
                "evidence_hits": [h.to_dict() for h in hits],
                "plan": {"notes": ()},
            }
        )
        for it in mapped:
            eid = str(it.get("evidence_id") or "")
            if eid and eid in existing_ids:
                continue
            it["gallery_default_hidden"] = True
            extra.append(it)
            if eid:
                existing_ids.add(eid)
    except Exception:  # noqa: BLE001
        extra = []

    out = list(items) + extra
    if not show_sms:
        for i in out:
            if _is_sms_type(i.get("type")):
                i["gallery_default_hidden"] = True
    sms_n = sum(1 for i in out if _is_sms_type(i.get("type")))
    hidden_n = sum(
        1
        for i in out
        if _is_sms_type(i.get("type")) and i.get("gallery_default_hidden")
    )
    if match_total > sms_n:
        sms_n = match_total
        if not show_sms:
            hidden_n = match_total
    return out, sms_n, hidden_n


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
    show_sms = explicit_text_gallery(result, text)
    items, sms_available, sms_hidden = _attach_hidden_sms(
        items, result, ask_text=text, show_sms=show_sms
    )
    visible_items = [
        i for i in items if not (i.get("gallery_default_hidden") and _is_sms_type(i.get("type")))
    ]
    # All-ask curator counts the archive (photos + hidden texts + video).
    # Gallery still hides SMS until Add texts / an explicit text ask.
    answer_for_curator = result.get("answer_text")
    if result.get("answer_kind") != "clarification":
        answer_for_curator = None
    title, summary = curator_from_items(
        text,
        visible_items,
        answer_for_curator,
        provider_status=result.get("provider_status") or {},
    )
    if sms_hidden and not show_sms and "are in the archive" not in (summary or ""):
        summary = (
            (summary or "").rstrip()
            + (
                f" {sms_available} text message(s) are in the archive "
                "(hidden in Gallery — say Add texts to show them)."
            )
        ).strip()
    chips = chips_from_ask_result(result)
    # Prefer plan temporal chip over item-derived year range when present
    if not any(c.get("kind") == "time" for c in chips):
        rc = range_chip_for_items(visible_items)
        if rc:
            chips.append(rc)

    counts: dict[str, int] = {}
    for i in visible_items:
        t = str(i.get("type") or "other")
        counts[t] = counts.get(t, 0) + 1
    counts["undated"] = sum(1 for i in visible_items if i.get("undated"))
    counts["sms_available"] = sms_available
    counts["sms_hidden"] = sms_hidden
    sms_match_total = 0
    sms_truncated = False
    for e in result.get("evidence_hits") or []:
        if e.get("match_total"):
            sms_match_total = max(sms_match_total, int(e.get("match_total") or 0))
        if e.get("truncated"):
            sms_truncated = True
    if sms_truncated and sms_match_total:
        summary = (
            (summary or "").rstrip()
            + (
                f" Showing {counts.get('sms', 0) or sms_available} of "
                f"{sms_match_total} matching texts (every year kept on the Timeline)."
            )
        ).strip()

    plan = result.get("plan") or {}
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
        "plan": plan,
        "context": result.get("context"),
        # Shared exploration hints for Gallery/Timeline/Map sync
        "explore_state": {
            "person_names": list(plan.get("person_names") or []),
            "place_names": list(plan.get("place_names") or []),
            "time_start": plan.get("time_start"),
            "time_end": plan.get("time_end"),
            "temporal_windows": list(plan.get("temporal_windows") or []),
            "temporal_label": plan.get("temporal_label"),
            "visual_scope": plan.get("visual_scope"),
            "life_event_kind": plan.get("life_event_kind"),
            "life_event_years": list(plan.get("life_event_years") or []),
            "gallery_show_sms": show_sms,
            "sms_available": sms_available,
            "sms_hidden": sms_hidden,
            "sms_match_total": sms_match_total,
            "sms_truncated": sms_truncated,
        },
    }
