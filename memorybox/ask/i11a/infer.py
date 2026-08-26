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
    eligible_observations,
    fallback_view,
    reason_payload,
    view_from_model_json,
)
from memorybox.ask.i11a.support import rank_episodes_for_narrator
from memorybox.ask.i11a.units import ask_kind_for_plan, compact_units_for_model, units_from_pack
from memorybox.ask.i11a.validate import parse_inference_json, validate_inference, validate_observations
from memorybox.ask.i11a.windows import _day
from memorybox.providers.base import ProviderError, ProviderUnavailable
from memorybox.providers.llm.dto import ChatMessage

OBSERVATION_EXTRACT = """OBSERVATION_EXTRACT
You extract Ask-independent grounded semantic observations. Return JSON only.
Answer: what does this evidence actually establish?
Do not create a trip, Person portrait, period narrative, holiday story, or relationship essay.
Do not use the user's question. These observations must be reusable across future Asks.

Emit objects with: observation_id (optional), kind, text, claim_type, people, places, time,
supporting_evidence_ids copied exactly from unit evidence_id / extra_ids / source_evidence_ids,
uncertainty[].

Kinds: person_at_place_time, calendar_records_event, communication_states,
travel_document_records, repeated_communication_pattern, people_interacting,
activity_named, place_referenced, relationship_stated, media_observation.

Preserve communication meaning (what was stated, offered, planned, or recollected),
not labels such as "email from Peggy" or "calendar event".
Examples of grounded text:
- Peggy and Tom exchanged affectionate messages: love you
- Calendar records Eagles Live at Sphere
- Travel document records Flight to Las Vegas
- Tom observed at Paradise on 2026-01-30

Rules:
- Do not invent people, places, dates, motives, or emotions.
- Never invent IDs.
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
    budget = _batch_chars()
    buckets: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for u in units:
        k = str(u.get("kind") or "other")
        if k not in buckets:
            buckets[k] = []
            order.append(k)
        buckets[k].append(u)
    mixed: list[dict[str, Any]] = []
    while any(buckets[k] for k in order):
        for k in order:
            if buckets[k]:
                mixed.append(buckets[k].pop(0))
    chunks: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    size = 0
    for u in mixed:
        piece = len(json.dumps(u, default=str))
        if cur and size + piece > budget:
            chunks.append(cur)
            cur = []
            size = 0
        cur.append(u)
        size += piece
    if cur:
        chunks.append(cur)
    return chunks


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
    return str(getattr(result, "content", "") or ""), {
        "model": getattr(result, "model", None),
        "provider_key": getattr(llm, "provider_key", None),
    }


def _call_with_retry(llm: Any, system: str, payload: dict[str, Any]) -> str:
    last: Exception | None = None
    attempts = 1 + _retries()
    for i in range(attempts):
        try:
            text, _meta = _chat_json(llm, system, payload)
            if text.strip():
                return text
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


def _unit_for_model(unit: dict[str, Any]) -> dict[str, Any]:
    row = {
        "unit_id": unit.get("unit_id"),
        "evidence_id": unit.get("evidence_id"),
        "kind": unit.get("kind"),
        "source_type": unit.get("source_type"),
        "time": _day(unit.get("time")) or str(unit.get("time") or "")[:10],
        "people": unit.get("people") or [],
        "place": unit.get("place"),
        "content": str(unit.get("content") or "")[:400],
        "asset_ref": unit.get("asset_ref"),
        "extra_ids": list(unit.get("extra_ids") or unit.get("source_evidence_ids") or [])[:8],
        "occurrence_count": unit.get("occurrence_count"),
        "pattern_type": unit.get("pattern_type"),
        "thread_id": unit.get("thread_id"),
        "title": unit.get("title"),
        "authored_text": str(unit.get("authored_text") or "")[:240],
    }
    if unit.get("media"):
        row["media"] = unit.get("media")
    return row


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
        if raw.isdigit():
            return int(raw)
        return 90


def _payload_stats(system: str, payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps({"system": system, "user": payload}, default=str)
    n = len(raw)
    obs = payload.get("observations") if isinstance(payload.get("observations"), list) else []
    return {
        "observation_n": len(obs),
        "payload_bytes": n,
        "approx_tokens": max(1, n // 4),
        "timeout_seconds": _configured_chat_timeout(),
        "num_ctx": None,
        "num_ctx_note": "Ollama chat options set temperature only; num_ctx is the model default",
        "compact_observations": True,
        "includes_full_evidence_id_arrays": False,
        "includes_excerpts": False,
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
    }
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
) -> dict[str, Any]:
    """Observations → IR → Ask-relative view. Heuristic episodes are never product truth."""
    t0 = time.perf_counter()
    person_context = build_person_context(plan)
    req = resolve_request_context(plan)
    kind_hint = ask_kind_for_plan(plan)
    from memorybox.ask.i11a.preaggregate import preaggregate_pack

    units = units_from_pack(pack)
    focal_id = None
    focals = req.get("focal_subject_person_ids") or []
    if focals:
        focal_id = str(focals[0])
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
        "raw_eligible": (pack.get("preaggregation") or {}).get("raw_eligible"),
        "preaggregation_units": len(agg_units),
        "preaggregation": pack.get("preaggregation"),
        "engine": "observations_ir_ask_relative",
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
        accounting["leaf_calls"] += 1
        accounting["extract_calls"] += 1
        payload = _obs_payload(chunk)
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
            model_obs.extend([r for r in rows if isinstance(r, dict)])
            accounting["successful_units"] += len(chunk)
            _trace_span(
                stage="i11a_inference",
                component="i11a",
                operation="observation_extract",
                status="ok",
                assembled_context={"chunk": idx, "unit_n": len(chunk)},
                provider_payload={"system": OBSERVATION_EXTRACT, "user": payload},
                raw_response={"content": raw},
                parsed={"observations": rows},
            )
        except Exception as exc:  # noqa: BLE001
            failed_chunks += 1
            accounting["failed_units"] += len(chunk)
            _trace_span(
                stage="i11a_inference",
                component="i11a",
                operation="observation_extract",
                status="error",
                error_class="MODEL_OUTPUT",
                assembled_context={"chunk": idx, "unit_n": len(chunk)},
                error={"message": str(exc)},
            )

    accounting["observations_b"] = len(model_obs)
    merged = merge_model_observations(deterministic, model_obs)
    if not merged:
        merged = [observation_from_unit(u) for u in (agg.get("units") or units)]
        merged = [o for o in merged if o]
    validated_obs = validate_observations(
        merged, pack=pack, person_context=person_context
    )
    observations = validated_obs.get("observations") or []
    pack["semantic_observations"] = observations
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

    eligible = eligible_observations(
        observations, plan=plan, request_context=req
    )
    ask = str(getattr(plan, "original_ask", "") or "")
    rp = reason_payload(
        plan=plan,
        observations=eligible,
        request_context=req,
        person_context=slim_person_context_for_model(person_context),
        ask_kind_hint=kind_hint,
    )
    parsed_view = None
    ask_t0 = time.perf_counter()
    stats = _payload_stats(ASK_RELATIVE_SYSTEM, rp)
    accounting["ask_relative_payload"] = stats
    _trace_span(
        stage="ask_relative_reasoning",
        component="i11a",
        operation="ask_relative_payload",
        status="ok",
        assembled_context=stats,
        parsed=stats,
    )
    try:
        accounting["ask_relative_calls"] = 1
        accounting["leaf_calls"] += 1
        raw_view = _call_with_retry(llm, ASK_RELATIVE_SYSTEM, rp)
        parsed_view = parse_inference_json(raw_view)
        _trace_span(
            stage="ask_relative_reasoning",
            component="i11a",
            operation="ask_relative",
            status="ok",
            duration_ms=int((time.perf_counter() - ask_t0) * 1000),
            provider_payload={"system": ASK_RELATIVE_SYSTEM, "user": rp},
            raw_response={"content": raw_view},
            parsed=parsed_view,
            assembled_context={
                **stats,
                "retry_count": _retries(),
                "provider_key": getattr(llm, "provider_key", None),
                "model": getattr(llm, "chat_model", None) or getattr(llm, "model", None),
            },
        )
    except ProviderUnavailable as exc:
        klass = classify_llm_error(exc)
        elapsed_ms = int((time.perf_counter() - ask_t0) * 1000)
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
        _trace_span(
            stage="ask_relative_reasoning",
            component="i11a",
            operation="ask_relative",
            status="error",
            error_class="PARSE_SCHEMA",
            error={"message": str(exc)},
        )
        parsed_view = None

    view = view_from_model_json(
        parsed_view, eligible, ask=ask, ask_kind_hint=kind_hint
    )
    if not view.get("episodes"):
        view = fallback_view(eligible, ask=ask, ask_kind_hint=kind_hint)
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

    validated = validate_inference(view, pack=pack, person_context=person_context)
    incomplete = failed_chunks > 0
    fail_closed = not validated.get("ok")
    result = {
        "ok": bool(validated.get("ok")) and not fail_closed,
        "fail_closed": fail_closed,
        "partial": incomplete and not fail_closed,
        "reason": None if validated.get("ok") and not fail_closed else "validation failed",
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
) -> dict[str, Any]:
    if not needs_semantic_inference(plan):
        pack["inference"] = {"ok": False, "bypassed": True}
        pack["i11a_ab_metrics"] = {}
        return pack
    inf = run_inference(plan, pack, llm, modality_state=modality_state)
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
        "stage": inf.get("stage"),
    }
    pack["person_context"] = inf.get("person_context")
    pack["request_context"] = inf.get("request_context")
    acc = inf.get("accounting") if isinstance(inf.get("accounting"), dict) else {}
    pack["i11a_ab_metrics"] = {
        "raw_eligible": acc.get("raw_eligible"),
        "preaggregation_units": acc.get("preaggregation_units"),
        "a_deterministic_units": acc.get("units_deterministic"),
        "b_semantic_units": acc.get("units_model_extract"),
        "deterministic_observations": acc.get("observations_a"),
        "model_derived_observations": acc.get("observations_b"),
        "observation_extract_calls": acc.get("extract_calls"),
        "ask_relative_calls": acc.get("ask_relative_calls"),
    }
    pack["semantic_observations"] = inf.get("observations") or pack.get("semantic_observations")
    pack["semantic_ir"] = inf.get("semantic_ir") or pack.get("semantic_ir")
    pack["ask_relative_view"] = inf.get("ask_relative_view") or pack.get("ask_relative_view")
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
