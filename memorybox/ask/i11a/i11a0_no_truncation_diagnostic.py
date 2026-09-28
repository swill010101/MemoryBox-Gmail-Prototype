"""Bounded Ollama 0.34.1 no-truncation/no-shift diagnostic. Not a ladder.

Uses top-level request fields truncate=false and shift=false (not options).
Does not resume Gate 3. Does not start Peggy, A/C, coexistence, I11A.1, or I11A.2.
"""
from __future__ import annotations

import hashlib
import json
import math
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from memorybox.ask.i11a.i11a0_benchmark import (
    I11A0Error,
    InferenceNotAuthorized,
    OUTPUT_RESERVE_TOKENS,
    SAFETY_MARGIN_TOKENS,
    VRAM_CEILING_GB,
    inventory_installed_models,
    new_execution_id,
)
from memorybox.ask.i11a.i11a0_full_prompt_v3 import (
    FROZEN_MAX_TOKENS_PER_EVIDENCE_BYTE,
    RATE_GUARD,
    truncation_limit,
)
from memorybox.ask.i11a.i11a0_host import (
    capture_clean_ladder_host_state,
    read_nvidia_snapshot,
    read_system_ram,
    require_flightsim_host_affinity,
    require_literal_loopback_ollama_url,
)
from memorybox.ask.i11a.i11a0_i14_source import verify_pinned_i14_export
from memorybox.ask.i11a.i11a0_ollama_log_cursor import (
    COMPLETE_EVALUATED,
    INVALID_TRUNCATED,
    classify_appended_log,
    classify_log_segment,
    snapshot_log,
)
from memorybox.ask.i11a.i11a0_placement import interpret_ollama_placement, read_ollama_ps
from memorybox.ask.i11a.i11a0_prompt import SYSTEM_PROMPT, render_user_message
from memorybox.ask.i11a.i11a0_smoke import PINNED_B_DIGEST, VRAM_RELEASE_SLACK_GB
from memorybox.ask.i11a.i11a0_unload_verify import verify_unload

B_TAG = "qwen3:14b-q8_0"
EXPERIMENT_ID = "i11a0_no_truncation_noshift_diagnostic_v1"
DIAGNOSTIC_A_NUM_CTX = 28416
DIAGNOSTIC_A_NUM_PREDICT = 256
DIAGNOSTIC_A_HALF = truncation_limit(DIAGNOSTIC_A_NUM_CTX)
HISTORICAL_18K_COMPLETE = 24109
DIAGNOSTIC_B_NUM_CTX = 2048
DIAGNOSTIC_B_NUM_PREDICT = 16
DIAGNOSTIC_B_HALF = truncation_limit(DIAGNOSTIC_B_NUM_CTX)
RAM_STOP_AVAILABLE_GB = 2.0
RAM_PROPOSED_GUARD_GB = 4.0
TEMPERATURE = 0.1
SEED = 42
TIMEOUT_SECONDS = 1800
CANARY_BEGIN = "MB-DIAG-BEGIN-7f3c9e2a"
CANARY_MID = "MB-DIAG-MID-c41b80d5"
CANARY_END = "MB-DIAG-END-aa19f6b4"

PostFn = Callable[[bytes, str, int], tuple[int, bytes, list[dict[str, Any]]]]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def build_chat_payload(
    *,
    user_text: str,
    num_ctx: int,
    num_predict: int,
    model_tag: str = B_TAG,
) -> dict[str, Any]:
    return {
        "model": model_tag,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "stream": True,
        "think": False,
        "keep_alive": 0,
        "truncate": False,
        "shift": False,
        "options": {
            "num_ctx": int(num_ctx),
            "num_predict": int(num_predict),
            "temperature": TEMPERATURE,
            "seed": SEED,
        },
    }


