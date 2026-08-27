"""I11A Ask + AI Trace regression harness.

Runs the four canonical Asks sequentially through the same production path as
POST /ask and Explore find (`AskOrchestrator.ask` → planner/retrieve/I11A/
narrator, wrapped in `tracing_ask`). Does not call leaf inference functions.

This module is instrumentation only: it does not change model, prompts, evidence,
or fail-closed behavior. Timeouts and provider errors are captured and the next
test still runs.
"""
from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

REGRESSION_ASKS: tuple[str, ...] = (
    "tell me what you know about Peggy",
    "write a narrative about my January 2025",
    "write a narrative about my trip to las vegas in January 2026",
    "write a narrative about my alaska trip in 2026",
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUT_DIR = _REPO_ROOT / "docs" / "test-output"


def default_output_path(*, when: datetime | None = None) -> Path:
    stamp = (when or datetime.now(timezone.utc)).strftime("%Y%m%d_%H%M%S")
    return _DEFAULT_OUT_DIR / f"I11A_regression_{stamp}.json"


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def _llm_runtime(orch: Any) -> dict[str, Any]:
    llm = getattr(orch, "llm", None)
    inner = getattr(llm, "inner", llm)
    health = None
    try:
        h = inner.health() if inner is not None else None
        if h is not None:
            health = {
                "ok": bool(getattr(h, "ok", False)),
                "detail": getattr(h, "detail", None) or getattr(h, "message", None),
            }
    except Exception as exc:  # noqa: BLE001
        health = {"ok": False, "detail": str(exc)}
    return {
        "provider_key": getattr(inner, "provider_key", None) or getattr(llm, "provider_key", None),
        "chat_model": getattr(inner, "chat_model", None),
        "base_url": getattr(inner, "base_url", None),
        "health": health,
    }


def _evidence_considered(result: Any) -> dict[str, Any]:
    if result is None:
        return {}
    pack = getattr(result, "narrative_pack", None) or {}
    coverage = getattr(result, "coverage", None) or pack.get("coverage") or {}
    vol = pack.get("volume") if isinstance(pack, dict) else None
    return {
        "communication": len(getattr(result, "evidence_hits", None) or []),
        "photo": len(getattr(result, "photo_hits", None) or []),
        "story": len(getattr(result, "story_hits", None) or []),
        "journal": len(getattr(result, "journal_hits", None) or []),
        "video": len(getattr(result, "video_hits", None) or []),
        "artifact": len(getattr(result, "artifact_hits", None) or []),
        "guided_capture": len(getattr(result, "guided_capture_hits", None) or []),
        "coverage": _jsonable(coverage) if coverage else {},
        "narrative_pack_volume": _jsonable(vol) if vol else None,
    }


def _load_full_trace(trace_id: str | None) -> dict[str, Any] | None:
    if not trace_id:
        return None
    from memorybox.ai_trace.store import get_trace

    return get_trace(str(trace_id))


def _find_trace(*, session_id: str, ask: str) -> dict[str, Any] | None:
    from memorybox.ai_trace.store import get_trace, list_traces

    for row in list_traces(q=session_id, limit=50):
        if str(row.get("session_id") or "") != session_id:
            continue
        if str(row.get("originating_ask") or "") != ask:
            continue
        tid = row.get("trace_id")
        if tid:
            full = get_trace(str(tid))
            if full:
                return full
    return None


def _error_from_trace(trace: dict[str, Any] | None) -> str | None:
    if not trace:
        return None
    cls = trace.get("error_class")
    if cls:
        return str(cls)
    for span in trace.get("spans") or []:
        if not isinstance(span, dict):
            continue
        span_cls = span.get("error_class")
        if span_cls:
            return str(span_cls)
    return None


def _provider_call_stats(trace: dict[str, Any] | None) -> dict[str, Any]:
    spans = (trace or {}).get("spans") if isinstance(trace, dict) else None
    if not isinstance(spans, list):
        return {
            "chat": 0,
            "embed": 0,
            "by_operation": {},
            "timeouts": 0,
            "errors": 0,
        }
    by_op: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    chat = embed = timeouts = errors = 0
    for span in spans:
        if not isinstance(span, dict):
            continue
        op = str(span.get("operation") or "")
        stage = str(span.get("stage") or "")
        if op in {"chat", "embed"}:
            by_op[op] = by_op.get(op, 0) + 1
            key = stage or op
            by_stage[key] = by_stage.get(key, 0) + 1
            if op == "chat":
                chat += 1
            else:
                embed += 1
        if str(span.get("error_class") or "") == "PROVIDER_TIMEOUT":
            timeouts += 1
        if str(span.get("status") or "") == "error" and op in {"chat", "embed"}:
            errors += 1
    return {
        "chat": chat,
        "embed": embed,
        "by_operation": by_op,
        "by_stage": by_stage,
        "timeouts": timeouts,
        "errors": errors,
    }


def _accounting_from_trace(trace: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(trace, dict):
        return {}
    for span in trace.get("spans") or []:
        if not isinstance(span, dict):
            continue
        assembled = span.get("assembled_context") if isinstance(span.get("assembled_context"), dict) else {}
        acc = assembled.get("accounting") if isinstance(assembled.get("accounting"), dict) else None
        if acc:
            return acc
        if span.get("operation") == "preaggregation" and assembled:
            return {
                "units_deterministic": assembled.get("deterministic_units"),
                "units_model_extract": assembled.get("extract_units"),
            }
    return {}


def _count_chats_with(trace: dict[str, Any] | None, needle: str) -> int:
    n = 0
    if not isinstance(trace, dict):
        return 0
    for span in trace.get("spans") or []:
        if not isinstance(span, dict):
            continue
        if str(span.get("operation") or "") != "chat":
            continue
        blob = json.dumps(span.get("provider_payload") or {}, default=str)
        if needle in blob:
            n += 1
    return n


def _ab_metrics(result: Any, trace: dict[str, Any] | None) -> dict[str, Any]:
    pack = getattr(result, "narrative_pack", None) if result is not None else None
    if not isinstance(pack, dict):
        pack = {}
    named = pack.get("i11a_ab_metrics") if isinstance(pack.get("i11a_ab_metrics"), dict) else {}
    acc = _accounting_from_trace(trace)
    inf = pack.get("inference") if isinstance(pack.get("inference"), dict) else {}
    inf_acc = inf.get("accounting") if isinstance(inf.get("accounting"), dict) else {}
    pre = pack.get("preaggregation") if isinstance(pack.get("preaggregation"), dict) else {}
    vol = pack.get("volume") if isinstance(pack.get("volume"), dict) else {}
    calls = _provider_call_stats(trace)

    def _first(*vals: Any) -> Any:
        for v in vals:
            if v is not None:
                return v
        return None

    extract = _first(
        named.get("observation_extract_calls"),
        inf_acc.get("extract_calls"),
        acc.get("extract_calls"),
        _count_chats_with(trace, "OBSERVATION_EXTRACT"),
    )
    ask_rel = _first(
        named.get("ask_relative_calls"),
        inf_acc.get("ask_relative_calls"),
        acc.get("ask_relative_calls"),
        _count_chats_with(trace, "ASK_RELATIVE_REASONING"),
    )
    narrator = _count_chats_with(trace, "NARRATIVE_SYNTHESIS")
    return {
        "raw_eligible_evidence": _first(
            named.get("raw_eligible"),
            inf_acc.get("raw_eligible"),
            acc.get("raw_eligible"),
            pre.get("raw_eligible"),
            vol.get("eligible_n"),
            vol.get("retrieved_n"),
        ),
        "preaggregation_units": _first(
            named.get("preaggregation_units"),
            inf_acc.get("preaggregation_units"),
            acc.get("preaggregation_units"),
            pre.get("inference_units"),
        ),
        "a_deterministic_units": _first(
            named.get("a_deterministic_units"),
            inf_acc.get("units_deterministic"),
            acc.get("units_deterministic"),
            pre.get("deterministic_units"),
        ),
        "b_semantic_units": _first(
            named.get("b_semantic_units"),
            inf_acc.get("units_model_extract"),
            acc.get("units_model_extract"),
            pre.get("extract_units"),
        ),
        "deterministic_observations": _first(
            named.get("deterministic_observations"),
            inf_acc.get("observations_a"),
            acc.get("observations_a"),
        ),
        "model_derived_observations": _first(
            named.get("model_derived_observations"),
            inf_acc.get("observations_b"),
            acc.get("observations_b"),
        ),
        "raw_comm_items": _first(
            named.get("raw_comm_items"),
            inf_acc.get("raw_comm_items"),
            acc.get("raw_comm_items"),
            pre.get("raw_comm_items"),
        ),
        "email_thread_units": _first(
            named.get("email_thread_units"),
            inf_acc.get("email_thread_units"),
            pre.get("email_thread_units"),
        ),
        "sms_segment_units": _first(
            named.get("sms_segment_units"),
            inf_acc.get("sms_segment_units"),
            pre.get("sms_segment_units"),
        ),
        "semantic_comm_units_after_dedupe": _first(
            named.get("semantic_comm_units_after_dedupe"),
            inf_acc.get("semantic_comm_units_after_dedupe"),
            pre.get("semantic_comm_units_after_dedupe"),
        ),
        "extract_chunks": _first(
            named.get("extract_chunks"),
            inf_acc.get("extract_chunks"),
            inf_acc.get("chunk_n"),
        ),
        "provenance_coverage": _first(
            named.get("provenance_coverage"),
            inf_acc.get("provenance_coverage"),
            pre.get("provenance_coverage"),
        ),
        "provenance_ids_raw_comm": _first(
            named.get("provenance_ids_raw_comm"),
            inf_acc.get("provenance_ids_raw_comm"),
            pre.get("provenance_ids_raw_comm"),
        ),
        "provenance_ids_retained": _first(
            named.get("provenance_ids_retained"),
            inf_acc.get("provenance_ids_retained"),
            pre.get("provenance_ids_retained"),
        ),
        "extract_observations_rejected": _first(
            named.get("extract_observations_rejected"),
            inf_acc.get("extract_observations_rejected"),
        ),
        "extract_timeouts": _first(
            named.get("extract_timeouts"),
            inf_acc.get("extract_timeouts"),
        ),
        "extract_cache_hits": _first(
            named.get("extract_cache_hits"),
            inf_acc.get("extract_cache_hits"),
        ),
        "extract_cache_misses": _first(
            named.get("extract_cache_misses"),
            inf_acc.get("extract_cache_misses"),
        ),
        "persisted_observations": _first(
            named.get("persisted_observations"),
            inf_acc.get("persisted_observations"),
        ),
        "extract_payloads": _first(
            named.get("extract_payloads"),
            inf_acc.get("extract_payloads"),
        ),
        "ask_relative_payload": _first(
            named.get("ask_relative_payload"),
            inf_acc.get("ask_relative_payload"),
            acc.get("ask_relative_payload"),
        ),
        "validated_observations": _first(
            named.get("validated_observations"),
            inf_acc.get("validated_observations"),
        ),
        "rollup_units": _first(named.get("rollup_units"), inf_acc.get("rollup_units")),
        "rollup_provenance_coverage": _first(
            named.get("rollup_provenance_coverage"),
            inf_acc.get("rollup_provenance_coverage"),
        ),
        "observations_expanded": _first(
            named.get("observations_expanded"),
            inf_acc.get("observations_expanded"),
        ),
        "enrichment_deferred": _first(
            named.get("enrichment_deferred"),
            inf_acc.get("enrichment_deferred"),
        ),
        "inference_stage": _first(
            named.get("inference_stage"),
            inf_acc.get("inference_stage"),
            inf.get("stage"),
        ),
        "sms_raw": _first(named.get("sms_raw"), inf_acc.get("sms_raw"), pre.get("sms_raw")),
        "sms_windows": _first(named.get("sms_windows"), inf_acc.get("sms_windows"), pre.get("sms_windows")),
        "max_messages_per_comm_unit": pre.get("max_messages_per_comm_unit"),
        "eligible_evidence_id_digest": _first(
            named.get("eligible_evidence_id_digest"),
            inf_acc.get("eligible_evidence_id_digest"),
            pre.get("eligible_evidence_id_digest"),
        ),
        "eligible_evidence_id_n": _first(
            named.get("eligible_evidence_id_n"),
            inf_acc.get("eligible_evidence_id_n"),
            pre.get("eligible_evidence_id_n"),
        ),
        "semantic_unit_fingerprint_digest": _first(
            named.get("semantic_unit_fingerprint_digest"),
            inf_acc.get("semantic_unit_fingerprint_digest"),
            pre.get("semantic_unit_fingerprint_digest"),
        ),
        "validated_observation_digest": _first(
            named.get("validated_observation_digest"),
            inf_acc.get("validated_observation_digest"),
        ),
        "eligible_evidence_ids": pre.get("eligible_evidence_ids"),
        "sms_evidence_ids": pre.get("sms_evidence_ids"),
        "email_evidence_ids": pre.get("email_evidence_ids"),
        "semantic_unit_fingerprints": pre.get("semantic_unit_fingerprints"),
        "observation_extract_calls": extract,
        "ask_relative_calls": ask_rel,
        "narrator_calls": narrator,
        "total_model_calls": None,
        "timeout_count": calls.get("timeouts"),
        "total_duration_ms": None,
        "units_total": _first(named.get("units_total"), inf_acc.get("units_total")),
        "units_complete": _first(named.get("units_complete"), inf_acc.get("units_complete")),
        "units_deferred": _first(named.get("units_deferred"), inf_acc.get("units_deferred")),
        "enrichment_complete": _first(
            named.get("enrichment_complete"),
            inf.get("enrichment_complete"),
            inf_acc.get("enrichment_complete"),
        ),
        "deferred_unit_fingerprints": _first(
            named.get("deferred_unit_fingerprints"),
            inf_acc.get("deferred_unit_fingerprints"),
        ),
        "stage_timings": _first(
            pack.get("stage_timings"),
            inf.get("stage_timings"),
            named.get("stage_timings"),
        ),
        "distinct_raw_evidence_items": _first(
            named.get("distinct_raw_evidence_items"),
            inf_acc.get("distinct_raw_evidence_items"),
            pre.get("distinct_raw_evidence_items"),
        ),
        "distinct_sms_messages": _first(
            named.get("distinct_sms_messages"),
            inf_acc.get("distinct_sms_messages"),
            pre.get("distinct_sms_messages"),
        ),
        "sms_provenance_id_n": _first(
            named.get("sms_provenance_id_n"),
            inf_acc.get("sms_provenance_id_n"),
            pre.get("sms_provenance_id_n"),
        ),
        "eligible_provenance_id_n": _first(
            named.get("eligible_provenance_id_n"),
            inf_acc.get("eligible_provenance_id_n"),
            pre.get("eligible_provenance_id_n"),
        ),
        "eligible_representation_id_n": _first(
            named.get("eligible_representation_id_n"),
            inf_acc.get("eligible_representation_id_n"),
            pre.get("eligible_representation_id_n"),
        ),
        "count_labels": _first(named.get("count_labels"), pre.get("count_labels")),
    }


def _run_one(
    orch: Any,
    ask: str,
    index: int,
    *,
    total: int = 4,
    inference_stage: str = "ask",
    pass_kind: str = "ask",
) -> dict[str, Any]:
    from memorybox.ask.orchestrator import AskResult

    session_id = f"i11a-regression-{index}-{uuid4()}"
    started = datetime.now(timezone.utc)
    started_iso = started.isoformat()
    result: AskResult | None = None
    harness_error: dict[str, Any] | None = None
    print(
        f"I11A regression TEST {index}/{total} starting ({pass_kind}): {ask!r} session={session_id}",
        flush=True,
    )
    try:
        result = orch.ask(
            ask,
            session_id=session_id,
            narrate=inference_stage != "enrich",
            inference_stage=inference_stage,
        )
    except Exception as exc:  # noqa: BLE001 — capture and continue
        harness_error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        print(
            f"I11A regression TEST {index}/{total} raised {type(exc).__name__}: {exc}",
            flush=True,
        )
    ended = datetime.now(timezone.utc)
    wall_ms = int((ended - started).total_seconds() * 1000)

    trace_id = getattr(result, "trace_id", None) if result is not None else None
    trace = _load_full_trace(trace_id)
    if trace is None:
        trace = _find_trace(session_id=session_id, ask=ask)
        if trace:
            trace_id = trace.get("trace_id")

    status = None
    error_class = None
    model_call_count = 0
    duration_ms = wall_ms
    if isinstance(trace, dict):
        status = trace.get("status")
        error_class = _error_from_trace(trace)
        try:
            model_call_count = int(trace.get("model_call_count") or 0)
        except (TypeError, ValueError):
            model_call_count = 0
        if trace.get("duration_ms") is not None:
            try:
                duration_ms = int(trace["duration_ms"])
            except (TypeError, ValueError):
                duration_ms = wall_ms
    if result is not None and getattr(result, "narration_unavailable", False):
        pack = getattr(result, "narrative_pack", None)
        inf = pack.get("inference") if isinstance(pack, dict) else {}
        if isinstance(inf, dict) and inf.get("fail_closed"):
            status = "error"
            error_class = error_class or inf.get("error_class")
        else:
            status = status or "ok"
    if result is not None:
        pack_st = getattr(result, "narrative_pack", None)
        inf_st = pack_st.get("inference") if isinstance(pack_st, dict) else {}
        if (
            isinstance(inf_st, dict)
            and inf_st.get("enrichment_complete") is False
            and not inf_st.get("fail_closed")
        ):
            status = "partial"
            error_class = error_class or inf_st.get("error_class")
    if harness_error is not None:
        status = status or "error"
        error_class = error_class or "ORCHESTRATION"
    status = status or "ok"

    curator = ""
    if result is not None:
        curator = result.answer_text if result.answer_text is not None else ""

    metrics = _ab_metrics(result, trace if isinstance(trace, dict) else None)
    metrics["total_model_calls"] = model_call_count
    metrics["total_duration_ms"] = duration_ms

    record = {
        "index": index,
        "ask": ask,
        "pass_kind": pass_kind,
        "inference_stage": inference_stage,
        "session_id": session_id,
        "trace_id": str(trace_id) if trace_id else None,
        "started_at": started_iso,
        "ended_at": ended.isoformat(),
        "duration_ms": duration_ms,
        "wall_duration_ms": wall_ms,
        "model_call_count": model_call_count,
        "status": status,
        "error_class": error_class,
        "curator_response": curator,
        "answer_kind": getattr(result, "answer_kind", None) if result is not None else None,
        "narration_unavailable": bool(getattr(result, "narration_unavailable", False))
        if result is not None
        else None,
        "evidence_considered": _evidence_considered(result),
        "provider_calls": _provider_call_stats(trace if isinstance(trace, dict) else None),
        "inference_accounting": _accounting_from_trace(trace if isinstance(trace, dict) else None),
        "metrics": metrics,
        "request_context": _jsonable(
            ((getattr(result, "narrative_pack", None) or {}) if result is not None else {}).get(
                "request_context"
            )
        )
        if result is not None
        else None,
        "peggy_diagnostics": {
            "sms_raw": metrics.get("sms_raw"),
            "sms_segment_units": metrics.get("sms_segment_units"),
            "sms_windows": metrics.get("sms_windows"),
            "max_messages_per_comm_unit": metrics.get("max_messages_per_comm_unit"),
            "extract_payloads": metrics.get("extract_payloads"),
            "extract_timeouts": metrics.get("extract_timeouts"),
            "extract_cache_hits": metrics.get("extract_cache_hits"),
            "extract_cache_misses": metrics.get("extract_cache_misses"),
            "persisted_observations": metrics.get("persisted_observations"),
            "sms_episode_units": metrics.get("sms_segment_units")
            or (getattr(result, "narrative_pack", None) or {}).get("preaggregation", {}).get(
                "sms_episode_units"
            )
            if result is not None
            else metrics.get("sms_segment_units"),
            "extract_observations_rejected": metrics.get("extract_observations_rejected"),
            "model_derived_observations": metrics.get("model_derived_observations"),
            "deterministic_observations": metrics.get("deterministic_observations"),
            "ask_relative_payload": metrics.get("ask_relative_payload"),
            "validated_observations": metrics.get("validated_observations"),
            "validated_observation_digest": metrics.get("validated_observation_digest"),
            "rollup_units": metrics.get("rollup_units"),
            "rollup_provenance_coverage": metrics.get("rollup_provenance_coverage"),
            "observations_expanded": metrics.get("observations_expanded"),
            "eligible_evidence_id_digest": metrics.get("eligible_evidence_id_digest"),
            "semantic_unit_fingerprint_digest": metrics.get("semantic_unit_fingerprint_digest"),
            "sms_raw": metrics.get("sms_raw"),
            "narrator_invoked": bool(metrics.get("narrator_calls")),
            "narrator_calls": metrics.get("narrator_calls"),
            "total_runtime_ms": duration_ms,
            "units_total": metrics.get("units_total"),
            "units_complete": metrics.get("units_complete"),
            "units_deferred": metrics.get("units_deferred"),
            "enrichment_complete": metrics.get("enrichment_complete"),
            "deferred_unit_fingerprints": metrics.get("deferred_unit_fingerprints"),
            "stage_timings": metrics.get("stage_timings"),
            "distinct_raw_evidence_items": metrics.get("distinct_raw_evidence_items"),
            "distinct_sms_messages": metrics.get("distinct_sms_messages"),
            "sms_provenance_id_n": metrics.get("sms_provenance_id_n"),
            "eligible_provenance_id_n": metrics.get("eligible_provenance_id_n"),
            "eligible_representation_id_n": metrics.get("eligible_representation_id_n"),
            "eligible_evidence_id_n": metrics.get("eligible_evidence_id_n"),
            "count_labels": metrics.get("count_labels"),
        },
        "harness_error": harness_error,
        "trace": _jsonable(trace) if trace is not None else None,
    }
    print(
        f"I11A regression TEST {index}/{total} done status={status} error_class={error_class} "
        f"model_calls={model_call_count} duration_ms={duration_ms} trace_id={trace_id}",
        flush=True,
    )
    return record


def build_payload(tests: list[dict[str, Any]], *, runtime: dict[str, Any]) -> dict[str, Any]:
    from memorybox.config import settings

    completed = len(tests)
    with_errors = sum(
        1
        for t in tests
        if t.get("harness_error")
        or str(t.get("status") or "") in {"error", "failed"}
    )
    stage_totals: dict[str, int] = {}
    for t in tests:
        for k, v in ((t.get("provider_calls") or {}).get("by_stage") or {}).items():
            try:
                stage_totals[str(k)] = stage_totals.get(str(k), 0) + int(v or 0)
            except (TypeError, ValueError):
                continue
    summary = {
        "tests_run": len(tests),
        "tests_completed": completed,
        "tests_with_errors": with_errors,
        "total_model_calls": sum(int(t.get("model_call_count") or 0) for t in tests),
        "total_duration_ms": sum(int(t.get("duration_ms") or 0) for t in tests),
        "total_timeouts": sum(int((t.get("provider_calls") or {}).get("timeouts") or 0) for t in tests),
        "totals": {
            "raw_eligible_evidence": sum(int((t.get("metrics") or {}).get("raw_eligible_evidence") or 0) for t in tests),
            "preaggregation_units": sum(int((t.get("metrics") or {}).get("preaggregation_units") or 0) for t in tests),
            "a_deterministic_units": sum(int((t.get("metrics") or {}).get("a_deterministic_units") or 0) for t in tests),
            "b_semantic_units": sum(int((t.get("metrics") or {}).get("b_semantic_units") or 0) for t in tests),
            "deterministic_observations": sum(int((t.get("metrics") or {}).get("deterministic_observations") or 0) for t in tests),
            "model_derived_observations": sum(int((t.get("metrics") or {}).get("model_derived_observations") or 0) for t in tests),
            "raw_comm_items": sum(int((t.get("metrics") or {}).get("raw_comm_items") or 0) for t in tests),
            "email_thread_units": sum(int((t.get("metrics") or {}).get("email_thread_units") or 0) for t in tests),
            "sms_segment_units": sum(int((t.get("metrics") or {}).get("sms_segment_units") or 0) for t in tests),
            "semantic_comm_units_after_dedupe": sum(int((t.get("metrics") or {}).get("semantic_comm_units_after_dedupe") or 0) for t in tests),
            "extract_chunks": sum(int((t.get("metrics") or {}).get("extract_chunks") or 0) for t in tests),
            "extract_observations_rejected": sum(int((t.get("metrics") or {}).get("extract_observations_rejected") or 0) for t in tests),
            "observation_extract_calls": sum(int((t.get("metrics") or {}).get("observation_extract_calls") or 0) for t in tests),
            "ask_relative_calls": sum(int((t.get("metrics") or {}).get("ask_relative_calls") or 0) for t in tests),
            "narrator_calls": sum(int((t.get("metrics") or {}).get("narrator_calls") or 0) for t in tests),
            "total_model_calls": sum(int(t.get("model_call_count") or 0) for t in tests),
            "timeout_count": sum(int((t.get("metrics") or {}).get("timeout_count") or 0) for t in tests),
            "total_duration_ms": sum(int(t.get("duration_ms") or 0) for t in tests),
        },
        "calls_by_stage": {
            "chat": sum(int((t.get("provider_calls") or {}).get("chat") or 0) for t in tests),
            "embed": sum(int((t.get("provider_calls") or {}).get("embed") or 0) for t in tests),
            "by_stage": stage_totals,
        },
        "per_test": [
            {
                "ask": t.get("ask"),
                "pass_kind": t.get("pass_kind"),
                "inference_stage": t.get("inference_stage"),
                "status": t.get("status"),
                "error_class": t.get("error_class"),
                "model_calls": t.get("model_call_count"),
                "duration_ms": t.get("duration_ms"),
                "timeouts": (t.get("provider_calls") or {}).get("timeouts"),
                "provider_calls": t.get("provider_calls") or {},
                "observations_a": (t.get("inference_accounting") or {}).get("observations_a"),
                "observations_b": (t.get("inference_accounting") or {}).get("observations_b"),
                "extract_calls": (t.get("inference_accounting") or {}).get("extract_calls"),
                "metrics": t.get("metrics") or {},
                "evidence_considered": t.get("evidence_considered") or {},
            }
            for t in tests
        ],
    }
    enrich_tests = [t for t in tests if t.get("pass_kind") == "cold_enrichment"]
    warm_tests = [t for t in tests if t.get("pass_kind") == "warm_ask"]
    if not warm_tests:
        warm_tests = [t for t in tests if t.get("pass_kind") != "cold_enrichment"]
    def _tok(t: dict[str, Any]) -> int:
        payload = ((t.get("metrics") or {}).get("ask_relative_payload") or {})
        try:
            return int(payload.get("approx_tokens") or 0)
        except (TypeError, ValueError):
            return 0
    summary["cold_enrichment_ms"] = sum(int(t.get("duration_ms") or 0) for t in enrich_tests)
    summary["warm_ask_ms"] = [int(t.get("duration_ms") or 0) for t in warm_tests]
    summary["cold_extract_calls"] = sum(
        int((t.get("metrics") or {}).get("observation_extract_calls") or 0) for t in enrich_tests
    )
    summary["warm_extract_calls"] = [
        int((t.get("metrics") or {}).get("observation_extract_calls") or 0) for t in warm_tests
    ]
    summary["warm_ask_relative_tokens"] = [_tok(t) for t in warm_tests]
    summary["warm_narrator_calls"] = [
        int((t.get("metrics") or {}).get("narrator_calls") or 0) for t in warm_tests
    ]

    def _ids(t: dict[str, Any], key: str) -> list[str]:
        raw = (t.get("metrics") or {}).get(key) or []
        return [str(x) for x in raw if str(x).strip()]

    def _id_diff(a: list[str], b: list[str]) -> dict[str, Any]:
        sa, sb = set(a), set(b)
        added = sorted(sb - sa)
        missing = sorted(sa - sb)
        return {
            "added_n": len(added),
            "missing_n": len(missing),
            "added_ids": added[:80],
            "missing_ids": missing[:80],
        }

    def _fp(t: dict[str, Any]) -> dict[str, Any]:
        m = t.get("metrics") or {}
        pay = m.get("ask_relative_payload") if isinstance(m.get("ask_relative_payload"), dict) else {}
        return {
            "pass_kind": t.get("pass_kind"),
            "sms_raw": m.get("sms_raw"),
            "sms_segment_units": m.get("sms_segment_units"),
            "email_raw": m.get("email_thread_units"),
            "eligible_evidence_id_n": m.get("eligible_evidence_id_n"),
            "eligible_evidence_id_digest": m.get("eligible_evidence_id_digest"),
            "distinct_raw_evidence_items": m.get("distinct_raw_evidence_items"),
            "distinct_sms_messages": m.get("distinct_sms_messages"),
            "sms_provenance_id_n": m.get("sms_provenance_id_n"),
            "eligible_provenance_id_n": m.get("eligible_provenance_id_n"),
            "eligible_representation_id_n": m.get("eligible_representation_id_n"),
            "units_total": m.get("units_total"),
            "units_complete": m.get("units_complete"),
            "units_deferred": m.get("units_deferred"),
            "enrichment_complete": m.get("enrichment_complete"),
            "stage_timings": m.get("stage_timings"),
            "semantic_unit_fingerprint_digest": m.get("semantic_unit_fingerprint_digest"),
            "validated_observation_digest": m.get("validated_observation_digest"),
            "extract_calls": m.get("observation_extract_calls"),
            "ask_relative_tokens": _tok(t),
            "provider_eval": pay.get("provider_eval"),
            "prompt_tokens": pay.get("prompt_tokens"),
            "response_tokens": pay.get("response_tokens"),
        }

    compare_pairs: list[dict[str, Any]] = []
    all_for_cmp = list(enrich_tests) + list(warm_tests)
    if all_for_cmp:
        base = all_for_cmp[0]
        base_ids = _ids(base, "eligible_evidence_ids")
        base_sms = _ids(base, "sms_evidence_ids")
        for other in all_for_cmp[1:]:
            compare_pairs.append(
                {
                    "from": base.get("pass_kind"),
                    "to": other.get("pass_kind"),
                    "from_index": base.get("index"),
                    "to_index": other.get("index"),
                    "source_counts": {"from": _fp(base), "to": _fp(other)},
                    "eligible_evidence_diff": _id_diff(base_ids, _ids(other, "eligible_evidence_ids")),
                    "sms_evidence_diff": _id_diff(base_sms, _ids(other, "sms_evidence_ids")),
                    "digests_equal": (
                        (base.get("metrics") or {}).get("eligible_evidence_id_digest")
                        == (other.get("metrics") or {}).get("eligible_evidence_id_digest")
                        and (base.get("metrics") or {}).get("semantic_unit_fingerprint_digest")
                        == (other.get("metrics") or {}).get("semantic_unit_fingerprint_digest")
                    ),
                    "wall_clock_cutoff_used": False,
                    "why_retrieval_changed": (
                        None
                        if (base.get("metrics") or {}).get("eligible_evidence_id_digest")
                        == (other.get("metrics") or {}).get("eligible_evidence_id_digest")
                        else (
                            "eligible evidence ID set differed; paging no longer stops on wall-clock. "
                            "If this is nonempty after this fix, inspect planner person_ids/windows."
                        )
                    ),
                }
            )
    warm_stable = False
    if len(warm_tests) >= 2:
        d0 = (warm_tests[0].get("metrics") or {}).get("eligible_evidence_id_digest")
        f0 = (warm_tests[0].get("metrics") or {}).get("semantic_unit_fingerprint_digest")
        o0 = (warm_tests[0].get("metrics") or {}).get("validated_observation_digest")
        warm_stable = all(
            (t.get("metrics") or {}).get("eligible_evidence_id_digest") == d0
            and (t.get("metrics") or {}).get("semantic_unit_fingerprint_digest") == f0
            and (t.get("metrics") or {}).get("validated_observation_digest") == o0
            and int((t.get("metrics") or {}).get("observation_extract_calls") or 0) == 0
            for t in warm_tests
        )
    summary["retrieve_stability"] = {
        "wall_clock_cutoff_used": False,
        "warm_asks_identical": warm_stable,
        "per_pass": [_fp(t) for t in all_for_cmp],
        "pairwise_vs_first": compare_pairs,
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.ollama_chat_model,
        "runtime": runtime,
        "summary": summary,
        "tests": tests,
    }


def run_i11a_regression(
    *,
    out_path: Path | None = None,
    asks: tuple[str, ...] | None = None,
    rebuild_observations: bool = False,
    repeat: int = 1,
    enrich_first: bool = False,
) -> dict[str, Any]:
    """Run the canonical Asks sequentially and write one UTF-8 JSON file. Returns payload."""
    from memorybox.app import get_orchestrator

    if rebuild_observations:
        from memorybox.ask.i11a.observation_cache import invalidate_extract_cache

        invalidate_extract_cache()
    orch = get_orchestrator()
    runtime = _llm_runtime(orch)
    base = asks if asks is not None else REGRESSION_ASKS
    tests: list[dict[str, Any]] = []
    index = 1
    if enrich_first:
        unique = tuple(dict.fromkeys(base))
        total = len(unique) + len(tuple(base) * max(1, int(repeat)))
        for ask in unique:
            tests.append(
                _run_one(
                    orch,
                    ask,
                    index,
                    total=total,
                    inference_stage="enrich",
                    pass_kind="cold_enrichment",
                )
            )
            index += 1
        sequence = tuple(base) * max(1, int(repeat))
        for ask in sequence:
            tests.append(
                _run_one(
                    orch,
                    ask,
                    index,
                    total=total,
                    inference_stage="ask",
                    pass_kind="warm_ask",
                )
            )
            index += 1
    else:
        sequence = tuple(base) * max(1, int(repeat))
        total = len(sequence)
        for i, ask in enumerate(sequence, start=1):
            tests.append(_run_one(orch, ask, i, total=total))

    payload = build_payload(tests, runtime=runtime)
    path = out_path or default_output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    path.write_text(text, encoding="utf-8")
    payload["_output_path"] = str(path)
    print(f"I11A regression wrote {path} ({path.stat().st_size} bytes)", flush=True)
    return payload
