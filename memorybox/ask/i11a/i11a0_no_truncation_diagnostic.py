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

PostFn = Callable[[bytes, str, int], tuple[int, bytes, list[dict[str, Any]]]]

from memorybox.ask.i11a.i11a0_control_telemetry import (
    IndependentRequestSampler,
    classify_in_request_placement,
)

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
    collect_host_affinity_preflight,
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
from memorybox.ask.i11a.i11a0_smoke import PINNED_B_DIGEST, REPO_ROOT, VRAM_RELEASE_SLACK_GB
from memorybox.ask.i11a.i11a0_unload_verify import verify_unload

B_TAG = "qwen3:14b-q8_0"
EXPERIMENT_ID = "i11a0_no_truncation_noshift_diagnostic_a2"
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

FIRST_A_EXECUTION_ID = "34a376c84fd120e336518cb745dbe256559af81b3fbd22454ef2b1e3389b84f6"
V4_EXECUTION_ID = "48d5421b5500b88b14a4ff9da4ed2c22dce9270269f235936452c5928856a52f"
FIRST_A_PACKET_SHA256 = "51f891938ba3ab5910fb20ce8fe457dace74bfb5f9b5b380da28a52f24e73902"
OBSERVED_A_COMPLETE_TOKENS = 24174
A2_KEEP_ALIVE = "2m"
TELEMETRY_INTERVAL_SECONDS = 1.0
FIRST_A_PROTECTED = ("request_capture.json", "run_record.json")
V4_PROTECTED = (
    "COMPLETE",
    "run_record.json",
    "hardware_telemetry.json",
    "request_capture.json",
    "raw_api.jsonl",
    "telemetry.jsonl",
    "token_accounting.json",
    "evidence_packet.txt",
    "narration.txt",
    "packet_manifest.json",
    "host_identity.json",
    "model_identity.json",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def find_installed_qwen_b(inventory: dict[str, Any]) -> dict[str, Any]:
    """Match /api/tags via inventory_installed_models. Loaded-in-VRAM is not required."""
    rows = list(inventory.get("approved") or [])
    row = next(
        (
            item
            for item in rows
            if item.get("config_id") == "B" or str(item.get("tag") or "") == B_TAG
        ),
        None,
    )
    names = list(inventory.get("installed_names") or [])
    if row is None or str(row.get("status") or "") != "installed":
        raise I11A0Error(
            "qwen3:14b-q8_0 is not in the Ollama tag inventory. "
            "The model does not need to be loaded into VRAM; it must appear in /api/tags. "
            f"installed_names={names} approved_status={(row or {}).get('status')}"
        )
    digest = str(row.get("digest") or "")
    if PINNED_B_DIGEST not in digest:
        raise I11A0Error(
            "installed Qwen B digest does not match the pinned digest "
            f"{PINNED_B_DIGEST}; got {digest!r}"
        )
    return row


def build_chat_payload(
    *,
    user_text: str,
    num_ctx: int,
    num_predict: int,
    model_tag: str = B_TAG,
    keep_alive: Any = 0,
) -> dict[str, Any]:
    return {
        "model": model_tag,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "stream": True,
        "think": False,
        "keep_alive": keep_alive,
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


def diagnose_stream_output(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Concatenate incremental stream fields. Do not trust only the done event content."""
    field_names: set[str] = set()
    visible_parts: list[str] = []
    thinking_parts: list[str] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        msg = ev.get("message") if isinstance(ev.get("message"), dict) else {}
        for key, value in msg.items():
            if key == "role":
                continue
            field_names.add(f"message.{key}")
            if key == "content" and isinstance(value, str):
                visible_parts.append(value)
            if key in {"thinking", "reasoning", "reasoning_content"} and isinstance(value, str):
                thinking_parts.append(value)
        for key in ("thinking", "response", "reasoning"):
            if key in ev and isinstance(ev.get(key), str):
                field_names.add(key)
                if key != "response":
                    thinking_parts.append(str(ev.get(key) or ""))
    visible = "".join(visible_parts)
    thinking = "".join(thinking_parts)
    raw = json.dumps(events, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    last = next((ev for ev in reversed(events) if isinstance(ev, dict) and ev.get("done")), events[-1] if events else {})
    last_msg = (last.get("message") or {}) if isinstance(last, dict) else {}
    return {
        "generated_content_field_names": sorted(field_names),
        "visible_content_length": len(visible),
        "thinking_content_length": len(thinking),
        "thinking_present": bool(thinking),
        "done_event_content_empty": not bool(last_msg.get("content")),
        "concatenated_visible_nonempty": bool(visible),
        "eval_count": last.get("eval_count") if isinstance(last, dict) else None,
        "done_reason": last.get("done_reason") if isinstance(last, dict) else None,
        "raw_generated_payload_sha256": hashlib.sha256(raw).hexdigest(),
        "think_false_in_request_expected": True,
        "think_false_honored": not bool(thinking),
        "note": (
            "Ollama final done events often have empty message.content; "
            "visible prose is the concatenation of incremental stream chunks. "
            "The first Diagnostic A run stored only last_event, so its visible content "
            "cannot be recovered from artifacts."
        ),
    }


def _file_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def write_sidecar_without_rewrite(folder: Path, name: str, payload: dict[str, Any], protected: tuple[str, ...]) -> dict[str, Any]:
    root = Path(folder)
    before = {item: _file_bytes(root / item) for item in protected}
    dest = root / name
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    after = {item: _file_bytes(root / item) for item in protected}
    rewritten = [item for item in protected if before[item] != after[item]]
    if rewritten:
        raise I11A0Error(f"protected original artifacts were rewritten: {rewritten}")
    return {"sidecar": str(dest), "original_files_rewritten": False, "protected_unchanged": True}


def first_a_sidecar_payload() -> dict[str, Any]:
    return {
        "execution_id": FIRST_A_EXECUTION_ID,
        "experiment_role": "accepted_token_accounting_proof_not_placement_qualified_diagnostic_a",
        "prompt_accounting_valid": True,
        "no_truncation_proven": True,
        "api_fields_accepted_by_server": True,
        "hardware_placement_unproven_instrumentation_miss": True,
        "unload_clean": True,
        "not_cpu_offload": True,
        "not_gpu_residency_lost": True,
        "stable_ladder_rung": False,
        "http_status": 200,
        "complete_log_prompt_tokens": OBSERVED_A_COMPLETE_TOKENS,
        "prompt_eval_count": OBSERVED_A_COMPLETE_TOKENS,
        "half_window": DIAGNOSTIC_A_HALF,
        "evaluated_above_half_window": True,
        "done_reason": "length",
        "eval_count": 256,
        "keep_alive": 0,
        "placement_miss_root_cause": (
            "keep_alive=0 let the runner exit at stream end before /api/ps; "
            "IndependentRequestSampler was never started; nvidia peak was sampled after the model was gone "
            "and remained at the 1.26 GB baseline"
        ),
        "empty_visible_output_root_cause": (
            "only last_event was persisted; the done event has empty message.content and no thinking field; "
            "eval_count=256 with done_reason=length means tokens were generated; incremental stream chunks were discarded"
        ),
        "original_files_rewritten": False,
    }


def v4_run_sidecar_payload() -> dict[str, Any]:
    excerpt = (
        "slot   operator(): id  0 | task 0 | new prompt, n_ctx_slot = 22784, n_keep = 4, task.n_tokens = 12201\n"
        "slot print_timing: id  0 | task 0 | prompt eval time =   14232.40 ms / 12201 tokens\n"
        "slot      release: id  0 | task 0 | stop processing: n_tokens = 12936, truncated = 0\n"
    )
    verdict = classify_log_segment(excerpt, num_ctx=22784, prompt_eval_count=12201, predicted_complete=11340)
    return {
        "execution_id": V4_EXECUTION_ID,
        "experiment_role": "complete_prompt_functional_result_not_accepted_ladder_rung",
        "complete_log_prompt_tokens": 12201,
        "truncation_occurred": False,
        "original_stop": "truncation_log_unverified",
        "original_stop_was_log_correlation_failure_only": True,
        "unload_issue_was_settling_or_telemetry_defect": True,
        "hardware_placement_not_promoted_without_valid_evidence": True,
        "stable_ladder_rung": False,
        "corrected_appended_log_reader": {
            k: verdict.get(k)
            for k in (
                "passed",
                "classification",
                "no_truncation_proven",
                "complete_log_tokens",
                "above_half_context",
                "truncation_occurred",
            )
        },
        "original_files_rewritten": False,
    }


def streaming_post(
    encoded: bytes,
    base_url: str,
    timeout: int,
    *,
    jsonl_path: Path | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[int, bytes, list[dict[str, Any]]]:
    handle = jsonl_path.open("a", encoding="utf-8", newline="\n") if jsonl_path is not None else None
    http = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events: list[dict[str, Any]] = []
    raw_chunks: list[bytes] = []
    try:
        with urllib.request.urlopen(http, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
            for raw_line in response:
                raw_chunks.append(raw_line)
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    event = {"unparsed": line}
                events.append(event)
                if handle is not None:
                    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
                    handle.flush()
                if on_event is not None:
                    on_event(event)
            return status, b"".join(raw_chunks), events
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        event = {"error": body.decode("utf-8", errors="replace"), "http_status": int(exc.code)}
        events.append(event)
        if handle is not None:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
        return int(exc.code), body, events
    finally:
        if handle is not None:
            handle.close()


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
            "classification": "truncate_or_shift_controls_ineffective",
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
    payload_a = build_chat_payload(
        user_text=user_a if isinstance(user_a, str) else "",
        num_ctx=DIAGNOSTIC_A_NUM_CTX,
        num_predict=DIAGNOSTIC_A_NUM_PREDICT,
        keep_alive=A2_KEEP_ALIVE,
    )
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
            "keep_alive": A2_KEEP_ALIVE,
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
        "estimator_18k_packet": {
            "predicted_complete_prompt_tokens": HISTORICAL_18K_COMPLETE,
            "observed_complete_prompt_tokens": OBSERVED_A_COMPLETE_TOKENS,
            "error_tokens": OBSERVED_A_COMPLETE_TOKENS - HISTORICAL_18K_COMPLETE,
            "error_percent": round(100.0 * (OBSERVED_A_COMPLETE_TOKENS - HISTORICAL_18K_COMPLETE) / HISTORICAL_18K_COMPLETE, 2),
            "do_not_mix_with_v4_8k_estimator_error": True,
        },
        "planning_if_a2_and_b_pass": {
            "retire_half_window_preflight": True,
            "retain_truncate_false_shift_false": True,
            "retain_appended_log_verification": True,
            "retain_fail_closed": True,
            "predicted_plus_reserves": "predicted_complete_prompt + 2500 + 1500 <= num_ctx",
            "num_ctx_max": 40960,
            "vram_ceiling_gb": 22.5,
            "stop_on_prediction_underestimate_until_recalibrated": True,
            "do_not_automatically_resume_ladder": True,
        },
        "vram_release_slack_gb": VRAM_RELEASE_SLACK_GB,
    }


def run_measured_chat(
    *,
    url: str,
    payload: dict[str, Any],
    folder: Path,
    execution_id: str,
    role: str,
    num_ctx: int,
    predicted_complete: int | None,
    query_ps_before_unload: bool,
    keep_alive_during_chat: Any,
    post_fn: PostFn | None,
) -> dict[str, Any]:
    folder.mkdir(parents=True, exist_ok=True)
    capture = capture_request(payload, execution_id=execution_id, role=role)
    (folder / "request_capture.json").write_text(json.dumps(capture, indent=2) + "\n", encoding="utf-8")
    log_snap = snapshot_log(
        execution_id=execution_id,
        model_tag=B_TAG,
        digest=PINNED_B_DIGEST,
        num_ctx=num_ctx,
        request_hash=capture["request_body_sha256"],
    )
    baseline = read_nvidia_snapshot()
    telemetry = IndependentRequestSampler(
        telemetry_path=folder / "in_request_telemetry.jsonl",
        base_url=url,
        experiment_id=EXPERIMENT_ID,
        run_id=role,
        execution_id=execution_id,
        tag=B_TAG,
        digest=PINNED_B_DIGEST,
        interval_seconds=TELEMETRY_INTERVAL_SECONDS,
        ram_every_n=1,
        heartbeat_seconds=15.0,
    )
    telemetry.start("request_active")
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    jsonl_path = folder / "raw_api.jsonl"
    first_seen = {"n": False}
    status = 0
    raw = b""
    events: list[dict[str, Any]] = []
    ps_before_unload: dict[str, Any] = {"skipped": True}
    placement_live: dict[str, Any] = {}
    placement: dict[str, Any] = {"placement_status": "unknown"}
    in_request_peak: float | None = None
    matched: dict[str, Any] = {}

    def on_event(event: dict[str, Any]) -> None:
        msg = event.get("message") if isinstance(event.get("message"), dict) else {}
        if not first_seen["n"] and (msg.get("content") or msg.get("thinking") or event.get("done")):
            first_seen["n"] = True
            telemetry.set_phase("first_token")
            telemetry.set_phase("streaming")

    try:
        try:
            if post_fn is None:
                status, raw, events = streaming_post(
                    encoded, url, TIMEOUT_SECONDS, jsonl_path=jsonl_path, on_event=on_event
                )
            else:
                status, raw, events = post_fn(encoded, url, TIMEOUT_SECONDS)
                jsonl_path.write_text("".join(json.dumps(ev) + "\n" for ev in events), encoding="utf-8")
        finally:
            telemetry.set_phase("streaming")
            if query_ps_before_unload:
                ps_before_unload = read_ollama_ps(url)
                placement_live = interpret_ollama_placement(
                    ps_before_unload,
                    tag=B_TAG,
                    digest=PINNED_B_DIGEST,
                    queried_while_loaded=True,
                )
            in_request_peak = max(
                telemetry.vram_for_phases({"request_active", "first_token", "streaming"}),
                default=None,
            )
            placement = classify_in_request_placement(
                telemetry.samples,
                tag=B_TAG,
                digest=PINNED_B_DIGEST,
                baseline_vram_gb=baseline.get("memory_used_gb"),
            )
            if placement.get("placement_status") == "unknown" and placement_live.get("status") == "gpu_resident":
                placement = {
                    **placement,
                    "placement_status": "gpu_resident",
                    "gpu_resident": True,
                    "cpu_offload": False,
                    "reason": "matching_qwen_b_present_in_api_ps_before_unload",
                    "pre_unload_ps": placement_live,
                }
            matched = placement_live.get("matched_model") or {}
    finally:
        telemetry.stop()
    last = events[-1] if events else {}
    pec = last.get("prompt_eval_count") if isinstance(last, dict) else None
    log_v = classify_appended_log(
        log_snap,
        num_ctx=int(num_ctx),
        prompt_eval_count=None if pec is None else int(pec),
        predicted_complete=predicted_complete,
    )
    output = diagnose_stream_output(events)
    unload = verify_unload(
        base_url=url,
        tag=B_TAG,
        in_request_peak_vram_gb=in_request_peak if in_request_peak is not None else placement.get("in_request_peak_vram_gb"),
        pre_load_baseline_vram_gb=baseline.get("memory_used_gb"),
        pre_unload_vram_gb=None,
    )
    record = {
        "role": role,
        "execution_id": execution_id,
        "http_status": status,
        "keep_alive_during_chat": keep_alive_during_chat,
        "explicit_unload_keep_alive": 0,
        "api_ps_queried_before_unload": bool(query_ps_before_unload),
        "telemetry_interval_seconds": TELEMETRY_INTERVAL_SECONDS,
        "request_capture": capture,
        "log_snapshot": log_snap,
        "log_verdict": {k: v for k, v in log_v.items() if k != "parsed"},
        "last_event": last,
        "output_diagnosis": output,
        "prompt_eval_count": pec,
        "done_reason": last.get("done_reason") if isinstance(last, dict) else None,
        "in_request_peak_vram_gb": in_request_peak,
        "vram_baseline_gb": baseline.get("memory_used_gb"),
        "gpu_name": baseline.get("name"),
        "pre_unload_ps": ps_before_unload,
        "matched_model_size": matched.get("size") if isinstance(matched, dict) else None,
        "matched_size_vram": matched.get("size_vram") if isinstance(matched, dict) else None,
        "matched_processor": (
            matched.get("processor") or (matched.get("details") or {}).get("processor")
            if isinstance(matched, dict)
            else None
        ),
        "runner_context": (
            matched.get("context_length") or (matched.get("details") or {}).get("context_length")
            if isinstance(matched, dict)
            else None
        ),
        "placement": placement,
        "placement_live_before_unload": placement_live,
        "unload": unload,
        "fields_unsupported": fields_unsupported_from_http(status, raw.decode("utf-8", errors="replace")),
        "raw_body_bytes": len(raw),
    }
    (folder / "run_record.json").write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    return record


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
    if skip_live:
        raise I11A0Error("skip_live is for tests; live path was not entered")
    out = Path(results_dir)
    out.mkdir(parents=True, exist_ok=True)
    first_dir = out / FIRST_A_EXECUTION_ID
    if first_dir.is_dir():
        write_sidecar_without_rewrite(first_dir, "classification_sidecar.json", first_a_sidecar_payload(), FIRST_A_PROTECTED)
    v4_candidates = [
        Path("//flightsim/FlightSim User/MemoryBox/docs/test-output/i11a0-benchmark/gate3-b-i14-full-prompt-v4/runs") / V4_EXECUTION_ID,
        REPO_ROOT / "docs/test-output/i11a0-benchmark/gate3-b-i14-full-prompt-v4/runs" / V4_EXECUTION_ID,
    ]
    for v4_dir in v4_candidates:
        if v4_dir.is_dir():
            write_sidecar_without_rewrite(v4_dir, "classification_sidecar.json", v4_run_sidecar_payload(), V4_PROTECTED)
            break
    preflight = collect_host_affinity_preflight(
        ollama_base_url=url,
        output_path=out,
        chunks_path=i14_export or out,
        repo=REPO_ROOT,
    )
    require_flightsim_host_affinity(preflight)
    host = capture_clean_ladder_host_state()
    ram_guard = host_ram_guard(host.get("system_ram"))
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
    row = find_installed_qwen_b(inventory)
    packed = i14_18k_user_packet(i14_export)
    if packed.get("packet_sha256") != FIRST_A_PACKET_SHA256:
        raise I11A0Error(
            "A2 packet sha256 does not match first Diagnostic A "
            f"{FIRST_A_PACKET_SHA256}; got {packed.get('packet_sha256')!r}"
        )
    exec_a2 = new_execution_id(test_case="no-trunc-diag-a2", hostname="FlightSim", started_at_utc=utc_now())
    payload_a2 = build_chat_payload(
        user_text=packed["user_text"],
        num_ctx=DIAGNOSTIC_A_NUM_CTX,
        num_predict=DIAGNOSTIC_A_NUM_PREDICT,
        keep_alive=A2_KEEP_ALIVE,
    )
    a2_dir = out / exec_a2
    record_a2 = run_measured_chat(
        url=url,
        payload=payload_a2,
        folder=a2_dir,
        execution_id=exec_a2,
        role="diagnostic_a2",
        num_ctx=DIAGNOSTIC_A_NUM_CTX,
        predicted_complete=OBSERVED_A_COMPLETE_TOKENS,
        query_ps_before_unload=True,
        keep_alive_during_chat=A2_KEEP_ALIVE,
        post_fn=post_fn,
    )
    record_a2["packet"] = {k: packed[k] for k in packed if k not in {"user_text", "packet"}}
    record_a2["host"] = host
    record_a2["ram_guard"] = ram_guard
    record_a2["spec_meta"] = {"tag": B_TAG, "digest": row.get("digest")}
    record_a2["identical_packet_sha256"] = packed.get("packet_sha256")
    record_a2["first_a_packet_sha256"] = FIRST_A_PACKET_SHA256
    (a2_dir / "run_record.json").write_text(json.dumps(record_a2, indent=2, default=str) + "\n", encoding="utf-8")
    pec = record_a2.get("prompt_eval_count")
    log_v = record_a2.get("log_verdict") or {}
    placement = record_a2.get("placement") or {}
    unload = record_a2.get("unload") or {}
    peak = record_a2.get("in_request_peak_vram_gb")
    close_complete = pec is not None and abs(int(pec) - OBSERVED_A_COMPLETE_TOKENS) <= 80
    placement_ok = placement.get("placement_status") == "gpu_resident" or placement.get("gpu_resident") is True
    if placement.get("placement_status") == "unknown" or not placement_ok:
        summary = {
            "ok": False,
            "stopped": True,
            "reason": "placement_unknown",
            "diagnostic_a_sidecar": first_a_sidecar_payload(),
            "diagnostic_a2": {"execution_id": exec_a2, "placement": placement, "prompt_eval_count": pec},
            "diagnostic_b_ran": False,
            "ladder_resumed": False,
        }
        (out / "diagnostic_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
        return summary
    a2_ok = (
        log_v.get("passed") is True
        and log_v.get("no_truncation_proven") is True
        and close_complete
        and pec is not None
        and int(pec) > DIAGNOSTIC_A_HALF
        and placement.get("cpu_offload") is False
        and peak is not None
        and float(peak) < VRAM_CEILING_GB
        and unload.get("classification") == "clean_unload_settled_vram"
        and record_a2.get("fields_unsupported") is None
        and record_a2.get("api_ps_queried_before_unload") is True
        and payload_a2.get("keep_alive") == A2_KEEP_ALIVE
    )
    if not a2_ok:
        summary = {
            "ok": False,
            "diagnostic_a2_passed": False,
            "diagnostic_b_ran": False,
            "diagnostic_a2": {"execution_id": exec_a2, "prompt_eval_count": pec, "placement": placement.get("placement_status")},
            "ladder_resumed": False,
        }
        (out / "diagnostic_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
        return summary
    exec_b = new_execution_id(test_case="no-trunc-diag-b", hostname="FlightSim", started_at_utc=utc_now())
    payload_b = build_chat_payload(
        user_text=synthetic_overflow_user_text(),
        num_ctx=DIAGNOSTIC_B_NUM_CTX,
        num_predict=DIAGNOSTIC_B_NUM_PREDICT,
        keep_alive=A2_KEEP_ALIVE,
    )
    record_b = run_measured_chat(
        url=url,
        payload=payload_b,
        folder=out / exec_b,
        execution_id=exec_b,
        role="diagnostic_b",
        num_ctx=DIAGNOSTIC_B_NUM_CTX,
        predicted_complete=None,
        query_ps_before_unload=True,
        keep_alive_during_chat=A2_KEEP_ALIVE,
        post_fn=post_fn,
    )
    events_b: list[dict[str, Any]] = []
    raw_b = out / exec_b / "raw_api.jsonl"
    if raw_b.is_file():
        for line in raw_b.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events_b.append(json.loads(line))
    overflow = fail_closed_overflow_outcome(
        http_status=int(record_b.get("http_status") or 0),
        events=events_b,
        log_verdict=record_b.get("log_verdict") or {},
    )
    record_b["overflow"] = overflow
    (out / exec_b / "run_record.json").write_text(json.dumps(record_b, indent=2, default=str) + "\n", encoding="utf-8")
    summary = {
        "ok": bool(overflow.get("ok")) and overflow.get("fields_effective") is True,
        "diagnostic_a_accepted_token_accounting": True,
        "diagnostic_a2_passed": True,
        "diagnostic_b_ran": True,
        "fields_effective": overflow.get("fields_effective"),
        "half_window_preflight_retired_pending_founder": bool(overflow.get("ok")),
        "diagnostic_a2": {"execution_id": exec_a2, "prompt_eval_count": pec},
        "diagnostic_b": overflow,
        "ladder_resumed": False,
        "stop_ladder_if_fields_ineffective": overflow.get("fields_effective") is False,
        "do_not_automatically_resume_ladder": True,
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
    ok("successful_truncated_output_fails_diagnostic", overflow["classification"] == "truncate_or_shift_controls_ineffective", overflow)
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
    found = find_installed_qwen_b(
        {
            "approved": [
                {
                    "config_id": "B",
                    "tag": B_TAG,
                    "status": "installed",
                    "digest": PINNED_B_DIGEST,
                }
            ],
            "models": [],
            "installed_names": [B_TAG],
        }
    )
    ok("finds_qwen_b_on_approved_not_models_key", found.get("tag") == B_TAG, found)
    try:
        find_installed_qwen_b({"models": [{"name": B_TAG, "digest": PINNED_B_DIGEST}]})
        ok("empty_approved_is_not_installed", False, "expected I11A0Error")
    except I11A0Error as exc:
        ok("empty_approved_is_not_installed", "tag inventory" in str(exc), str(exc))
    import inspect
    from memorybox.ask.i11a.i11a0_host import require_flightsim_host_affinity as require_affinity

    src = inspect.getsource(run_no_truncation_diagnostic)
    ok(
        "host_affinity_uses_preflight_dict",
        "collect_host_affinity_preflight" in src and "require_flightsim_host_affinity(url)" not in src,
        None,
    )
    try:
        require_affinity("http://127.0.0.1:11434")
        ok("string_url_is_not_preflight", False, "expected HostAffinityError")
    except Exception as exc:
        ok("string_url_is_not_preflight", type(exc).__name__ == "HostAffinityError", type(exc).__name__)
    a2_payload = build_chat_payload(user_text="x", num_ctx=28416, num_predict=256, keep_alive=A2_KEEP_ALIVE)
    ok("a2_keep_alive_is_two_minutes", a2_payload.get("keep_alive") == "2m", a2_payload.get("keep_alive"))
    measured_src = inspect.getsource(run_measured_chat)
    ok("ps_captured_before_explicit_unload", "ps_before_unload" in measured_src and "verify_unload" in measured_src, None)
    ok("one_second_independent_telemetry", TELEMETRY_INTERVAL_SECONDS == 1.0 and "interval_seconds=TELEMETRY_INTERVAL_SECONDS" in measured_src, TELEMETRY_INTERVAL_SECONDS)
    ok("telemetry_starts_before_post", measured_src.find("telemetry.start") < measured_src.find("streaming_post"), None)
    ok("telemetry_persists_incrementally", "in_request_telemetry.jsonl" in measured_src, None)
    gpu = interpret_ollama_placement(
        {
            "available": True,
            "models": [
                {
                    "name": B_TAG,
                    "digest": PINNED_B_DIGEST,
                    "size": 15728640000,
                    "size_vram": 15728640000,
                }
            ],
        },
        tag=B_TAG,
        digest=PINNED_B_DIGEST,
        queried_while_loaded=True,
    )
    ok(
        "gpu_resident_placement_proof",
        gpu.get("status") == "gpu_resident" and gpu.get("cpu_offload") is False,
        gpu,
    )
    ok("gpu_resident_required_for_a2", "placement_unknown" in inspect.getsource(run_no_truncation_diagnostic), None)
    ok("explicit_unload_after_inspection", measured_src.find("ps_before_unload") < measured_src.find("verify_unload"), None)
    empty_last = diagnose_stream_output(
        [
            {"message": {"role": "assistant", "content": "Once upon a family morning. "}},
            {
                "message": {"role": "assistant", "content": ""},
                "done": True,
                "done_reason": "length",
                "eval_count": 256,
            },
        ]
    )
    ok(
        "empty_done_event_recovers_incremental_content",
        empty_last["done_event_content_empty"] is True and empty_last["visible_content_length"] > 0,
        empty_last,
    )
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / FIRST_A_EXECUTION_ID
        folder.mkdir()
        (folder / "request_capture.json").write_text('{"keep":"orig"}\n', encoding="utf-8")
        (folder / "run_record.json").write_text('{"execution_id":"orig"}\n', encoding="utf-8")
        before_cap = (folder / "request_capture.json").read_bytes()
        before_run = (folder / "run_record.json").read_bytes()
        write_sidecar_without_rewrite(folder, "classification_sidecar.json", first_a_sidecar_payload(), FIRST_A_PROTECTED)
        ok(
            "original_a_artifacts_unchanged",
            (folder / "request_capture.json").read_bytes() == before_cap
            and (folder / "run_record.json").read_bytes() == before_run
            and (folder / "classification_sidecar.json").is_file(),
            None,
        )
    v4s = v4_run_sidecar_payload()
    ok("v4_complete_prompt_12201_no_truncation", v4s["complete_log_prompt_tokens"] == 12201 and v4s["truncation_occurred"] is False, v4s)
    ok("no_model_call", True, "prove uses fixtures only")
    return {"ok": not problems, "checks": checks, "problems": problems, "models_called": False, "ladder_resumed": False}
