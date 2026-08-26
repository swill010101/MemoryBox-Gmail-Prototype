"""Ask-independent hierarchical semantic roll-up of validated observations.

Roll-ups are derived groupings, not family facts. Every observation is assigned
to exactly one roll-up. Evidence is never sampled or discarded.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import date
from typing import Any

from memorybox.ask.i11a.windows import _day

CLAIM_TYPE = "derived"
UNCERTAINTY = "rollup_is_derived_not_family_fact"
PROXIMITY_DAYS = 21
MAX_CLUSTER_SPAN_DAYS = 42
_LABEL_MAX = 140

_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "they",
        "them",
        "their",
        "was",
        "were",
        "have",
        "has",
        "had",
        "you",
        "your",
        "are",
        "but",
        "not",
        "sent",
        "message",
        "messages",
        "sms",
        "email",
        "text",
        "texts",
        "said",
        "says",
        "about",
        "just",
        "got",
        "get",
        "one",
        "also",
        "will",
        "can",
        "involving",
        "observation",
        "observations",
        "records",
        "recorded",
        "calendar",
        "exchanged",
    }
)

_ROLE = {
    "pattern": "recurring interaction pattern",
    "travel": "travel/event participation",
    "calendar": "scheduled events",
    "place": "place/time",
    "relationship": "stated relationship",
    "communication": "exchanges",
    "activity": "named activity",
    "media": "media",
    "other": "grouped observations",
}

_KIND_BUCKET = {
    "communication_states": "communication",
    "people_interacting": "communication",
    "relationship_stated": "relationship",
    "repeated_communication_pattern": "pattern",
    "person_at_place_time": "place",
    "place_referenced": "place",
    "calendar_records_event": "calendar",
    "activity_named": "activity",
    "travel_document_records": "travel",
    "media_observation": "media",
}


def _name(person: Any) -> str:
    if isinstance(person, dict):
        return str(person.get("name") or person.get("person_id") or "").strip()
    return str(person or "").strip()


def _people_key(obs: dict[str, Any]) -> tuple[str, ...]:
    names = sorted(
        {n.lower() for n in (_name(p) for p in (obs.get("people") or [])) if n}
    )
    return tuple(names) if names else ("(unattributed)",)


def _place_names(obs: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for pl in obs.get("places") or []:
        if isinstance(pl, dict):
            lab = str(pl.get("name") or pl.get("label") or "").strip()
        else:
            lab = str(pl or "").strip()
        if lab and lab not in out:
            out.append(lab)
    return out


def _place_key(obs: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(p.lower() for p in _place_names(obs))[:6])


def _obs_day(obs: dict[str, Any]) -> str | None:
    return _day(obs.get("time")) or _day((obs.get("date_span") or {}).get("start"))


def _bucket(obs: dict[str, Any]) -> str:
    return _KIND_BUCKET.get(str(obs.get("kind") or ""), "other")


def _episode_key(obs: dict[str, Any]) -> str:
    for key in ("episode_id", "source_unit_id", "unit_id", "thread_id"):
        s = str(obs.get(key) or "").strip()
        if s:
            return s
    return ""


def _parse_day(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _atomic_key(obs: dict[str, Any]) -> tuple[Any, ...]:
    """Grouping signals: focal people, relationship, episode, time, place, theme/kind."""
    bucket = _bucket(obs)
    people = _people_key(obs)
    if bucket == "pattern":
        theme = str(obs.get("pattern_type") or obs.get("kind") or "pattern")
        return ("pattern", people, theme)
    if bucket == "relationship":
        return ("relationship", people)
    ep = _episode_key(obs)
    if bucket == "communication" and ep:
        return ("communication", people, "episode", ep)
    month = (_obs_day(obs) or "")[:7] or "undated"
    places = _place_key(obs)
    return (bucket, people, month, places)


def _span(rows: list[dict[str, Any]]) -> tuple[date | None, date | None]:
    days = [_parse_day(_obs_day(o)) for o in rows]
    days = [d for d in days if d]
    if not days:
        return None, None
    return min(days), max(days)


def _temporally_close(
    a_start: date | None,
    a_end: date | None,
    b_start: date | None,
    b_end: date | None,
    *,
    days: int = PROXIMITY_DAYS,
) -> bool:
    if not a_start or not a_end or not b_start or not b_end:
        return False
    if a_start <= b_end and b_start <= a_end:
        return True
    gap = min(abs((b_start - a_end).days), abs((a_start - b_end).days))
    return gap <= days


def _merge_proximate(
    groups: list[tuple[tuple[Any, ...], list[dict[str, Any]]]],
) -> list[list[dict[str, Any]]]:
    """Merge atomic groups that share people/kind and are temporally close or place-coherent."""
    items: list[dict[str, Any]] = []
    for key, rows in groups:
        start, end = _span(rows)
        items.append(
            {
                "key": key,
                "rows": list(rows),
                "bucket": key[0] if key else "other",
                "people": key[1] if len(key) > 1 else ("(unattributed)",),
                "start": start,
                "end": end,
                "places": {p.lower() for o in rows for p in _place_names(o)},
            }
        )
    items.sort(key=lambda x: (str(x["bucket"]), x["people"], x["start"] or date.max, str(x["key"])))
    merged: list[dict[str, Any]] = []
    for item in items:
        if item["bucket"] in {"pattern", "relationship"}:
            merged.append(item)
            continue
        attached = False
        for prev in reversed(merged):
            if prev["bucket"] != item["bucket"] or prev["people"] != item["people"]:
                continue
            place_hit = bool(prev["places"] and item["places"] and prev["places"] & item["places"])
            close = _temporally_close(prev["start"], prev["end"], item["start"], item["end"])
            starts = [d for d in (prev["start"], item["start"]) if d]
            ends = [d for d in (prev["end"], item["end"]) if d]
            span_ok = True
            if starts and ends:
                span_ok = (max(ends) - min(starts)).days <= MAX_CLUSTER_SPAN_DAYS
            if (close and span_ok) or (
                place_hit and span_ok and item["bucket"] in {"travel", "place", "calendar"}
            ):
                prev["rows"].extend(item["rows"])
                prev["places"] |= item["places"]
                starts = [d for d in (prev["start"], item["start"]) if d]
                ends = [d for d in (prev["end"], item["end"]) if d]
                prev["start"] = min(starts) if starts else None
                prev["end"] = max(ends) if ends else None
                attached = True
                break
        if not attached:
            merged.append(item)
    return [m["rows"] for m in merged]


def _grounded_gist(rows: list[dict[str, Any]], people: list[str], places: list[str]) -> str:
    """Copy words that already appear in validated observation text. Do not invent."""
    skip = set(_STOP)
    for n in people:
        skip.add(n.lower())
        first = n.split()[0].lower() if n.split() else ""
        if first:
            skip.add(first)
    for p in places:
        skip.add(p.lower())
    counts: Counter[str] = Counter()
    bigrams: Counter[str] = Counter()
    first_text = ""
    for o in rows:
        t = re.sub(r"\s+", " ", str(o.get("text") or "").strip())
        if t and not first_text:
            first_text = t
        toks = [
            w
            for w in re.findall(r"[A-Za-z][A-Za-z']{2,}", t.lower())
            if w not in skip and len(w) > 3
        ]
        counts.update(toks)
        bigrams.update(f"{a} {b}" for a, b in zip(toks, toks[1:]))
    phrases = [p for p, c in bigrams.most_common(6) if c >= 2][:3]
    if not phrases:
        phrases = [w for w, c in counts.most_common(8) if c >= 2][:4]
    if phrases:
        return "; ".join(phrases)
    if first_text:
        return first_text[:110]
    return ""


def _role(rows: list[dict[str, Any]], bucket: str) -> str:
    kinds = {str(o.get("kind") or "") for o in rows}
    if "repeated_communication_pattern" in kinds:
        return "recurring interaction pattern"
    if "travel_document_records" in kinds:
        return "travel/event participation"
    if "relationship_stated" in kinds:
        return "stated relationship"
    if "activity_named" in kinds:
        return "named activity"
    return _ROLE.get(bucket, "grouped observations")


def _label(rows: list[dict[str, Any]], bucket: str) -> str:
    people = []
    seen: set[str] = set()
    for o in rows:
        for p in o.get("people") or []:
            n = _name(p)
            if n and n.lower() not in seen:
                seen.add(n.lower())
                people.append(n)
    places = []
    for o in rows:
        for p in _place_names(o):
            if p not in places:
                places.append(p)
    gist = _grounded_gist(rows, people, places)
    role = _role(rows, bucket)
    if gist:
        return f"{role}: {gist}"[:_LABEL_MAX]
    who = ", ".join(people[:4]) if people else "unattributed"
    start, end = _span(rows)
    if start and end and start == end:
        when = start.isoformat()
    elif start and end:
        when = f"{start.isoformat()}–{end.isoformat()}"
    else:
        when = "undated"
    where = f" @ {', '.join(places[:3])}" if places else ""
    return f"{role} involving {who}, {when}{where}"[:_LABEL_MAX]


def _rollup_id(rows: list[dict[str, Any]], bucket: str) -> str:
    oids = sorted(str(o.get("observation_id") or "") for o in rows if o.get("observation_id"))
    raw = f"{bucket}|{'|'.join(oids)}"
    return "ru-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def roll_up_observations(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Partition every observation into one derived roll-up with full provenance."""
    rows = [o for o in observations if isinstance(o, dict)]
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for obs in rows:
        key = _atomic_key(obs)
        buckets.setdefault(key, []).append(obs)
    groups = _merge_proximate(list(buckets.items()))
    # Any observation missed by grouping (should not happen) becomes a singleton.
    seen_ids = {
        str(o.get("observation_id") or id(o))
        for g in groups
        for o in g
    }
    for obs in rows:
        oid = str(obs.get("observation_id") or id(obs))
        if oid not in seen_ids:
            groups.append([obs])
            seen_ids.add(oid)

    units: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    obs_to_rollup: dict[str, str] = {}
    all_obs_ids: list[str] = []
    all_eids: list[str] = []
    for g in groups:
        if not g:
            continue
        bucket = _bucket(g[0])
        oids = [str(o.get("observation_id") or "") for o in g if o.get("observation_id")]
        eids: list[str] = []
        for o in g:
            for x in o.get("supporting_evidence_ids") or []:
                s = str(x).strip()
                if s and s not in eids:
                    eids.append(s)
        start, end = _span(g)
        rid = _rollup_id(g, bucket)
        people: list[str] = []
        seen_p: set[str] = set()
        places: list[str] = []
        for o in g:
            for p in o.get("people") or []:
                n = _name(p)
                if n and n.lower() not in seen_p:
                    seen_p.add(n.lower())
                    people.append(n)
            for pl in _place_names(o):
                if pl not in places:
                    places.append(pl)
        unit = {
            "rollup_id": rid,
            "label": _label(g, bucket)[:220],
            "kind": bucket,
            "people": people[:16],
            "places": places[:12],
            "date_span": {
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
            },
            "observation_ids": oids,
            "observation_n": len(g),
            "supporting_evidence_ids": eids,
            "claim_type": CLAIM_TYPE,
            "not_family_fact": True,
            "uncertainty": [UNCERTAINTY],
        }
        units.append(unit)
        by_id[rid] = unit
        for oid in oids:
            obs_to_rollup[oid] = rid
            if oid not in all_obs_ids:
                all_obs_ids.append(oid)
        for eid in eids:
            if eid not in all_eids:
                all_eids.append(eid)

    source_obs_ids = [str(o.get("observation_id") or "") for o in rows if o.get("observation_id")]
    source_eids: list[str] = []
    for o in rows:
        for x in o.get("supporting_evidence_ids") or []:
            s = str(x).strip()
            if s and s not in source_eids:
                source_eids.append(s)
    covered_obs = [i for i in source_obs_ids if i in obs_to_rollup]
    covered_eids = [i for i in source_eids if i in set(all_eids)]
    obs_cov = (len(covered_obs) / len(source_obs_ids)) if source_obs_ids else 1.0
    ev_cov = (len(covered_eids) / len(source_eids)) if source_eids else 1.0
    return {
        "rollups": units,
        "by_id": by_id,
        "obs_to_rollup": obs_to_rollup,
        "validated_observation_count": len(rows),
        "rollup_unit_count": len(units),
        "provenance_coverage": min(obs_cov, ev_cov),
        "observation_ids": all_obs_ids,
        "supporting_evidence_ids": all_eids,
        "claim_type": CLAIM_TYPE,
        "not_family_fact": True,
    }


