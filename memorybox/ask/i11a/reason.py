"""Ask-relative reasoning over grounded observations.

Deterministic code may establish requestor/focal subject, time/place/person
scope, permissions, eligibility, provenance, exact dates/metadata, and source
compatibility. Semantic judgment — what matters, what is the same real-world
thing, how to organize — is model-assisted with a single prompt. Ask kind is a
hint, not a closed reducer taxonomy.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from memorybox.ask.i11a.ir import attach_links
from memorybox.ask.i11a.person_ir import (
    compact_higher_order_for_reason,
    expand_higher_order_ids,
    higher_order_from_rollups,
)
from memorybox.ask.i11a.rollup import compact_rollup_for_reason, expand_rollup_ids
from memorybox.ask.i11a.windows import _day

ASK_RELATIVE_SYSTEM = """ASK_RELATIVE_REASONING
You organize compact higher-order Person semantic units to answer one Ask.
These units are derived summaries of roll-ups of validated observations — not family facts.
Do not re-extract from raw mail. Do not invent people, places, dates, motives, or kin labels.
JSON only. Python expands selected higher-order units to every child roll-up and observation.

{
  "answer_focus": "short string",
  "selected_higher_order_ids": ["ho-..."],
  "selected_rollup_ids": [],
  "selected_observation_ids": [],
  "correlations": [{"label": "", "kind": "trip_span|event|relationship|theme|period_cluster|other", "higher_order_ids": ["ho-..."], "why": ""}],
  "themes": [{"label": ""}],
  "unresolved": ["..."]
}

Select higher-order ids that matter to the Ask. Leave selected_rollup_ids empty unless a unit needs explicit roll-up resolution.
Do not copy observation text, evidence arrays, or episode prose.
Treat labels as derived summaries, not established facts.
ask_kind_hint is a view strategy, not a closed taxonomy.
"""

ASK_RELATIVE_SCHEMA_KEYS = (
    "answer_focus",
    "selected_higher_order_ids",
    "selected_rollup_ids",
    "selected_observation_ids",
    "themes",
    "unresolved",
)


def ask_relative_schema_ok(parsed: Any) -> tuple[bool, str]:
    """Fail-closed ASK_RELATIVE schema. Compact roll-up/HO echoes are invalid."""
    if not isinstance(parsed, dict):
        return False, "ask-relative output is not a JSON object"
    if parsed.get("rollup_id") and "selected_rollup_ids" not in parsed:
        return False, "ask-relative output is a roll-up object, not ASK_RELATIVE schema"
    if parsed.get("higher_order_id") and "selected_higher_order_ids" not in parsed:
        return False, "ask-relative output is a higher-order object, not ASK_RELATIVE schema"
    missing = [k for k in ASK_RELATIVE_SCHEMA_KEYS if k not in parsed]
    if missing:
        return False, "ask-relative schema missing: " + ", ".join(missing)
    if not isinstance(parsed.get("answer_focus"), str):
        return False, "answer_focus must be a string"
    if not isinstance(parsed.get("selected_higher_order_ids"), list):
        return False, "selected_higher_order_ids must be a list"
    if not isinstance(parsed.get("selected_rollup_ids"), list):
        return False, "selected_rollup_ids must be a list"
    if not isinstance(parsed.get("selected_observation_ids"), list):
        return False, "selected_observation_ids must be a list"
    if not isinstance(parsed.get("themes"), list):
        return False, "themes must be a list"
    if not isinstance(parsed.get("unresolved"), list):
        return False, "unresolved must be a list"
    if parsed.get("correlations") is not None and not isinstance(parsed.get("correlations"), list):
        return False, "correlations must be a list"
    return True, ""


def ask_relative_semantic_ok(
    parsed: Any,
    *,
    rollups: dict[str, Any] | None = None,
    observations: list[dict[str, Any]] | None = None,
    higher_order: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Fail-closed semantic check after ASK_RELATIVE schema validation."""
    if not isinstance(parsed, dict):
        return False, "ask-relative output is not a JSON object"
    by_ru: dict[str, Any] = {}
    if isinstance(rollups, dict):
        raw_by = rollups.get("by_id")
        if isinstance(raw_by, dict):
            by_ru = {str(k): v for k, v in raw_by.items()}
        for row in rollups.get("rollups") or []:
            if isinstance(row, dict) and row.get("rollup_id"):
                by_ru[str(row.get("rollup_id"))] = row
    by_ho: dict[str, Any] = {}
    if isinstance(higher_order, dict):
        raw_ho = higher_order.get("by_id")
        if isinstance(raw_ho, dict):
            by_ho = {str(k): v for k, v in raw_ho.items()}
        for row in higher_order.get("units") or []:
            if isinstance(row, dict) and row.get("higher_order_id"):
                by_ho[str(row.get("higher_order_id"))] = row
    known_obs = {
        str(o.get("observation_id"))
        for o in (observations or [])
        if isinstance(o, dict) and o.get("observation_id")
    }
    ho_ids = [
        str(x).strip() for x in (parsed.get("selected_higher_order_ids") or []) if str(x).strip()
    ]
    ru_ids = [str(x).strip() for x in (parsed.get("selected_rollup_ids") or []) if str(x).strip()]
    ob_ids = [
        str(x).strip() for x in (parsed.get("selected_observation_ids") or []) if str(x).strip()
    ]
    unknown_ho = [h for h in ho_ids if h not in by_ho]
    if unknown_ho:
        return False, "unknown selected_higher_order_ids: " + ", ".join(unknown_ho[:8])
    unknown_ru = [r for r in ru_ids if r not in by_ru]
    if unknown_ru:
        return False, "unknown selected_rollup_ids: " + ", ".join(unknown_ru[:8])
    unknown_ob = [o for o in ob_ids if o not in known_obs]
    if unknown_ob:
        return False, "unknown selected_observation_ids: " + ", ".join(unknown_ob[:8])
    corr = [c for c in (parsed.get("correlations") or []) if isinstance(c, dict)]
    if not ho_ids and not ru_ids and not ob_ids and not corr:
        return False, "ask-relative selected no higher-order units, roll-ups, or observations"
    return True, ""


