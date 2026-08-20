"""Ask integration: resolve Occurrence → membership retrieve; discovery as candidates."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from memorybox.occurrence.discover import discover_candidates
from memorybox.occurrence.resolve import occurrence_slots, resolve_occurrence
from memorybox.occurrence.retrieve import hydrate_memberships
from memorybox.occurrence.store import upsert_occurrence
from memorybox.planner import QueryPlan


def maybe_create_from_plan(plan: QueryPlan) -> dict[str, Any] | None:
    slots = occurrence_slots(plan)
    if not slots:
        return None
    kind, label = slots[0]
    t0 = plan.time_start
    t1 = plan.time_end
    windows = list(getattr(plan, "temporal_windows", ()) or ())
    if windows and not (t0 and t1):
        t0 = windows[0][0]
        t1 = windows[0][1]
    occ = upsert_occurrence(
        kind=kind,
        label=label,
        time_start=t0,
        time_end=t1,
        status="candidate",
        actor_key="system",
        provenance={"source": "ask_slot", "ask": plan.original_ask},
    )
    for place in plan.place_names or ():
        from memorybox.occurrence.store import link_place

        link_place(str(occ["id"]), str(place))
    return occ


def apply_occurrence_retrieve(
    plan: QueryPlan,
    *,
    photo_hits: list[Any] | None = None,
) -> tuple[QueryPlan, dict[str, Any] | None, dict[str, Any] | None]:
    """Returns (plan, occ_dict, hydrated) when membership retrieval should replace OR-search."""
    slots = occurrence_slots(plan)
    if not slots:
        return plan, None, None
    occ = resolve_occurrence(plan)
    if occ is None:
        occ = maybe_create_from_plan(plan)
    if occ is None or str(occ.get("status")) in ("rejected", "withdrawn"):
        return plan, None, None
    include_sms = str(getattr(plan, "refine_verb", "") or "") == "add_texts"
    try:
        discover_candidates(
            occ,
            include_sms=include_sms or bool(plan.want_communication),
            photo_hits=photo_hits,
        )
    except Exception:
        pass
    hydrated = hydrate_memberships(str(occ["id"]))
    members = hydrated.get("members") or []
    if not members:
        return plan, occ, None
    notes = list(plan.notes) + ["i10_occurrence_membership_retrieve"]
    plan = replace(plan, notes=tuple(notes))
    return plan, occ, hydrated


def occurrence_payload(occ: dict[str, Any], hydrated: dict[str, Any]) -> dict[str, Any]:
    confirmed = int(hydrated.get("confirmed_n") or 0)
    candidates = int(hydrated.get("candidate_n") or 0)
    label = occ.get("label")
    kind = occ.get("kind")
    extra = ""
    if candidates:
        extra = (
            f" {candidates} additional item"
            f"{'s' if candidates != 1 else ''} may also belong to this "
            f"{kind} (candidates, not silently added history)."
        )
    text = (
        f"Showing the {kind} “{label}” from its durable membership "
        f"({confirmed} confirmed, {candidates} candidate)."
        f"{extra}"
    )
    return {
        "id": occ.get("id"),
        "kind": kind,
        "label": label,
        "status": occ.get("status"),
        "time_start": occ.get("time_start"),
        "time_end": occ.get("time_end"),
        "places": hydrated.get("places") or [],
        "confirmed_n": confirmed,
        "candidate_n": candidates,
        "kinds": hydrated.get("kinds") or [],
        "spoken_precise": hydrated.get("spoken_precise") or [],
        "retrieval": "membership",
        "disclosure": text,
    }
