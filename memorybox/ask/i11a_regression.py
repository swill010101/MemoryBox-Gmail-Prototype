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
    "write a narrative about my January 2025",
    "write a narrative about my trip to las vegas in January 2026",
    "write a narrative about my alaska trip in 2026",
    "tell me what you know about Peggy",
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


def _run_one(orch: Any, ask: str, index: int) -> dict[str, Any]:
    from memorybox.ask.orchestrator import AskResult

    session_id = f"i11a-regression-{index}-{uuid4()}"
    started = datetime.now(timezone.utc)
    started_iso = started.isoformat()
    result: AskResult | None = None
    harness_error: dict[str, Any] | None = None
    print(f"I11A regression TEST {index}/4 starting: {ask!r} session={session_id}", flush=True)
    try:
        result = orch.ask(ask, session_id=session_id)
    except Exception as exc:  # noqa: BLE001 — capture and continue
        harness_error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        print(
            f"I11A regression TEST {index}/4 raised {type(exc).__name__}: {exc}",
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
        status = status or "ok"
    if harness_error is not None:
        status = status or "error"
        error_class = error_class or "ORCHESTRATION"
    status = status or "ok"

    curator = ""
    if result is not None:
        curator = result.answer_text if result.answer_text is not None else ""

    record = {
        "index": index,
        "ask": ask,
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
        "harness_error": harness_error,
        "trace": _jsonable(trace) if trace is not None else None,
    }
    print(
        f"I11A regression TEST {index}/4 done status={status} error_class={error_class} "
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
        if t.get("error_class")
        or t.get("harness_error")
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
        "calls_by_stage": {
            "chat": sum(int((t.get("provider_calls") or {}).get("chat") or 0) for t in tests),
            "embed": sum(int((t.get("provider_calls") or {}).get("embed") or 0) for t in tests),
            "by_stage": stage_totals,
        },
        "per_test": [
            {
                "ask": t.get("ask"),
                "status": t.get("status"),
                "error_class": t.get("error_class"),
                "model_calls": t.get("model_call_count"),
                "duration_ms": t.get("duration_ms"),
                "timeouts": (t.get("provider_calls") or {}).get("timeouts"),
                "provider_calls": t.get("provider_calls") or {},
                "observations_a": (t.get("inference_accounting") or {}).get("observations_a"),
                "observations_b": (t.get("inference_accounting") or {}).get("observations_b"),
                "extract_calls": (t.get("inference_accounting") or {}).get("extract_calls"),
                "evidence_considered": t.get("evidence_considered") or {},
            }
            for t in tests
        ],
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.ollama_chat_model,
        "runtime": runtime,
        "summary": summary,
        "tests": tests,
    }


def run_i11a_regression(*, out_path: Path | None = None) -> dict[str, Any]:
    """Run the four Asks sequentially and write one UTF-8 JSON file. Returns payload."""
    from memorybox.app import get_orchestrator

    orch = get_orchestrator()
    runtime = _llm_runtime(orch)
    tests: list[dict[str, Any]] = []
    for i, ask in enumerate(REGRESSION_ASKS, start=1):
        tests.append(_run_one(orch, ask, i))

    payload = build_payload(tests, runtime=runtime)
    path = out_path or default_output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    path.write_text(text, encoding="utf-8")
    payload["_output_path"] = str(path)
    print(f"I11A regression wrote {path} ({path.stat().st_size} bytes)", flush=True)
    return payload
