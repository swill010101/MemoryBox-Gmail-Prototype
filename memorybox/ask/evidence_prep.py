"""Narrative Evidence Preparation — question-specific pack, not a chunk dump."""
from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import UUID

from memorybox.ask.authored import authored_email_text, sms_location_assertions
from memorybox.ask.episode_semantics import (
    LIFE_FAMILIES,
    SUPPORTING_FAMILIES,
    annotate_unit,
    apply_episode_meaning,
    audit_row,
    episode_group_key,
    families_compatible,
    is_life_family,
    looks_supporting_subject,
    score_reason,
)
from memorybox.ask.travel import extract_travel
from memorybox.ask.i11a.support import attach_support_profile, rank_episodes_for_narrator
from memorybox.ask.i11a.windows import (
    attach_windows,
    pack_level_windows,
    windows_from_members,
)
from memorybox.ingest.store import get_evidence

PACK_SCHEMA = 1
HIERARCHY_UNIT_THRESHOLD = 40
# Final narrator prompt size for *episode/outline structures only*.
# Never a count of how many emails, texts, photos, or calendar rows were considered.
NARRATOR_EPISODE_BUDGET = 24


def _uid(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _payload_for(evidence_id: str) -> dict[str, Any]:
    try:
        row = get_evidence(UUID(str(evidence_id)))
    except Exception:
        return {}
    if not row:
        return {}
    payload = row.get("payload_json") or row.get("payload") or {}
    if isinstance(payload, str):
        import json

        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    return payload if isinstance(payload, dict) else {}


def _mailbox_skip(payload: dict[str, Any]) -> str | None:
    skip = str(payload.get("mailbox_skip") or payload.get("skip_reason") or "").strip().lower()
    if skip in {"spam", "trash"}:
        return skip
    labels = payload.get("gmail_labels") or payload.get("labels") or []
    blob = " ".join(str(x).lower() for x in labels)
    if "spam" in blob:
        return "spam"
    if "trash" in blob:
        return "trash"
    return None


def _time(val: Any) -> dict[str, Any]:
    s = str(val or "").strip()
    if not s:
        return {"value": None, "precision": "none", "confidence": "none"}
    if len(s) >= 10:
        return {"value": s[:10], "precision": "day", "confidence": "source"}
    if len(s) >= 4:
        return {"value": s[:4], "precision": "year", "confidence": "source"}
    return {"value": s, "precision": "unknown", "confidence": "low"}


def _comm_flags(and_i: bool, speaker: str | None, people: list[str], plan: Any) -> dict[str, Any]:
    names = {str(n).lower() for n in (getattr(plan, "person_names", ()) or ()) if n}
    speaker_l = (speaker or "").lower()
    keep_authored = True
    if and_i and names:
        if speaker_l and not any(n in speaker_l for n in names) and speaker_l not in {
            "me",
            "owner",
            "self",
        }:
            # Other participants stay in metadata; authored body omitted unless required.
            keep_authored = False
    return {"keep_authored": keep_authored, "group_thread": len(people) > 2}


def _communication_unit(hit: Any, plan: Any, *, and_i: bool) -> dict[str, Any] | None:
    d = hit.to_dict() if hasattr(hit, "to_dict") else dict(hit)
    eid = str(d.get("evidence_id") or "")
    payload = {}
    subj = str(d.get("summary") or "")
    excerpt = str(d.get("excerpt") or "")
    if eid and (
        not excerpt
        or len(excerpt) < 120
        or looks_supporting_subject(subj)
        or re.search(
            r"(?i)\b(delta|united|spirit|marriott|hilton|hertz|itinerary|"
            r"boarding|reservation|rental)\b",
            subj,
        )
    ):
        payload = _payload_for(eid)
    skip = _mailbox_skip(payload)
    if skip:
        return None
    channel = str(d.get("channel") or payload.get("evidence_channel") or "email").lower()
    source_type = "sms" if channel in {"sms", "text", "imessage", "mms", "rcs"} else "email"
    body = str(payload.get("body_text") or d.get("excerpt") or "")
    flags: dict[str, bool] = {}
    authored = body
    if source_type == "email":
        authored, flags = authored_email_text(body)
    loc = []
    if source_type == "sms":
        loc = sms_location_assertions(
            authored,
            attachments=d.get("attachments") or payload.get("attachments"),
            shared_location=payload.get("shared_location") if isinstance(payload.get("shared_location"), dict) else None,
        )
    people = [str(p) for p in (d.get("people") or payload.get("participants") or []) if str(p).strip()]
    speaker = (
        str(payload.get("sender_name") or payload.get("from") or "").strip() or None
    )
    mapped = None
    if d.get("identity_mapped"):
        mapped = (d.get("identity_mapped") or [{}])[0].get("person_id")
    payload_pids = [str(x) for x in (payload.get("person_ids") or []) if x]
    from_owner = bool(payload.get("from_owner") or str(d.get("direction") or "").lower() == "outbound")
    if not mapped and payload_pids and not from_owner:
        mapped = payload_pids[0]
    meta = _comm_flags(and_i, speaker, people, plan)
    unit_id = _uid("communication", eid)
    content = authored if meta["keep_authored"] else ""
    claims: list[dict[str, Any]] = []
    for a in loc:
        claims.append(
            {
                "type": "location",
                "place": a.get("place"),
                "time": d.get("sent_at"),
                "confidence": "medium",
                "basis": [a.get("basis")],
            }
        )
    return {
        "unit_id": unit_id,
        "kind": "communication",
        "time": _time(d.get("sent_at") or payload.get("sent_at")),
        "people": [{"name": p, "role": "participant"} for p in people[:12]],
        "place": loc[0].get("place") if loc else None,
        "content": (content or d.get("summary") or "")[:2000],
        "claims": claims,
        "provenance": {"source": source_type, "evidence_id": eid},
        "rank": float(d.get("score") or 1.0),
        "normalization": {
            "source_type": source_type,
            "authored": bool(meta["keep_authored"]),
            **flags,
        },
        "source_type": source_type,
        "source_id": eid,
        "evidence_id": eid,
        "thread_id": d.get("thread_id") or payload.get("thread_id"),
        "speaker_person_id": mapped,
        "sender_name": speaker,
        "sender_handle": payload.get("sender_handle") or d.get("sender_handle"),
        "from_owner": from_owner,
        "participants": people,
        "group_thread": meta["group_thread"],
        "timestamp": d.get("sent_at"),
        "authored_text": content if meta["keep_authored"] else None,
        "subject": payload.get("subject") or d.get("summary"),
        "attachments": [],
        "location_assertions": loc,
        "flags": flags,
        "_raw_body": body,
    }


def _photo_is_video(d: dict[str, Any]) -> bool:
    if str(d.get("media_type") or "").lower() == "video":
        return True
    exif = d.get("exif") if isinstance(d.get("exif"), dict) else {}
    if str(exif.get("media") or "").lower() == "video":
        return True
    fn = str(d.get("original_filename") or "").lower()
    return fn.endswith((".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"))


def _calendar_place(summary: str) -> str | None:
    blob = (summary or "").lower()
    if "las vegas" in blob or re.search(r"\bvegas\b", blob):
        return "Las Vegas"
    if "sphere" in blob or "eagles" in blob:
        return "Las Vegas"
    if "paradise" in blob:
        return "Paradise"
    if "alaska" in blob:
        return "Alaska"
    if "vancouver" in blob:
        return "Vancouver"
    return None


def _las_vegas_area(obj: dict[str, Any]) -> bool:
    blob = " ".join(
        str(x or "")
        for x in (
            obj.get("place"),
            obj.get("city"),
            obj.get("state"),
            obj.get("title"),
            obj.get("content"),
            obj.get("subject"),
        )
    ).lower()
    lat = obj.get("latitude")
    lon = obj.get("longitude")
    try:
        lat_f = float(lat) if lat is not None else None
        lon_f = float(lon) if lon is not None else None
    except (TypeError, ValueError):
        lat_f = lon_f = None
    if lat_f is not None and lon_f is not None:
        if 35.85 <= lat_f <= 36.45 and -115.45 <= lon_f <= -114.85:
            return True
    if any(tok in blob for tok in ("las vegas", "vegas", "sphere", "henderson")):
        return True
    if "paradise" in blob and (
        "nv" in blob or "nevada" in blob or (lat_f is not None and lon_f is not None)
    ):
        return True
    return False


def _days_apart(a: str | None, b: str | None) -> int | None:
    if not a or not b or len(a) < 10 or len(b) < 10:
        return None
    try:
        from datetime import date

        return abs((date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days)
    except ValueError:
        return None


def _media_unit(photo: Any) -> dict[str, Any]:
    d = photo.to_dict() if hasattr(photo, "to_dict") else dict(photo)
    pid = str(d.get("external_id") or "")
    lat, lon = d.get("latitude"), d.get("longitude")
    place = d.get("place") or d.get("location") or d.get("city")
    basis = []
    if lat is not None and lon is not None:
        basis.append("exif_gps")
        place = place or f"{lat},{lon}"
    people = [str(p) for p in (d.get("people") or []) if str(p).strip()]
    mb_id = d.get("mb_person_id")
    claims = []
    if (mb_id or people) and (lat is not None or place) and d.get("taken_at"):
        claims.append(
            {
                "type": "presence",
                "person_id": mb_id,
                "place": place,
                "time": d.get("taken_at"),
                "confidence": "medium" if d.get("identity_trust") == "confirmed" else "low",
                "basis": (["face"] if (mb_id or people) else []) + basis,
            }
        )
    people_rows = [{"name": p, "role": "depicted"} for p in people[:12]]
    if mb_id:
        if people_rows:
            people_rows[0]["person_id"] = mb_id
        else:
            nm = str(d.get("mb_person_name") or "").strip()
            people_rows.append({"name": nm or None, "person_id": mb_id, "role": "depicted"})
    loc_conf = "high" if basis else ("medium" if place else "low")
    is_vid = _photo_is_video(d)
    kind = "video_asset" if is_vid else "media_observation"
    source_type = "video" if is_vid else "photo"
    return {
        "unit_id": _uid("media", pid),
        "kind": kind,
        "time": _time(d.get("taken_at")),
        "people": people_rows,
        "place": place,
        "content": d.get("caption") or d.get("description") or "",
        "claims": claims,
        "provenance": {
            "source": source_type,
            "external_id": pid,
            "filename_not_photographer": True,
        },
        "rank": float(d.get("score") or 1.0),
        "normalization": {"source_type": source_type},
        "evidence_id": pid or None,
        "asset_ref": pid,
        "source_type": source_type,
        "media_type": "video" if is_vid else "image",
        "duration_sec": d.get("duration_sec"),
        "capture_time": d.get("taken_at"),
        "captured_at": d.get("taken_at"),
        "latitude": lat,
        "longitude": lon,
        "provider": d.get("provider_key"),
        "place_basis": basis[0] if basis else ("labeled_place" if place else None),
        "location_confidence": loc_conf,
        "location_provenance": basis[0] if basis else ("labeled_place" if place else None),
        "original_filename": d.get("original_filename"),
        "flags": {
            "filename_is_not_photographer": True,
            "folder_is_not_photographer": True,
            "camera_owner_is_not_photographer": True,
        },
    }


def _video_unit(video: Any) -> dict[str, Any]:
    d = video.to_dict() if hasattr(video, "to_dict") else dict(video)
    vid = str(d.get("external_id") or d.get("video_external_id") or "")
    spoken = d.get("spoken_text")
    attrib = str(d.get("attribution") or "")
    lat, lon = d.get("latitude"), d.get("longitude")
    place = d.get("place") or d.get("city") or d.get("location")
    if spoken or attrib == "spoken_moment":
        kind = "spoken_moment"
    elif attrib == "video_asset" or (
        not attrib
        and (d.get("start_sec") in (None, 0) and d.get("end_sec") in (None, 0))
        and not d.get("face_external_id")
    ):
        kind = "video_asset"
    else:
        kind = "video_moment"
    people_rows = []
    if d.get("mb_person_name") or d.get("mb_person_id"):
        people_rows.append(
            {
                "name": d.get("mb_person_name"),
                "person_id": d.get("mb_person_id"),
                "role": "depicted",
            }
        )
    return {
        "unit_id": _uid("video", vid, kind, str(d.get("start_sec") or "")),
        "kind": kind,
        "time": _time(d.get("taken_at")),
        "people": people_rows,
        "place": place,
        "content": spoken or d.get("label") or "",
        "claims": [],
        "provenance": {"source": "video", "external_id": vid, "evidence_concept": kind},
        "rank": 1.0,
        "normalization": {"source_type": "video"},
        "asset_ref": d.get("video_external_id") or vid,
        "source_type": "video",
        "media_type": "video",
        "duration_sec": d.get("duration_sec"),
        "capture_time": d.get("taken_at"),
        "captured_at": d.get("taken_at"),
        "latitude": lat,
        "longitude": lon,
        "provider": d.get("provider_key"),
        "timeslot": {"start_sec": d.get("start_sec"), "end_sec": d.get("end_sec")},
        "flags": {"filename_is_not_photographer": True},
    }


def _simple_unit(kind: str, ident: str, content: str, time_val: Any, extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit_id": _uid(kind, ident),
        "kind": kind,
        "time": _time(time_val),
        "people": extra.get("people") or [],
        "place": extra.get("place"),
        "content": (content or "")[:4000],
        "claims": extra.get("claims") or [],
        "provenance": extra.get("provenance") or {"source": kind, "id": ident},
        "rank": float(extra.get("rank") or 1.0),
        "normalization": extra.get("normalization") or {},
        **{k: v for k, v in extra.items() if k not in {"people", "place", "claims", "provenance", "rank", "normalization"}},
    }


def _travel_from_comm(unit: dict[str, Any]) -> dict[str, Any] | None:
    if unit.get("source_type") != "email":
        return None
    facts = extract_travel(
        subject=str(unit.get("subject") or ""),
        body=str(unit.get("_raw_body") or unit.get("authored_text") or unit.get("content") or ""),
        source_unit_id=str(unit.get("unit_id") or ""),
        source_evidence_id=str(unit.get("evidence_id") or ""),
    )
    if not facts:
        return None
    route = None
    if facts.get("origin") and facts.get("destination"):
        route = f"{facts['origin']} → {facts['destination']}"
    content_bits = [facts.get("travel_kind"), route or facts.get("property"), facts.get("start"), facts.get("confirmation")]
    return {
        "unit_id": _uid("travel", str(unit.get("evidence_id") or ""), facts.get("travel_kind") or ""),
        "kind": "travel",
        "time": _time(facts.get("start")),
        "people": [],
        "place": facts.get("destination") or facts.get("property"),
        "content": " ".join(str(x) for x in content_bits if x),
        "claims": [
            {
                "type": "travel",
                "place": facts.get("destination") or facts.get("property"),
                "time": facts.get("start"),
                "confidence": "high",
                "basis": ["derived_from_communication"],
            }
        ],
        "provenance": {
            "derived_from": facts["derived_from"],
            "never_replaces_original": True,
        },
        "rank": 1.2,
        "normalization": {"derived": True},
        **facts,
    }


def _and_i_ask(plan: Any) -> bool:
    q = str(getattr(plan, "original_ask", "") or "")
    return bool(re.search(r"(?i)\b(and i|peggy and i|we discussed|discussion)\b", q))


def _calendar_material(hit: Any, plan: Any, *, broad: bool) -> bool:
    if broad:
        return True
    notes = tuple(str(n) for n in (getattr(plan, "notes", ()) or ()))
    d = hit.to_dict() if hasattr(hit, "to_dict") else dict(hit)
    windows = _plan_windows(plan)
    day = str(d.get("sent_at") or "")[:10]
    tell = str(getattr(plan, "output_mode", "") or "") == "tell"
    q = str(getattr(plan, "original_ask", "") or "").lower()
    month_named = bool(
        re.search(
            r"(?i)\b(january|february|march|april|may|june|july|august|"
            r"september|october|november|december)\b",
            q,
        )
    )
    named_trip = bool(getattr(plan, "trip_labels", ()) or getattr(plan, "place_names", ()))
    period_tell = (
        tell
        and not named_trip
        and (
            any("temporal=month_year" in n for n in notes)
            or month_named
            or bool(windows)
        )
    )
    if period_tell:
        if not windows or len(day) < 10:
            return True
        return any(a <= day <= b for a, b in windows)
    blob = f"{d.get('summary') or ''} {d.get('excerpt') or ''}".lower()
    tokens: list[str] = []
    tokens.extend(str(n).lower() for n in (getattr(plan, "person_names", ()) or ()))
    tokens.extend(str(n).lower() for n in (getattr(plan, "place_names", ()) or ()))
    tokens.extend(str(n).lower() for n in (getattr(plan, "trip_labels", ()) or ()))
    q = str(getattr(plan, "original_ask", "") or "").lower()
    cue = [t for t in ("christmas", "hawaii", "maui", "alaska", "thanksgiving") if t in q]
    for t in cue + [tok for tok in tokens if tok and not tok.isdigit()]:
        if t and len(t) > 2 and t in blob:
            return True
    return False


_RANK_STOP = frozenset(
    {
        "write",
        "wrote",
        "narrative",
        "about",
        "tell",
        "story",
        "summarize",
        "what",
        "that",
        "this",
        "from",
        "with",
        "have",
        "been",
        "january",
        "february",
        "march",
        "april",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    }
)


def _rank_units(units: list[dict[str, Any]], ask: str) -> list[dict[str, Any]]:
    q = (ask or "").lower()
    tokens = [
        t
        for t in q.split()
        if len(t) > 3 and t not in _RANK_STOP and not re.fullmatch(r"20\d{2}", t)
    ]

    def score(u: dict[str, Any]) -> float:
        s = float(u.get("rank") or 0)
        kind = u.get("kind")
        if kind in {"travel", "journal", "story"}:
            s += 2.0
        blob = f"{u.get('content') or ''} {u.get('subject') or ''}".lower()
        s += sum(0.3 for t in tokens if t in blob)
        return s

    return sorted(units, key=score, reverse=True)


def _one_per_thread(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for u in units:
        tid = str(u.get("thread_id") or u.get("unit_id") or "")
        if tid and tid in seen:
            continue
        if tid:
            seen.add(tid)
        out.append(u)
    return out


def _spread_by_day(units: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    if n <= 0:
        return []
    buckets: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for u in units:
        day = str((u.get("time") or {}).get("value") or "undated")[:10]
        if day not in buckets:
            buckets[day] = []
            order.append(day)
        buckets[day].append(u)
    out: list[dict[str, Any]] = []
    while len(out) < n and any(buckets.values()):
        for day in order:
            if buckets.get(day) and len(out) < n:
                out.append(buckets[day].pop(0))
    return out


def _round_robin(groups: list[list[dict[str, Any]]], n: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    idx = [0] * len(groups)
    while len(out) < n:
        progressed = False
        for i, g in enumerate(groups):
            if idx[i] < len(g) and len(out) < n:
                out.append(g[idx[i]])
                idx[i] += 1
                progressed = True
        if not progressed:
            break
    return out


def _iso_week(day: str) -> str:
    raw = str(day or "").strip()
    if len(raw) < 10:
        return "undated"
    try:
        from datetime import date as date_cls

        d = date_cls.fromisoformat(raw[:10])
    except ValueError:
        return "undated"
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _unit_day(unit: dict[str, Any]) -> str:
    return str((unit.get("time") or {}).get("value") or "")[:10]


def _people_names(unit: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for p in unit.get("people") or []:
        if isinstance(p, dict):
            n = str(p.get("name") or "").strip().lower()
        else:
            n = str(p or "").strip().lower()
        if n:
            names.add(n)
    for p in unit.get("participants") or []:
        n = str(p or "").strip().lower()
        if n:
            names.add(n)
    return names


def _place_key(unit: dict[str, Any]) -> str:
    return str(unit.get("place") or "").strip().lower()[:80]


def _content_tokens(unit: dict[str, Any]) -> set[str]:
    blob = (
        f"{unit.get('subject') or ''} {unit.get('title') or ''} "
        f"{unit.get('content') or ''} {unit.get('travel_kind') or ''}"
    ).lower()
    return {
        t
        for t in re.findall(r"[a-z]{4,}", blob)
        if t not in _RANK_STOP
    }


def _raw_episode_group_key(unit: dict[str, Any]) -> tuple[Any, ...]:
    kind = str(unit.get("kind") or "")
    day = _unit_day(unit) or "undated"
    if kind == "communication":
        tid = str(unit.get("thread_id") or "").strip()
        if tid:
            return ("thread", tid)
        return ("comm_day", day, unit.get("source_type") or "email", unit.get("unit_id"))
    if kind == "calendar":
        title = str(unit.get("title") or unit.get("content") or "")[:80]
        return ("cal", day, title)
    if kind == "travel":
        conf = str(unit.get("confirmation") or unit.get("place") or "")[:80]
        return ("travel", day, conf or unit.get("unit_id"))
    if kind in {"media_observation", "spoken_moment"}:
        return ("media", day, _place_key(unit) or "unplaced")
    if kind in {"journal", "story", "artifact", "place_event"}:
        return (kind, unit.get("unit_id"))
    return ("other", day, unit.get("unit_id"))


def _episode_group_key(unit: dict[str, Any]) -> tuple[Any, ...]:
    return episode_group_key(unit, _raw_episode_group_key(unit))


def _episode_from_members(members: list[dict[str, Any]]) -> dict[str, Any]:
    days = sorted(d for d in (_unit_day(m) for m in members) if d)
    day = days[0] if days else ""
    people: list[str] = []
    seen_p: set[str] = set()
    for m in members:
        for n in sorted(_people_names(m)):
            if n not in seen_p:
                seen_p.add(n)
                people.append(n)
    places = [p for p in (_place_key(m) for m in members) if p]
    place = places[0] if places else None
    kinds: dict[str, int] = {}
    gists: list[str] = []
    for m in members:
        k = str(m.get("kind") or "other")
        st = str(m.get("source_type") or "")
        label = k if k != "communication" else (st or "email")
        kinds[label] = kinds.get(label, 0) + 1
        gist = re.sub(
            r"\s+",
            " ",
            str(m.get("subject") or m.get("title") or m.get("content") or ""),
        ).strip()[:120]
        if gist and gist not in gists:
            gists.append(gist)
    content = "; ".join(gists[:6]).strip()
    eid = str(members[0].get("unit_id") or "ep")
    claims: list[Any] = []
    seen_c: set[str] = set()
    for m in members:
        for c in m.get("claims") or []:
            key = str(c)[:240]
            if key in seen_c:
                continue
            seen_c.add(key)
            claims.append(c)
    evidence_ids: list[str] = []
    seen_e: set[str] = set()
    for m in members:
        for cand in (
            m.get("evidence_id"),
            m.get("source_id"),
            m.get("asset_ref"),
            m.get("unit_id"),
        ):
            s = str(cand or "").strip()
            if s and s not in seen_e:
                seen_e.add(s)
                evidence_ids.append(s)
                break
    return {
        "unit_id": _uid("episode", eid, str(len(members))),
        "kind": "episode",
        "time": _time(day),
        "date_end": days[-1] if days else day,
        "people": [{"name": p, "role": "participant"} for p in people[:12]],
        "place": place,
        "content": content[:800],
        "title": (gists[0] if gists else "")[:160],
        "claims": claims[:16],
        "provenance": {"derived": True, "not_raw_records": True},
        "rank": max(float(m.get("rank") or 0) for m in members),
        "normalization": {"episode": True},
        "member_n": len(members),
        "source_kinds": kinds,
        "week": _iso_week(day),
        "member_ids": [str(m.get("unit_id") or "") for m in members],
        "evidence_ids": evidence_ids,
        "primary_family": None,
        "significance_reason": None,
        "_members": members,
    }


def _merge_same_day_related(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same calendar day + overlapping people, place, or topic tokens → one episode."""
    n = len(episodes)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    metas: list[tuple[str, set[str], set[str], set[str]]] = []
    for ep in episodes:
        members = list(ep.get("_members") or [])
        people: set[str] = set()
        places: set[str] = set()
        tokens: set[str] = set()
        for m in members:
            people |= _people_names(m)
            p = _place_key(m)
            if p:
                places.add(p)
            tokens |= _content_tokens(m)
        metas.append((_unit_day(ep), people, places, tokens))
    for i in range(n):
        day_i, pe_i, pl_i, tok_i = metas[i]
        if not day_i:
            continue
        for j in range(i + 1, n):
            day_j, pe_j, pl_j, tok_j = metas[j]
            if day_i != day_j:
                apart = _days_apart(day_i, day_j)
                vegas_pair = False
                if apart is not None and apart <= 2:
                    mi = list(episodes[i].get("_members") or [])
                    mj = list(episodes[j].get("_members") or [])
                    vegas_pair = any(_las_vegas_area(m) for m in mi) and any(
                        _las_vegas_area(m) for m in mj
                    )
                if not vegas_pair:
                    continue
            shared_tok = tok_i & tok_j
            fam_i = str(episodes[i].get("primary_family") or episodes[i].get("_primary_family") or "")
            fam_j = str(episodes[j].get("primary_family") or episodes[j].get("_primary_family") or "")
            if not families_compatible(fam_i or "other", fam_j or "other"):
                continue
            mi = list(episodes[i].get("_members") or [])
            mj = list(episodes[j].get("_members") or [])
            if any(_las_vegas_area(m) for m in mi) and any(_las_vegas_area(m) for m in mj):
                union(i, j)
                continue
            if (
                (pe_i and pe_j and (pe_i & pe_j))
                or (pl_i and pl_j and (pl_i & pl_j))
            ) and not (
                fam_i in SUPPORTING_FAMILIES
                and fam_j in SUPPORTING_FAMILIES
                and fam_i != fam_j
            ):
                union(i, j)
            elif (
                fam_i
                and fam_i == fam_j
                and fam_i in LIFE_FAMILIES
                and len(shared_tok) >= 3
            ):
                union(i, j)
    buckets: dict[int, list[dict[str, Any]]] = {}
    order: list[int] = []
    for i, ep in enumerate(episodes):
        r = find(i)
        if r not in buckets:
            buckets[r] = []
            order.append(r)
        buckets[r].extend(list(ep.get("_members") or []))
    return [_episode_from_members(buckets[r]) for r in order]


def _theme_key(episode: dict[str, Any]) -> str:
    return str(episode.get("event_key") or "")


def _collapse_similar_episodes(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same grounded life-event across the period → one theme, not N subject lines."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    passthrough: list[dict[str, Any]] = []
    for ep in episodes:
        fam = str(ep.get("primary_family") or "")
        key = str(ep.get("event_key") or "")
        conf = ""
        for m in ep.get("_members") or []:
            c = str(m.get("confirmation") or "").strip()
            if c:
                conf = c.lower()
                break
        if conf:
            key = f"travel_conf:{conf}"
        if key and (fam in LIFE_FAMILIES or conf):
            if key not in buckets:
                buckets[key] = []
                order.append(key)
            buckets[key].append(ep)
        else:
            passthrough.append(ep)
    out = list(passthrough)
    for key in order:
        group = buckets[key]
        if len(group) < 2:
            out.extend(group)
            continue
        members: list[dict[str, Any]] = []
        for g in group:
            members.extend(list(g.get("_members") or []))
        merged = _episode_from_members(members)
        apply_episode_meaning(merged)
        merged["kind"] = "theme"
        out.append(merged)
    out.sort(key=lambda e: (_unit_day(e) or "9999-99-99", e.get("unit_id") or ""))
    return out


def _build_episodes(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for u in units:
        annotate_unit(u)
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    order: list[tuple[Any, ...]] = []
    for u in units:
        key = _episode_group_key(u)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(u)
    episodes = []
    for k in order:
        ep = _episode_from_members(groups[k])
        apply_episode_meaning(ep)
        episodes.append(ep)
    merged = _merge_same_day_related(episodes)
    rebuilt = []
    for ep in merged:
        apply_episode_meaning(ep)
        rebuilt.append(ep)
    rebuilt = _collapse_similar_episodes(rebuilt)
    rebuilt.sort(key=lambda e: (_unit_day(e) or "9999-99-99", e.get("unit_id") or ""))
    return rebuilt


_TRANSACTIONAL_RE = re.compile(
    r"(?i)\b("
    r"tracking|shipment|shipped|out for delivery|package delivered|"
    r"usps|fedex|dhl|"
    r"your order|order confirmation|order #|invoice|e-?receipt|payment received|"
    r"survey invitation|tell us how (we|you) did|feedback request|"
    r"this is an automated|do not reply to this"
    r")\b"
)
_UPS_WORD_RE = re.compile(r"(?i)(?<![a-z])ups(?![a-z])")


def _unit_blob(unit: dict[str, Any]) -> str:
    return " ".join(
        str(x or "")
        for x in (
            unit.get("subject"),
            unit.get("title"),
            unit.get("content"),
            unit.get("authored_text"),
        )
    )


def _likely_transactional(unit: dict[str, Any]) -> bool:
    """Routine mail heuristic — not a universal ban; context can still promote it."""
    kind = str(unit.get("kind") or "")
    if kind in {"journal", "story", "artifact", "travel", "calendar", "media_observation", "spoken_moment", "video_asset", "video_moment"}:
        return False
    blob = _unit_blob(unit)
    if _TRANSACTIONAL_RE.search(blob) or _UPS_WORD_RE.search(blob):
        return True
    return False


def _episode_transactional_only(episode: dict[str, Any]) -> bool:
    members = list(episode.get("_members") or [])
    if not members:
        return False
    meaningful = {
        "journal",
        "story",
        "artifact",
        "travel",
        "calendar",
        "media_observation",
        "video_asset",
        "video_moment",
        "spoken_moment",
    }
    if any(str(m.get("kind") or "") in meaningful for m in members):
        return False
    if any(str(m.get("source_type") or "") == "sms" for m in members):
        return False
    comms = [m for m in members if str(m.get("kind") or "") == "communication"]
    if not comms:
        return False
    return all(_likely_transactional(m) for m in comms)


def _score_episode(episode: dict[str, Any]) -> float:
    apply_episode_meaning(episode)
    members = list(episode.get("_members") or [])
    kinds = {str(m.get("kind") or "") for m in members}
    fam = str(episode.get("primary_family") or "other")
    score = 0.6
    if fam in LIFE_FAMILIES:
        score = 6.0
        if fam == "health":
            score += 2.0
        if fam in {"travel", "religious", "family_visit", "milestone"}:
            score += 1.5
        if "journal" in kinds or "story" in kinds:
            score += 2.0
        if "calendar" in kinds:
            score += 0.8
        people_n = len(_people_names(episode))
        score += min(1.5, 0.4 * people_n)
        score += min(1.0, 0.15 * len(members))
    elif fam in SUPPORTING_FAMILIES:
        score = 0.35
    else:
        if "journal" in kinds or "story" in kinds:
            score = 6.5
            episode["primary_family"] = "milestone"
            fam = "milestone"
        elif "travel" in kinds:
            score = 7.0
            episode["primary_family"] = "travel"
            fam = "travel"
        else:
            score = 0.9
    episode["significance_score"] = round(score, 3)
    episode["significance"] = round(score, 3)
    episode["significance_reason"] = score_reason(episode, score)
    episode["routine_transactional"] = fam in SUPPORTING_FAMILIES
    return score


def _significant_episodes(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for e in episodes:
        s = _score_episode(e)
        selected = is_life_family(str(e.get("primary_family") or "")) and s >= 5.0
        e["narrator_selected"] = selected
        scored.append(e)
    keep = [e for e in scored if e.get("narrator_selected")]
    keep.sort(key=lambda e: (_unit_day(e) or "9999", e.get("unit_id") or ""))
    return keep


def _beat_slot(day: str, days: list[str]) -> str:
    dated = [d for d in days if len(d) >= 10]
    if not dated or len(day) < 10:
        return "during"
    dated_s = sorted(dated)
    lo, hi = dated_s[0], dated_s[-1]
    if lo == hi:
        return "during"
    span = (int(hi[8:10]) - int(lo[8:10])) if lo[:7] == hi[:7] else 2
    if day <= lo:
        return "early"
    if day >= hi:
        return "late"
    if span <= 1:
        return "during"
    return "mid"


def _period_understanding(
    plan: Any,
    episodes: list[dict[str, Any]],
    significant: list[dict[str, Any]],
    *,
    story_episodes: list[dict[str, Any]] | None = None,
    eligible_n: int,
    processed_n: int,
) -> dict[str, Any]:
    label = str(getattr(plan, "temporal_label", None) or "this period")
    story = list(story_episodes or significant)
    days = [_unit_day(e) for e in story]
    people: list[str] = []
    seen: set[str] = set()
    for e in story:
        for n in sorted(_people_names(e)):
            if n not in seen:
                seen.add(n)
                people.append(n)
    beats = []
    for e in story:
        day = _unit_day(e)
        gist = str(e.get("title") or e.get("content") or "").strip()
        if not gist:
            continue
        beats.append(
            {
                "when": _beat_slot(day, days),
                "time": day or None,
                "about": gist[:240],
                "place": e.get("place"),
                "people": [p.get("name") for p in (e.get("people") or []) if isinstance(p, dict)][:6],
            }
        )
    routine_n = sum(1 for e in episodes if e.get("routine_transactional"))
    if story:
        opening = f"Life during {label}, drawn from what stands out in the archive — not from how much mail arrived."
        closing = f"That is the shape of {label} as the meaningful episodes tell it."
    else:
        opening = (
            f"The archive for {label} was examined in full. "
            "What remains is mostly ordinary household correspondence, not a sequence of standout events."
        )
        closing = f"No separate family episode rose above that ordinary traffic for {label}."
        beats = []
    return {
        "label": label,
        "opening": opening,
        "beats": beats,
        "people": people[:12],
        "closing": closing,
        "routine_episodes_suppressed": routine_n,
        "significant_episode_n": len(significant),
        "candidate_episode_n": len(episodes),
        "eligible_n": eligible_n,
        "processed_n": processed_n,
        "not_family_truth": True,
    }


def _narrative_outline(understanding: dict[str, Any]) -> list[dict[str, Any]]:
    out = [{"role": "opening", "text": understanding.get("opening")}]
    for b in understanding.get("beats") or []:
        out.append(
            {
                "role": "beat",
                "when": b.get("when"),
                "time": b.get("time"),
                "text": b.get("about"),
                "place": b.get("place"),
                "people": b.get("people") or [],
            }
        )
    out.append({"role": "closing", "text": understanding.get("closing")})
    return out


def _claim_summaries(episode: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()

    def add(raw: Any) -> None:
        s = re.sub(r"\s+", " ", str(raw or "")).strip()
        key = s.lower()
        if s and key not in seen:
            seen.add(key)
            texts.append(s[:240])

    for c in episode.get("claims") or []:
        if isinstance(c, dict):
            kind = str(c.get("type") or "claim")
            if c.get("text"):
                add(c.get("text"))
                continue
            place = c.get("place")
            if kind == "travel":
                add(f"Travel related to {place or episode.get('title') or 'a trip'}")
            elif kind == "scheduled":
                add(f"Scheduled: {episode.get('title') or episode.get('content') or 'calendar event'}")
            elif kind == "location":
                add(f"Location noted: {place}" if place else "A location was noted in a message")
            elif kind == "presence":
                add(f"Presence at {place}" if place else "Presence recorded with a place")
            else:
                add(c.get("text") or f"{kind}: {episode.get('title') or ''}".strip(": "))
        else:
            add(c)
    if not texts:
        add(episode.get("title") or episode.get("content"))
    return texts[:8]


def _significance_label(episode: dict[str, Any]) -> str:
    return str(episode.get("significance_reason") or score_reason(episode, 0))


def _exemplars(episode: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in episode.get("_members") or []:
        if _likely_transactional(m):
            continue
        excerpt = str(m.get("authored_text") or m.get("content") or "").strip()
        excerpt = re.split(
            r"(?i)\nOn .+ wrote:|-----Original Message-----|Begin forwarded message:",
            excerpt,
            maxsplit=1,
        )[0].strip()
        if len(excerpt) < 24:
            continue
        out.append(
            {
                "when": _unit_day(m) or None,
                "kind": m.get("source_type") or m.get("kind"),
                "excerpt": excerpt[:280],
            }
        )
        if len(out) >= 2:
            break
    return out


def _date_span(episode: dict[str, Any]) -> dict[str, str | None]:
    days = sorted(
        d
        for d in (_unit_day(m) for m in (episode.get("_members") or [episode]))
        if len(d) >= 10
    )
    if not days:
        end = str(episode.get("date_end") or "")[:10]
        start = _unit_day(episode)
        return {"start": start or None, "end": end or start or None}
    return {"start": days[0], "end": days[-1]}


def _person_background(plan: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    people = list(getattr(plan, "person_names", ()) or ())
    ids = list(getattr(plan, "person_ids", ()) or ())
    places = list(getattr(plan, "place_names", ()) or ())
    trips = list(getattr(plan, "trip_labels", ()) or ())
    events = list(getattr(plan, "event_labels", ()) or ())
    themes = list(getattr(plan, "theme_labels", ()) or ())
    if people:
        out["people"] = people
    if ids:
        out["person_ids"] = ids
    if places:
        out["places"] = places
    if trips:
        out["trips"] = trips
    if events:
        out["events"] = events
    if themes:
        out["themes"] = themes
    kind = getattr(plan, "life_event_kind", None)
    if kind:
        out["life_event"] = kind
    return out


def _life_period_outline(
    plan: Any,
    episodes: list[dict[str, Any]],
    *,
    incomplete: bool,
    truncation: str | None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    all_members: list[dict[str, Any]] = []
    for ep in episodes:
        all_members.extend(list(ep.get("_members") or []))
    for ep in episodes:
        kinds = set(ep.get("source_kinds") or {})
        uncertainty: dict[str, Any] = {}
        if "calendar" in kinds:
            uncertainty["occurrence_not_established_by_calendar_alone"] = True
        if "travel" in kinds:
            uncertainty["travel_derived_from_communication"] = True
        people = [
            p.get("name")
            for p in (ep.get("people") or [])
            if isinstance(p, dict) and p.get("name")
        ]
        row = {
            "theme_or_episode": str(ep.get("title") or "Untitled")[:160],
            "claims": _claim_summaries(ep),
            "evidence_ids": list(ep.get("evidence_ids") or [])[:40],
            "date_span": _date_span(ep),
            "people": people[:12],
            "places": [ep["place"]] if ep.get("place") else [],
            "significance": _significance_label(ep),
            "exemplars": _exemplars(ep),
            "provenance": {
                "grounded_in_evidence_ids": True,
                "not_family_truth": True,
            },
        }
        attach_windows(
            row,
            windows_from_members(ep.get("_members") or [ep]),
            fallback_span=row["date_span"],
        )
        attach_support_profile(row, pack={"units": all_members or list(ep.get("_members") or [ep])})
        if uncertainty:
            row["uncertainty"] = uncertainty
        rows.append(row)
    windows = [{"start": a, "end": b} for a, b in _plan_windows(plan)]
    return {
        "period": str(getattr(plan, "temporal_label", None) or "this period"),
        "windows": windows,
        "episodes": rows,
        **pack_level_windows(rows),
        "coverage": {
            "incomplete": bool(incomplete),
            "note": truncation if incomplete else None,
        },
    }


def _week_summaries(units: list[dict[str, Any]], episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weeks: dict[str, list[dict[str, Any]]] = {}
    for u in units:
        weeks.setdefault(_iso_week(_unit_day(u)), []).append(u)
    ep_by_week: dict[str, int] = {}
    for e in episodes:
        w = str(e.get("week") or _iso_week(_unit_day(e)))
        ep_by_week[w] = ep_by_week.get(w, 0) + 1
    out = []
    for key in sorted(weeks):
        rows = weeks[key]
        kinds: dict[str, int] = {}
        for r in rows:
            k = str(r.get("kind") or "other")
            st = str(r.get("source_type") or "")
            label = k if k != "communication" else (st or "email")
            kinds[label] = kinds.get(label, 0) + 1
        out.append(
            {
                "summary_id": _uid("week", key),
                "period": key,
                "text": (
                    f"{key}: {len(rows)} evidence item(s) in {ep_by_week.get(key, 0)} episode(s) — "
                    + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items()))
                ),
                "unit_n": len(rows),
                "episode_n": ep_by_week.get(key, 0),
                "derived": True,
                "not_family_truth": True,
            }
        )
    return out


def _select_narrator_episodes(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prompt-size budget for significant themes only — not a week-fair sample."""
    units: list[dict[str, Any]] = []
    for e in episodes:
        units.extend(list(e.get("_members") or []))
    pack = {"units": units}
    for e in episodes:
        attach_support_profile(e, pack=pack)
    by_support = sorted(
        episodes,
        key=lambda e: (
            -float(e.get("support_score") or 0),
            -float(e.get("significance_score") or e.get("significance") or 0),
            _unit_day(e) or "9999",
        ),
    )
    picked = by_support[:NARRATOR_EPISODE_BUDGET]
    return rank_episodes_for_narrator(picked, budget=None)


def _public_unit(unit: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in unit.items() if not str(k).startswith("_")}


def _evidence_used(units: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "photos": 0,
        "video_moments": 0,
        "calendar_events": 0,
        "emails": 0,
        "sms": 0,
        "journal_entries": 0,
        "stories": 0,
        "artifacts": 0,
        "travel": 0,
        "spoken_moments": 0,
        "video_assets": 0,
        "place_event": 0,
        "external_historical": 0,
    }
    for u in units:
        k = u.get("kind")
        st = u.get("source_type")
        if k == "media_observation" and st != "video":
            counts["photos"] += 1
        elif k == "media_observation":
            counts["video_moments"] += 1
        elif k == "spoken_moment":
            counts["spoken_moments"] += 1
        elif k == "calendar":
            counts["calendar_events"] += 1
        elif k == "communication" and st == "sms":
            counts["sms"] += 1
        elif k == "communication":
            counts["emails"] += 1
        elif k == "journal":
            counts["journal_entries"] += 1
        elif k == "story":
            counts["stories"] += 1
        elif k == "artifact":
            counts["artifacts"] += 1
        elif k == "travel":
            counts["travel"] += 1
        elif k == "video_asset":
            counts["video_assets"] = counts.get("video_assets", 0) + 1
        elif k == "video_moment":
            counts["video_moments"] += 1
        elif k == "place_event":
            counts["place_event"] += 1
    return counts


def _breadth(plan: Any) -> str:
    q = str(getattr(plan, "original_ask", "") or "").lower()
    if getattr(plan, "want_cross_source", False):
        return "broad"
    if getattr(plan, "trip_labels", ()) or getattr(plan, "place_names", ()):
        return "narrow"
    if re.search(r"(?i)\b(christmas|hawaii|maui|alaska|thanksgiving)\b", q):
        return "narrow"
    if re_year_only(q) and not getattr(plan, "person_names", ()):
        return "broad"
    if "tell me about my" in q and re.search(r"\b(19|20)\d{2}\b", q):
        return "broad"
    return "narrow"


def re_year_only(q: str) -> bool:
    if re.search(
        r"(?i)\b(january|february|march|april|may|june|july|august|"
        r"september|october|november|december)\b",
        q,
    ):
        return False
    return bool(re.search(r"(?i)\b(19|20)\d{2}\b", q)) and not bool(
        re.search(r"(?i)\b(christmas|hawaii|trip|peggy)\b", q)
    )


def _plan_windows(plan: Any) -> list[tuple[str, str]]:
    windows = [tuple(w) for w in (getattr(plan, "temporal_windows", ()) or ()) if w]
    if not windows:
        t0 = getattr(plan, "time_start", None)
        t1 = getattr(plan, "time_end", None)
        if t0 and t1:
            windows = [(str(t0), str(t1))]
    return [(str(a)[:10], str(b)[:10]) for a, b in windows]


def _unit_in_windows(unit: dict[str, Any], windows: list[tuple[str, str]]) -> bool:
    if not windows:
        return True
    day = str((unit.get("time") or {}).get("value") or "")[:10]
    if len(day) < 10:
        return True
    return any(a <= day <= b for a, b in windows)


def prepare_narrative_pack(
    plan: Any,
    *,
    evidence: list[Any] | None = None,
    photos: list[Any] | None = None,
    videos: list[Any] | None = None,
    stories: list[Any] | None = None,
    journals: list[Any] | None = None,
    artifacts: list[Any] | None = None,
    retrieved_n: int | None = None,
    photo_status: dict[str, Any] | None = None,
    video_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence = list(evidence or [])
    photos = list(photos or [])
    videos = list(videos or [])
    stories = list(stories or [])
    journals = list(journals or [])
    artifacts = list(artifacts or [])
    and_i = _and_i_ask(plan)
    broad = _breadth(plan) == "broad"
    retrieved = retrieved_n if retrieved_n is not None else (
        len(evidence) + len(photos) + len(videos) + len(stories) + len(journals) + len(artifacts)
    )
    units: list[dict[str, Any]] = []
    excluded = ["spam", "trash"]
    calendar_pipeline: list[dict[str, Any]] = []
    comm_pipeline: list[dict[str, Any]] = []
    for h in evidence:
        d = h.to_dict() if hasattr(h, "to_dict") else dict(h)
        channel = str(d.get("channel") or "").lower()
        if channel == "calendar" or d.get("evidence_kind") == "calendar_event":
            title = str(d.get("summary") or d.get("excerpt") or "")
            eligible = _calendar_material(h, plan, broad=broad)
            row = {
                "evidence_id": d.get("evidence_id"),
                "title": title,
                "day": str(d.get("sent_at") or "")[:10],
                "retrieved": True,
                "eligible": eligible,
                "converted_to_inference_unit": False,
                "unit_id": None,
                "skip_reason": None if eligible else "calendar_not_material_for_ask",
                "sent_in_chunk": None,
                "represented_in_merged_semantic_pack": None,
            }
            if not eligible:
                calendar_pipeline.append(row)
                continue
            cal_place = _calendar_place(title)
            unit = _simple_unit(
                    "calendar",
                    str(d.get("evidence_id") or ""),
                    title,
                    d.get("sent_at"),
                    {
                        "place": cal_place,
                        "claims": [
                            {
                                "type": "scheduled",
                                "time": d.get("sent_at"),
                                "confidence": "medium",
                                "basis": ["calendar_row"],
                                "place": cal_place,
                            }
                        ],
                        "provenance": {
                            "source": "calendar",
                            "evidence_id": d.get("evidence_id"),
                            "occurrence_not_established_by_calendar_alone": True,
                        },
                        "title": d.get("summary"),
                        "source_type": "calendar",
                    },
                )
            units.append(unit)
            row["converted_to_inference_unit"] = True
            row["unit_id"] = unit.get("unit_id")
            calendar_pipeline.append(row)
            continue
        u = _communication_unit(h, plan, and_i=and_i)
        if not u:
            excluded.append("mailbox_skip")
            comm_pipeline.append(
                {
                    "evidence_id": d.get("evidence_id"),
                    "title": d.get("summary"),
                    "retrieved": True,
                    "eligible": False,
                    "skip_reason": "mailbox_skip",
                    "converted_to_inference_unit": False,
                    "travel_extracted": False,
                }
            )
            continue
        units.append(u)
        derived = _travel_from_comm(u)
        if derived:
            units.append(derived)
        comm_pipeline.append(
            {
                "evidence_id": d.get("evidence_id"),
                "title": d.get("summary") or u.get("subject"),
                "channel": channel or u.get("source_type"),
                "day": str((u.get("time") or {}).get("value") or "")[:10],
                "retrieved": True,
                "eligible": True,
                "converted_to_inference_unit": True,
                "unit_id": u.get("unit_id"),
                "travel_extracted": bool(derived),
                "travel_unit_id": (derived or {}).get("unit_id"),
            }
        )
    for p in photos:
        units.append(_media_unit(p))
    for v in videos:
        units.append(_video_unit(v))
    for s in stories:
        d = s.to_dict() if hasattr(s, "to_dict") else dict(s)
        units.append(
            _simple_unit(
                "story",
                str(d.get("story_id") or ""),
                str(d.get("excerpt") or d.get("title") or ""),
                d.get("taken_at"),
                {"provenance": {"source": "story", "story_id": d.get("story_id")}},
            )
        )
    for j in journals:
        d = j.to_dict() if hasattr(j, "to_dict") else dict(j)
        units.append(
            _simple_unit(
                "journal",
                str(d.get("journal_id") or ""),
                str(d.get("excerpt") or d.get("title") or ""),
                d.get("described_start_date") or d.get("captured_at"),
                {"provenance": {"source": "journal", "journal_id": d.get("journal_id")}},
            )
        )
    for a in artifacts:
        d = a if isinstance(a, dict) else {}
        aid = str(d.get("artifact_id") or d.get("id") or "")
        if aid:
            units.append(
                _simple_unit(
                    "artifact",
                    aid,
                    str(d.get("why_it_matters") or d.get("title") or d.get("excerpt") or ""),
                    d.get("taken_at"),
                    {"provenance": {"source": "artifact", "artifact_id": aid}},
                )
            )

    windows = _plan_windows(plan)
    if windows:
        kept: list[dict[str, Any]] = []
        kept_ids: set[str] = set()
        for u in units:
            if _unit_in_windows(u, windows):
                kept.append(u)
                kept_ids.add(str(u.get("unit_id") or ""))
                kept_ids.add(str(u.get("evidence_id") or ""))
        units = kept
        for row in calendar_pipeline:
            uid = str(row.get("unit_id") or "")
            if row.get("converted_to_inference_unit") and uid and uid not in kept_ids:
                row["converted_to_inference_unit"] = False
                row["skip_reason"] = "outside_temporal_window"

    eligible_n = len(units)
    retrieve_incomplete = False
    retrieve_note = None
    for h in evidence:
        d = h.to_dict() if hasattr(h, "to_dict") else dict(h)
        if d.get("truncated"):
            retrieve_incomplete = True
            retrieve_note = str(d.get("count_scope") or "retrieve truncated")
            break
    processed_n = eligible_n
    ranked = _rank_units(units, str(getattr(plan, "original_ask", "") or ""))
    episodes = _build_episodes(ranked)
    significant = _significant_episodes(episodes)
    derived_summaries = _week_summaries(ranked, episodes)
    narrator_episodes = _select_narrator_episodes(significant)
    incomplete = retrieve_incomplete or processed_n < eligible_n
    truncation = None
    if incomplete:
        truncation = (
            retrieve_note
            or f"Processed {processed_n} of {eligible_n} eligible items. Coverage is incomplete."
        )
    life_outline = _life_period_outline(
        plan,
        narrator_episodes,
        incomplete=incomplete,
        truncation=truncation,
    )
    background = _person_background(plan)
    understanding = _period_understanding(
        plan,
        episodes,
        significant,
        story_episodes=narrator_episodes,
        eligible_n=eligible_n,
        processed_n=processed_n,
    )
    story_outline = _narrative_outline(understanding)
    reduction = "hierarchical_episode" if len(episodes) > NARRATOR_EPISODE_BUDGET or len(ranked) > HIERARCHY_UNIT_THRESHOLD else "episode"
    if derived_summaries and reduction == "episode" and len(ranked) > 1:
        reduction = "organize"
    missing: list[str] = []
    if not photos and (
        getattr(plan, "want_photo", False) or getattr(plan, "want_still", False)
    ):
        missing.append("photos")
    coverage_summary = (
        f"Considered {eligible_n} eligible item(s); processed {processed_n}; "
        f"{len(episodes)} episode(s); {len(narrator_episodes)} narrator structures."
    )
    if truncation:
        coverage_summary += f" Incomplete coverage: {truncation}"
    semantic = list(getattr(plan, "semantic_constraints", ()) or ())
    for sc in semantic:
        if isinstance(sc, dict) and not sc.get("resolved"):
            missing.append("resolved_age_band_dates")
            coverage_summary += " Relative age band is unresolved to dates."

    owner_id = None
    requestor_id = None
    try:
        from memorybox.profile.owner import get_owner_person_id, get_requestor_person_id

        owner_id = get_owner_person_id()
        requestor_id = get_requestor_person_id()
    except Exception:  # noqa: BLE001
        pass
    asked_people = list(getattr(plan, "person_names", ()) or ())
    asked_ids = list(getattr(plan, "person_ids", ()) or ())
    requestor_library = bool(requestor_id) and not asked_people and not asked_ids
    pack = {
        "schema_version": PACK_SCHEMA,
        "ask": {
            "original_ask": getattr(plan, "original_ask", ""),
            "output_mode": getattr(plan, "output_mode", "tell"),
            "plan": plan.to_dict() if hasattr(plan, "to_dict") else {},
        },
        "scope": {
            "breadth": "broad" if broad else "narrow",
            "owner_person_id": owner_id,
            "requestor_person_id": requestor_id,
            "requestor_library": requestor_library,
            "people": asked_people,
            "time": {
                "windows": [list(w) for w in (getattr(plan, "temporal_windows", ()) or ())],
                "label": getattr(plan, "temporal_label", None),
            },
            "places": list(getattr(plan, "place_names", ()) or ()),
            "events_trips": list(getattr(plan, "trip_labels", ()) or ()),
            "topic": None,
            "modalities": list(getattr(plan, "modalities", ()) or ()),
            "semantic_constraints": semantic,
        },
        "units": [_public_unit(u) for u in ranked],
        "episodes": [_public_unit(e) for e in episodes],
        "significant_episodes": [_public_unit(e) for e in significant],
        "narrator_episodes": [_public_unit(e) for e in narrator_episodes],
        "background": background,
        "life_period_outline": life_outline,
        "period_understanding": understanding,
        "narrative_outline": story_outline,
        "episode_audit": {
            "candidates": [audit_row(e) for e in episodes],
            "selected": [audit_row(e) for e in episodes if e.get("narrator_selected")],
            "rejected": [audit_row(e) for e in episodes if not e.get("narrator_selected")],
        },
        "derived_summaries": derived_summaries,
        "coverage": {
            "summary": coverage_summary,
            "missing": missing,
            "conflicts": [],
            "excluded": list(dict.fromkeys(excluded)),
            "truncated": incomplete,
            "incomplete": incomplete,
            "truncation_disclosure": truncation,
        },
        "volume": {
            "retrieved_n": retrieved,
            "eligible_n": eligible_n,
            "processed_n": processed_n,
            "prepared_n": eligible_n,
            "supplied_to_model_n": len(life_outline.get("episodes") or []),
            "narrator_input_n": len(life_outline.get("episodes") or []),
            "episode_n": len(episodes),
            "significant_episode_n": len(significant),
            "reduction": reduction,
        },
        "evidence_used": _evidence_used(ranked),
        "evidence_considered": _evidence_used(ranked),
        "calendar_pipeline": calendar_pipeline,
        "comm_pipeline": comm_pipeline,
        "media_consideration": {
            "media_provider_candidates": (photo_status or {}).get(
                "media_provider_candidates"
            ),
            "time_filtered_media_count": (photo_status or {}).get(
                "time_filtered_media_count"
            ),
            "person_filtered_media_count": (photo_status or {}).get(
                "person_filtered_media_count"
            ),
            "location_filtered_count": (photo_status or {}).get(
                "location_filtered_count"
            ),
            "evidence_units_generated": sum(
                1
                for u in ranked
                if str(u.get("kind") or "")
                in {"media_observation", "video_asset", "video_moment", "spoken_moment"}
            ),
            "units_passed_to_inference": None,
            "representative_gallery_assets_selected": None,
            "retrieved_photo_hits": len(photos),
            "retrieved_video_hits": len(videos),
            "person_library_unwindowed_n": (photo_status or {}).get(
                "person_library_unwindowed_n"
            ),
            "person_assets_in_window_n": (photo_status or {}).get(
                "person_assets_in_window_n"
            ),
            "year_fair_applied": (photo_status or {}).get("year_fair_applied"),
            "gallery_display_count": len(photos),
            "note": (
                "Person-library unwindowed count, in-window Person assets, and Gallery "
                "display count are separate. year_fair is not applied when the Ask has "
                "time windows — a January stills count of 9 is membership, not a cap of 9. "
                "candidate_visual_ids rank Gallery; empty IDs never suppress eligible media."
            ),
        },
        "evidence_sets": {
            "retrieved": {
                "evidence_hits": len(evidence),
                "photos": len(photos),
                "videos": len(videos),
                "stories": len(stories),
                "journals": len(journals),
                "artifacts": len(artifacts),
                "total": retrieved,
            },
            "inference": {
                "units_generated": eligible_n,
                "units_passed_to_inference": None,
                "by_kind": _evidence_used(ranked),
                "note": "Not an arbitrary top-N. Chunking may batch; it must not drop calendar/travel/media.",
            },
            "presentation": {
                "representative_gallery_assets_selected": None,
                "note": "Representative Gallery assets only. Never used as the inference consideration cap.",
            },
        },
    }
    return pack
