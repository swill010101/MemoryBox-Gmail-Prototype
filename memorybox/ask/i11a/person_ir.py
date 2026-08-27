"""Higher-order Person semantic units above episode/theme roll-ups.

Ask-independent. Derived, not family facts. Every roll-up is assigned to
exactly one higher-order unit. Evidence is never sampled.
"""
from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from memorybox.ask.i11a.rollup import expand_rollup_ids

CLAIM_TYPE = "derived"
UNCERTAINTY = "higher_order_is_derived_not_family_fact"
_LABEL_MAX = 160


def _people(unit: dict[str, Any]) -> tuple[str, ...]:
    names = []
    seen: set[str] = set()
    for p in unit.get("people") or []:
        n = str(p or "").strip()
        if n and n.lower() not in seen:
            seen.add(n.lower())
            names.append(n.lower())
    return tuple(sorted(names)) if names else ("(unattributed)",)


def _places(unit: dict[str, Any]) -> tuple[str, ...]:
    out = []
    seen: set[str] = set()
    for p in unit.get("places") or []:
        n = str(p or "").strip().lower()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return tuple(out[:4])


def _year(unit: dict[str, Any]) -> str:
    span = unit.get("date_span") if isinstance(unit.get("date_span"), dict) else {}
    raw = str(span.get("start") or "")[:4]
    return raw if raw.isdigit() else "undated"