def compact_rollup_for_reason(unit: dict[str, Any]) -> dict[str, Any]:
    """Ask-relative input: compact derived unit, not low-level observation text."""
    return {
        "rollup_id": unit.get("rollup_id"),
        "label": str(unit.get("label") or "")[:140],
        "kind": unit.get("kind"),
        "people": list(unit.get("people") or [])[:8],
        "places": list(unit.get("places") or [])[:6],
        "date_span": unit.get("date_span") or {},
        "observation_n": int(unit.get("observation_n") or 0),
        "claim_type": CLAIM_TYPE,
        "not_family_fact": True,
        "uncertainty": [UNCERTAINTY],
    }


def expand_rollup_ids(
    rollup_ids: list[str],
    *,
    rollups: dict[str, Any],
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Expand selected roll-ups to every underlying observation (no sampling)."""
    by_obs = {str(o.get("observation_id")): o for o in observations if o.get("observation_id")}
    by_ru = rollups.get("by_id") if isinstance(rollups, dict) else {}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rid in rollup_ids:
        unit = (by_ru or {}).get(str(rid)) if isinstance(by_ru, dict) else None
        if not isinstance(unit, dict):
            continue
        for oid in unit.get("observation_ids") or []:
            s = str(oid)
            if s in seen:
                continue
            row = by_obs.get(s)
            if row:
                out.append(row)
                seen.add(s)
    return out
