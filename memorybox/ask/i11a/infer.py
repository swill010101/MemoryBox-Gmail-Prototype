"""Provider-neutral I11A inference: observations → IR → Ask-relative view → validate."""
from __future__ import annotations

import json
import os
import time
from typing import Any

from memorybox.ask.i11a import needs_semantic_inference, resolve_request_context
from memorybox.ask.i11a.ir import ir_from_observations
from memorybox.ask.i11a.observations import (
    extract_observations,
    merge_model_observations,
    observation_from_unit,
    requires_model_interpretation,
)
from memorybox.ask.i11a.person_context import build_person_context, slim_person_context_for_model
from memorybox.ask.i11a.reason import (
    ASK_RELATIVE_SYSTEM,
    apply_correlations_to_ir,
    ask_relative_schema_ok,
    ask_relative_semantic_ok,
    eligible_observations,
    reason_payload,
    view_from_model_json,
)
from memorybox.ask.i11a.person_ir import higher_order_from_rollups
from memorybox.ask.i11a.rollup import roll_up_observations
from memorybox.ask.i11a.support import rank_episodes_for_narrator
from memorybox.ask.i11a.units import ask_kind_for_plan, compact_units_for_model, units_from_pack
from memorybox.ask.i11a.validate import parse_inference_json, validate_inference, validate_observations
from memorybox.ask.i11a.comm_compact import (
    chunk_units_semantically,
    filter_extract_observations,
    unit_evidence_ids,
    unit_for_extract_model,
)
from memorybox.ask.i11a.observation_cache import (
    load_episode_observations,
    save_episode_observations,
    source_hash,
    unit_source_hash,
)
from memorybox.providers.base import ProviderError, ProviderUnavailable
from memorybox.providers.llm.dto import ChatMessage

STAGE_ASK = "ask"
STAGE_ENRICH = "enrich"

OBSERVATION_EXTRACT = """OBSERVATION_EXTRACT
You extract Ask-independent grounded semantic observations. Return JSON only.
Answer: what does this evidence actually establish?
Do not create a trip, Person portrait, period narrative, holiday story, or relationship essay.
Do not use the user's question. These observations must be reusable across future Asks.

Emit objects with: kind, text, claim_type, people, places, time,
supporting_evidence_ids copied exactly from the supplied units' evidence_id /
extra_ids / source_evidence_ids / messages[].evidence_id.
Do not invent observation IDs or evidence IDs.

Kinds (canonical only): person_at_place_time, calendar_records_event,
communication_states, travel_document_records, repeated_communication_pattern,
people_interacting, activity_named, place_referenced, relationship_stated,
media_observation.

When a unit includes messages[], each object is one authored message with
sender / sender_person_id / from_owner, recipients, conversation, time, text,
and evidence_id. Attribute “X said …” only to that message’s sender. Do not
treat the conversation as unattributed text.

Communications must state meaning, not transport:
Bad: "A sent a message." "A thread exists." "Mail was exchanged."
Good: restated only using names, places, dates, and activities that appear in
the supplied message text (copy those words; do not substitute a different topic).
If the messages mention a medical appointment, the observation may mention that
appointment — not an unrelated hobby, event, or group.
Do not infer personality or character from message volume or tone.

person_at_place_time is only valid when the evidence explicitly states presence
(for example "I'm at", "we are in", "arrived in"). Mentioning a place in an email
is place_referenced or communication_states, not presence.

Rules:
- Do not invent people, places, dates, motives, topics, or emotions.
- Never invent IDs. Copy supporting_evidence_ids from the supplied units only.
- An observation is invalid if it names a topic, entity, or activity that is
  not present in its supporting authored message text.
- GPS/reverse-geocode city is presence at capture, not residence.
- Calendar listing is scheduled/recorded, not occurrence.
- Itinerary/reservation is not completed travel.
- Relationship labels only if the evidence states them; kin labels are validated later against the graph.
- Return {"observations": [...]} with no coverage counts.
"""


def _batch_chars() -> int:
    raw = (os.environ.get("MEMORYBOX_I11A_BATCH_CHARS") or "").strip()
    if raw.isdigit() and int(raw) > 500:
        return int(raw)
    return 12_000


def _retries() -> int:
    raw = (os.environ.get("MEMORYBOX_I11A_BATCH_RETRIES") or "").strip()
    if raw.isdigit():
        return max(0, min(5, int(raw)))
    return 1


