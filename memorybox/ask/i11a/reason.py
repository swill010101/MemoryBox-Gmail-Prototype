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
from memorybox.ask.i11a.rollup import compact_rollup_for_reason, expand_rollup_ids
from memorybox.ask.i11a.windows import _day

ASK_RELATIVE_SYSTEM = """ASK_RELATIVE_REASONING
You organize compact derived semantic roll-ups to answer one Ask.
Roll-ups are derived groupings of validated observations — not family facts.
Do not re-extract from raw mail. Do not invent people, places, dates, motives, or kin labels.
JSON only. Python expands selected roll-ups to every underlying observation.

{
  "answer_focus": "short string",
  "selected_rollup_ids": ["ru-..."],
  "selected_observation_ids": [],
  "correlations": [{"label": "", "kind": "trip_span|event|relationship|theme|period_cluster|other", "rollup_ids": ["ru-..."], "why": ""}],
  "themes": [{"label": ""}],
  "unresolved": ["..."]
}

Select roll-up ids that matter to the Ask. Do not copy observation text, evidence arrays, or episode prose.
Treat roll-up labels as derived summaries, not established facts.
ask_kind_hint is a view strategy, not a closed taxonomy.
"""


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
) -> dict[str, Any]:
    if not isinstance(parsed, dict) or not (
        parsed.get("episodes")
        or parsed.get("selected_observation_ids")
        or parsed.get("selected_rollup_ids")
        or parsed.get("correlations")
    ):
        return fallback_view(observations, ask=ask, ask_kind_hint=ask_kind_hint)
    by_id = {str(o.get("observation_id")): o for o in observations if o.get("observation_id")}
    expanded = []
    if rollups and parsed.get("selected_rollup_ids"):
        expanded = expand_rollup_ids(
            [str(x) for x in (parsed.get("selected_rollup_ids") or [])],
            rollups=rollups,
            observations=observations,
        )
    selected_ids = [str(x) for x in (parsed.get("selected_observation_ids") or []) if str(x) in by_id]
    for row in expanded:
        oid = str(row.get("observation_id") or "")
        if oid and oid not in selected_ids:
            selected_ids.append(oid)
    correlations = [c for c in (parsed.get("correlations") or []) if isinstance(c, dict)]
    for row in correlations:
        extra_ru = [str(x) for x in (row.get("rollup_ids") or []) if str(x).strip()]
        if extra_ru and rollups:
            more = expand_rollup_ids(extra_ru, rollups=rollups, observations=observations)
            oids = list(row.get("observation_ids") or [])
            for extra in more:
                oid = str(extra.get("observation_id") or "")
                if oid and oid not in oids:
                    oids.append(oid)
                if oid and oid not in selected_ids:
                    selected_ids.append(oid)
            row["observation_ids"] = oids
    used: set[str] = set()
    episodes = [e for e in (parsed.get("episodes") or []) if isinstance(e, dict)]
    if not episodes:
        groups: list[list[dict[str, Any]]] = []
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
            return fallback_view(
                [by_id[i] for i in selected_ids] or observations,
                ask=ask,
                ask_kind_hint=ask_kind_hint,
            )
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
        "selected_rollup_ids": [
            str(x) for x in (parsed.get("selected_rollup_ids") or []) if str(x).strip()
        ],
        "observations_expanded": len(list(dict.fromkeys(selected_ids))),
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
) -> dict[str, Any]:
    ask = str(getattr(plan, "original_ask", "") or "")
    allowed = []
    if isinstance(person_context, dict):
        allowed = list(person_context.get("allowed_relationship_labels") or [])[:24]
    compact = [compact_rollup_for_reason(r) for r in (rollups or []) if isinstance(r, dict)]
    return {
        "ask": ask,
        "ask_kind_hint": ask_kind_hint,
        "request_context": {
            "requestor_person_id": request_context.get("requestor_person_id"),
            "focal_subject_person_ids": request_context.get("focal_subject_person_ids"),
            "focal_subject_names": request_context.get("focal_subject_names"),
        },
        "allowed_relationship_labels": allowed,
        "rollups": compact,
        "validated_observation_count": len(observations),
        "rollup_unit_count": len(compact),
        "note": (
            "Derived semantic roll-ups, not family facts. Select rollup_id values. "
            "Underlying observations expand on demand. Do not copy evidence arrays."
        ),
    }


def apply_correlations_to_ir(ir: dict[str, Any], view: dict[str, Any]) -> dict[str, Any]:
    return attach_links(ir, view.get("correlations") or [])