def assert_top_level_controls(payload: dict[str, Any]) -> None:
    if "truncate" in (payload.get("options") or {}):
        raise I11A0Error("truncate must be top-level, not inside options")
    if "shift" in (payload.get("options") or {}):
        raise I11A0Error("shift must be top-level, not inside options")
    if payload.get("truncate") is not False or payload.get("shift") is not False:
        raise I11A0Error("truncate and shift must be JSON false at top level")


def capture_request(payload: dict[str, Any], *, execution_id: str, role: str) -> dict[str, Any]:
    assert_top_level_controls(payload)
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return {
        "execution_id": execution_id,
        "role": role,
        "captured_at_utc": utc_now(),
        "endpoint": "/api/chat",
        "request_json": payload,
        "request_body_utf8": encoded.decode("utf-8"),
        "request_body_sha256": hashlib.sha256(encoded).hexdigest(),
        "request_body_bytes": len(encoded),
        "truncate_top_level": payload.get("truncate") is False,
        "shift_top_level": payload.get("shift") is False,
        "keep_alive": payload.get("keep_alive"),
        "options_keys": sorted((payload.get("options") or {}).keys()),
    }


def fields_unsupported_from_http(status: int, body_text: str) -> str | None:
    lowered = body_text.lower()
    if status >= 400 and any(key in lowered for key in ("truncate", "shift", "unknown field", "invalid", "unmarshal")):
        return f"http_{status}_mentions_truncate_or_shift"
    if status >= 400:
        return f"http_{status}"
    return None