def _chunk_units(units: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    return chunk_units_semantically(units, budget=_batch_chars())


def _trace_span(**kwargs: Any) -> None:
    try:
        from memorybox.ai_trace import context as ai_ctx
        from memorybox.ai_trace import store

        tid = ai_ctx.current_trace_id()
        if not tid:
            return
        store.insert_span(trace_id=tid, **kwargs)
    except Exception:  # noqa: BLE001
        return


def _chat_json(llm: Any, system: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if llm is None:
        raise ProviderUnavailable("No language model is configured.")
    messages = [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=json.dumps(payload, default=str)),
    ]
    result = llm.chat(messages, json_mode=True)
    usage = dict(getattr(result, "usage", None) or {})
    usage.setdefault("provider_key", getattr(llm, "provider_key", None))
    usage.setdefault(
        "model",
        getattr(result, "model", None)
        or getattr(llm, "chat_model", None)
        or getattr(llm, "model", None),
    )
    return str(getattr(result, "content", "") or ""), usage


def _call_with_retry_meta(
    llm: Any, system: str, payload: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    last: Exception | None = None
    attempts = 1 + _retries()
    for i in range(attempts):
        try:
            text, usage = _chat_json(llm, system, payload)
            if text.strip():
                return text, {
                    **usage,
                    "attempts": i + 1,
                    "retries": i,
                    "timeout_retried": False,
                }
            last = ProviderError("empty inference response")
        except ProviderUnavailable:
            raise
        except (ProviderError, Exception) as exc:  # noqa: BLE001
            last = exc
            if i + 1 < attempts:
                time.sleep(0.05 * (i + 1))
                continue
            raise last
    raise last or ProviderError("inference failed")


def _call_with_retry(llm: Any, system: str, payload: dict[str, Any]) -> str:
    text, _usage = _call_with_retry_meta(llm, system, payload)
    return text


def _unit_for_model(unit: dict[str, Any]) -> dict[str, Any]:
    return unit_for_extract_model(unit)


def _obs_payload(chunk: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "units": [_unit_for_model(u) for u in chunk],
        "note": "Ask-independent. Do not invent a trip, Person portrait, or period story.",
    }


def classify_llm_error(exc: BaseException) -> str:
    msg = str(exc).lower()
    if "timed out" in msg or "timeout" in msg:
        return "PROVIDER_TIMEOUT"
    if isinstance(exc, ProviderUnavailable):
        return "PROVIDER_TRANSPORT"
    if isinstance(exc, ProviderError):
        return "PARSE_SCHEMA" if "parse" in msg or "json" in msg else "MODEL_OUTPUT"
    return "MODEL_OUTPUT"


def _configured_chat_timeout() -> int | None:
    try:
        from memorybox.providers.llm.ollama import ollama_chat_timeout_seconds

        return ollama_chat_timeout_seconds()
    except Exception:  # noqa: BLE001
        raw = (os.environ.get("MEMORYBOX_OLLAMA_CHAT_TIMEOUT") or "").strip()
        if raw.isdigit() and int(raw) >= 600:
            return int(raw)
        return 600


def _payload_stats(system: str, payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps({"system": system, "user": payload}, default=str)
    n = len(raw)
    obs = payload.get("observations") if isinstance(payload.get("observations"), list) else []
    stubs = (
        payload.get("observation_stubs")
        if isinstance(payload.get("observation_stubs"), list)
        else []
    )
    hos = payload.get("higher_order") if isinstance(payload.get("higher_order"), list) else []
    rollups = payload.get("rollups") if isinstance(payload.get("rollups"), list) else []
    ru_stubs = (
        payload.get("rollup_stubs") if isinstance(payload.get("rollup_stubs"), list) else []
    )
    obs_sent = len(obs) + len(stubs)
    ru_sent = len(rollups) + len(ru_stubs)
    return {
        "observation_n": obs_sent,
        "validated_observation_total": payload.get("validated_observation_total")
        or payload.get("validated_observation_count"),
        "rollup_total": payload.get("rollup_total") or payload.get("rollup_unit_count") or 0,
        "higher_order_unit_total": payload.get("higher_order_unit_total") or len(hos),
        "higher_order_units_sent": payload.get("higher_order_units_sent") or len(hos),
        "rollups_sent_to_ask_relative": ru_sent,
        "observations_sent_to_ask_relative": obs_sent,
        "lower_level_rollups_expanded": payload.get("lower_level_rollups_expanded") or 0,
        "rollup_n": ru_sent,
        "higher_order_n": len(hos),
        "payload_bytes": n,
        "approx_tokens": max(1, n // 4),
        "timeout_seconds": _configured_chat_timeout(),
        "num_ctx": None,
        "num_ctx_note": "Ollama chat options set temperature only; num_ctx is the model default",
        "compact_observations": obs_sent == 0,
        "compact_rollups": ru_sent == 0,
        "compact_higher_order": bool(hos),
        "includes_full_evidence_id_arrays": False,
        "includes_excerpts": False,
        "includes_observation_objects": obs_sent > 0,
        "default_ir": "higher_order_person",
    }


def _mark_trace_error(error_class: str, *, reason: str) -> None:
    try:
        from memorybox.ai_trace import context as ai_ctx
        from memorybox.ai_trace import store

        tid = ai_ctx.current_trace_id()
        if tid:
            store.update_trace(tid, status="error", error_class=error_class)
    except Exception:  # noqa: BLE001
        return


def _fail(
    *,
    reason: str,
    person_context: dict[str, Any],
    req: dict[str, Any],
    accounting: dict[str, Any],
    rejected: list[Any] | None = None,
    error_class: str = "PARSE_SCHEMA",
    stage: str = "i11a_validate",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "ok": False,
        "fail_closed": True,
        "reason": reason,
        "error_class": error_class,
        "document": None,
        "rejected": rejected or [],
        "person_context": slim_person_context_for_model(person_context)
        if reason == "no evidence units"
        else person_context,
        "request_context": req,
        "accounting": accounting,
        "partial": False,
        "enrichment_complete": accounting.get("enrichment_complete"),
        "stage_timings": None,
    }
    try:
        from memorybox.ask import stage_clock

        result["stage_timings"] = stage_clock.snapshot()
    except Exception:  # noqa: BLE001
        pass
    assembled = {
        "ok": False,
        "reason": reason,
        "partial": False,
        "document": None,
        "rejected": result["rejected"],
        "accounting": accounting,
        "fail_closed": True,
        "error_class": error_class,
        "person_context": slim_person_context_for_model(person_context),
        "request_context": req,
    }
    if extra:
        assembled.update(extra)
        result.update({k: v for k, v in extra.items() if k not in result})
    _trace_span(
        stage=stage,
        component="i11a",
        operation="fail_closed",
        status="error",
        error_class=error_class,
        assembled_context=assembled,
    )
    _mark_trace_error(error_class, reason=reason)
    return result


def run_inference(
    plan: Any,
    pack: dict[str, Any],
    llm: Any,
    *,
    modality_state: dict[str, Any] | None = None,
    stage: str = STAGE_ASK,
) -> dict[str, Any]:
    """Observations → IR → Ask-relative view. Heuristic episodes are never product truth.

    stage=ask never calls OBSERVATION_EXTRACT; it reuses persisted fingerprints.
    stage=enrich runs Ask-independent extract + persist and stops before Ask-relative.
    """
    t0 = time.perf_counter()
    stage = STAGE_ENRICH if str(stage or "").strip().lower() == STAGE_ENRICH else STAGE_ASK
    allow_llm_extract = stage == STAGE_ENRICH
    from memorybox.ask import stage_clock

    with stage_clock.timed("person_resolution_ms"):
        person_context = build_person_context(plan)
        req = resolve_request_context(plan)
    kind_hint = ask_kind_for_plan(plan)
    from memorybox.ask.i11a.preaggregate import preaggregate_pack

    units = units_from_pack(pack)
    focal_id = None
    focals = req.get("focal_subject_person_ids") or []
    if focals:
        focal_id = str(focals[0])
    with stage_clock.timed("preaggregation_ms"):
        agg = preaggregate_pack(pack, person_id=focal_id)
    pack["preaggregation"] = agg.get("trace") or {}
    pack["inference_units"] = agg.get("units") or []
    agg_units = list(agg.get("units") or units)
    a_units = [u for u in agg_units if not requires_model_interpretation(u)]
    b_units = [u for u in agg_units if requires_model_interpretation(u)]
    model_units = compact_units_for_model(b_units)
    pack["preaggregation"]["inference_units_after_compact"] = len(agg_units)
    pack["preaggregation"]["deterministic_units"] = len(a_units)
    pack["preaggregation"]["extract_units"] = len(model_units)
    chunks = _chunk_units(model_units)
    _trace_span(
        stage="i11a_inference",
        component="i11a",
        operation="preaggregation",
        status="ok",
        assembled_context=pack.get("preaggregation"),
        parsed=pack.get("preaggregation"),
    )
    chunk_map: dict[str, int] = {}
    for i, ch in enumerate(chunks):
        for u in ch:
            for key in (u.get("unit_id"), u.get("evidence_id"), u.get("asset_ref")):
                s = str(key or "").strip()
                if s:
                    chunk_map[s] = i
            for extra in u.get("extra_ids") or []:
                s = str(extra or "").strip()
                if s:
                    chunk_map[s] = i
    accounting = {
        "eligible_units": len(units),
        "chunk_n": len(chunks),
        "attempted_units": 0,
        "successful_units": 0,
        "failed_units": 0,
        "retries": _retries(),
        "merge_depth": 0,
        "units_generated": len(units),
        "units_passed_to_inference": len(model_units),
        "units_deterministic": len(a_units),
        "units_model_extract": len(model_units),
        "dropped_before_inference": max(0, len(units) - len(agg_units)),
        "extract_calls": 0,
        "leaf_calls": 0,
        "ask_relative_calls": 0,
        "observations_a": 0,
        "observations_b": 0,
        "extract_observations_rejected": 0,
        "extract_timeouts": 0,
        "extract_payloads": [],
        "extract_chunks": len(chunks),
        "extract_cache_hits": 0,
        "extract_cache_misses": 0,
        "persisted_observations": 0,
        "enrichment_deferred": 0,
        "inference_stage": stage,
        "raw_eligible": (pack.get("preaggregation") or {}).get("raw_eligible"),
        "raw_comm_items": (pack.get("preaggregation") or {}).get("raw_comm_items"),
        "email_thread_units": (pack.get("preaggregation") or {}).get("email_thread_units"),
        "sms_segment_units": (pack.get("preaggregation") or {}).get("sms_segment_units"),
        "sms_raw": (pack.get("preaggregation") or {}).get("sms_raw"),
        "sms_windows": (pack.get("preaggregation") or {}).get("sms_windows"),
        "semantic_comm_units_after_dedupe": (pack.get("preaggregation") or {}).get(
            "semantic_comm_units_after_dedupe"
        ),
        "provenance_coverage": (pack.get("preaggregation") or {}).get("provenance_coverage"),
        "provenance_ids_raw_comm": (pack.get("preaggregation") or {}).get("provenance_ids_raw_comm"),
        "provenance_ids_retained": (pack.get("preaggregation") or {}).get("provenance_ids_retained"),
        "preaggregation_units": len(agg_units),
        "preaggregation": pack.get("preaggregation"),
        "eligible_evidence_id_digest": (pack.get("preaggregation") or {}).get(
            "eligible_evidence_id_digest"
        ),
        "eligible_evidence_id_n": (pack.get("preaggregation") or {}).get("eligible_evidence_id_n"),
        "semantic_unit_fingerprint_digest": (pack.get("preaggregation") or {}).get(
            "semantic_unit_fingerprint_digest"
        ),
        "semantic_unit_fingerprint_n": (pack.get("preaggregation") or {}).get(
            "semantic_unit_fingerprint_n"
        ),
        "distinct_raw_evidence_items": (pack.get("preaggregation") or {}).get(
            "distinct_raw_evidence_items"
        ),
        "distinct_sms_messages": (pack.get("preaggregation") or {}).get("distinct_sms_messages"),
        "sms_provenance_id_n": (pack.get("preaggregation") or {}).get("sms_provenance_id_n"),
        "eligible_provenance_id_n": (pack.get("preaggregation") or {}).get("eligible_provenance_id_n"),
        "eligible_representation_id_n": (pack.get("preaggregation") or {}).get(
            "eligible_representation_id_n"
        ),
        "count_labels": (pack.get("preaggregation") or {}).get("count_labels"),
        "engine": "observations_ir_ask_relative",
        "units_total": len(model_units),
        "units_complete": 0,
        "units_deferred": 0,
        "enrichment_complete": True,
        "deferred_unit_fingerprints": [],
    }
    if not units:
        return _fail(
            reason="no evidence units",
            person_context=person_context,
            req=req,
            accounting=accounting,
        )

    deterministic = extract_observations(a_units, person_id=focal_id)
    accounting["observations_a"] = len(deterministic)
    model_obs: list[dict[str, Any]] = []
    failed_chunks = 0
    for idx, chunk in enumerate(chunks):
        accounting["attempted_units"] += len(chunk)
        cached_rows: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []
        for unit in chunk:
            with stage_clock.timed("observation_cache_lookup_ms"):
                hit = load_episode_observations(unit)
            if hit is not None:
                cached_rows.extend(hit)
                accounting["extract_cache_hits"] = int(accounting.get("extract_cache_hits") or 0) + 1
            else:
                pending.append(unit)
                accounting["extract_cache_misses"] = int(accounting.get("extract_cache_misses") or 0) + 1
        if cached_rows:
            model_obs.extend(cached_rows)
        if not pending:
            accounting["successful_units"] += len(chunk)
            _trace_span(
                stage="i11a_inference",
                component="i11a",
                operation="observation_extract",
                status="ok",
                assembled_context={
                    "chunk": idx,
                    "unit_n": len(chunk),
                    "cache_hit": True,
                    "observation_n": len(cached_rows),
                },
                parsed={"observations": cached_rows, "rejected": [], "cache_hit": True},
            )
            continue
        if not allow_llm_extract:
            accounting["enrichment_deferred"] = int(accounting.get("enrichment_deferred") or 0) + len(
                pending
            )
            accounting["units_deferred"] = int(accounting.get("units_deferred") or 0) + len(pending)
            fps = accounting.setdefault("deferred_unit_fingerprints", [])
            for unit in pending:
                fp = unit_source_hash(unit)
                if fp and fp not in fps:
                    fps.append(fp)
            accounting["successful_units"] += len(chunk) - len(pending)
            _trace_span(
                stage="i11a_inference",
                component="i11a",
                operation="observation_extract",
                status="ok",
                assembled_context={
                    "chunk": idx,
                    "unit_n": len(chunk),
                    "cache_hit": bool(cached_rows),
                    "deferred": len(pending),
                    "ask_reuses_persisted_only": True,
                },
                parsed={"observations": cached_rows, "rejected": [], "deferred": True},
            )
            continue
        accounting["leaf_calls"] += 1
        accounting["extract_calls"] += 1
        payload = _obs_payload(pending)
        extract_stats = _payload_stats(OBSERVATION_EXTRACT, payload)
        extract_stats["chunk"] = idx
        extract_stats["unit_n"] = len(pending)
        extract_stats["message_n"] = sum(
            len(u.get("messages") or []) if isinstance(u.get("messages"), list) else 0
            for u in pending
        )
        accounting.setdefault("extract_payloads", []).append(extract_stats)
        try:
            raw = _call_with_retry(llm, OBSERVATION_EXTRACT, payload)
            parsed = parse_inference_json(raw) or {}
            rows = parsed.get("observations") if isinstance(parsed.get("observations"), list) else []
            if not rows and parsed.get("episodes"):
                for ep in parsed.get("episodes") or []:
                    if isinstance(ep, dict):
                        rows.append(
                            {
                                "kind": "activity_named",
                                "text": ep.get("label") or "",
                                "claim_type": "observed",
                                "supporting_evidence_ids": ep.get("supporting_evidence_ids") or [],
                                "people": ep.get("people") or [],
                                "places": ep.get("places") or [],
                                "time": (ep.get("date_span") or {}).get("start"),
                            }
                        )
            kept, rej = filter_extract_observations(rows, pending)
            model_obs.extend(kept)
            accounting["extract_observations_rejected"] = int(
                accounting.get("extract_observations_rejected") or 0
            ) + len(rej)
            accounting["successful_units"] += len(pending)
            model_name = getattr(llm, "chat_model", None) or getattr(llm, "model", None)
            for unit in pending:
                uids = set(unit_evidence_ids(unit))
                subset = [
                    obs
                    for obs in kept
                    if set(str(x) for x in (obs.get("supporting_evidence_ids") or [])) & uids
                ]
                save_episode_observations(unit, subset, model=str(model_name) if model_name else None)
                accounting["persisted_observations"] = int(
                    accounting.get("persisted_observations") or 0
                ) + len(subset)
            _trace_span(
                stage="i11a_inference",
                component="i11a",
                operation="observation_extract",
                status="ok",
                assembled_context={"chunk": idx, "unit_n": len(pending), "cache_hit": False},
                provider_payload={"system": OBSERVATION_EXTRACT, "user": payload},
                raw_response={"content": raw},
                parsed={"observations": kept, "rejected": rej},
            )
        except Exception as exc:  # noqa: BLE001
            failed_chunks += 1
            accounting["failed_units"] += len(pending)
            klass = classify_llm_error(exc)
            if klass == "PROVIDER_TIMEOUT":
                accounting["extract_timeouts"] = int(accounting.get("extract_timeouts") or 0) + 1
            fps = accounting.setdefault("deferred_unit_fingerprints", [])
            for unit in pending:
                fp = unit_source_hash(unit)
                if fp and fp not in fps:
                    fps.append(fp)
            accounting["units_deferred"] = int(accounting.get("units_deferred") or 0) + len(pending)
            extract_stats["error_class"] = klass
            _trace_span(
                stage="i11a_inference",
                component="i11a",
                operation="observation_extract",
                status="error",
                error_class=klass,
                assembled_context={"chunk": idx, "unit_n": len(pending), **extract_stats},
                error={"message": str(exc), "error_class": klass},
            )
            # Persist successful episodes already stored; skip this episode and continue
            # so a later Ask can reuse cache hits without repeating finished work.

    accounting["units_total"] = len(model_units)
    accounting["units_complete"] = int(accounting.get("successful_units") or 0)
    accounting["units_deferred"] = int(accounting.get("units_deferred") or 0)
    accounting["enrichment_complete"] = int(accounting.get("units_deferred") or 0) == 0
    if accounting.get("deferred_unit_fingerprints"):
        accounting["deferred_unit_fingerprints"] = list(accounting["deferred_unit_fingerprints"])[:80]

    accounting["observations_b"] = len(model_obs)
    with stage_clock.timed("observation_hydration_ms"):
        merged = merge_model_observations(deterministic, model_obs)
        if not merged:
            if stage == STAGE_ENRICH and int(accounting.get("extract_timeouts") or 0) > 0:
                return _fail(
                    reason="observation extract timed out after retry",
                    person_context=person_context,
                    req=req,
                    accounting=accounting,
                    error_class="PROVIDER_TIMEOUT",
                    stage="i11a_inference",
                )
            merged = [observation_from_unit(u) for u in (agg.get("units") or units)]
            merged = [o for o in merged if o]
    with stage_clock.timed("provenance_validation_ms"):
        validated_obs = validate_observations(
            merged, pack=pack, person_context=person_context
        )
    observations = validated_obs.get("observations") or []
    pack["semantic_observations"] = observations
    with stage_clock.timed("rollup_ms"):
        rolled = roll_up_observations(observations)
        ho_all = higher_order_from_rollups(rolled)
    pack["semantic_rollups"] = rolled.get("rollups") or []
    pack["semantic_higher_order"] = ho_all.get("units") or []
    accounting["validated_observations"] = len(observations)
    accounting["rollup_units"] = int(rolled.get("rollup_unit_count") or 0)
    accounting["rollup_provenance_coverage"] = rolled.get("provenance_coverage")
    accounting["higher_order_unit_total"] = int(ho_all.get("higher_order_unit_total") or 0)
    accounting["higher_order_provenance_coverage"] = ho_all.get("provenance_coverage")
    oids = sorted(str(o.get("observation_id") or "") for o in observations if o.get("observation_id"))
    accounting["validated_observation_digest"] = source_hash(oids) if oids else ""
    _trace_span(
        stage="i11a_inference",
        component="i11a",
        operation="semantic_observations",
        status="ok" if observations else "error",
        parsed={"observations": observations, "rejected": validated_obs.get("rejected")},
        validation={"rejected": validated_obs.get("rejected"), "ok": validated_obs.get("ok")},
    )
    if not observations:
        return _fail(
            reason="no grounded observations",
            person_context=person_context,
            req=req,
            accounting=accounting,
            rejected=validated_obs.get("rejected") or [],
        )

    ir = ir_from_observations(observations)
    pack["semantic_ir"] = ir
    _trace_span(
        stage="i11a_inference",
        component="i11a",
        operation="semantic_ir",
        status="ok",
        parsed=ir,
    )
    _trace_span(
        stage="i11a_inference",
        component="i11a",
        operation="semantic_rollup",
        status="ok",
        parsed={
            "validated_observations": accounting.get("validated_observations"),
            "rollup_units": accounting.get("rollup_units"),
            "provenance_coverage": accounting.get("rollup_provenance_coverage"),
            "claim_type": "derived",
            "not_family_fact": True,
        },
    )
    if stage == STAGE_ENRICH:
        complete = bool(accounting.get("enrichment_complete"))
        klass = None
        if not complete and int(accounting.get("extract_timeouts") or 0) > 0:
            klass = "PROVIDER_TIMEOUT"
        try:
            from memorybox.ai_trace import context as ai_ctx
            from memorybox.ai_trace import store

            tid = ai_ctx.current_trace_id()
            if tid:
                store.update_trace(
                    tid,
                    status="ok" if complete else "partial",
                    error_class=klass,
                )
        except Exception:  # noqa: BLE001
            pass
        return {
            "ok": True,
            "fail_closed": False,
            "partial": (not complete) or failed_chunks > 0,
            "enrichment_complete": complete,
            "reason": None if complete else "partial observation enrichment; deferred units remain",
            "error_class": klass,
            "document": None,
            "rejected": validated_obs.get("rejected") or [],
            "person_context": person_context,
            "request_context": req,
            "accounting": accounting,
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            "chunk_map": chunk_map,
            "observations": observations,
            "semantic_ir": ir,
            "semantic_rollups": rolled,
            "semantic_higher_order": ho_all,
            "ask_relative_view": None,
            "stage": STAGE_ENRICH,
            "stage_timings": stage_clock.snapshot(),
        }

    eligible = eligible_observations(
        observations, plan=plan, request_context=req
    )
    with stage_clock.timed("rollup_ms"):
        rolled_eligible = roll_up_observations(eligible)
        ho_eligible = higher_order_from_rollups(rolled_eligible)
    pack["semantic_rollups"] = rolled_eligible.get("rollups") or []
    pack["semantic_higher_order"] = ho_eligible.get("units") or []
    accounting["validated_observations"] = len(eligible)
    accounting["rollup_units"] = int(rolled_eligible.get("rollup_unit_count") or 0)
    accounting["rollup_provenance_coverage"] = rolled_eligible.get("provenance_coverage")
    accounting["higher_order_unit_total"] = int(ho_eligible.get("higher_order_unit_total") or 0)
    accounting["higher_order_provenance_coverage"] = ho_eligible.get("provenance_coverage")
    ask = str(getattr(plan, "original_ask", "") or "")
    with stage_clock.timed("ask_relative_prep_ms"):
        rp = reason_payload(
            plan=plan,
            observations=eligible,
            request_context=req,
            person_context=slim_person_context_for_model(person_context),
            ask_kind_hint=kind_hint,
            rollups=rolled_eligible.get("rollups") or [],
            higher_order=ho_eligible,
        )
        stats = _payload_stats(ASK_RELATIVE_SYSTEM, rp)
        accounting["ask_relative_payload"] = stats
        accounting["validated_observation_total"] = stats.get("validated_observation_total")
        accounting["rollup_total"] = stats.get("rollup_total")
        accounting["higher_order_units_sent"] = stats.get("higher_order_units_sent")
        accounting["rollups_sent_to_ask_relative"] = stats.get(
            "rollups_sent_to_ask_relative"
        )
        accounting["observations_sent_to_ask_relative"] = stats.get(
            "observations_sent_to_ask_relative"
        )
        _trace_span(
            stage="ask_relative_reasoning",
            component="i11a",
            operation="ask_relative_payload",
            status="ok",
            assembled_context=stats,
            parsed=stats,
        )
    parsed_view = None
    t_prov = time.perf_counter()
    try:
        accounting["ask_relative_calls"] = 1
        accounting["leaf_calls"] += 1
        raw_view, call_meta = _call_with_retry_meta(llm, ASK_RELATIVE_SYSTEM, rp)
        stage_clock.add("ask_relative_provider_ms", int((time.perf_counter() - t_prov) * 1000))
        stats = {
            **stats,
            "provider_eval": {
                k: call_meta.get(k)
                for k in (
                    "total_duration",
                    "load_duration",
                    "prompt_eval_count",
                    "prompt_eval_duration",
                    "eval_count",
                    "eval_duration",
                    "attempts",
                    "retries",
                    "timeout_retried",
                    "keep_alive",
                    "done_reason",
                    "num_ctx",
                    "num_ctx_note",
                    "options",
                    "timeout_seconds",
                    "model",
                    "provider_key",
                )
                if call_meta.get(k) is not None or k in {"attempts", "retries", "timeout_retried"}
            },
        }
        if call_meta.get("prompt_eval_count") is not None:
            stats["prompt_tokens"] = call_meta.get("prompt_eval_count")
        if call_meta.get("eval_count") is not None:
            stats["response_tokens"] = call_meta.get("eval_count")
        if call_meta.get("num_ctx") is not None:
            stats["num_ctx"] = call_meta.get("num_ctx")
        if call_meta.get("num_ctx_note"):
            stats["num_ctx_note"] = call_meta.get("num_ctx_note")
        accounting["ask_relative_payload"] = stats
        with stage_clock.timed("result_validation_ms"):
            parsed_view = parse_inference_json(raw_view)
            if parsed_view is None:
                schema_ok, schema_reason = False, "ask-relative output is not valid JSON"
                sem_ok, sem_reason = False, schema_reason
            else:
                schema_ok, schema_reason = ask_relative_schema_ok(parsed_view)
                if schema_ok:
                    sem_ok, sem_reason = ask_relative_semantic_ok(
                        parsed_view,
                        rollups=rolled_eligible,
                        observations=eligible,
                        higher_order=ho_eligible,
                    )
                else:
                    sem_ok, sem_reason = False, schema_reason
        elapsed_ms = int((time.perf_counter() - t_prov) * 1000)
        valid = bool(schema_ok and sem_ok)
        fail_reason = schema_reason if not schema_ok else sem_reason
        _trace_span(
            stage="ask_relative_reasoning",
            component="i11a",
            operation="ask_relative",
            status="ok" if valid else "error",
            error_class=None if valid else "MODEL_OUTPUT",
            duration_ms=elapsed_ms,
            provider_payload={"system": ASK_RELATIVE_SYSTEM, "user": rp},
            raw_response={"content": raw_view},
            parsed=parsed_view,
            assembled_context={
                **stats,
                "schema_ok": schema_ok,
                "schema_reason": None if schema_ok else schema_reason,
                "semantic_ok": sem_ok,
                "semantic_reason": None if sem_ok else sem_reason,
                "retry_count": int((stats.get("provider_eval") or {}).get("retries") or 0),
                "timeout_retried": False,
                "provider_key": getattr(llm, "provider_key", None),
                "model": getattr(llm, "chat_model", None) or getattr(llm, "model", None),
            },
        )
        if not valid:
            extra = {
                "stage": "ask-relative reasoning",
                "schema_reason": schema_reason if not schema_ok else None,
                "semantic_reason": sem_reason if schema_ok and not sem_ok else None,
                "ask_relative_payload": stats,
                "raw_ask_relative": (raw_view or "")[:4000],
            }
            return _fail(
                reason=fail_reason or "ask-relative validation failed",
                person_context=person_context,
                req=req,
                accounting=accounting,
                error_class="MODEL_OUTPUT",
                stage="ask_relative_reasoning",
                extra=extra,
            )
    except ProviderUnavailable as exc:
        klass = classify_llm_error(exc)
        elapsed_ms = int((time.perf_counter() - t_prov) * 1000)
        stage_clock.add("ask_relative_provider_ms", elapsed_ms)
        timeout_s = stats.get("timeout_seconds")
        if klass == "PROVIDER_TIMEOUT":
            reason = (
                f"ask-relative reasoning timed out after {elapsed_ms}ms "
                f"(limit {timeout_s}s)"
            )
        else:
            reason = f"ask-relative reasoning unavailable: {exc}"
        extra = {
            "stage": "ask-relative reasoning",
            "provider_key": getattr(llm, "provider_key", None),
            "model": getattr(llm, "chat_model", None) or getattr(llm, "model", None),
            "timeout_seconds": timeout_s,
            "duration_ms": elapsed_ms,
            "retry_count": _retries(),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "ask_relative_payload": stats,
        }
        _trace_span(
            stage="ask_relative_reasoning",
            component="i11a",
            operation="ask_relative",
            status="error",
            error_class=klass,
            duration_ms=elapsed_ms,
            error=extra,
            assembled_context=extra,
            provider_payload={"system": ASK_RELATIVE_SYSTEM, "user": rp},
        )
        return _fail(
            reason=reason,
            person_context=person_context,
            req=req,
            accounting=accounting,
            error_class=klass,
            stage="ask_relative_reasoning",
            extra=extra,
        )
    except Exception as exc:  # noqa: BLE001
        klass = classify_llm_error(exc)
        elapsed_ms = int((time.perf_counter() - t_prov) * 1000)
        stage_clock.add("ask_relative_provider_ms", elapsed_ms)
        extra = {
            "stage": "ask-relative reasoning",
            "provider_key": getattr(llm, "provider_key", None),
            "model": getattr(llm, "chat_model", None) or getattr(llm, "model", None),
            "timeout_seconds": stats.get("timeout_seconds"),
            "duration_ms": elapsed_ms,
            "retry_count": _retries(),
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "ask_relative_payload": stats,
        }
        _trace_span(
            stage="ask_relative_reasoning",
            component="i11a",
            operation="ask_relative",
            status="error",
            error_class=klass,
            duration_ms=elapsed_ms,
            error=extra,
            assembled_context=extra,
            provider_payload={"system": ASK_RELATIVE_SYSTEM, "user": rp},
        )
        return _fail(
            reason=f"ask-relative reasoning failed: {exc}",
            person_context=person_context,
            req=req,
            accounting=accounting,
            error_class=klass,
            stage="ask_relative_reasoning",
            extra=extra,
        )

    view = view_from_model_json(
        parsed_view,
        eligible,
        ask=ask,
        ask_kind_hint=kind_hint,
        rollups=rolled_eligible,
        higher_order=ho_eligible,
        allow_fallback=False,
    )
    if not view.get("episodes"):
        return _fail(
            reason="ask-relative produced no grounded episodes",
            person_context=person_context,
            req=req,
            accounting=accounting,
            error_class="MODEL_OUTPUT",
            stage="ask_relative_reasoning",
            extra={
                "stage": "ask-relative reasoning",
                "semantic_reason": "no grounded episodes after ASK_RELATIVE expansion",
                "ask_relative_payload": stats,
            },
        )
    accounting["observations_expanded"] = len(view.get("selected_observation_ids") or [])
    accounting["lower_level_expansion_count"] = accounting["observations_expanded"]
    accounting["lower_level_rollups_expanded"] = int(
        view.get("lower_level_rollups_expanded") or 0
    )
    ir = apply_correlations_to_ir(ir, view)
    pack["semantic_ir"] = ir
    pack["ask_relative_view"] = view
    _trace_span(
        stage="i11a_inference",
        component="i11a",
        operation="ask_relative_view",
        status="ok",
        parsed=view,
    )

    with stage_clock.timed("result_validation_ms"):
        validated = validate_inference(view, pack=pack, person_context=person_context)
    incomplete = failed_chunks > 0
    fail_closed = not validated.get("ok")
    result = {
        "ok": bool(validated.get("ok")) and not fail_closed,
        "fail_closed": fail_closed,
        "partial": incomplete and not fail_closed,
        "reason": None if validated.get("ok") and not fail_closed else "validation failed",
        "error_class": "MODEL_OUTPUT" if fail_closed else None,
        "document": validated.get("document") if not fail_closed else None,
        "rejected": list(validated_obs.get("rejected") or []) + list(validated.get("rejected") or []),
        "person_context": person_context,
        "request_context": req,
        "accounting": accounting,
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        "chunk_map": chunk_map,
        "observations": observations,
        "semantic_ir": ir,
        "ask_relative_view": view,
        "semantic_rollups": rolled_eligible,
        "semantic_higher_order": ho_eligible,
        "stage": STAGE_ASK,
        "enrichment_complete": accounting.get("enrichment_complete"),
        "stage_timings": stage_clock.snapshot(),
    }
    _trace_span(
        stage="i11a_validate",
        component="i11a",
        operation="validate",
        status="ok" if result["ok"] else "error",
        parsed=validated.get("document"),
        validation={"rejected": result["rejected"], "ok": result["ok"]},
        assembled_context={
            "request_context": req,
            "accounting": accounting,
            "partial": result["partial"],
            "person_context": slim_person_context_for_model(person_context),
            "semantic_observations": observations,
            "semantic_ir": ir,
            "ask_relative_view": view,
        },
        disposition={"validated_semantic_pack": validated.get("document") if result["ok"] else None},
    )
    return result


def outline_from_inference(document: dict[str, Any], plan: Any) -> dict[str, Any]:
    episodes = []
    for ep in document.get("episodes") or []:
        claims = [c.get("text") for c in (ep.get("claims") or []) if isinstance(c, dict) and c.get("text")]
        people = []
        for p in ep.get("people") or []:
            if isinstance(p, dict):
                people.append(str(p.get("name") or p.get("person_id") or "").strip())
            else:
                people.append(str(p))
        people = [x for x in people if x]
        eids = list(ep.get("supporting_evidence_ids") or [])
        for c in ep.get("claims") or []:
            if isinstance(c, dict):
                eids.extend(str(x) for x in (c.get("supporting_evidence_ids") or []))
        eids = list(dict.fromkeys(eids))
        uncertainty: dict[str, Any] = {}
        for c in ep.get("claims") or []:
            if not isinstance(c, dict):
                continue
            if c.get("claim_type") == "recorded":
                uncertainty["occurrence_not_established_by_calendar_alone"] = True
            if c.get("claim_type") == "derived":
                uncertainty["travel_derived_from_communication"] = True
        row = {
            "theme_or_episode": ep.get("label") or "Untitled",
            "claims": claims,
            "evidence_ids": eids[:40],
            "date_span": ep.get("date_span") or {},
            "scheduled_window": ep.get("scheduled_window") or {"start": None, "end": None, "evidence_ids": []},
            "observed_window": ep.get("observed_window") or {"start": None, "end": None, "evidence_ids": []},
            "derived_window": ep.get("derived_window") or {"start": None, "end": None, "evidence_ids": []},
            "people": people[:12],
            "places": ep.get("places") or [],
            "significance": str(ep.get("why_relevant_to_ask") or "characterizes the period"),
            "exemplars": [],
            "provenance": {"grounded_in_evidence_ids": True, "not_family_truth": True},
            "candidate_visual_ids": ep.get("candidate_visual_ids") or [],
            "support_profile": ep.get("support_profile") or {},
            "support_score": ep.get("support_score"),
        }
        if uncertainty:
            row["uncertainty"] = uncertainty
        episodes.append(row)
    episodes = rank_episodes_for_narrator(episodes, budget=24)
    windows_raw = [tuple(w) for w in (getattr(plan, "temporal_windows", ()) or ()) if w]
    if not windows_raw:
        t0 = getattr(plan, "time_start", None)
        t1 = getattr(plan, "time_end", None)
        if t0 and t1:
            windows_raw = [(t0, t1)]
    from memorybox.ask.i11a.windows import pack_level_windows

    return {
        "period": str(getattr(plan, "temporal_label", None) or "this period"),
        "windows": [{"start": str(a)[:10], "end": str(b)[:10]} for a, b in windows_raw],
        "episodes": episodes,
        **pack_level_windows(episodes),
        "person_understanding": document.get("person_understanding"),
    }


def apply_inference_to_pack(
    plan: Any,
    pack: dict[str, Any],
    llm: Any,
    *,
    modality_state: dict[str, Any] | None = None,
    stage: str = STAGE_ASK,
) -> dict[str, Any]:
    if not needs_semantic_inference(plan):
        pack["inference"] = {"ok": False, "bypassed": True}
        pack["i11a_ab_metrics"] = {}
        return pack
    inf = run_inference(plan, pack, llm, modality_state=modality_state, stage=stage)
    acc = inf.get("accounting") if isinstance(inf.get("accounting"), dict) else {}
    pack["inference"] = {
        "ok": inf.get("ok"),
        "fail_closed": inf.get("fail_closed"),
        "partial": inf.get("partial"),
        "reason": inf.get("reason"),
        "accounting": inf.get("accounting"),
        "rejected": inf.get("rejected"),
        "request_context": inf.get("request_context"),
        "heuristic_not_product_truth": True,
        "error_class": inf.get("error_class"),
        "timeout_seconds": inf.get("timeout_seconds"),
        "duration_ms": inf.get("duration_ms"),
        "retry_count": inf.get("retry_count"),
        "stage": inf.get("stage") or stage,
        "schema_reason": inf.get("schema_reason"),
        "semantic_reason": inf.get("semantic_reason"),
        "enrichment_complete": inf.get("enrichment_complete"),
        "stage_timings": inf.get("stage_timings"),
    }
    pack["person_context"] = inf.get("person_context")
    pack["request_context"] = inf.get("request_context")
    pack["i11a_ab_metrics"] = {
        "raw_eligible": acc.get("raw_eligible"),
        "preaggregation_units": acc.get("preaggregation_units"),
        "a_deterministic_units": acc.get("units_deterministic"),
        "b_semantic_units": acc.get("units_model_extract"),
        "deterministic_observations": acc.get("observations_a"),
        "model_derived_observations": acc.get("observations_b"),
        "observation_extract_calls": acc.get("extract_calls"),
        "ask_relative_calls": acc.get("ask_relative_calls"),
        "extract_chunks": acc.get("extract_chunks"),
        "raw_comm_items": acc.get("raw_comm_items"),
        "email_thread_units": acc.get("email_thread_units"),
        "sms_segment_units": acc.get("sms_segment_units"),
        "semantic_comm_units_after_dedupe": acc.get("semantic_comm_units_after_dedupe"),
        "provenance_coverage": acc.get("provenance_coverage"),
        "provenance_ids_raw_comm": acc.get("provenance_ids_raw_comm"),
        "provenance_ids_retained": acc.get("provenance_ids_retained"),
        "extract_observations_rejected": acc.get("extract_observations_rejected"),
        "extract_timeouts": acc.get("extract_timeouts"),
        "extract_payloads": acc.get("extract_payloads"),
        "extract_cache_hits": acc.get("extract_cache_hits"),
        "extract_cache_misses": acc.get("extract_cache_misses"),
        "persisted_observations": acc.get("persisted_observations"),
        "ask_relative_payload": acc.get("ask_relative_payload"),
        "validated_observations": acc.get("validated_observations"),
        "rollup_units": acc.get("rollup_units"),
        "rollup_provenance_coverage": acc.get("rollup_provenance_coverage"),
        "higher_order_unit_total": acc.get("higher_order_unit_total"),
        "higher_order_units_sent": acc.get("higher_order_units_sent"),
        "higher_order_provenance_coverage": acc.get("higher_order_provenance_coverage"),
        "lower_level_rollups_expanded": acc.get("lower_level_rollups_expanded"),
        "observations_expanded": acc.get("observations_expanded"),
        "lower_level_expansion_count": acc.get("lower_level_expansion_count"),
        "validated_observation_total": acc.get("validated_observation_total"),
        "rollup_total": acc.get("rollup_total"),
        "rollups_sent_to_ask_relative": acc.get("rollups_sent_to_ask_relative"),
        "observations_sent_to_ask_relative": acc.get("observations_sent_to_ask_relative"),
        "enrichment_deferred": acc.get("enrichment_deferred"),
        "inference_stage": acc.get("inference_stage") or stage,
        "sms_raw": acc.get("sms_raw") or (pack.get("preaggregation") or {}).get("sms_raw"),
        "sms_windows": (pack.get("preaggregation") or {}).get("sms_windows"),
        "sms_episode_units": acc.get("sms_segment_units")
        or (pack.get("preaggregation") or {}).get("sms_episode_units"),
        "eligible_evidence_id_digest": acc.get("eligible_evidence_id_digest")
        or (pack.get("preaggregation") or {}).get("eligible_evidence_id_digest"),
        "eligible_evidence_id_n": acc.get("eligible_evidence_id_n")
        or (pack.get("preaggregation") or {}).get("eligible_evidence_id_n"),
        "semantic_unit_fingerprint_digest": acc.get("semantic_unit_fingerprint_digest")
        or (pack.get("preaggregation") or {}).get("semantic_unit_fingerprint_digest"),
        "validated_observation_digest": acc.get("validated_observation_digest"),
        "units_total": acc.get("units_total"),
        "units_complete": acc.get("units_complete"),
        "units_deferred": acc.get("units_deferred"),
        "enrichment_complete": acc.get("enrichment_complete"),
        "deferred_unit_fingerprints": acc.get("deferred_unit_fingerprints"),
        "stage_timings": inf.get("stage_timings"),
        "distinct_raw_evidence_items": acc.get("distinct_raw_evidence_items")
        or (pack.get("preaggregation") or {}).get("distinct_raw_evidence_items"),
        "distinct_sms_messages": acc.get("distinct_sms_messages")
        or (pack.get("preaggregation") or {}).get("distinct_sms_messages"),
        "sms_provenance_id_n": acc.get("sms_provenance_id_n")
        or (pack.get("preaggregation") or {}).get("sms_provenance_id_n"),
        "eligible_provenance_id_n": acc.get("eligible_provenance_id_n")
        or (pack.get("preaggregation") or {}).get("eligible_provenance_id_n"),
        "eligible_representation_id_n": acc.get("eligible_representation_id_n")
        or (pack.get("preaggregation") or {}).get("eligible_representation_id_n"),
        "count_labels": acc.get("count_labels")
        or (pack.get("preaggregation") or {}).get("count_labels"),
    }
    pack["semantic_observations"] = inf.get("observations") or pack.get("semantic_observations")
    pack["semantic_ir"] = inf.get("semantic_ir") or pack.get("semantic_ir")
    pack["semantic_higher_order"] = pack.get("semantic_higher_order") or inf.get(
        "semantic_higher_order"
    )
    pack["ask_relative_view"] = inf.get("ask_relative_view")
    if inf.get("fail_closed"):
        pack["ask_relative_view"] = None
        pack.pop("validated_inference", None)
        pack.pop("life_period_outline", None)
    if inf.get("partial"):
        cov = pack.get("coverage") if isinstance(pack.get("coverage"), dict) else {}
        cov["incomplete"] = True
        cov["truncated"] = True
        cov["truncation_disclosure"] = (
            cov.get("truncation_disclosure")
            or "Some evidence batches could not be inferred."
        )
        pack["coverage"] = cov
    if inf.get("ok") and inf.get("document"):
        pack["validated_inference"] = inf["document"]
        outline = outline_from_inference(inf["document"], plan)
        pack["life_period_outline"] = outline
        vol = pack.get("volume") if isinstance(pack.get("volume"), dict) else {}
        vol["narrator_input_n"] = len(outline.get("episodes") or [])
        vol["supplied_to_model_n"] = vol["narrator_input_n"]
        vol["reduction"] = "i11a_inference"
        pack["volume"] = vol
        vis: list[str] = []
        for ep in inf["document"].get("episodes") or []:
            vis.extend(ep.get("candidate_visual_ids") or [])
        pack["candidate_visual_ids"] = list(dict.fromkeys(vis))
    from memorybox.ask.i11a.consideration import finish_consideration
    from memorybox.ask import stage_clock

    with stage_clock.timed("gallery_pack_assembly_ms"):
        finish_consideration(
            pack,
            chunk_map=inf.get("chunk_map") or {},
            document=inf.get("document"),
            accounting=inf.get("accounting"),
        )
    return pack


def rank_photos_by_candidates(photos: list[Any], candidate_ids: list[str]) -> list[Any]:
    """Reorder only. Never drop in-scope photos."""
    if not candidate_ids or not photos:
        return list(photos)
    wanted = {str(x) for x in candidate_ids}
    head: list[Any] = []
    tail: list[Any] = []
    for p in photos:
        d = p.to_dict() if hasattr(p, "to_dict") else p
        eid = str((d or {}).get("external_id") or "")
        if eid in wanted:
            head.append(p)
        else:
            tail.append(p)
    return head + tail
