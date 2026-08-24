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
MODEL_UNIT_BUDGET = 24


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


def _select_supplied(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cap the model pack. Travel is derived — never crowd out authored units."""
    if len(ranked) <= MODEL_UNIT_BUDGET:
        return list(ranked)
    journals = [u for u in ranked if u.get("kind") in {"journal", "story"}]
    travel = [u for u in ranked if u.get("kind") == "travel"][:6]
    calendars = [u for u in ranked if u.get("kind") == "calendar"]
    comms = _one_per_thread([u for u in ranked if u.get("kind") == "communication"])
    other = [
        u
        for u in ranked
        if u.get("kind") not in {"journal", "story", "travel", "calendar", "communication"}
    ]
    keep = journals + travel
    room = max(0, MODEL_UNIT_BUDGET - len(keep))
    cal_n = min(len(calendars), 6, max(0, room // 4)) if calendars else 0
    comm_n = max(0, room - cal_n)
    supplied = keep + _spread_by_day(comms, comm_n) + _spread_by_day(calendars, cal_n)
    leftover_room = MODEL_UNIT_BUDGET - len(supplied)
    if leftover_room > 0:
        used = {id(u) for u in supplied}
        for u in other:
            if id(u) in used:
                continue
            supplied.append(u)
            leftover_room -= 1
            if leftover_room <= 0:
                break
    return supplied[:MODEL_UNIT_BUDGET]


def _hierarchical_summaries(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for u in units:
        key = str((u.get("time") or {}).get("value") or "undated")[:7]
        groups.setdefault(key, []).append(u)
    out = []
    for key, rows in sorted(groups.items()):
        kinds: dict[str, int] = {}
        for r in rows:
            k = str(r.get("kind") or "other")
            kinds[k] = kinds.get(k, 0) + 1
        out.append(
            {
                "summary_id": _uid("sum", key),
                "period": key,
                "text": f"{key}: " + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items())),
                "unit_n": len(rows),
                "unit_ids": [r["unit_id"] for r in rows[:12]],
                "derived": True,
                "not_family_truth": True,
            }
        )
    return out


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
    ranked = _rank_units(units, str(getattr(plan, "original_ask", "") or ""))
    derived_summaries: list[dict[str, Any]] = []
    reduction = "rank"
    truncated = False
    truncation = None
    supplied = ranked
    if len(ranked) > HIERARCHY_UNIT_THRESHOLD:
        derived_summaries = _hierarchical_summaries(ranked)
        reduction = "hierarchical_summary"
        supplied = _select_supplied(ranked)
        if len(supplied) < len(ranked):
            truncated = True
            truncation = (
                f"Prepared {len(ranked)} units; supplied {len(supplied)} plus "
                f"{len(derived_summaries)} derived period summaries. Not a first-N dump."
            )
    elif len(ranked) > MODEL_UNIT_BUDGET:
        reduction = "organize"
        derived_summaries = _hierarchical_summaries(ranked)
        supplied = _select_supplied(ranked)
        truncated = len(supplied) < len(ranked)
        truncation = (
            f"Organized {len(ranked)} units into chronology; "
            f"{len(supplied)} supplied to the model."
            if truncated
            else None
        )

    missing: list[str] = []
    if not photos:
        missing.append("photos")
    coverage_summary = (
        f"{len(supplied)} prepared unit(s) for this Ask"
        + (f"; {truncation}" if truncation else "")
    )
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
        "units": [{k: v for k, v in u.items() if not str(k).startswith("_")} for u in supplied],
        "derived_summaries": derived_summaries,
        "coverage": {
            "summary": coverage_summary,
            "missing": missing,
            "conflicts": [],
            "excluded": list(dict.fromkeys(excluded)),
            "truncated": truncated,
            "truncation_disclosure": truncation,
        },
        "volume": {
            "retrieved_n": retrieved,
            "eligible_n": eligible_n,
            "prepared_n": eligible_n,
            "supplied_to_model_n": len(supplied),
            "reduction": reduction,
        },
        "evidence_used": _evidence_used(supplied),
    }
    return pack