def synthetic_overflow_user_text(*, num_ctx: int = DIAGNOSTIC_B_NUM_CTX) -> str:
    filler = ("alpha-bravo-charlie-delta-echo-foxtrot-golf " * 80)
    target_chars = max(8000, int(num_ctx) * 8)
    body = (filler * ((target_chars // len(filler)) + 3))[:target_chars]
    return (
        f"{CANARY_BEGIN}\nThis is a synthetic fail-closed overflow diagnostic. "
        f"It is not household email and not a Peggy scenario.\n{body}\n"
        f"{CANARY_MID}\n{body}\n{CANARY_END}\n"
    )


def default_post(encoded: bytes, base_url: str, timeout: int) -> tuple[int, bytes, list[dict[str, Any]]]:
    http = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events: list[dict[str, Any]] = []
    try:
        with urllib.request.urlopen(http, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
            raw_chunks: list[bytes] = []
            for raw_line in response:
                raw_chunks.append(raw_line)
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    events.append({"unparsed": line})
            return status, b"".join(raw_chunks), events
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return int(exc.code), body, [{"error": body.decode("utf-8", errors="replace"), "http_status": int(exc.code)}]


def host_ram_guard(ram: dict[str, Any] | None = None) -> dict[str, Any]:
    snap = ram or read_system_ram()
    available = snap.get("available_gb")
    stop = available is not None and float(available) <= RAM_STOP_AVAILABLE_GB
    return {
        "system_ram": snap,
        "stop_before_inference": stop,
        "stop_threshold_available_gb": RAM_STOP_AVAILABLE_GB,
        "proposed_diagnostic_minimum_available_gb": RAM_PROPOSED_GUARD_GB,
        "reason": "flightsim_available_ram_at_or_below_1_to_2_gb" if stop else None,
        "high_ram_use_is_not_cpu_offload": True,
    }


def fail_closed_overflow_outcome(*, http_status: int, events: list[dict[str, Any]], log_verdict: dict[str, Any]) -> dict[str, Any]:
    generated = any(bool((ev.get("message") or {}).get("content")) for ev in events if isinstance(ev, dict))
    done = next((ev for ev in reversed(events) if isinstance(ev, dict) and ev.get("done")), None)
    truncated_log = log_verdict.get("classification") == INVALID_TRUNCATED or log_verdict.get("truncation_occurred") is True
    if truncated_log and (generated or (done and done.get("prompt_eval_count"))):
        return {
            "ok": False,
            "fields_effective": False,
            "classification": "truncate_shift_fields_ineffective_silent_truncation",
            "reason": "ollama_generated_after_truncation_despite_truncate_false_shift_false",
        }
    if http_status >= 400 or (done and done.get("error")):
        return {
            "ok": True,
            "fields_effective": True,
            "classification": "fail_closed_overflow_rejected",
            "reason": "explicit_request_or_server_failure",
        }
    if generated and not truncated_log:
        return {
            "ok": False,
            "fields_effective": False,
            "classification": "overflow_unexpectedly_succeeded",
            "reason": "generation_completed_without_fit",
        }
    return {
        "ok": True,
        "fields_effective": True,
        "classification": "fail_closed_overflow_rejected",
        "reason": "no_truncated_generation",
    }


def i14_18k_user_packet(export_dir: Path | str | None = None) -> dict[str, Any]:
    from memorybox.ask.i11a.i11a0_full_prompt_v4 import i14_export_candidates
    from memorybox.ask.i11a.i11a0_gate3 import NestedMessagePacker
    from memorybox.ask.i11a.i11a0_i14_source import load_frozen_prompt_messages

    root = Path(export_dir) if export_dir else next((p for p in i14_export_candidates() if p.is_dir()), None)
    if root is None:
        raise I11A0Error("pinned I14 cleaned export is not available")
    verify_pinned_i14_export(root)
    packet = NestedMessagePacker(load_frozen_prompt_messages(root)).packet_for_target(18000)
    user = render_user_message(
        packet_id="no-trunc-diag-18k",
        packet_role="no_truncation_diagnostic_a",
        time_start=packet.time_start,
        time_end=packet.time_end,
        partial_context=bool(packet.partial_context),
        partial_boundary_note=packet.partial_boundary_note,
        evidence_ids=list(packet.evidence_ids),
        evidence_text=packet.text,
    )
    return {
        "export_dir": str(root),
        "estimated_evidence_tokens": packet.estimated_evidence_tokens,
        "evidence_bytes": packet.evidence_bytes,
        "evidence_characters": packet.evidence_characters,
        "message_count": packet.message_count,
        "packet_sha256": packet.sha256,
        "partial_context": packet.partial_context,
        "user_text": user,
        "packet": packet,
    }


def estimator_note(observed_complete: int = 12201, evidence_bytes: int = 34657) -> dict[str, Any]:
    old = float(FROZEN_MAX_TOKENS_PER_EVIDENCE_BYTE)
    observed_rate = float(observed_complete) / float(evidence_bytes)
    revised = max(old, observed_rate)
    def pred(nbytes: int, rate: float) -> int:
        return int(math.ceil(nbytes * rate * (1.0 + RATE_GUARD) - 1e-12))
    return {
        "v4_predicted": 11340,
        "observed_complete_if_log_confirms": observed_complete,
        "error_tokens": observed_complete - 11340,
        "error_percent": round(100.0 * (observed_complete - 11340) / 11340, 2),
        "do_not_enlarge_ladder": True,
        "update_envelope_only_after_founder_review": True,
        "do_not_calibrate_from_truncated_prompt_eval_count": True,
        "frozen_rate": old,
        "observed_rate": observed_rate,
        "proposed_revised_rate": revised,
        "historical_18k_complete_from_logs": HISTORICAL_18K_COMPLETE,
        "policy_a_required_num_ctx_for_24109": int(math.ceil((HISTORICAL_18K_COMPLETE + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS) / 256) * 256),
        "note": "If founder accepts the 8K observed rate, recompute 18K predicted from actual 18K evidence bytes; do not apply until review.",
    }


def diagnostic_request_plans(*, export_dir: Path | str | None = None) -> dict[str, Any]:
    info = None
    try:
        packed = i14_18k_user_packet(export_dir)
        info = {k: packed[k] for k in packed if k not in {"user_text", "packet"}}
        user_a = packed["user_text"]
    except Exception as exc:
        user_a = "(I14 export unavailable on this machine; FlightSim uses frozen export)"
        info = {"error": str(exc)}
    payload_a = build_chat_payload(user_text=user_a if isinstance(user_a, str) else "", num_ctx=DIAGNOSTIC_A_NUM_CTX, num_predict=DIAGNOSTIC_A_NUM_PREDICT)
    payload_b = build_chat_payload(user_text=synthetic_overflow_user_text(), num_ctx=DIAGNOSTIC_B_NUM_CTX, num_predict=DIAGNOSTIC_B_NUM_PREDICT)
    return {
        "experiment_id": EXPERIMENT_ID,
        "planner_not_reinstated": True,
        "policy_a": "predicted+2500+1500<=num_ctx plus truncate=false shift=false, num_ctx<=40960, VRAM<22.5, post-run log no truncation",
        "policy_b": "explicit controls ineffective; do not accept half-window as production; workaround or other runtime",
        "diagnostic_a": {
            "why": "24109 > half of 28416 (14210) and 24109 < 28416",
            "packet": info,
            "num_ctx": DIAGNOSTIC_A_NUM_CTX,
            "num_predict": DIAGNOSTIC_A_NUM_PREDICT,
            "half_window": DIAGNOSTIC_A_HALF,
            "expected_complete_prompt_tokens": HISTORICAL_18K_COMPLETE,
            "keep_alive": 0,
            "thinking": "off",
            "temperature": TEMPERATURE,
            "seed": SEED,
            "truncate": False,
            "shift": False,
            "top_level_not_options": True,
            "request_json_template_keys": sorted(payload_a.keys()),
        },
        "diagnostic_b": {
            "run_only_if_a_passes_and_fields_active": True,
            "synthetic_not_family_evidence": True,
            "canaries": [CANARY_BEGIN, CANARY_MID, CANARY_END],
            "num_ctx": DIAGNOSTIC_B_NUM_CTX,
            "num_predict": DIAGNOSTIC_B_NUM_PREDICT,
            "half_window": DIAGNOSTIC_B_HALF,
            "expected": "explicit failure; no successful truncated generation",
            "truncate": False,
            "shift": False,
            "request_json_template_keys": sorted(payload_b.keys()),
        },
        "estimator": estimator_note(),
        "vram_release_slack_gb": VRAM_RELEASE_SLACK_GB,
    }


def run_no_truncation_diagnostic(
    *,
    confirm_benchmark: bool,
    ollama_base_url: str,
    i14_export: str | None,
    results_dir: Path | str,
    post_fn: PostFn | None = None,
    skip_live: bool = False,
) -> dict[str, Any]:
    if not confirm_benchmark:
        raise InferenceNotAuthorized("pass --confirm-benchmark on FlightSim to run the diagnostic")
    url = require_literal_loopback_ollama_url(ollama_base_url)
    require_flightsim_host_affinity(url)
    if skip_live:
        raise I11A0Error("skip_live is for tests; live path was not entered")
    host = capture_clean_ladder_host_state()
    ram_guard = host_ram_guard(host.get("system_ram"))
    out = Path(results_dir)
    out.mkdir(parents=True, exist_ok=True)
    if ram_guard["stop_before_inference"]:
        payload = {
            "ok": False,
            "stopped_before_inference": True,
            "host": host,
            "ram_guard": ram_guard,
            "ladder_resumed": False,
        }
        (out / "diagnostic_stop.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload
    inventory = inventory_installed_models(base_url=url)
    row = next((item for item in (inventory.get("models") or []) if str(item.get("tag") or item.get("name") or "") == B_TAG), None)
    if row is None:
        raise I11A0Error("qwen3:14b-q8_0 is not installed")
    digest = str(row.get("digest") or "")
    if PINNED_B_DIGEST not in digest:
        raise I11A0Error("installed Qwen B digest does not match the pinned digest")
    spec_meta = {"tag": B_TAG, "digest": digest}
    packed = i14_18k_user_packet(i14_export)
    exec_a = new_execution_id(test_case="no-trunc-diag-a", hostname="FlightSim", started_at_utc=utc_now())
    payload_a = build_chat_payload(user_text=packed["user_text"], num_ctx=DIAGNOSTIC_A_NUM_CTX, num_predict=DIAGNOSTIC_A_NUM_PREDICT)
    capture_a = capture_request(payload_a, execution_id=exec_a, role="diagnostic_a")
    log_snap = snapshot_log(execution_id=exec_a, model_tag=B_TAG, digest=PINNED_B_DIGEST, num_ctx=DIAGNOSTIC_A_NUM_CTX, request_hash=capture_a["request_body_sha256"])
    baseline = read_nvidia_snapshot()
    encoded = json.dumps(payload_a, ensure_ascii=False).encode("utf-8")
    poster = post_fn or default_post
    status, raw, events = poster(encoded, url, TIMEOUT_SECONDS)
    unsupported = fields_unsupported_from_http(status, raw.decode("utf-8", errors="replace"))
    last = events[-1] if events else {}
    pec = last.get("prompt_eval_count") if isinstance(last, dict) else None
    log_v = classify_appended_log(log_snap, num_ctx=DIAGNOSTIC_A_NUM_CTX, prompt_eval_count=None if pec is None else int(pec), predicted_complete=HISTORICAL_18K_COMPLETE)
    loaded_ps = read_ollama_ps(url)
    placement = interpret_ollama_placement(loaded_ps, tag=B_TAG, digest=PINNED_B_DIGEST, queried_while_loaded=True)
    peak = read_nvidia_snapshot()
    unload = verify_unload(
        base_url=url,
        tag=B_TAG,
        in_request_peak_vram_gb=peak.get("memory_used_gb"),
        pre_load_baseline_vram_gb=baseline.get("memory_used_gb"),
        pre_unload_vram_gb=peak.get("memory_used_gb"),
    )
    a_dir = out / exec_a
    a_dir.mkdir(parents=True, exist_ok=True)
    record_a = {
        "role": "diagnostic_a",
        "execution_id": exec_a,
        "http_status": status,
        "fields_unsupported": unsupported,
        "request_capture": capture_a,
        "log_snapshot": log_snap,
        "log_verdict": {k: v for k, v in log_v.items() if k != "parsed"},
        "last_event": last,
        "done_reason": last.get("done_reason") if isinstance(last, dict) else None,
        "prompt_eval_count": pec,
        "placement": placement,
        "unload": unload,
        "packet": {k: packed[k] for k in packed if k not in {"user_text", "packet"}},
        "host": host,
        "ram_guard": ram_guard,
        "spec_meta": spec_meta,
    }
    (a_dir / "request_capture.json").write_text(json.dumps(capture_a, indent=2) + "\n", encoding="utf-8")
    (a_dir / "run_record.json").write_text(json.dumps(record_a, indent=2, default=str) + "\n", encoding="utf-8")
    if unsupported:
        summary = {
            "ok": False,
            "stopped": True,
            "reason": unsupported,
            "diagnostic_a": record_a,
            "diagnostic_b_ran": False,
            "ladder_resumed": False,
        }
        (out / "diagnostic_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
        return summary
    a_ok = (
        log_v.get("passed") is True
        and log_v.get("no_truncation_proven") is True
        and pec is not None
        and int(pec) > DIAGNOSTIC_A_HALF
        and placement.get("gpu_resident") is True
        and placement.get("cpu_offload") is False
        and (peak.get("memory_used_gb") or 0) < VRAM_CEILING_GB
        and unload.get("classification") == "clean_unload_settled_vram"
        and last.get("done_reason")
    )
    if not a_ok:
        summary = {
            "ok": False,
            "diagnostic_a_passed": False,
            "diagnostic_b_ran": False,
            "diagnostic_a": record_a,
            "ladder_resumed": False,
        }
        (out / "diagnostic_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
        return summary
    exec_b = new_execution_id(test_case="no-trunc-diag-b", hostname="FlightSim", started_at_utc=utc_now())
    payload_b = build_chat_payload(user_text=synthetic_overflow_user_text(), num_ctx=DIAGNOSTIC_B_NUM_CTX, num_predict=DIAGNOSTIC_B_NUM_PREDICT)
    capture_b = capture_request(payload_b, execution_id=exec_b, role="diagnostic_b")
    log_snap_b = snapshot_log(execution_id=exec_b, model_tag=B_TAG, digest=PINNED_B_DIGEST, num_ctx=DIAGNOSTIC_B_NUM_CTX, request_hash=capture_b["request_body_sha256"])
    status_b, raw_b, events_b = poster(json.dumps(payload_b, ensure_ascii=False).encode("utf-8"), url, TIMEOUT_SECONDS)
    last_b = events_b[-1] if events_b else {}
    pec_b = last_b.get("prompt_eval_count") if isinstance(last_b, dict) else None
    log_b = classify_appended_log(log_snap_b, num_ctx=DIAGNOSTIC_B_NUM_CTX, prompt_eval_count=None if pec_b is None else int(pec_b))
    overflow = fail_closed_overflow_outcome(http_status=status_b, events=events_b, log_verdict=log_b)
    unload_b = verify_unload(
        base_url=url,
        tag=B_TAG,
        in_request_peak_vram_gb=None,
        pre_load_baseline_vram_gb=baseline.get("memory_used_gb"),
        pre_unload_vram_gb=None,
    )
    record_b = {
        "role": "diagnostic_b",
        "execution_id": exec_b,
        "http_status": status_b,
        "request_capture": capture_b,
        "log_verdict": {k: v for k, v in log_b.items() if k != "parsed"},
        "overflow": overflow,
        "last_event": last_b,
        "unload": unload_b,
    }
    b_dir = out / exec_b
    b_dir.mkdir(parents=True, exist_ok=True)
    (b_dir / "request_capture.json").write_text(json.dumps(capture_b, indent=2) + "\n", encoding="utf-8")
    (b_dir / "run_record.json").write_text(json.dumps(record_b, indent=2, default=str) + "\n", encoding="utf-8")
    summary = {
        "ok": bool(overflow.get("ok")),
        "diagnostic_a_passed": True,
        "diagnostic_b_ran": True,
        "fields_effective": overflow.get("fields_effective"),
        "diagnostic_a": {"execution_id": exec_a, "prompt_eval_count": pec},
        "diagnostic_b": overflow,
        "ladder_resumed": False,
        "stop_ladder_if_fields_ineffective": overflow.get("fields_effective") is False,
    }
    (out / "diagnostic_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    return summary


def prove_no_truncation_diagnostic_offline() -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, cond: bool, detail: Any = None) -> None:
        checks.append(name)
        if not cond:
            problems.append(f"{name}: {detail}")

    half = truncation_limit(22784)
    ok("half_22784_is_11394", half == 11394, half)
    above = (
        "slot   operator(): id  0 | task 0 | new prompt, n_ctx_slot = 22784, n_keep = 4, task.n_tokens = 12201\n"
        "slot print_timing: id  0 | task 0 | prompt eval time =   14232.40 ms / 12201 tokens (    1.17 ms per token)\n"
        "slot      release: id  0 | task 0 | stop processing: n_tokens = 12936, truncated = 0\n"
    )
    v = classify_log_segment(above, num_ctx=22784, prompt_eval_count=12201, predicted_complete=11340)
    ok("above_half_not_auto_truncated", v["passed"] is True and v["above_half_context"] is True and v["classification"] == COMPLETE_EVALUATED, v)
    ok("log_confirmed_complete_above_half_valid", v.get("complete_log_tokens") == 12201 and v.get("truncation_occurred") is False, v)
    trunc = (
        'time=2026-09-27T17:07:09.904-05:00 level=WARN source=llama_server.go:318 '
        'msg="truncating input prompt" limit=1026 prompt=5000 keep=4 new=1026\n'
        "generated tokens anyway\n"
    )
    bad = classify_log_segment(trunc, num_ctx=2048, prompt_eval_count=1026)
    ok("successful_truncated_response_invalid", bad["passed"] is False and bad["classification"] == INVALID_TRUNCATED, bad)
    overflow = fail_closed_overflow_outcome(
        http_status=200,
        events=[{"message": {"content": "hello"}, "done": True, "prompt_eval_count": 1026, "done_reason": "stop"}],
        log_verdict=bad,
    )
    ok("overflow_truncate_false_must_fail_closed_if_truncated_generation", overflow["fields_effective"] is False, overflow)
    closed = fail_closed_overflow_outcome(
        http_status=400,
        events=[{"error": "prompt too long"}],
        log_verdict={"classification": "ollama_log_missing", "truncation_occurred": None},
    )
    ok("overflow_http_error_is_fail_closed_success", closed["ok"] is True and closed["classification"] == "fail_closed_overflow_rejected", closed)
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "server.log"
        log.write_text("prior historical truncating input prompt limit=15362 prompt=34872\n", encoding="utf-8")
        snap = snapshot_log(path=log, execution_id="t", model_tag=B_TAG, num_ctx=22784, request_hash="abc")
        log.write_text(log.read_text(encoding="utf-8") + above, encoding="utf-8")
        appended = classify_appended_log(snap, num_ctx=22784, prompt_eval_count=12201)
        ok("parses_only_appended_bytes", appended["passed"] is True and "34872" not in json.dumps(appended.get("parsed")), appended.get("reason"))
        log.write_text("rotated\n", encoding="utf-8")
        rot = classify_appended_log(snap, num_ctx=22784, prompt_eval_count=12201)
        ok("log_rotation_detected", rot["classification"] in {"ollama_log_rotated_or_replaced", "truncation_log_unverified"} or rot.get("segment_inspected") is False, rot)
    missing = classify_appended_log(
        {"available": False, "status": "ollama_log_missing", "byte_offset": None, "ollama_log_path": "nope"},
        num_ctx=22784,
        prompt_eval_count=12201,
    )
    ok("missing_log_cannot_pass", missing["passed"] is False and missing.get("no_truncation_proven") is False, missing)
    peaks: dict[str, float] = {"n": 20.75}

    def nvidia() -> dict[str, Any]:
        return {"memory_used_gb": peaks["n"], "available": True}

    def ps(_url: str) -> dict[str, Any]:
        if peaks["n"] > 5:
            return {"models": [{"name": B_TAG}]}
        return {"models": []}

    def sleeper(_s: float) -> None:
        peaks["n"] = 2.6

    from memorybox.ask.i11a.i11a0_unload_verify import verify_unload as vu

    unload = vu(
        base_url="http://127.0.0.1:11434",
        tag=B_TAG,
        in_request_peak_vram_gb=20.75,
        pre_load_baseline_vram_gb=2.625,
        pre_unload_vram_gb=20.75,
        unload_fn=lambda *_a, **_k: 0.01,
        ps_fn=ps,
        nvidia_fn=nvidia,
        sleep_fn=sleeper,
        poll_seconds=2,
        max_seconds=8,
    )
    ok(
        "unload_preserves_in_request_peak",
        unload["in_request_peak_vram_gb"] == 20.75 and unload["settled_post_unload_vram_gb"] == 2.6,
        unload,
    )
    payload = build_chat_payload(user_text="x", num_ctx=28416, num_predict=256)
    ok("truncate_shift_top_level", payload.get("truncate") is False and "truncate" not in payload["options"], payload)
    ok("no_model_call", True)
    return {"ok": not problems, "checks": checks, "problems": problems, "models_called": False, "ladder_resumed": False}
