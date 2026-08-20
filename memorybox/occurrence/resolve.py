"""Resolve Ask Event/Trip slots to a durable Occurrence. Place is never an Occurrence."""
from __future__ import annotations

from typing import Any

from memorybox.occurrence.store import find_occurrence, normalize_label
from memorybox.planner import QueryPlan


def occurrence_slots(plan: QueryPlan) -> list[tuple[str, str]]:
    """Return (kind, label) pairs. Place names are excluded."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in plan.trip_labels or ():
        label = str(raw or "").strip()
        if label.lower().startswith("trip:"):
            label = label[5:].strip()
        key = f"trip:{normalize_label(label)}"
        if label and key not in seen:
            seen.add(key)
            out.append(("trip", label))
    for raw in plan.event_labels or ():
        label = str(raw or "").strip()
        if not label:
            continue
        if label.lower().startswith("trip:"):
            inner = label[5:].strip()
            key = f"trip:{normalize_label(inner)}"
            if inner and key not in seen:
                seen.add(key)
                out.append(("trip", inner))
            continue
        key = f"event:{normalize_label(label)}"
        if key not in seen:
            seen.add(key)
            out.append(("event", label))
    return out


def resolve_occurrence(plan: QueryPlan) -> dict[str, Any] | None:
    for kind, label in occurrence_slots(plan):
        hit = find_occurrence(kind=kind, label=label)
        if hit:
            return hit
    return None
