"""Prepared historian input — deterministic→historian boundary (I11A dev/test)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from memorybox.ask.i11a.reason import ASK_RELATIVE_SYSTEM

FIXTURE_VERSION = 1

_TUPLE_PLAN_KEYS = (
    "person_names",
    "person_ids",
    "place_names",
    "event_labels",
    "trip_labels",
    "temporal_windows",
    "notes",
    "retrieval_constraints",
    "life_event_years",
    "theme_labels",
    "semantic_constraints",
)


def plan_to_snapshot(plan: Any) -> dict[str, Any]:
    if hasattr(plan, "to_dict"):
        return dict(plan.to_dict())
    if isinstance(plan, dict):
        return dict(plan)
    return {"original_ask": str(getattr(plan, "original_ask", "") or "")}


def plan_from_snapshot(snapshot: dict[str, Any]) -> Any:
    from memorybox.planner import QueryPlan

    data = dict(snapshot)
    for key in _TUPLE_PLAN_KEYS:
        if key in data and isinstance(data[key], list):
            data[key] = tuple(data[key])
        elif key in data and data[key] is None:
            data[key] = ()
    return QueryPlan(**data)


def scope_units_from_observations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Minimal evidence-id stubs for validate_inference in_scope_ids — no bodies."""
    seen: set[str] = set()
    units: list[dict[str, Any]] = []
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        for raw in obs.get("supporting_evidence_ids") or []:
            eid = str(raw or "").strip()
            if not eid or eid in seen:
                continue
            seen.add(eid)
            units.append({"evidence_id": eid, "kind": "evidence"})
    return units