def _parse_day(raw: Any) -> date | None:
    d = _day(raw)
    if not d:
        return None
    try:
        return date.fromisoformat(d)
    except ValueError:
        return None


def eligible_observations(
    observations: list[dict[str, Any]],
    *,
    plan: Any,
    request_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Scope/eligibility only — not an importance scorer."""
    windows: list[tuple[date, date]] = []
    for w in getattr(plan, "temporal_windows", ()) or ():
        if not w:
            continue
        a, b = _parse_day(w[0]), _parse_day(w[1] if len(w) > 1 else w[0])
        if a and b:
            windows.append((a, b))
    t0, t1 = _parse_day(getattr(plan, "time_start", None)), _parse_day(
        getattr(plan, "time_end", None)
    )
    if t0 and t1 and not windows:
        windows.append((t0, t1))
    names = {
        str(n).strip().lower()
        for n in (
            list(getattr(plan, "person_names", ()) or [])
            + list((request_context or {}).get("focal_subject_names") or [])
        )
        if str(n).strip()
    }
    notes = " ".join(getattr(plan, "notes", ()) or ())
    unconstrained = "exploratory_about_subject" in notes or (
        names and not windows and not getattr(plan, "trip_labels", ())
    )
    out: list[dict[str, Any]] = []
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        day = _parse_day(obs.get("time")) or _parse_day((obs.get("date_span") or {}).get("start"))
        if windows and day and not unconstrained:
            if not any(a <= day <= b for a, b in windows):
                continue
        if names and not unconstrained:
            blob = " ".join(
                [
                    str(obs.get("text") or ""),
                    " ".join(str(p.get("name") or "") for p in (obs.get("people") or []) if isinstance(p, dict)),
                ]
            ).lower()
            if not any(n in blob for n in names) and str(obs.get("kind") or "") not in {
                "calendar_records_event",
                "travel_document_records",
                "place_referenced",
                "person_at_place_time",
                "media_observation",
            }:
                continue
        out.append(obs)
    return out or list(observations)


def _place_tokens(obs: dict[str, Any]) -> set[str]:
    blob = " ".join(
        [
            str(obs.get("text") or ""),
            " ".join(str(p) for p in (obs.get("places") or [])),
        ]
    ).lower()
    toks = {t for t in blob.replace(",", " ").split() if len(t) >= 4}
    lat, lon = obs.get("latitude"), obs.get("longitude")
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        if 35.85 <= lat_f <= 36.45 and -115.45 <= lon_f <= -114.85:
            toks.update({"vegas", "paradise", "nevada"})
    except (TypeError, ValueError):
        pass
    return toks


def _obs_day(obs: dict[str, Any]) -> str | None:
    return _day(obs.get("time")) or _day((obs.get("date_span") or {}).get("start"))


def _nearby(a: str | None, b: str | None, days: int = 5) -> bool:
    if not a or not b:
        return False
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days) <= days
    except ValueError:
        return a == b


def _structural_groups(observations: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group by overlapping time and shared place tokens. Not a topic-importance table."""
    remaining = [o for o in observations if isinstance(o, dict)]
    groups: list[list[dict[str, Any]]] = []
    used: set[int] = set()
    for i, obs in enumerate(remaining):
        if i in used:
            continue
        group = [obs]
        used.add(i)
        tokens = _place_tokens(obs)
        day = _obs_day(obs)
        changed = True
        while changed:
            changed = False
            for j, other in enumerate(remaining):
                if j in used:
                    continue
                ot = _place_tokens(other)
                od = _obs_day(other)
                share = bool(tokens & ot) and not tokens.isdisjoint(ot)
                close = _nearby(day, od) or (day and od and day == od)
                same_people = False
                na = {
                    str(p.get("name") or "").lower()
                    for p in (obs.get("people") or [])
                    if isinstance(p, dict) and p.get("name")
                }
                nb = {
                    str(p.get("name") or "").lower()
                    for p in (other.get("people") or [])
                    if isinstance(p, dict) and p.get("name")
                }
                if na and nb and na & nb and _nearby(day, od, days=2):
                    same_people = True
                if (share and close) or (share and not day) or (share and not od):
                    group.append(other)
                    used.add(j)
                    tokens |= ot
                    if od and (not day or od < day):
                        day = od
                    changed = True
                elif same_people and str(other.get("kind") or "") == str(obs.get("kind") or "") == "communication_states":
                    group.append(other)
                    used.add(j)
                    changed = True
        groups.append(group)
    return groups


def _episode_from_group(rows: list[dict[str, Any]], *, why: str) -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    eids: list[str] = []
    vis: list[str] = []
    people: list[dict[str, Any]] = []
    places: list[str] = []
    seen_c: set[str] = set()
    seen_p: set[str] = set()
    days: list[str] = []
    oids: list[str] = []
    for obs in rows:
        oid = str(obs.get("observation_id") or "")
        if oid:
            oids.append(oid)
        text = str(obs.get("text") or "").strip()
        ids = [str(x) for x in (obs.get("supporting_evidence_ids") or []) if str(x).strip()]
        if text and text not in seen_c and ids:
            seen_c.add(text)
            claims.append(
                {
                    "text": text[:500],
                    "supporting_evidence_ids": ids[:40],
                    "claim_type": obs.get("claim_type") or "observed",
                    "uncertainty": list(obs.get("uncertainty") or []),
                }
            )
        for i in ids:
            if i not in eids:
                eids.append(i)
        if str(obs.get("kind") or "") in {
            "person_at_place_time",
            "media_observation",
            "place_referenced",
        } or obs.get("asset_ref") or (obs.get("media") if isinstance(obs.get("media"), dict) else None):
            for i in ids + [str(obs.get("asset_ref") or "")]:
                if i and i not in vis:
                    vis.append(i)
        for p in obs.get("people") or []:
            if isinstance(p, dict):
                k = str(p.get("person_id") or p.get("name") or "")
            else:
                k = str(p)
            if k and k not in seen_p:
                seen_p.add(k)
                people.append(p if isinstance(p, dict) else {"name": k, "role": "participant"})
        for pl in obs.get("places") or []:
            s = str(pl or "").strip()
            if s and s not in places:
                places.append(s)
        d = _obs_day(obs)
        if d:
            days.append(d)
    days = sorted(days)
    label = claims[0]["text"][:80] if claims else "Untitled"
    kinds = {str(o.get("kind") or "") for o in rows}
    if "repeated_communication_pattern" in kinds and len(rows) == 1:
        label = str(rows[0].get("text") or label)[:80]
    return {
        "label": label,
        "date_span": {"start": days[0] if days else None, "end": days[-1] if days else None},
        "people": people[:24],
        "places": places[:12],
        "claims": claims,
        "why_relevant_to_ask": why[:400],
        "supporting_evidence_ids": eids[:80],
        "candidate_visual_ids": vis[:40],
        "observation_ids": oids,
        "source_kinds": sorted(k for k in kinds if k),
    }


def _person_projection(episodes: list[dict[str, Any]], observations: list[dict[str, Any]]) -> dict[str, Any]:
    patterns = [
        e
        for e in episodes
        if "repeated_communication_pattern" in (e.get("source_kinds") or [])
        or "communication_pattern" in str(e.get("label") or "").lower()
        or "affection" in str(e.get("label") or "").lower()
        or any("pattern" in str(k) for k in (e.get("source_kinds") or []))
    ]
    if not patterns:
        patterns = [
            _episode_from_group([o], why="communication pattern")
            for o in observations
            if str(o.get("kind") or "") == "repeated_communication_pattern"
        ]
    places = [
        e
        for e in episodes
        if str(e.get("source_kinds") and "place_referenced" in (e.get("source_kinds") or []))
        or "place_referenced" in (e.get("source_kinds") or [])
        or "person_at_place_time" in (e.get("source_kinds") or [])
    ]
    return {
        "biographical_facts": [],
        "relationships": {"confirmed": [], "inferred": []},
        "recurring_interactions": patterns,
        "life_episodes": [e for e in episodes if e not in patterns],
        "recurring_activities": [
            e for e in episodes if "calendar_records_event" in (e.get("source_kinds") or [])
        ],
        "trips": [],
        "observed_places": places,
        "communication_patterns": patterns,
        "themes": ["communication_pattern"] if patterns else [],
        "unresolved": [],
    }


def fallback_view(
    observations: list[dict[str, Any]],
    *,
    ask: str,
    ask_kind_hint: str,
) -> dict[str, Any]:
    groups = _structural_groups(observations)
    # Keep pattern observations as their own episodes so Person Asks are not one blob.
    patterned = []
    rest_groups = []
    for g in groups:
        if len(g) == 1 and str(g[0].get("kind") or "") == "repeated_communication_pattern":
            patterned.append(g)
        else:
            rest_groups.append(g)
    ordered = patterned + rest_groups
    why = f"organized for: {ask[:120]}"
    episodes = [_episode_from_group(g, why=why) for g in ordered if g]
    episodes = [e for e in episodes if e.get("claims")]
    correlations = []
    for g, ep in zip(ordered, episodes):
        oids = [str(o.get("observation_id") or "") for o in g if o.get("observation_id")]
        if len(oids) >= 2:
            correlations.append(
                {
                    "label": ep.get("label"),
                    "kind": "period_cluster",
                    "observation_ids": oids,
                    "why": "shared place tokens and nearby dates",
                }
            )
    selected = []
    for e in episodes:
        selected.extend(e.get("observation_ids") or [])
    doc: dict[str, Any] = {
        "schema_version": 2,
        "ask_semantics": {"kind": ask_kind_hint or "other", "constraints": {}},
        "focal_subjects": [],
        "episodes": episodes[:80],
        "themes": [],
        "unresolved": [],
        "answer_focus": ask[:160],
        "selected_observation_ids": list(dict.fromkeys(selected)),
        "selected_rollup_ids": [],
        "selected_higher_order_ids": [],
        "correlations": correlations,
    }
    if ask_kind_hint == "person":
        doc["person_understanding"] = _person_projection(episodes, observations)
    return doc


def view_from_model_json(
    parsed: dict[str, Any] | None,
    observations: list[dict[str, Any]],
    *,
    ask: str,
    ask_kind_hint: str,
    rollups: dict[str, Any] | None = None,
    higher_order: dict[str, Any] | None = None,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    empty = {
        "schema_version": 2,
        "ask_semantics": {"kind": ask_kind_hint or "other", "constraints": {}},
        "focal_subjects": [],
        "episodes": [],
        "themes": [],
        "unresolved": [],
        "answer_focus": ask[:160],
        "selected_observation_ids": [],
        "selected_rollup_ids": [],
        "selected_higher_order_ids": [],
        "correlations": [],
        "lower_level_rollups_expanded": 0,
    }
    if not isinstance(parsed, dict) or not (
        parsed.get("episodes")
        or parsed.get("selected_observation_ids")
        or parsed.get("selected_rollup_ids")
        or parsed.get("selected_higher_order_ids")
        or parsed.get("correlations")
    ):
        if allow_fallback:
            return fallback_view(observations, ask=ask, ask_kind_hint=ask_kind_hint)
        return empty
    by_id = {str(o.get("observation_id")): o for o in observations if o.get("observation_id")}
    expanded: list[dict[str, Any]] = []
    expanded_ru: list[str] = []
    if higher_order and parsed.get("selected_higher_order_ids"):
        ho_obs, ru_ids = expand_higher_order_ids(
            [str(x) for x in (parsed.get("selected_higher_order_ids") or [])],
            higher_order=higher_order,
            rollups=rollups or {},
            observations=observations,
        )
        expanded.extend(ho_obs)
        expanded_ru.extend(ru_ids)
    if rollups and parsed.get("selected_rollup_ids"):
        more_obs = expand_rollup_ids(
            [str(x) for x in (parsed.get("selected_rollup_ids") or [])],
            rollups=rollups,
            observations=observations,
        )
        expanded.extend(more_obs)
        for rid in parsed.get("selected_rollup_ids") or []:
            s = str(rid)
            if s and s not in expanded_ru:
                expanded_ru.append(s)
    selected_ids = [str(x) for x in (parsed.get("selected_observation_ids") or []) if str(x) in by_id]
    for row in expanded:
        oid = str(row.get("observation_id") or "")
        if oid and oid not in selected_ids:
            selected_ids.append(oid)
    correlations = [c for c in (parsed.get("correlations") or []) if isinstance(c, dict)]
    for row in correlations:
        extra_ho = [str(x) for x in (row.get("higher_order_ids") or []) if str(x).strip()]
        extra_ru = [str(x) for x in (row.get("rollup_ids") or []) if str(x).strip()]
        if extra_ho and higher_order:
            more, ru_ids = expand_higher_order_ids(
                extra_ho,
                higher_order=higher_order,
                rollups=rollups or {},
                observations=observations,
            )
            extra_ru = list(dict.fromkeys(extra_ru + ru_ids))
            oids = list(row.get("observation_ids") or [])
            for extra in more:
                oid = str(extra.get("observation_id") or "")
                if oid and oid not in oids:
                    oids.append(oid)
                if oid and oid not in selected_ids:
                    selected_ids.append(oid)
            row["observation_ids"] = oids
            row["rollup_ids"] = extra_ru
            for rid in ru_ids:
                if rid not in expanded_ru:
                    expanded_ru.append(rid)
        elif extra_ru and rollups:
            more = expand_rollup_ids(extra_ru, rollups=rollups, observations=observations)
            oids = list(row.get("observation_ids") or [])
            for extra in more:
                oid = str(extra.get("observation_id") or "")
                if oid and oid not in oids:
                    oids.append(oid)
                if oid and oid not in selected_ids:
                    selected_ids.append(oid)
            row["observation_ids"] = oids
            for rid in extra_ru:
                if rid not in expanded_ru:
                    expanded_ru.append(rid)
    used: set[str] = set()
    episodes = [e for e in (parsed.get("episodes") or []) if isinstance(e, dict)]
    if not episodes:
        groups: list[list[dict[str, Any]]] = []
        if higher_order and parsed.get("selected_higher_order_ids"):
            by_ho = higher_order.get("by_id") if isinstance(higher_order.get("by_id"), dict) else {}
            for hid in parsed.get("selected_higher_order_ids") or []:
                unit = by_ho.get(str(hid)) if isinstance(by_ho, dict) else None
                if not isinstance(unit, dict):
                    continue
                g = [by_id[i] for i in (unit.get("observation_ids") or []) if str(i) in by_id]
                if g:
                    groups.append(g)
                    used.update(str(o.get("observation_id") or "") for o in g)
        if rollups and parsed.get("selected_rollup_ids"):
            by_ru = rollups.get("by_id") if isinstance(rollups.get("by_id"), dict) else {}
            for rid in parsed.get("selected_rollup_ids") or []:
                unit = by_ru.get(str(rid)) if isinstance(by_ru, dict) else None
                if not isinstance(unit, dict):
                    continue
                g = [by_id[i] for i in (unit.get("observation_ids") or []) if str(i) in by_id]
                if g:
                    groups.append(g)
                    used.update(str(o.get("observation_id") or "") for o in g)
        for row in correlations:
            oids = [str(x) for x in (row.get("observation_ids") or []) if str(x) in by_id]
            if not oids:
                continue
            groups.append([by_id[i] for i in oids])
            used.update(oids)
        for oid in selected_ids:
            if oid not in used and oid in by_id:
                groups.append([by_id[oid]])
                used.add(oid)
        if not groups:
            if allow_fallback:
                return fallback_view(
                    [by_id[i] for i in selected_ids] or observations,
                    ask=ask,
                    ask_kind_hint=ask_kind_hint,
                )
            return empty
        why = str(parsed.get("answer_focus") or ask)[:400]
        episodes = [_episode_from_group(g, why=why) for g in groups if g]
        episodes = [e for e in episodes if e.get("claims")]
    else:
        if not selected_ids:
            selected_ids = list(by_id)
        for ep in episodes:
            oids = [str(x) for x in (ep.get("observation_ids") or []) if str(x) in by_id]
            if oids and not ep.get("claims"):
                rebuilt = _episode_from_group(
                    [by_id[i] for i in oids],
                    why=str(ep.get("why_relevant_to_ask") or ask)[:400],
                )
                ep.update({k: rebuilt[k] for k in rebuilt if k not in ep or not ep.get(k)})
            for cl in ep.get("claims") or []:
                if not isinstance(cl, dict):
                    continue
                if not cl.get("supporting_evidence_ids") and oids:
                    ids: list[str] = []
                    for oid in oids:
                        ids.extend(str(x) for x in (by_id[oid].get("supporting_evidence_ids") or []))
                    cl["supporting_evidence_ids"] = list(dict.fromkeys(ids))[:40]
    if not selected_ids:
        for e in episodes:
            selected_ids.extend(str(x) for x in (e.get("observation_ids") or []) if str(x) in by_id)
    doc = {
        "schema_version": 2,
        "ask_semantics": {"kind": ask_kind_hint or "other", "constraints": {}},
        "focal_subjects": parsed.get("focal_subjects") or [],
        "episodes": episodes,
        "themes": parsed.get("themes") or [],
        "unresolved": parsed.get("unresolved") or [],
        "answer_focus": parsed.get("answer_focus") or ask[:160],
        "selected_observation_ids": list(dict.fromkeys(selected_ids)),
        "selected_rollup_ids": list(dict.fromkeys(expanded_ru)),
        "selected_higher_order_ids": [
            str(x) for x in (parsed.get("selected_higher_order_ids") or []) if str(x).strip()
        ],
        "observations_expanded": len(list(dict.fromkeys(selected_ids))),
        "lower_level_rollups_expanded": len(list(dict.fromkeys(expanded_ru))),
        "correlations": correlations,
    }
    if ask_kind_hint == "person" and not doc.get("person_understanding"):
        doc["person_understanding"] = _person_projection(episodes, observations)
    return doc


def compact_observation_for_reason(obs: dict[str, Any]) -> dict[str, Any]:
    """Ask-relative input: meaning + typed fields, not full provenance dumps."""
    people = []
    for p in obs.get("people") or []:
        if isinstance(p, dict) and p.get("name"):
            people.append(str(p.get("name")))
        elif str(p).strip():
            people.append(str(p).strip())
    places = []
    for pl in obs.get("places") or []:
        if isinstance(pl, dict):
            lab = str(pl.get("name") or pl.get("label") or "").strip()
        else:
            lab = str(pl or "").strip()
        if lab and lab not in places:
            places.append(lab)
    refs = [str(x) for x in (obs.get("representative_evidence_ids") or []) if str(x).strip()]
    if not refs:
        refs = [str(x) for x in (obs.get("supporting_evidence_ids") or []) if str(x).strip()][:3]
    return {
        "observation_id": obs.get("observation_id"),
        "kind": obs.get("kind"),
        "text": str(obs.get("text") or "")[:280],
        "claim_type": obs.get("claim_type"),
        "people": people[:8],
        "places": places[:6],
        "time": obs.get("time"),
        "date_span": obs.get("date_span") or {},
        "uncertainty": list(obs.get("uncertainty") or [])[:4],
        "evidence_refs": refs[:3],
    }


def reason_payload(
    *,
    plan: Any,
    observations: list[dict[str, Any]],
    request_context: dict[str, Any],
    person_context: dict[str, Any],
    ask_kind_hint: str,
    rollups: list[dict[str, Any]] | None = None,
    higher_order: list[dict[str, Any]] | dict[str, Any] | None = None,
    observations_for_resolution: list[dict[str, Any]] | None = None,
    rollups_for_resolution: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Default Ask-relative IR is higher-order Person units, not roll-ups or observations.

    Child roll-ups and observations are omitted unless explicitly passed for
    resolution stubs (never a full dump, never sampling of evidence).
    """
    ask = str(getattr(plan, "original_ask", "") or "")
    allowed = []
    if isinstance(person_context, dict):
        allowed = list(person_context.get("allowed_relationship_labels") or [])[:24]
    ho_rows: list[dict[str, Any]]
    if isinstance(higher_order, dict):
        ho_rows = [u for u in (higher_order.get("units") or []) if isinstance(u, dict)]
    elif isinstance(higher_order, list):
        ho_rows = [u for u in higher_order if isinstance(u, dict)]
    else:
        built = higher_order_from_rollups(rollups or [])
        ho_rows = built.get("units") or []
    compact_ho = [compact_higher_order_for_reason(u) for u in ho_rows]
    ru_stubs = [
        compact_rollup_for_reason(r) for r in (rollups_for_resolution or []) if isinstance(r, dict)
    ]
    stubs: list[dict[str, Any]] = []
    for obs in observations_for_resolution or []:
        if isinstance(obs, dict):
            stubs.append(compact_observation_for_reason(obs))
    payload: dict[str, Any] = {
        "ask": ask,
        "ask_kind_hint": ask_kind_hint,
        "request_context": {
            "requestor_person_id": request_context.get("requestor_person_id"),
            "focal_subject_person_ids": request_context.get("focal_subject_person_ids"),
            "focal_subject_names": request_context.get("focal_subject_names"),
        },
        "allowed_relationship_labels": allowed,
        "higher_order": compact_ho,
        "validated_observation_total": len(observations),
        "validated_observation_count": len(observations),
        "rollup_total": len(rollups or []),
        "higher_order_unit_total": len(compact_ho),
        "higher_order_units_sent": len(compact_ho),
        "rollups_sent_to_ask_relative": len(ru_stubs),
        "observations_sent_to_ask_relative": len(stubs),
        "note": (
            "Higher-order Person units are the Ask-relative IR, not family facts. "
            "Select higher_order_id values. Child roll-ups and observations are not in "
            "this payload; Python expands selected units to every child roll-up and observation."
        ),
    }
    if ru_stubs:
        payload["rollup_stubs"] = ru_stubs
        payload["note"] += " rollup_stubs are explicit lower-level expansions, not a full dump."
    if stubs:
        payload["observation_stubs"] = stubs
        payload["note"] += " observation_stubs are explicit evidence-resolution expansions, not a full dump."
    return payload


def apply_correlations_to_ir(ir: dict[str, Any], view: dict[str, Any]) -> dict[str, Any]:
    return attach_links(ir, view.get("correlations") or [])
