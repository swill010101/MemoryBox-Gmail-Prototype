"""Prepared historian input — deterministic→historian boundary (I11A dev/test)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from memorybox.ask.i11a.reason import ASK_RELATIVE_SYSTEM

FIXTURE_VERSION = 1

# Top-level fixture fields excluded from input_sha256 (metadata / derived / self-ref).
FIXTURE_HASH_EXCLUDE_TOP: frozenset[str] = frozenset(
    {"input_sha256", "source_commit", "built_at", "digests"}
)

# Prepared fields excluded from hash — runtime diagnostics or derived from hashed fields.
PREPARED_HASH_EXCLUDE: frozenset[str] = frozenset(
    {
        "accounting",
        "chunk_map",
        "ask_relative_payload_stats",
        "ask_relative_user_message",
        "narrator_system",
    }
)

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


def canonical_json_normalize(value: Any) -> Any:
    """Recursively normalize to JSON-native types (tuples → lists, stable dict keys)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): canonical_json_normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical_json_normalize(v) for v in value]
    return str(value)


def canonical_json_dumps(value: Any) -> str:
    """Deterministic JSON bytes for hashing: sorted keys, compact separators, UTF-8."""
    normalized = canonical_json_normalize(value)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fixture_document_for_hash(fixture_doc: dict[str, Any]) -> dict[str, Any]:
    """Model-independent historian input identity — excludes metadata and volatile fields."""
    prepared_raw = fixture_doc.get("prepared")
    prepared: dict[str, Any] = {}
    if isinstance(prepared_raw, dict):
        prepared = {
            k: v for k, v in prepared_raw.items() if k not in PREPARED_HASH_EXCLUDE
        }
    return {
        "fixture_version": fixture_doc.get("fixture_version"),
        "case_id": fixture_doc.get("case_id"),
        "ask": fixture_doc.get("ask"),
        "prepared": prepared,
    }


def historian_input_sha256(fixture_doc: dict[str, Any]) -> str:
    """Single canonical input_sha256 for builder, manifest, loader, and replay runner.

    Hashes only model-independent prepared historian input. Never includes
    input_sha256, source_commit, built_at, digests, or volatile prepared diagnostics.
    Applies JSON round-trip normalization so on-disk fixtures match in-memory hash.
    """
    payload = fixture_document_for_hash(fixture_doc)
    roundtripped = json.loads(canonical_json_dumps(payload))
    digest_input = canonical_json_dumps(roundtripped)
    return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()


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
        "narrator_system": None,
    }


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


# Back-compat aliases (deprecated — use historian_input_sha256).
def input_hash_payload(fixture_body: dict[str, Any]) -> dict[str, Any]:
    return fixture_document_for_hash(fixture_body)


def sha256_input(payload: dict[str, Any]) -> str:
    return historian_input_sha256(payload)