def pack_minimal_for_historian(
    *,
    plan: Any,
    pack: dict[str, Any],
    observations: list[dict[str, Any]],
    person_context: dict[str, Any],
    modality_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scope_units = scope_units_from_observations(observations)
    places = list(getattr(plan, "place_names", ()) or ())
    trips = list(getattr(plan, "trip_labels", ()) or ())
    windows = [list(w) for w in (getattr(plan, "temporal_windows", ()) or ()) if w]
    return {
        "units": scope_units,
        "inference_units": scope_units,
        "ask": {"original_ask": str(getattr(plan, "original_ask", "") or "")},
        "scope": {
            "people": (person_context or {}).get("people") or [],
            "places": places,
            "events_trips": trips,
            "time": {
                "label": getattr(plan, "temporal_label", None),
                "windows": windows,
            },
        },
        "background": (person_context or {}).get("background") or {},
        "volume": dict(pack.get("volume") or {}) if isinstance(pack.get("volume"), dict) else {},
        "coverage": dict(pack.get("coverage") or {}) if isinstance(pack.get("coverage"), dict) else {},
        "evidence_considered": pack.get("evidence_considered") or pack.get("evidence_used") or {},
        "modality_state": modality_state or pack.get("modality_state") or {},
    }


def build_prepared_historian_input(
    *,
    plan: Any,
    pack: dict[str, Any],
    person_context: dict[str, Any],
    request_context: dict[str, Any],
    ask_kind_hint: str,
    observations: list[dict[str, Any]],
    eligible_observations: list[dict[str, Any]],
    semantic_rollups: dict[str, Any],
    semantic_higher_order: dict[str, Any],
    semantic_ir: dict[str, Any],
    ask_relative_user_payload: dict[str, Any],
    ask_relative_payload_stats: dict[str, Any],
    chunk_map: dict[str, int],
    accounting: dict[str, Any],
    validated_obs_rejected: list[Any] | None = None,
    modality_state: dict[str, Any] | None = None,
    failed_chunks: int = 0,
) -> dict[str, Any]:
    """Model-independent prepared state immediately before ASK_RELATIVE LLM call."""
    user_json = json.dumps(ask_relative_user_payload, default=str, sort_keys=True)
    return {
        "prepared_version": 1,
        "ask": str(getattr(plan, "original_ask", "") or ""),
        "plan_snapshot": plan_to_snapshot(plan),
        "request_context": request_context,
        "person_context": person_context,
        "ask_kind_hint": ask_kind_hint,
        "observations": observations,
        "eligible_observations": eligible_observations,
        "semantic_rollups": semantic_rollups,
        "semantic_higher_order": semantic_higher_order,
        "semantic_ir": semantic_ir,
        "ask_relative_system": ASK_RELATIVE_SYSTEM,
        "ask_relative_user_payload": ask_relative_user_payload,
        "ask_relative_user_message": user_json,
        "ask_relative_payload_stats": ask_relative_payload_stats,
        "pack_minimal": pack_minimal_for_historian(
            plan=plan,
            pack=pack,
            observations=observations,
            person_context=person_context,
            modality_state=modality_state,
        ),
        "chunk_map": chunk_map,
        "accounting": accounting,
        "validated_obs_rejected": list(validated_obs_rejected or []),
        "json_mode": True,
        "temperature": 0.1,
        "provider_options": {"temperature": 0.1},
        "modality_state": modality_state or {},
        "failed_chunks": failed_chunks,
        "narrator_system": None,  # filled at run time from narrative.SYSTEM_PROMPT constant
    }


def input_hash_payload(fixture_body: dict[str, Any]) -> dict[str, Any]:
    """Fields included in model-independent input SHA (excludes commit/timestamp/filename)."""
    return {
        "fixture_version": fixture_body.get("fixture_version"),
        "case_id": fixture_body.get("case_id"),
        "ask": fixture_body.get("ask"),
        "request_context": fixture_body.get("request_context"),
        "person_context": fixture_body.get("prepared", fixture_body).get("person_context")
        if isinstance(fixture_body.get("prepared"), dict)
        else fixture_body.get("person_context"),
        "plan_snapshot": fixture_body.get("prepared", fixture_body).get("plan_snapshot")
        if isinstance(fixture_body.get("prepared"), dict)
        else fixture_body.get("plan_snapshot"),
        "ask_relative_system": fixture_body.get("prepared", fixture_body).get("ask_relative_system")
        if isinstance(fixture_body.get("prepared"), dict)
        else fixture_body.get("ask_relative_system"),
        "ask_relative_user_payload": fixture_body.get("prepared", fixture_body).get(
            "ask_relative_user_payload"
        )
        if isinstance(fixture_body.get("prepared"), dict)
        else fixture_body.get("ask_relative_user_payload"),
        "eligible_observations": fixture_body.get("prepared", fixture_body).get(
            "eligible_observations"
        )
        if isinstance(fixture_body.get("prepared"), dict)
        else fixture_body.get("eligible_observations"),
        "semantic_rollups": fixture_body.get("prepared", fixture_body).get("semantic_rollups")
        if isinstance(fixture_body.get("prepared"), dict)
        else fixture_body.get("semantic_rollups"),
        "semantic_higher_order": fixture_body.get("prepared", fixture_body).get(
            "semantic_higher_order"
        )
        if isinstance(fixture_body.get("prepared"), dict)
        else fixture_body.get("semantic_higher_order"),
        "semantic_ir": fixture_body.get("prepared", fixture_body).get("semantic_ir")
        if isinstance(fixture_body.get("prepared"), dict)
        else fixture_body.get("semantic_ir"),
        "pack_minimal": fixture_body.get("prepared", fixture_body).get("pack_minimal")
        if isinstance(fixture_body.get("prepared"), dict)
        else fixture_body.get("pack_minimal"),
        "json_mode": fixture_body.get("prepared", fixture_body).get("json_mode")
        if isinstance(fixture_body.get("prepared"), dict)
        else fixture_body.get("json_mode"),
        "temperature": fixture_body.get("prepared", fixture_body).get("temperature")
        if isinstance(fixture_body.get("prepared"), dict)
        else fixture_body.get("temperature"),
        "provider_options": fixture_body.get("prepared", fixture_body).get("provider_options")
        if isinstance(fixture_body.get("prepared"), dict)
        else fixture_body.get("provider_options"),
    }


def sha256_input(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, default=str, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def duplicate_higher_order_count(ho: dict[str, Any] | None) -> int:
    if not isinstance(ho, dict):
        return 0
    rows = ho.get("units") or []
    ids = [str(u.get("higher_order_id") or "") for u in rows if isinstance(u, dict)]
    ids = [i for i in ids if i]
    return max(0, len(ids) - len(set(ids)))


def count_rollups(ru: dict[str, Any] | None) -> int:
    if not isinstance(ru, dict):
        return 0
    return int(ru.get("rollup_unit_count") or len(ru.get("rollups") or []))


def count_ho_units(ho: dict[str, Any] | None) -> int:
    if not isinstance(ho, dict):
        return 0
    return int(ho.get("higher_order_unit_total") or len(ho.get("units") or []))
