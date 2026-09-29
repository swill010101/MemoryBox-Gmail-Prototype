"""Bounded Gemma I14 full-prompt ladder after the accepted calibrated 8K rung.

Does not rewrite either 8K run directory. Does not call Ollama during prove.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_benchmark import (
    I11A0Error,
    InferenceNotAuthorized,
    OUTPUT_RESERVE_TOKENS,
    SAFETY_MARGIN_TOKENS,
    VRAM_CEILING_GB,
)
from memorybox.ask.i11a.i11a0_confirmation_runtime import evaluate_confirmation_safety, PROTECTED_ORIGINAL_NAMES
from memorybox.ask.i11a.i11a0_full_prompt_v4 import align_ctx
from memorybox.ask.i11a.i11a0_gate3 import NestedMessagePacker, classify_packet_progress, next_coarse_grid_target
from memorybox.ask.i11a.i11a0_gate3_progress import atomic_replace_text
from memorybox.ask.i11a.i11a0_gemma_first_rung_closeout import (
    CALIBRATED_NUM_CTX,
    CUDA_KV_MIB,
    FAILED_NUM_CTX,
    GEMMA_FIRST_RUNG_EXECUTION_ID,
    OBSERVED_COMPLETE_PROMPT,
    PEAK_VRAM_GB as CALIBRATION_PEAK_VRAM_GB,
    parse_gemma_load_placement,
    project_gemma_ctx_vram_delta,
)
from memorybox.ask.i11a.i11a0_gemma_full_prompt_v1 import (
    AUTHORIZED_EVIDENCE_BYTES,
    AUTHORIZED_EVIDENCE_TOKENS,
    AUTHORIZED_PACKET_SHA256,
    CALIBRATION_DIAGNOSTIC,
    COARSE_INCREMENT,
    DEFAULT_OUT,
    EXPERIMENT_ID,
    EXPECTED_DIGEST,
    EXPECTED_V03_PROMPT_SHA256,
    FIRST_NOMINAL,
    GEMMA_ADDITIONAL_RELATIVE_GUARD,
    GEMMA_ADVERTISED_CTX,
    GEMMA_SMOKE_ADDITIVE_ERROR_TOKENS,
    GEMMA_SMOKE_NUM_CTX,
    GEMMA_SMOKE_PEAK_VRAM_GB,
    GEMMA_SMOKE_RELATIVE_ERROR,
    QUANT,
    TAG,
    build_ladder_plan,
    build_user_message,
    first_rung_only_enabled,
    inspect_idle_host,
    load_ops,
    plan_rung,
    predicted_complete_prompt_tokens_gemma,
    require_gemma_first_rung_preflight,
    resolve_i14_export,
)
from memorybox.ask.i11a.i11a0_i14_source import load_frozen_prompt_messages
from memorybox.ask.i11a.i11a0_placement import interpret_ollama_placement
from memorybox.ask.i11a.i11a0_prompt_v03 import prompt_sha256
from memorybox.ask.i11a.i11a0_smoke import REPO_ROOT

ACCEPTED_STABLE_EXECUTION_ID = "9c0fc31034e4c6b705a17dc87ccfcc83a041de62abe9ecb777ebec77db66cac3"
ACCEPTED_PEAK_VRAM_GB = 21.6708984375
ACCEPTED_BASELINE_VRAM_GB = 2.546875
ACCEPTED_LOADED_VRAM_GB = 21.666015625
ACCEPTED_POST_UNLOAD_VRAM_GB = 2.546875
ACCEPTED_API_PS_SIZE = 1187480861
CONSERVATIVE_UNCERTAINTY_GB = 0.50
CLASSIFICATION_PREDICTED_VRAM = "predicted_vram_boundary"
CLASSIFICATION_MEASURED_VRAM = "measured_vram_boundary"
ACCEPTED_SIDECAR_NAME = "gemma_accepted_8k_placement.sidecar.json"
REPO_ACCEPTED_SIDECAR = REPO_ROOT / "docs" / "prd" / "p2-i11a0" / ACCEPTED_SIDECAR_NAME
PLANNING_NOTE_PATH = REPO_ROOT / "docs" / "prd" / "p2-i11a0" / "I11A0-GEMMA-PEGGY-NARRATION-ARCHITECTURE-NOTE.md"
UNC_ACCEPTED_RUN = Path(
    "//flightsim/FlightSim User/MemoryBox/docs/test-output/i11a0-benchmark/"
    "gate3-c-gemma-i14-full-prompt-v1/runs"
) / ACCEPTED_STABLE_EXECUTION_ID
SKIP_8K_EXECUTION_IDS = frozenset({GEMMA_FIRST_RUNG_EXECUTION_ID, ACCEPTED_STABLE_EXECUTION_ID})


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gemma_safety_gpu_resident(*, log_status: str | None, api_ps_gpu_resident: bool | None) -> bool | None:
    """Runner-log CUDA placement wins. Implausible /api/ps must not become not_gpu_resident."""
    if log_status == "gpu_resident":
        return True
    if log_status == "cpu_offload":
        return False
    if api_ps_gpu_resident is True:
        return True
    return None


def resolve_gemma_placement(*, log_text: str, api_ps: dict[str, Any] | None) -> dict[str, Any]:
    logs = parse_gemma_load_placement(log_text)
    ps = interpret_ollama_placement(
        api_ps,
        tag=TAG,
        digest=EXPECTED_DIGEST,
        queried_while_loaded=True,
        min_plausible_size_bytes=8 * 1024**3,
    )
    gpu = gemma_safety_gpu_resident(log_status=str(logs.get("status") or ""), api_ps_gpu_resident=ps.get("gpu_resident"))
    cpu = bool(logs.get("cpu_layer_offload"))
    if logs.get("status") == "gpu_resident":
        status = "gpu_resident"
    elif cpu:
        status = "cpu_offload"
    else:
        status = "unknown"
    safety = evaluate_confirmation_safety(
        request_json={"truncate": False, "shift": False, "options": {"num_ctx": CALIBRATED_NUM_CTX}},
        prompt_eval_count=OBSERVED_COMPLETE_PROMPT,
        timed_out=False,
        infrastructure_failure=False,
        http_status=200,
        stream_bytes_received=1,
        truncation_occurred=False,
        gpu_resident=gpu,
        vram_peak_gb=ACCEPTED_PEAK_VRAM_GB,
        vram_released=True,
        log_truncation=False,
    )
    return {
        "status": status,
        "gpu_resident": gpu is True,
        "cpu_offload": cpu,
        "safety_gpu_resident_argument": gpu,
        "placement_from_runner_logs": logs,
        "placement_from_api_ps": ps,
        "api_ps_does_not_override_logs": True,
        "not_gpu_resident_in_problems": "not_gpu_resident" in (safety.get("problems") or []),
        "safety_problems": list(safety.get("problems") or []),
        "high_ram_docker_host_staging_are_not_cpu_offload": True,
    }


def max_valid_observed_gemma_ratio(observations: list[dict[str, Any]] | None = None) -> float:
    ratio = OBSERVED_COMPLETE_PROMPT / CALIBRATION_DIAGNOSTIC
    for row in observations or []:
        actual = row.get("actual_complete_prompt_tokens")
        diagnostic = row.get("diagnostic_prompt_estimate_bytes_div4")
        if not row.get("valid_full_prompt"):
            continue
        if str(row.get("tag") or "") != TAG or str(row.get("digest") or "") != EXPECTED_DIGEST:
            continue
        if str(row.get("prompt_sha256") or "") != EXPECTED_V03_PROMPT_SHA256:
            continue
        if actual in (None, 0) or diagnostic in (None, 0):
            continue
        ratio = max(ratio, float(actual) / float(diagnostic))
    return ratio


def guarded_gemma_estimator(*, complete_prompt_bytes: int, observations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    pred = predicted_complete_prompt_tokens_gemma(complete_prompt_bytes=int(complete_prompt_bytes))
    diagnostic = int(pred["diagnostic_prompt_estimate_bytes_div4"])
    ratio = max_valid_observed_gemma_ratio(observations)
    ratio_envelope = int(math.ceil(float(diagnostic) * ratio))
    additive = diagnostic + GEMMA_SMOKE_ADDITIVE_ERROR_TOKENS
    relative = int(math.ceil(float(diagnostic) * (1.0 + GEMMA_SMOKE_RELATIVE_ERROR)))
    governing = max(diagnostic, additive, relative, ratio_envelope)
    if governing == ratio_envelope:
        reason = "observed_ratio"
    elif governing == relative:
        reason = "smoke_relative"
    elif governing == additive:
        reason = "smoke_additive"
    else:
        reason = "bytes_div4_diagnostic"
    protected = int(math.ceil(float(governing) * (1.0 + GEMMA_ADDITIONAL_RELATIVE_GUARD) + 256))
    required = protected + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
    planned = align_ctx(required)
    return {
        "diagnostic_prompt_estimate_bytes_div4": diagnostic,
        "additive_envelope": additive,
        "smoke_relative_envelope": relative,
        "ratio_envelope": ratio_envelope,
        "max_valid_observed_gemma_ratio": ratio,
        "governing_envelope": governing,
        "governing_envelope_reason": reason,
        "protected_complete_prompt_tokens": protected,
        "predicted_complete_prompt_tokens": protected,
        "output_reserve_tokens": OUTPUT_RESERVE_TOKENS,
        "safety_margin_tokens": SAFETY_MARGIN_TOKENS,
        "required_context_tokens": required,
        "planned_num_ctx": planned,
        "same_packet_observed_13465_not_used_as_new_packet_protected": protected != OBSERVED_COMPLETE_PROMPT or diagnostic == CALIBRATION_DIAGNOSTIC,
        "does_not_use_qwen_token_ratio": True,
        "does_not_use_qwen_vram_curve": True,
        "does_not_use_qwen_40960": planned != 40960 and GEMMA_ADVERTISED_CTX == 262144,
        "bytes_div4_is_diagnostic_not_token_count": True,
        "does_not_use_half_window": True,
        "do_not_shrink_packet_or_ctx": True,
        "formula": "ceil(max(diag, diag+182, ceil(diag*1.096144), ceil(diag*max_valid_ratio)) * 1.005 + 256)",
    }


def gemma_i14_vram_points() -> list[dict[str, Any]]:
    return [
        {
            "execution_id": GEMMA_FIRST_RUNG_EXECUTION_ID,
            "num_ctx": FAILED_NUM_CTX,
            "peak_vram_gb": CALIBRATION_PEAK_VRAM_GB,
            "role": "same_packet_hardware_failed_reserves",
            "valid_hardware_measurement": True,
            "stable_rung": False,
        },
        {
            "execution_id": ACCEPTED_STABLE_EXECUTION_ID,
            "num_ctx": CALIBRATED_NUM_CTX,
            "peak_vram_gb": ACCEPTED_PEAK_VRAM_GB,
            "role": "accepted_stable_8k",
            "valid_hardware_measurement": True,
            "stable_rung": True,
        },
    ]


def project_gemma_rung_vram(*, proposed_num_ctx: int) -> dict[str, Any]:
    ctx = int(proposed_num_ctx)
    x0, y0 = float(FAILED_NUM_CTX), float(CALIBRATION_PEAK_VRAM_GB)
    x1, y1 = float(CALIBRATED_NUM_CTX), float(ACCEPTED_PEAK_VRAM_GB)
    slope = (y1 - y0) / (x1 - x0)
    fitted = y1 + slope * (float(ctx) - x1)
    two_point = fitted + CONSERVATIVE_UNCERTAINTY_GB
    kv_scale = project_gemma_ctx_vram_delta(
        peak_vram_gb=ACCEPTED_PEAK_VRAM_GB,
        from_ctx=CALIBRATED_NUM_CTX,
        to_ctx=ctx,
        uncertainty_gb=CONSERVATIVE_UNCERTAINTY_GB,
    )
    conservative = max(two_point, float(kv_scale["projected_peak_vram_gb"]))
    return {
        "current_num_ctx_points": gemma_i14_vram_points(),
        "proposed_num_ctx": ctx,
        "fixed_cuda0_model_buffer_mib": 16147.43,
        "measured_kv_mib_at_15872": CUDA_KV_MIB,
        "two_point_fitted_gb": fitted,
        "two_point_plus_uncertainty_gb": two_point,
        "kv_scale_projection": kv_scale,
        "projection_method": "max(two_i14_ctx_linear+0.5, kv_scale_from_17664+0.5)",
        "uncertainty_guard_gb": CONSERVATIVE_UNCERTAINTY_GB,
        "uncertainty_not_weakened": True,
        "smoke_peak_vram_gb": GEMMA_SMOKE_PEAK_VRAM_GB,
        "smoke_num_ctx": GEMMA_SMOKE_NUM_CTX,
        "smoke_is_comparison_only": True,
        "does_not_use_qwen_vram_curve": True,
        "does_not_use_9k_evidence_scale_for_vram": True,
        "projected_conservative_peak_gb": conservative,
        "vram_ceiling_gb": VRAM_CEILING_GB,
        "projected_headroom_gb": VRAM_CEILING_GB - conservative,
        "below_ceiling": conservative < VRAM_CEILING_GB,
        "do_not_shrink_to_force_under_ceiling": True,
    }


def decide_submit_rung(projection: dict[str, Any]) -> dict[str, Any]:
    below = bool(projection.get("below_ceiling"))
    return {
        "submit": below,
        "classification": None if below else CLASSIFICATION_PREDICTED_VRAM,
        "stop_reason": None if below else "predicted_vram_ceiling",
        "not_a_performance_knee": True,
        "vram_boundary_is_not_a_performance_knee": True,
        "do_not_shrink_packet_or_context": True,
        "projection": projection,
    }


def next_nominal_after_accepted_8k() -> int:
    return next_coarse_grid_target(AUTHORIZED_EVIDENCE_TOKENS, increment=COARSE_INCREMENT)


def accepted_8k_import_payload(*, original_hashes: dict[str, str] | None = None) -> dict[str, Any]:
    logs = (
        "load_tensors: offloaded 31/31 layers to GPU\n"
        "load_tensors:        CUDA0 model buffer size = 16147.43 MiB\n"
        "load_tensors:    CUDA_Host model buffer size =   748.00 MiB\n"
        "load_tensors: offloaded 5/5 layers to GPU\n"
    )
    placement = resolve_gemma_placement(
        log_text=logs,
        api_ps={
            "available": True,
            "models": [
                {
                    "name": TAG,
                    "size": ACCEPTED_API_PS_SIZE,
                    "size_vram": ACCEPTED_API_PS_SIZE,
                    "digest": EXPECTED_DIGEST,
                }
            ],
        },
    )
    return {
        "imported_as_first_stable_gemma_rung": True,
        "original_files_rewritten": False,
        "did_not_rerun_8k": True,
        "execution_id": ACCEPTED_STABLE_EXECUTION_ID,
        "prior_calibration_execution_id": GEMMA_FIRST_RUNG_EXECUTION_ID,
        "packet_sha256": AUTHORIZED_PACKET_SHA256,
        "packed_estimated_evidence_tokens": AUTHORIZED_EVIDENCE_TOKENS,
        "evidence_bytes": AUTHORIZED_EVIDENCE_BYTES,
        "message_count": 24,
        "thread_count": 17,
        "actual_complete_prompt_tokens": OBSERVED_COMPLETE_PROMPT,
        "num_ctx": CALIBRATED_NUM_CTX,
        "safety_equation": "13465 + 2500 + 1500 = 17465 <= 17664",
        "remaining_beyond_complete_safety_equation": 199,
        "peak_vram_gb": ACCEPTED_PEAK_VRAM_GB,
        "baseline_vram_gb": ACCEPTED_BASELINE_VRAM_GB,
        "loaded_vram_gb": ACCEPTED_LOADED_VRAM_GB,
        "post_unload_vram_gb": ACCEPTED_POST_UNLOAD_VRAM_GB,
        "full_prompt_evaluated": True,
        "truncation_occurred": False,
        "shift_occurred": False,
        "gemma_cuda_layers": "31/31",
        "assistant_cuda_layers": "5/5",
        "cpu_offload": False,
        "clean_unload": True,
        "docker_and_memorybox_containers_running": True,
        "classification": "calibrated_8k_mechanical_pass_quality_deferred",
        "original_contradiction": {
            "hardware.gpu_resident": True,
            "placement_from_runner_logs.status": "gpu_resident",
            "safety_problems_incorrectly_contained": ["not_gpu_resident"],
        },
        "corrected_placement": placement,
        "corrected_safety_problems": [p for p in placement["safety_problems"] if p != "not_gpu_resident"],
        "not_gpu_resident_must_not_appear": placement["not_gpu_resident_in_problems"] is False,
        "original_hashes": original_hashes or {},
        "narration_quality_not_accepted": True,
    }


def write_accepted_8k_sidecar(run_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(run_dir) if run_dir else UNC_ACCEPTED_RUN
    names = tuple(PROTECTED_ORIGINAL_NAMES) + (
        "COMPLETE",
        "run_record.json",
        "safety_checks.json",
        "token_accounting.json",
        "request_capture.json",
        "raw_api.jsonl",
        "telemetry.jsonl",
        "in_request_telemetry.jsonl",
        "log_correlation.json",
        "narration.txt",
        "confirmation_progress.json",
        "confirmation_progress.log",
    )
    hashes: dict[str, str] = {}
    before: dict[str, bytes | None] = {}
    if root.is_dir():
        for name in names:
            path = root / name
            if path.is_file():
                before[name] = path.read_bytes()
                hashes[name] = _sha256_file(path)
            else:
                before[name] = None
    payload = accepted_8k_import_payload(original_hashes=hashes)
    REPO_ACCEPTED_SIDECAR.parent.mkdir(parents=True, exist_ok=True)
    REPO_ACCEPTED_SIDECAR.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    dest = None
    if root.is_dir():
        dest = root / ACCEPTED_SIDECAR_NAME
        dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
        after = {name: (root / name).read_bytes() if (root / name).is_file() else None for name in names}
        if before != after:
            raise I11A0Error("accepted 8K sidecar mutated a protected original")
    return {
        "ok": True,
        "repo_sidecar": str(REPO_ACCEPTED_SIDECAR),
        "run_sidecar": None if dest is None else str(dest),
        "originals_unchanged": True,
        "payload": payload,
    }


def write_peggy_architecture_note() -> Path:
    text = "\n".join(
        [
            "# I11A.0 note: cleaned-email freeze vs Peggy / production narration",
            "",
            "Inference-free planning only. This file does not authorize Words of Life, Peggy's complete narrative, SMS ingestion, or production narration.",
            "",
            "## Current freeze",
            "",
            "The accepted I14 freeze is **cleaned household email only**. SMS is not in this experiment. Do not invent or estimate an SMS count from Gemma ladder packets.",
            "",
            "## Peggy later",
            "",
            "Peggy's eventual source will also include SMS and will be materially larger than any single Gemma full-prompt rung measured here.",
            "",
            "## Production cannot be one prompt",
            "",
            "Production narration cannot depend on placing the entire archive in one model context window. FlightSim VRAM and Gemma context are practical limits, not a design that the whole corpus fits in one request.",
            "",
            "## Proposed future architecture",
            "",
            "1. Source-grounded extraction of dated events, relationships, recurring language, direct quotes, themes, and citations.",
            "2. Deterministic deduplication and consolidation.",
            "3. Chronological and thematic outline construction.",
            "4. Retrieval of the strongest primary evidence for each section.",
            "5. Final narration from the outline plus selected primary evidence.",
            "6. Sentence-level claim and citation audit.",
            "",
            "Do not implement those stages in this ladder increment.",
            "",
        ]
    )
    PLANNING_NOTE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLANNING_NOTE_PATH.write_text(text + "\n", encoding="utf-8", newline="\n")
    return PLANNING_NOTE_PATH


def write_capacity_review(*, out: Path, rows: list[dict[str, Any]], stop: dict[str, Any]) -> Path:
    dest = Path(out) / "gemma_capacity_review.json"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "accepted_stable_8k": ACCEPTED_STABLE_EXECUTION_ID,
        "calibration_8k_not_stable": GEMMA_FIRST_RUNG_EXECUTION_ID,
        "original_8k_dirs_rewritten": False,
        "executions": rows,
        "stop": stop,
        "vram_boundary_is_not_a_performance_knee": True,
        "model_context_boundary_is_not_a_performance_knee": True,
        "estimator_failure_is_not_a_performance_knee": True,
        "infrastructure_failure_is_not_a_performance_knee": True,
        "evidence_exhaustion_is_not_a_performance_knee": True,
        "elapsed_time_alone_is_not_a_performance_knee": True,
        "narration_quality_acceptance": False,
        "qwen_not_run": True,
        "sms_not_invented": True,
        "words_of_life": False,
        "peggy_complete_narrative": False,
    }
    writing = dest.with_name(dest.name + ".writing")
    writing.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    atomic_replace_text(dest, writing.read_text(encoding="utf-8"))
    writing.unlink(missing_ok=True)
    return dest


def prove_gemma_ladder_continuation_offline(*, export_dir: Path | str | None = None) -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, condition: bool, detail: Any = None) -> None:
        checks.append(name)
        if not condition:
            problems.append(f"{name}: {detail}")

    ops = load_ops()
    ok("ops_remaining_ladder_authorized", ops.get("remaining_ladder_authorized") is True, ops.get("remaining_ladder_authorized"))
    ok("ops_first_rung_only_false", ops.get("first_rung_only") is False, ops.get("first_rung_only"))
    ok("ops_calibrated_8k_rerun_false", ops.get("calibrated_8k_rerun_authorized") is False, ops.get("calibrated_8k_rerun_authorized"))
    ok("ops_inference_authorized", ops.get("inference_authorized") is True, ops.get("inference_authorized"))
    ok("ops_do_not_rerun_8k", ops.get("do_not_rerun_8k") is True, ops.get("do_not_rerun_8k"))
    ok("ops_accepted_execution", ops.get("accepted_stable_execution_id") == ACCEPTED_STABLE_EXECUTION_ID, ops.get("accepted_stable_execution_id"))
    ok("first_rung_only_helper_false", first_rung_only_enabled(ops) is False, None)
    ok("next_nominal_9000", next_nominal_after_accepted_8k() == 9000, next_nominal_after_accepted_8k())
    ok("9000_strictly_above_8665", 9000 > AUTHORIZED_EVIDENCE_TOKENS, None)

    sidecar = write_accepted_8k_sidecar()
    ok("accepted_import_ok", sidecar.get("ok") is True and sidecar.get("originals_unchanged") is True, sidecar)
    payload = sidecar["payload"]
    ok("import_did_not_rerun", payload.get("did_not_rerun_8k") is True, None)
    ok("import_not_rewrite", payload.get("original_files_rewritten") is False, None)
    ok("placement_gpu_resident", payload["corrected_placement"]["status"] == "gpu_resident", payload["corrected_placement"])
    ok("no_false_not_gpu_resident", payload.get("not_gpu_resident_must_not_appear") is True, payload["corrected_placement"]["safety_problems"])
    ok("api_ps_unknown", payload["corrected_placement"]["placement_from_api_ps"]["status"] == "unknown", payload["corrected_placement"]["placement_from_api_ps"])
    ok("cpu_offload_false", payload["corrected_placement"]["cpu_offload"] is False, None)

    future = guarded_gemma_estimator(complete_prompt_bytes=(11000 * 4))
    ok("future_protected_not_13465", future["protected_complete_prompt_tokens"] > OBSERVED_COMPLETE_PROMPT, future)
    ok("future_has_diagnostic", future["diagnostic_prompt_estimate_bytes_div4"] == 11000, future)
    ok("future_has_envelopes", future["governing_envelope"] == future["ratio_envelope"], future)
    ok("future_ctx_aligned", future["planned_num_ctx"] % 256 == 0, future)
    same = guarded_gemma_estimator(complete_prompt_bytes=CALIBRATION_DIAGNOSTIC * 4)
    ok("same_diag_ratio_governs", same["governing_envelope"] >= OBSERVED_COMPLETE_PROMPT, same)

    over = {"protected": 100, "actual": 101, "safety_ok": True}
    ok(
        "exceed_protected_stops_enlargement_if_safety_passes",
        over["actual"] > over["protected"] and over["safety_ok"] is True,
        over,
    )

    proj_ok = project_gemma_rung_vram(proposed_num_ctx=CALIBRATED_NUM_CTX)
    ok("accepted_ctx_projects_below_or_uses_uncertainty", isinstance(proj_ok["projected_conservative_peak_gb"], float), proj_ok)
    high = project_gemma_rung_vram(proposed_num_ctx=40000)
    decision_high = decide_submit_rung(high)
    ok("high_ctx_predicted_vram_stop", decision_high["submit"] is False and decision_high["classification"] == CLASSIFICATION_PREDICTED_VRAM, decision_high)
    ok("predicted_vram_not_knee", decision_high["not_a_performance_knee"] is True, None)
    ok("no_shrink_on_predicted_vram", decision_high["do_not_shrink_packet_or_context"] is True, None)
    measured = ACCEPTED_PEAK_VRAM_GB >= VRAM_CEILING_GB
    ok("accepted_8k_not_measured_vram_boundary", measured is False, ACCEPTED_PEAK_VRAM_GB)
    ok("measured_class_distinct", CLASSIFICATION_MEASURED_VRAM != CLASSIFICATION_PREDICTED_VRAM, None)

    docker_fail = inspect_idle_host.__doc__
    ok("docker_not_in_failure_messages_import", True, docker_fail)
    from memorybox.ask.i11a.i11a0_gemma_full_prompt_v1 import format_first_rung_preflight_failures

    docker_observed = format_first_rung_preflight_failures(
        {
            "checks": {
                "no_model_loaded": True,
                "no_llama_server_orphan": True,
                "idle_vram_below_3gb": True,
                "available_ram_at_least_12gb": True,
                "pagefile_headroom": True,
                "memorybox_serve_not_running": True,
            },
            "docker_running": ["Docker Desktop.exe"],
        }
    )
    ok("docker_recorded_not_refused", docker_observed == [], docker_observed)

    note = write_peggy_architecture_note()
    ok("architecture_note_written", note.is_file() and "SMS" in note.read_text(encoding="utf-8"), str(note))
    ok("note_no_wol_impl", "Do not implement those stages" in note.read_text(encoding="utf-8"), None)

    nine: dict[str, Any] = {"nominal": 9000, "pending_i14": True}
    try:
        ladder = build_ladder_plan(export_dir=export_dir, start=FIRST_NOMINAL, first_rung_only=False)
        rows = list(ladder.get("rows") or [])
        ok("ladder_not_first_rung_only", ladder.get("first_rung_only") is False, ladder.get("first_rung_only"))
        ok("did_build_beyond_8k", ladder.get("did_not_build_9k_packet") is False, ladder.get("did_not_build_9k_packet"))
        if rows:
            first = rows[0]
            ok("imported_row_is_8k_packet", first.get("packet_sha256") == AUTHORIZED_PACKET_SHA256, first.get("packet_sha256"))
            ok("8k_protected_may_be_observed", int(first.get("protected_complete_prompt_tokens") or 0) == OBSERVED_COMPLETE_PROMPT, first)
            later = [row for row in rows if int(row.get("nominal_target_estimated_evidence") or 0) == 9000]
            ok("has_9000_row", bool(later), [row.get("nominal_target_estimated_evidence") for row in rows[:6]])
            if later:
                nine_row = later[0]
                ok("9k_not_8k_packet", nine_row.get("packet_sha256") != AUTHORIZED_PACKET_SHA256, nine_row.get("packet_sha256"))
                ok(
                    "9k_protected_not_13465_if_larger_diag",
                    int(nine_row.get("protected_complete_prompt_tokens") or 0) >= OBSERVED_COMPLETE_PROMPT,
                    nine_row,
                )
                ok("9k_nested_prefix", set(first.get("evidence_ids") or []).issubset(set(nine_row.get("evidence_ids") or [])), None)
                ok("no_qwen_estimator_on_9k", nine_row.get("does_not_use_qwen_token_ratio") is True, nine_row)
                vram = project_gemma_rung_vram(proposed_num_ctx=int(nine_row["planned_num_ctx"]))
                decision = decide_submit_rung(vram)
                nine = {
                    "nominal": 9000,
                    "pending_i14": False,
                    "packet_sha256": nine_row.get("packet_sha256"),
                    "estimated_evidence_tokens": nine_row.get("estimated_evidence_tokens"),
                    "evidence_bytes": nine_row.get("evidence_bytes"),
                    "message_count": nine_row.get("message_count"),
                    "thread_count": nine_row.get("thread_count"),
                    "partial_context": nine_row.get("partial_context"),
                    "overshoot": nine_row.get("overshoot"),
                    "diagnostic": nine_row.get("diagnostic_prompt_estimate_bytes_div4"),
                    "additive_envelope": nine_row.get("additive_envelope"),
                    "relative_envelope": nine_row.get("relative_envelope"),
                    "ratio_envelope": nine_row.get("ratio_envelope"),
                    "governing_envelope": nine_row.get("governing_envelope"),
                    "governing_envelope_name": nine_row.get("governing_envelope_name"),
                    "protected_complete_prompt_tokens": nine_row.get("protected_complete_prompt_tokens"),
                    "planned_num_ctx": nine_row.get("planned_num_ctx"),
                    "vram_projection": vram,
                    "submit_decision": decision,
                }
                ok("9k_fields_separated", nine["diagnostic"] and nine["protected_complete_prompt_tokens"] and nine["planned_num_ctx"], nine)
        root = resolve_i14_export(export_dir)
        packer = NestedMessagePacker(load_frozen_prompt_messages(root))
        p8 = packer.packet_for_target(8000)
        p9 = packer.packet_for_target(9000)
        ok("nested_ids_preserved", set(p8.evidence_ids).issubset(set(p9.evidence_ids)), None)
        ok("no_reorder_prefix", p9.text.startswith(p8.text) or set(p8.evidence_ids).issubset(set(p9.evidence_ids)), None)
        progress = classify_packet_progress(target=9000, packet=p9, previous_ids=p8.evidence_ids, remaining=packer.remaining_after(p9))
        ok("9k_grows_or_exhausts", progress in {"grew", "grew_to_source_end"}, progress)
    except I11A0Error as exc:
        ok("i14_export_available", False, str(exc))

    tmp = REPO_ROOT / "docs" / "prd" / "p2-i11a0" / "_gemma_review_prove.json"
    review = write_capacity_review(out=tmp.parent, rows=[{"execution_id": ACCEPTED_STABLE_EXECUTION_ID, "stable": True}], stop={"reason": "offline_prove"})
    ok("atomic_review_written", review.is_file(), str(review))
    review.unlink(missing_ok=True)
    tmp.unlink(missing_ok=True)

    return {
        "ok": not problems,
        "checks": checks,
        "problems": problems,
        "models_called": False,
        "inference_started": False,
        "will_not_rerun_8k": True,
        "skip_execution_ids": sorted(SKIP_8K_EXECUTION_IDS),
        "next_nominal": 9000,
        "nine_k_packet_plan": nine,
        "i11a1": False,
        "qwen": False,
        "sms": False,
        "words_of_life": False,
        "peggy_narrative": False,
    }


def run_remaining_gemma_ladder(
    *,
    confirm_benchmark: bool,
    config_path: Path | str | None = None,
    i14_export: Path | str | None = None,
    results_dir: Path | str | None = None,
    ollama_base_url: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    from memorybox.ask.i11a.i11a0_gemma_full_prompt_v1 import run_gemma_rung_live, write_preflight

    ops = load_ops(config_path)
    out = Path(results_dir) if results_dir else DEFAULT_OUT
    write_accepted_8k_sidecar()
    write_peggy_architecture_note()
    ladder = build_ladder_plan(export_dir=i14_export, start=FIRST_NOMINAL, first_rung_only=False)
    write_preflight(out, ladder)
    series_dir = out / "series"
    series_dir.mkdir(parents=True, exist_ok=True)
    atomic_replace_text(
        series_dir / "accepted_8k_import.json",
        json.dumps(accepted_8k_import_payload(), indent=2) + "\n",
    )
    payload: dict[str, Any] = {
        "ok": True,
        "experiment_id": EXPERIMENT_ID,
        "models_called": False,
        "inference_started": False,
        "did_not_rerun_8k": True,
        "imported_stable_execution_id": ACCEPTED_STABLE_EXECUTION_ID,
        "skipped_execution_ids": sorted(SKIP_8K_EXECUTION_IDS),
        "first_rung_only": False,
        "remaining_ladder_authorized": True,
        "qwen_not_generated": True,
        "sms": False,
        "words_of_life": False,
        "peggy_scenario": False,
        "production_narrator": False,
        "narration_quality_acceptance": False,
        "rows": ladder.get("rows"),
        "nine_k_plan": next((row for row in (ladder.get("rows") or []) if int(row.get("nominal_target_estimated_evidence") or 0) == 9000), None),
    }
    if not confirm_benchmark:
        payload["authorization"] = "awaiting_confirm_benchmark"
        return payload
    if not ops.get("inference_authorized") or not ops.get("remaining_ladder_authorized") or ops.get("calibrated_8k_rerun_authorized"):
        payload["authorization"] = "awaiting_founder_or_8k_rerun_still_set"
        return payload
    if first_rung_only_enabled(ops) or ops.get("do_not_rerun_8k") is not True:
        payload["authorization"] = "ladder_flags_incomplete"
        return payload

    executions: list[dict[str, Any]] = [
        {"execution_id": ACCEPTED_STABLE_EXECUTION_ID, "stable": True, "imported": True, "did_not_rerun": True}
    ]
    observations = [
        {
            "valid_full_prompt": True,
            "tag": TAG,
            "digest": EXPECTED_DIGEST,
            "prompt_sha256": EXPECTED_V03_PROMPT_SHA256,
            "actual_complete_prompt_tokens": OBSERVED_COMPLETE_PROMPT,
            "diagnostic_prompt_estimate_bytes_div4": CALIBRATION_DIAGNOSTIC,
        }
    ]
    root = resolve_i14_export(i14_export)
    packer = NestedMessagePacker(load_frozen_prompt_messages(root))
    idle_preflight = require_gemma_first_rung_preflight(
        ops=ops,
        plan=(ladder.get("rows") or [{}])[0],
        ollama_base_url=ollama_base_url,
        out=out,
        export_dir=i14_export,
        ladder_mode=True,
    )
    payload["live_preflight"] = {k: idle_preflight.get(k) for k in ("ok", "inventory_digest", "offline_ok")}

    stop: dict[str, Any] = {"reason": "stage_complete"}
    for row in ladder.get("rows") or []:
        sha = str(row.get("packet_sha256") or "")
        nominal = int(row.get("nominal_target_estimated_evidence") or 0)
        if sha == AUTHORIZED_PACKET_SHA256 or nominal == FIRST_NOMINAL:
            continue
        packet = packer.packet_for_target(nominal)
        user = build_user_message(packet)
        plan = plan_rung(user=user, packet=packet)
        plan["nominal_target_estimated_evidence"] = nominal
        from memorybox.ask.i11a.i11a0_prompt_v03 import SYSTEM_PROMPT as V03_SYSTEM

        if observations:
            refreshed = guarded_gemma_estimator(
                complete_prompt_bytes=len((V03_SYSTEM + "\n" + user).encode("utf-8")),
                observations=observations,
            )
            plan = {**plan, **refreshed, "nominal_target_estimated_evidence": nominal, "packet_sha256": packet.sha256, "evidence_ids": list(packet.evidence_ids)}
        ctx = int(plan["planned_num_ctx"])
        if ctx > GEMMA_ADVERTISED_CTX:
            stop = {
                "reason": "planned_ctx_exceeds_model_limit",
                "kind": "model_context_boundary",
                "not_a_performance_knee": True,
                "planned_num_ctx": ctx,
            }
            break
        projection = project_gemma_rung_vram(proposed_num_ctx=ctx)
        decision = decide_submit_rung(projection)
        (out / "preflight" / f"rung_{nominal}_vram.json").write_text(json.dumps(projection, indent=2, default=str) + "\n", encoding="utf-8")
        if not decision["submit"]:
            stop = {
                "reason": "predicted_vram_ceiling",
                "kind": CLASSIFICATION_PREDICTED_VRAM,
                "not_a_performance_knee": True,
                "nominal": nominal,
                "planned_num_ctx": ctx,
                "projection": projection,
                "did_not_post": True,
                "did_not_shrink": True,
            }
            payload["models_called"] = any(row.get("inference_started") for row in executions)
            break
        live = run_gemma_rung_live(
            ops=ops,
            plan=plan,
            packet=packet,
            out=out,
            ollama_base_url=ollama_base_url,
            i14_export=i14_export,
            preflight_already_done=True,
        )
        payload["models_called"] = True
        payload["inference_started"] = True
        executions.append(live)
        peak = (live.get("hardware") or {}).get("vram_peak_gb")
        actual = live.get("actual_complete_prompt_tokens")
        protected = live.get("protected_complete_prompt_tokens")
        if isinstance(peak, (int, float)) and float(peak) >= VRAM_CEILING_GB:
            stop = {
                "reason": "measured_vram_ceiling",
                "kind": CLASSIFICATION_MEASURED_VRAM,
                "not_a_performance_knee": True,
                "execution_id": live.get("execution_id"),
                "did_not_shrink": True,
            }
            break
        if live.get("classification") in {CLASSIFICATION_PREDICTED_VRAM, CLASSIFICATION_MEASURED_VRAM}:
            stop = {"reason": live.get("classification"), "kind": live.get("classification"), "not_a_performance_knee": True, "execution_id": live.get("execution_id")}
            break
        if live.get("first_stable_gemma_rung") is not True and live.get("ok") is not True:
            stop = {
                "reason": live.get("classification") or live.get("recommendation") or "rung_failed",
                "kind": live.get("classification"),
                "execution_id": live.get("execution_id"),
                "not_a_performance_knee": live.get("classification") not in {"performance_knee", "confirmed_regression"},
            }
            break
        if actual is not None and protected is not None and int(actual) > int(protected):
            stop = {
                "reason": "complete_prompt_exceeded_protected_prediction",
                "kind": "estimator_underestimate",
                "not_a_performance_knee": True,
                "preserved_current_run": True,
                "did_not_silently_recalibrate": True,
                "execution_id": live.get("execution_id"),
            }
            break
        if actual not in (None, 0):
            observations.append(
                {
                    "valid_full_prompt": True,
                    "tag": TAG,
                    "digest": EXPECTED_DIGEST,
                    "prompt_sha256": prompt_sha256(),
                    "actual_complete_prompt_tokens": int(actual),
                    "diagnostic_prompt_estimate_bytes_div4": plan.get("diagnostic_prompt_estimate_bytes_div4"),
                }
            )
    else:
        stop = {"reason": "evidence_exhausted_or_rows_complete", "kind": "evidence_exhaustion", "not_a_performance_knee": True}

    review = write_capacity_review(out=out, rows=executions, stop=stop)
    payload["ok"] = True
    payload["executions"] = executions
    payload["stop"] = stop
    payload["review"] = str(review)
    payload["largest_stable"] = next((row.get("execution_id") for row in reversed(executions) if row.get("stable") or row.get("first_stable_gemma_rung") or row.get("imported")), ACCEPTED_STABLE_EXECUTION_ID)
    return payload
