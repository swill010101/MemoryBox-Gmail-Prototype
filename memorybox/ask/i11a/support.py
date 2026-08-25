"""Episode support profile — ranking only, not family truth or narrator prose."""
from __future__ import annotations

import re
from typing import Any

from memorybox.ask.i11a.windows import _day, _index_pack_units

_STOP = frozenset(
    {
        "this",
        "that",
        "from",
        "with",
        "have",
        "been",
        "were",
        "they",
        "them",
        "their",
        "about",
        "after",
        "before",
        "family",
        "records",
        "record",
        "photos",
        "photo",
        "messages",
        "message",
        "calendar",
        "travel",
        "indicate",
        "showed",
        "suggest",
        "place",
        "places",
        "people",
        "person",
        "item",
        "items",
        "unit",
        "untitled",
        "content",
        "related",
        "near",
        "somewhere",
        "unspecified",
        "highway",
        "roadside",
        "unknown",
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
_KIND_SOURCE = {
    "media_observation": "photo",
    "spoken_moment": "video",
    "calendar": "calendar",
    "calendar_event": "calendar",
    "travel": "travel",
    "journal": "journal",
    "story": "story",
    "artifact": "artifact",
    "place_event": "place",
}


def source_type_of(unit: dict[str, Any] | None) -> str:
    if not isinstance(unit, dict):
        return "other"
    kind = str(unit.get("kind") or "").lower()
    st = str(unit.get("source_type") or "").lower()
    prov = unit.get("provenance") if isinstance(unit.get("provenance"), dict) else {}
    pst = str(prov.get("source") or "").lower()
    if kind == "communication" or st in {"sms", "email", "text", "imessage", "mms"}:
        if st in {"sms", "text", "imessage", "mms"} or pst in {"sms", "sms_export"}:
            return "sms"
        return "email"
    if st in {"photo", "immich"} or pst == "photo":
        return "photo"
    if st == "video" or pst == "video":
        return "video"
    if st in {"ics", "calendar"} or pst == "calendar":
        return "calendar"
    return _KIND_SOURCE.get(kind, st or pst or kind or "other")


def _tokens(*parts: Any) -> set[str]:
    blob = " ".join(str(p or "") for p in parts)
    return {
        t
        for t in re.findall(r"[a-z]{4,}", blob.lower())
        if t not in _STOP
    }


def _unit_day(unit: dict[str, Any]) -> str | None:
    t = unit.get("time")
    if isinstance(t, dict):
        t = t.get("value") or t.get("start")
    return _day(t or unit.get("capture_time") or unit.get("captured_at"))


def _people_names(obj: dict[str, Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for p in obj.get("people") or []:
        if isinstance(p, dict):
            n = str(p.get("name") or p.get("person_id") or "").strip()
        else:
            n = str(p or "").strip()
        key = n.lower()
        if n and key not in seen:
            seen.add(key)
            out.append(n)
    return out


def _places_of(obj: dict[str, Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for p in list(obj.get("places") or []) + [obj.get("place")]:
        s = str(p or "").strip()
        key = s.lower()
        if s and key not in {"none", "null", "unknown"} and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def _has_exif_gps(unit: dict[str, Any]) -> bool:
    media = unit.get("media") if isinstance(unit.get("media"), dict) else {}
    gps = media.get("exif_gps") if isinstance(media.get("exif_gps"), dict) else None
    if gps and (gps.get("latitude") is not None and gps.get("longitude") is not None):
        return True
    return unit.get("latitude") is not None and unit.get("longitude") is not None


def _unit_blob(unit: dict[str, Any]) -> str:
    return " ".join(
        str(x or "")
        for x in (
            unit.get("content"),
            unit.get("title"),
            unit.get("subject"),
            unit.get("place"),
        )
    )


def _in_span(day: str | None, start: str | None, end: str | None, *, slop_days: int = 1) -> bool:
    if not day or not start:
        return False
    end = end or start
    if start <= day <= end:
        return True
    try:
        from datetime import date, timedelta

        d = date.fromisoformat(day)
        a = date.fromisoformat(str(start)[:10])
        b = date.fromisoformat(str(end)[:10])
        pad = timedelta(days=slop_days)
        return (a - pad) <= d <= (b + pad)
    except ValueError:
        return False


def _collect_member_units(episode: dict[str, Any], pack: dict[str, Any] | None) -> list[dict[str, Any]]:
    members = [m for m in (episode.get("_members") or []) if isinstance(m, dict)]
    idx = _index_pack_units(pack)
    ids: list[str] = []
    for raw in list(episode.get("supporting_evidence_ids") or []) + list(
        episode.get("evidence_ids") or []
    ):
        s = str(raw or "").strip()
        if s and s not in ids:
            ids.append(s)
    for cl in episode.get("claims") or []:
        if not isinstance(cl, dict):
            continue
        for raw in cl.get("supporting_evidence_ids") or []:
            s = str(raw or "").strip()
            if s and s not in ids:
                ids.append(s)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for m in members:
        key = str(m.get("evidence_id") or m.get("unit_id") or id(m))
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    for eid in ids:
        u = idx.get(eid)
        if not u:
            continue
        key = str(u.get("evidence_id") or u.get("unit_id") or eid)
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


def _corroborating_units(
    episode: dict[str, Any],
    members: list[dict[str, Any]],
    pack: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Nearby pack units that share a distinctive place/event token — ranking only."""
    span = episode.get("date_span") if isinstance(episode.get("date_span"), dict) else {}
    start = _day(span.get("start")) or _day((episode.get("observed_window") or {}).get("start"))
    end = _day(span.get("end")) or start
    if not start:
        for m in members:
            start = start or _unit_day(m)
            end = _unit_day(m) or end
    claim_bits = []
    for cl in episode.get("claims") or []:
        if isinstance(cl, dict):
            claim_bits.append(cl.get("text"))
        else:
            claim_bits.append(cl)
    seeds = _tokens(
        episode.get("label"),
        episode.get("theme_or_episode"),
        episode.get("title"),
        episode.get("content"),
        " ".join(_places_of(episode)),
        *claim_bits,
        *[_unit_blob(m) for m in members],
    )
    member_keys = {
        str(m.get("evidence_id") or m.get("unit_id") or "")
        for m in members
    }
    extra: list[dict[str, Any]] = []
    for u in (pack or {}).get("units") or []:
        if not isinstance(u, dict):
            continue
        key = str(u.get("evidence_id") or u.get("unit_id") or "")
        if key and key in member_keys:
            continue
        day = _unit_day(u)
        if start and not _in_span(day, start, end, slop_days=2):
            continue
        utoks = _tokens(_unit_blob(u), u.get("place"))
        if seeds & utoks:
            extra.append(u)
    return extra


def episode_support_profile(
    episode: dict[str, Any],
    *,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    members = _collect_member_units(episode, pack)
    extra = _corroborating_units(episode, members, pack)
    used = members + extra
    types: list[str] = []
    seen_t: set[str] = set()
    gps = False
    reliable_time = False
    for u in used:
        st = source_type_of(u)
        if st and st not in seen_t and st != "other":
            seen_t.add(st)
            types.append(st)
        if _has_exif_gps(u):
            gps = True
        day = _unit_day(u)
        if day and (
            u.get("capture_time")
            or u.get("captured_at")
            or str(u.get("kind") or "") in {"media_observation", "spoken_moment"}
        ):
            reliable_time = True
        if st == "photo" and day:
            reliable_time = True
    people = list(_people_names(episode))
    if not people:
        for u in used:
            for n in _people_names(u):
                if n not in people:
                    people.append(n)
    places = list(_places_of(episode))
    if not places:
        for u in used:
            for p in _places_of(u):
                if p not in places:
                    places.append(p)
    named_event = bool({"calendar", "story", "journal"} & seen_t)
    if not named_event:
        # Same distinctive token in two independent types → named/event-like.
        by_type: dict[str, set[str]] = {}
        for u in used:
            st = source_type_of(u)
            by_type.setdefault(st, set()).update(_tokens(_unit_blob(u), u.get("place")))
        shared = set()
        tlist = [t for t in by_type if t != "other"]
        for i, a in enumerate(tlist):
            for b in tlist[i + 1 :]:
                shared |= by_type[a] & by_type[b]
        named_event = bool(shared)
    n = len(types)
    score = 1.0 * n + 1.6 * max(0, n - 1)
    if "photo" in seen_t:
        score += 1.5 if gps else 0.35
        if reliable_time and gps:
            score += 0.6
    if "video" in seen_t:
        score += 0.8
    if "calendar" in seen_t:
        score += 1.2
    if "travel" in seen_t:
        score += 1.2
    if "sms" in seen_t:
        score += 0.9
    if "email" in seen_t:
        score += 0.6
    if "journal" in seen_t or "story" in seen_t:
        score += 1.4
    if people:
        score += min(1.2, 0.4 * len(people))
    if named_event:
        score += 1.1
    # Isolated weak place / single clue must not dominate.
    if n <= 1:
        only = types[0] if types else ""
        if only in {"place", "photo"} and not gps and not named_event:
            score *= 0.22
        elif not gps and not named_event and only not in {"journal", "story", "travel"}:
            score *= 0.4
    span = episode.get("date_span") if isinstance(episode.get("date_span"), dict) else {}
    if not span.get("start"):
        days = sorted(d for d in (_unit_day(u) for u in used) if d)
        if days:
            span = {"start": days[0], "end": days[-1]}
    return {
        "source_types": types,
        "independent_sources": n,
        "temporal_span": {"start": span.get("start"), "end": span.get("end") or span.get("start")},
        "people": people[:12],
        "places": places[:12],
        "named_event": named_event,
        "support_score": round(score, 3),
    }


def attach_support_profile(
    episode: dict[str, Any],
    *,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prof = episode_support_profile(episode, pack=pack)
    episode["support_profile"] = prof
    episode["support_score"] = prof["support_score"]
    return episode


def rank_episodes_for_narrator(
    episodes: list[dict[str, Any]],
    *,
    budget: int | None = None,
) -> list[dict[str, Any]]:
    """Highest corroboration first, then keep chronological order among the kept set."""

    def _score(e: dict[str, Any]) -> float:
        if e.get("support_score") is not None:
            return float(e.get("support_score") or 0)
        prof = e.get("support_profile") if isinstance(e.get("support_profile"), dict) else {}
        return float(prof.get("support_score") or 0)

    def _start(e: dict[str, Any]) -> str:
        span = e.get("date_span") if isinstance(e.get("date_span"), dict) else {}
        return str((span or {}).get("start") or "9999")[:10]

    ranked = sorted(episodes, key=lambda e: (-_score(e), _start(e)))
    if budget is not None:
        ranked = ranked[: max(0, budget)]
    ranked.sort(key=_start)
    return ranked
