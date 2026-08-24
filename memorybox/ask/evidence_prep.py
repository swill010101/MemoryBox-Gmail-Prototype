"""Narrative Evidence Preparation — question-specific pack, not a chunk dump."""
from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import UUID

from memorybox.ask.authored import authored_email_text, sms_location_assertions
from memorybox.ask.travel import extract_travel
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
    if eid and not (d.get("excerpt") or d.get("summary")):
        payload = _payload_for(eid)
    elif eid:
        # Skip a per-row Evidence fetch unless travel-shaped; excerpt is enough for pack text.
        subj = str(d.get("summary") or "")
        if re.search(
            r"(?i)\b(delta|united|spirit|marriott|hilton|hertz|itinerary|"
            r"boarding|reservation|rental)\b",
            subj,
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
        "content": (content or d.get("summary") or "")[:400],
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
        "speaker_person_id": (d.get("identity_mapped") or [{}])[0].get("person_id")
        if d.get("identity_mapped")
        else None,
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
    return {
        "unit_id": _uid("media", pid),
        "kind": "media_observation",
        "time": _time(d.get("taken_at")),
        "people": [{"name": p, "role": "depicted"} for p in people[:12]],
        "place": place,
        "content": d.get("caption") or d.get("description") or "",
        "claims": claims,
        "provenance": {
            "source": "photo",
            "external_id": pid,
            "filename_not_photographer": True,
        },
        "rank": float(d.get("score") or 1.0),
        "normalization": {"source_type": "photo"},
        "asset_ref": pid,
        "source_type": "photo",
        "capture_time": d.get("taken_at"),
        "place_basis": basis[0] if basis else ("labeled_place" if place else None),
        "original_filename": d.get("original_filename"),
        "flags": {
            "filename_is_not_photographer": True,
            "folder_is_not_photographer": True,
            "camera_owner_is_not_photographer": True,
        },
    }


def _video_unit(video: Any) -> dict[str, Any]:
    d = video.to_dict() if hasattr(video, "to_dict") else dict(video)
    vid = str(d.get("external_id") or "")
    spoken = d.get("spoken_text")
    kind = "spoken_moment" if spoken or d.get("attribution") == "spoken_moment" else "media_observation"
    return {
        "unit_id": _uid("video", vid, str(d.get("start_sec") or "")),
        "kind": kind,
        "time": _time(d.get("taken_at")),
        "people": (
            [{"name": d.get("mb_person_name"), "role": "depicted"}]
            if d.get("mb_person_name")
            else []
        ),
        "place": None,
        "content": spoken or d.get("label") or "",
        "claims": [],
        "provenance": {"source": "video", "external_id": vid},
        "rank": 1.0,
        "normalization": {"source_type": "video"},
        "asset_ref": vid,
        "source_type": "video",
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
    # Month+year Asks are not a year dump: keep calendar rows that fall in the month.
    if any("temporal=month_year" in n for n in notes):
        day = str(d.get("sent_at") or "")[:10]
        windows = _plan_windows(plan)
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


def _episode_group_key(unit: dict[str, Any]) -> tuple[Any, ...]:
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
    return {
        "unit_id": _uid("episode", eid, str(len(members))),
        "kind": "episode",
        "time": _time(day),
        "people": [{"name": p, "role": "participant"} for p in people[:12]],
        "place": place,
        "content": content[:800],
        "title": (gists[0] if gists else "")[:160],
        "claims": [],
        "provenance": {"derived": True, "member_n": len(members), "not_raw_records": True},
        "rank": max(float(m.get("rank") or 0) for m in members),
        "normalization": {"episode": True},
        "member_n": len(members),
        "source_kinds": kinds,
        "week": _iso_week(day),
        "member_ids": [str(m.get("unit_id") or "") for m in members[:8]],
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
                continue
            shared_tok = tok_i & tok_j
            if (
                (pe_i and pe_j and (pe_i & pe_j))
                or (pl_i and pl_j and (pl_i & pl_j))
                or len(shared_tok) >= 2
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


def _build_episodes(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    order: list[tuple[Any, ...]] = []
    for u in units:
        key = _episode_group_key(u)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(u)
    episodes = [_episode_from_members(groups[k]) for k in order]
    episodes = _merge_same_day_related(episodes)
    episodes.sort(key=lambda e: (_unit_day(e) or "9999-99-99", e.get("unit_id") or ""))
    return episodes


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
    if kind in {"journal", "story", "artifact", "travel", "calendar", "media_observation", "spoken_moment"}:
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
    members = list(episode.get("_members") or [])
    kinds = {str(m.get("kind") or "") for m in members}
    score = 1.0
    if "journal" in kinds or "story" in kinds:
        score += 5.0
    if "artifact" in kinds:
        score += 3.0
    if "travel" in kinds:
        score += 4.0
    if "calendar" in kinds:
        score += 3.0
    if "media_observation" in kinds or "spoken_moment" in kinds:
        score += 2.0
    if any(str(m.get("source_type") or "") == "sms" for m in members):
        score += 1.5
    if any(
        str(m.get("kind") or "") == "communication" and not _likely_transactional(m)
        for m in members
    ):
        score += 1.2
    people_n = len(_people_names(episode))
    score += min(2.0, 0.5 * people_n)
    distinct_kinds = len({k for k in kinds if k})
    score += min(3.0, max(0, distinct_kinds - 1) * 1.5)
    if _episode_transactional_only(episode):
        score *= 0.12
    episode["significance"] = round(score, 3)
    episode["routine_transactional"] = _episode_transactional_only(episode)
    return score


def _significant_episodes(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for e in episodes:
        s = _score_episode(e)
        scored.append((s, e))
    keep = [e for s, e in scored if s >= 2.0 and not e.get("routine_transactional")]
    if keep:
        keep.sort(key=lambda e: (_unit_day(e) or "9999", e.get("unit_id") or ""))
        return keep
    # Nothing rose above routine: still allow non-transactional comms/life notes.
    fallback = [e for s, e in scored if s >= 1.2 and not e.get("routine_transactional")]
    fallback.sort(key=lambda e: (_unit_day(e) or "9999", e.get("unit_id") or ""))
    return fallback


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
    """Prompt-size budget for significant episode structures only."""
    ranked = sorted(
        episodes,
        key=lambda e: (-float(e.get("significance") or 0), _unit_day(e) or "9999"),
    )
    if len(ranked) <= NARRATOR_EPISODE_BUDGET:
        ranked.sort(key=lambda e: (_unit_day(e) or "9999", e.get("unit_id") or ""))
        return ranked
    by_week: dict[str, list[dict[str, Any]]] = {}
    week_order: list[str] = []
    for e in ranked:
        w = str(e.get("week") or "undated")
        if w not in by_week:
            by_week[w] = []
            week_order.append(w)
        by_week[w].append(e)
    groups = [by_week[w] for w in week_order]
    picked = _round_robin(groups, NARRATOR_EPISODE_BUDGET)
    picked.sort(key=lambda e: (_unit_day(e) or "9999", e.get("unit_id") or ""))
    return picked[:NARRATOR_EPISODE_BUDGET]


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
    for h in evidence:
        d = h.to_dict() if hasattr(h, "to_dict") else dict(h)
        channel = str(d.get("channel") or "").lower()
        if channel == "calendar" or d.get("evidence_kind") == "calendar_event":
            if not _calendar_material(h, plan, broad=broad):
                continue
            units.append(
                _simple_unit(
                    "calendar",
                    str(d.get("evidence_id") or ""),
                    str(d.get("summary") or d.get("excerpt") or ""),
                    d.get("sent_at"),
                    {
                        "place": None,
                        "claims": [
                            {
                                "type": "scheduled",
                                "time": d.get("sent_at"),
                                "confidence": "medium",
                                "basis": ["calendar_row"],
                            }
                        ],
                        "provenance": {
                            "source": "calendar",
                            "evidence_id": d.get("evidence_id"),
                            "scheduled_not_occurred": True,
                        },
                        "title": d.get("summary"),
                    },
                )
            )
            continue
        u = _communication_unit(h, plan, and_i=and_i)
        if not u:
            excluded.append("mailbox_skip")
            continue
        units.append(u)
        derived = _travel_from_comm(u)
        if derived:
            units.append(derived)
        u.pop("_raw_body", None)
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
        units = [u for u in units if _unit_in_windows(u, windows)]

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
    incomplete = retrieve_incomplete or processed_n < eligible_n
    truncation = None
    if incomplete:
        truncation = (
            retrieve_note
            or f"Processed {processed_n} of {eligible_n} eligible items. Coverage is incomplete."
        )
    missing: list[str] = []
    if not photos:
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

    pack = {
        "schema_version": PACK_SCHEMA,
        "ask": {
            "original_ask": getattr(plan, "original_ask", ""),
            "output_mode": getattr(plan, "output_mode", "tell"),
            "plan": plan.to_dict() if hasattr(plan, "to_dict") else {},
        },
        "scope": {
            "breadth": "broad" if broad else "narrow",
            "owner_person_id": None,
            "people": list(getattr(plan, "person_names", ()) or ()),
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
        "period_understanding": understanding,
        "narrative_outline": story_outline,
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
            "supplied_to_model_n": len(narrator_episodes),
            "narrator_input_n": len(narrator_episodes),
            "episode_n": len(episodes),
            "significant_episode_n": len(significant),
            "reduction": reduction,
        },
        "evidence_used": _evidence_used(ranked),
        "evidence_considered": _evidence_used(ranked),
    }
    return pack