def _ho_kind_and_key(unit: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
    bucket = str(unit.get("kind") or "other")
    people = _people(unit)
    places = _places(unit)
    if bucket in {"communication", "pattern"}:
        return "communication_theme", ("communication_theme", people)
    if bucket == "relationship":
        return "relationship_pattern", ("relationship_pattern", people)
    if bucket == "travel":
        return "travel_pattern", ("travel_pattern", people, places)
    if bucket in {"calendar", "activity", "place", "media"}:
        place_key = places[:1] or ("unplaced",)
        return "life_period", ("life_period", _year(unit), place_key)
    return "other", ("other", people, bucket)


def _span(units: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    days: list[date] = []
    for u in units:
        span = u.get("date_span") if isinstance(u.get("date_span"), dict) else {}
        for key in ("start", "end"):
            raw = str(span.get(key) or "")[:10]
            if len(raw) >= 10:
                try:
                    days.append(date.fromisoformat(raw))
                except ValueError:
                    pass
    if not days:
        return None, None
    return min(days).isoformat(), max(days).isoformat()


def _label(kind: str, rows: list[dict[str, Any]]) -> str:
    people: list[str] = []
    seen: set[str] = set()
    for u in rows:
        for p in u.get("people") or []:
            n = str(p or "").strip()
            if n and n.lower() not in seen:
                seen.add(n.lower())
                people.append(n)
    places: list[str] = []
    for u in rows:
        for p in u.get("places") or []:
            n = str(p or "").strip()
            if n and n not in places:
                places.append(n)
    start, end = _span(rows)
    when = ""
    if start and end and start == end:
        when = start
    elif start and end:
        when = f"{start[:4]}–{end[:4]}" if start[:4] != end[:4] else f"{start}–{end}"
    who = ", ".join(people[:4]) if people else "unattributed"
    where = f" @ {', '.join(places[:3])}" if places else ""
    n = len(rows)
    role = {
        "communication_theme": "recurring communication",
        "relationship_pattern": "recurring relationship/interaction",
        "travel_pattern": "travel/event pattern",
        "life_period": "life period",
        "activity_pattern": "recurring activity",
        "other": "grouped roll-ups",
    }.get(kind, "grouped roll-ups")
    change = ""
    if start and end:
        try:
            span_days = (date.fromisoformat(end) - date.fromisoformat(start)).days
        except ValueError:
            span_days = 0
        if span_days >= 365 and kind in {"communication_theme", "relationship_pattern"}:
            change = "; durable across years"
    return f"{role}: {who}{where} ({n} roll-ups{', ' + when if when else ''}){change}"[:_LABEL_MAX]


def _ho_id(kind: str, rows: list[dict[str, Any]]) -> str:
    rids = sorted(str(u.get("rollup_id") or "") for u in rows if u.get("rollup_id"))
    raw = f"{kind}|{'|'.join(rids)}"
    return "ho-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def higher_order_from_rollups(rolled: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    """Partition every roll-up into one Person-level derived unit."""
    if isinstance(rolled, list):
        rows = [u for u in rolled if isinstance(u, dict)]
        source = {"rollups": rows}
    else:
        source = rolled if isinstance(rolled, dict) else {}
        rows = [u for u in (source.get("rollups") or []) if isinstance(u, dict)]
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    kinds: dict[tuple[Any, ...], str] = {}
    for unit in rows:
        kind, key = _ho_kind_and_key(unit)
        buckets.setdefault(key, []).append(unit)
        kinds[key] = kind
    units: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    ru_to_ho: dict[str, str] = {}
    all_ru: list[str] = []
    all_obs: list[str] = []
    all_eids: list[str] = []
    for key, group in buckets.items():
        if not group:
            continue
        kind = kinds.get(key) or "other"
        hid = _ho_id(kind, group)
        rids = [str(u.get("rollup_id") or "") for u in group if u.get("rollup_id")]
        oids: list[str] = []
        eids: list[str] = []
        people: list[str] = []
        seen_p: set[str] = set()
        places: list[str] = []
        obs_n = 0
        for u in group:
            obs_n += int(u.get("observation_n") or len(u.get("observation_ids") or []) or 0)
            for oid in u.get("observation_ids") or []:
                s = str(oid)
                if s and s not in oids:
                    oids.append(s)
            for eid in u.get("supporting_evidence_ids") or []:
                s = str(eid)
                if s and s not in eids:
                    eids.append(s)
            for p in u.get("people") or []:
                n = str(p or "").strip()
                if n and n.lower() not in seen_p:
                    seen_p.add(n.lower())
                    people.append(n)
            for pl in u.get("places") or []:
                n = str(pl or "").strip()
                if n and n not in places:
                    places.append(n)
        start, end = _span(group)
        row = {
            "higher_order_id": hid,
            "label": _label(kind, group),
            "kind": kind,
            "people": people[:16],
            "places": places[:12],
            "date_span": {"start": start, "end": end},
            "rollup_ids": rids,
            "rollup_n": len(group),
            "observation_ids": oids,
            "observation_n": obs_n or len(oids),
            "supporting_evidence_ids": eids,
            "claim_type": CLAIM_TYPE,
            "not_family_fact": True,
            "uncertainty": [UNCERTAINTY],
        }
        units.append(row)
        by_id[hid] = row
        for rid in rids:
            ru_to_ho[rid] = hid
            if rid not in all_ru:
                all_ru.append(rid)
        for oid in oids:
            if oid not in all_obs:
                all_obs.append(oid)
        for eid in eids:
            if eid not in all_eids:
                all_eids.append(eid)
    src_ru = [str(u.get("rollup_id") or "") for u in rows if u.get("rollup_id")]
    src_eids: list[str] = []
    for u in rows:
        for x in u.get("supporting_evidence_ids") or []:
            s = str(x).strip()
            if s and s not in src_eids:
                src_eids.append(s)
    ru_cov = (len([i for i in src_ru if i in ru_to_ho]) / len(src_ru)) if src_ru else 1.0
    ev_cov = (len([i for i in src_eids if i in set(all_eids)]) / len(src_eids)) if src_eids else 1.0
    return {
        "units": units,
        "by_id": by_id,
        "rollup_to_higher_order": ru_to_ho,
        "higher_order_unit_total": len(units),
        "rollup_total": len(rows),
        "provenance_coverage": min(ru_cov, ev_cov),
        "rollup_ids": all_ru,
        "observation_ids": all_obs,
        "supporting_evidence_ids": all_eids,
        "claim_type": CLAIM_TYPE,
        "not_family_fact": True,
    }


def compact_higher_order_for_reason(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "higher_order_id": unit.get("higher_order_id"),
        "label": str(unit.get("label") or "")[:140],
        "kind": unit.get("kind"),
        "people": list(unit.get("people") or [])[:6],
        "places": list(unit.get("places") or [])[:4],
        "date_span": unit.get("date_span") or {},
        "rollup_n": int(unit.get("rollup_n") or 0),
        "observation_n": int(unit.get("observation_n") or 0),
    }


def expand_higher_order_ids(
    higher_order_ids: list[str],
    *,
    higher_order: dict[str, Any],
    rollups: dict[str, Any],
    observations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Expand selected Person units to every child roll-up, then every observation."""
    by_ho = higher_order.get("by_id") if isinstance(higher_order, dict) else {}
    ru_ids: list[str] = []
    seen: set[str] = set()
    for hid in higher_order_ids:
        unit = (by_ho or {}).get(str(hid)) if isinstance(by_ho, dict) else None
        if not isinstance(unit, dict):
            continue
        for rid in unit.get("rollup_ids") or []:
            s = str(rid)
            if s and s not in seen:
                seen.add(s)
                ru_ids.append(s)
    obs = expand_rollup_ids(ru_ids, rollups=rollups, observations=observations)
    return obs, ru_ids
