"""Sidecar correction for Gemma 8K execution a3446594… Original artifacts are never rewritten."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_benchmark import I11A0Error, OUTPUT_RESERVE_TOKENS, SAFETY_MARGIN_TOKENS
from memorybox.ask.i11a.i11a0_confirmation_runtime import PROTECTED_ORIGINAL_NAMES
from memorybox.ask.i11a.i11a0_full_prompt_v4 import align_ctx
from memorybox.ask.i11a.i11a0_smoke import REPO_ROOT

GEMMA_FIRST_RUNG_EXECUTION_ID = "a34465944adba324c6660a8c5a25f6f7a3dff067c845ce42582b9d85ee787cfc"
CLASSIFICATION = "full_prompt_evaluated_estimator_and_safety_margin_failed"
SIDECAR_NAME = "gemma_first_rung_correction.sidecar.json"
OBSERVED_COMPLETE_PROMPT = 13465
FAILED_PROTECTED_PREDICTION = 11757
FAILED_NUM_CTX = 15872
CALIBRATED_NUM_CTX = 17664
DIAGNOSTIC_BYTES_DIV4 = 10439
OUTPUT_RESERVE = OUTPUT_RESERVE_TOKENS
SAFETY_MARGIN = SAFETY_MARGIN_TOKENS
VRAM_CEILING_GB = 22.5
BASELINE_VRAM_GB = 2.5400390625
PEAK_VRAM_GB = 21.615234375
SMOKE_PEAK_VRAM_GB = 21.65
SMOKE_NUM_CTX = 6144
CUDA_MODEL_BUFFER_MIB = 16147.43
CUDA_HOST_MODEL_BUFFER_MIB = 748.00
CUDA_KV_MIB = 710.00
CUDA_COMPUTE_MIB = 315.04
ASSISTANT_CUDA_MODEL_MIB = 425.34
API_PS_SIZE_BYTES = 1183810845
MIN_PLAUSIBLE_26B_Q4_BYTES = 8 * 1024 ** 3
UNC_RUN = Path(
    "//flightsim/FlightSim User/MemoryBox/docs/test-output/i11a0-benchmark/"
    "gate3-c-gemma-i14-full-prompt-v1/runs"
) / GEMMA_FIRST_RUNG_EXECUTION_ID
REPO_SIDECAR = REPO_ROOT / "docs" / "prd" / "p2-i11a0" / SIDECAR_NAME
EXTRA_PROTECTED = (
    "gemma_estimator_underestimate.json",
    "in_request_telemetry.jsonl",
    "confirmation_progress.json",
    "confirmation_progress.log",
    "COMPLETE",
)
LAYERS_RE = re.compile(r"offloaded (?P<done>\d+)/(?P<total>\d+) layers to GPU")
CUDA_MODEL_RE = re.compile(r"CUDA0 model buffer size =\s+(?P<mib>[\d.]+) MiB")
CUDA_HOST_MODEL_RE = re.compile(r"CUDA_Host model buffer size =\s+(?P<mib>[\d.]+) MiB")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gemma_safety_table(
    *,
    actual_complete_prompt_tokens: int,
    num_ctx: int,
    protected_prediction: int,
    output_reserve: int = OUTPUT_RESERVE,
    safety_margin: int = SAFETY_MARGIN,
) -> dict[str, Any]:
    actual = int(actual_complete_prompt_tokens)
    ctx = int(num_ctx)
    remaining_after_prompt = ctx - actual
    remaining_after_prompt_and_output = remaining_after_prompt - int(output_reserve)
    total_required_context = actual + int(output_reserve) + int(safety_margin)
    safety_margin_shortfall = max(0, total_required_context - ctx)
    return {
        "actual_complete_prompt_tokens": actual,
        "num_ctx": ctx,
        "remaining_after_prompt": remaining_after_prompt,
        "remaining_after_prompt_and_output": remaining_after_prompt_and_output,
        "required_safety_margin": int(safety_margin),
        "total_required_context": total_required_context,
        "safety_margin_shortfall": safety_margin_shortfall,
        "planner_underestimate_tokens": actual - int(protected_prediction),
        "remaining_after_prompt_and_output_is_not_the_safety_shortfall": True,
        "equation": f"{actual} + {output_reserve} + {safety_margin} = {total_required_context}",
    }


def gemma_control_labels(*, full_prompt_evaluated: bool, truncation_occurred: bool) -> dict[str, Any]:
    evaluated = bool(full_prompt_evaluated)
    truncated = bool(truncation_occurred)
    control = "effective" if evaluated and not truncated else ("ineffective" if evaluated else "unverified")
    return {
        "truncate_false_control": control,
        "shift_false_control": control,
        "truncation_occurred": truncated,
        "full_prompt_evaluated": evaluated,
    }


def observed_ratio() -> float:
    return OBSERVED_COMPLETE_PROMPT / DIAGNOSTIC_BYTES_DIV4


def future_packet_protected_prompt(diagnostic: int) -> dict[str, Any]:
    diag = max(1, int(diagnostic))
    ratio = observed_ratio()
    additive = diag + 182
    smoke_relative = int(math.ceil(float(diag) * 1.096144))
    ratio_envelope = int(math.ceil(float(diag) * ratio))
    governing = max(diag, additive, smoke_relative, ratio_envelope)
    protected = int(math.ceil(float(governing) * 1.005 + 256))
    planned = align_ctx(protected + OUTPUT_RESERVE + SAFETY_MARGIN)
    return {
        "diagnostic_prompt_estimate_bytes_div4": diag,
        "observed_ratio": ratio,
        "observed_ratio_exact": f"{OBSERVED_COMPLETE_PROMPT}/{DIAGNOSTIC_BYTES_DIV4}",
        "additive_envelope": additive,
        "smoke_relative_envelope": smoke_relative,
        "ratio_envelope": ratio_envelope,
        "governing_envelope": governing,
        "governing_is_observed_ratio": governing == ratio_envelope,
        "obsolete_11757_not_used": True,
        "protected_complete_prompt_tokens": protected,
        "planned_num_ctx": planned,
        "formula": "ceil(max(diag, diag+182, ceil(diag*1.096144), ceil(diag*13465/10439)) * 1.005 + 256)",
    }


def same_packet_calibrated_num_ctx() -> int:
    return align_ctx(OBSERVED_COMPLETE_PROMPT + OUTPUT_RESERVE + SAFETY_MARGIN)


def project_calibrated_8k_vram() -> dict[str, Any]:
    scale = CALIBRATED_NUM_CTX / FAILED_NUM_CTX
    kv_extra_mib = CUDA_KV_MIB * (scale - 1.0)
    compute_extra_mib = CUDA_COMPUTE_MIB * 0.10
    extra_gb = (kv_extra_mib + compute_extra_mib) / 1024.0
    uncertainty_gb = 0.50
    projected = PEAK_VRAM_GB + extra_gb + uncertainty_gb
    return {
        "method": "weights_fixed_from_llama_log_plus_kv_scale_plus_uncertainty",
        "does_not_use_9k_evidence_scale": True,
        "baseline_vram_gb": BASELINE_VRAM_GB,
        "current_run_peak_vram_gb": PEAK_VRAM_GB,
        "current_run_num_ctx": FAILED_NUM_CTX,
        "gemma_smoke_peak_vram_gb": SMOKE_PEAK_VRAM_GB,
        "gemma_smoke_num_ctx": SMOKE_NUM_CTX,
        "smoke_vs_8k_shows_weights_dominate": abs(PEAK_VRAM_GB - SMOKE_PEAK_VRAM_GB) < 0.1,
        "cuda0_model_buffer_mib": CUDA_MODEL_BUFFER_MIB,
        "kv_buffer_mib_at_15872": CUDA_KV_MIB,
        "compute_buffer_mib_at_15872": CUDA_COMPUTE_MIB,
        "calibrated_num_ctx": CALIBRATED_NUM_CTX,
        "kv_scale": scale,
        "projected_extra_gb": extra_gb,
        "conservative_uncertainty_gb": uncertainty_gb,
        "projected_peak_vram_gb": projected,
        "vram_ceiling_gb": VRAM_CEILING_GB,
        "likely_below_ceiling": projected < VRAM_CEILING_GB,
        "headroom_gb": VRAM_CEILING_GB - projected,
        "thin_headroom": (VRAM_CEILING_GB - projected) < 0.5,
    }


def parse_gemma_load_placement(log_text: str) -> dict[str, Any]:
    layers = [(int(m.group("done")), int(m.group("total"))) for m in LAYERS_RE.finditer(log_text)]
    cuda_model = [float(m.group("mib")) for m in CUDA_MODEL_RE.finditer(log_text)]
    host_model = [float(m.group("mib")) for m in CUDA_HOST_MODEL_RE.finditer(log_text)]
    gemma_layers = next((row for row in layers if row == (31, 31)), None)
    assistant_layers = next((row for row in layers if row == (5, 5)), None)
    full_cuda_layers = gemma_layers == (31, 31)
    cpu_layer_offload = any(done < total for done, total in layers if total > 0)
    if full_cuda_layers and not cpu_layer_offload:
        status = "gpu_resident"
    elif cpu_layer_offload:
        status = "cpu_offload"
    else:
        status = "unknown"
    return {
        "layer_offload_pairs": layers,
        "gemma_layers_offloaded": gemma_layers,
        "assistant_layers_offloaded": assistant_layers,
        "cuda0_model_buffer_mib": cuda_model,
        "cuda_host_model_buffer_mib": host_model,
        "cuda_host_buffer_is_not_cpu_layer_offload": True,
        "full_cuda_layer_placement": full_cuda_layers,
        "cpu_layer_offload": cpu_layer_offload,
        "status": status,
        "high_system_ram_or_docker_is_not_cpu_offload": True,
        "api_ps_size_bytes": API_PS_SIZE_BYTES,
        "api_ps_size_implausible_for_26b_q4": API_PS_SIZE_BYTES < MIN_PLAUSIBLE_26B_Q4_BYTES,
        "api_ps_likely_draft_or_runner_component": True,
        "api_ps_not_used_as_affirmative_gpu_residency": True,
        "why_api_ps_was_about_1_1gb": (
            "Ollama 0.34.4 /api/ps size/size_vram (~1.184e9 bytes) matches a runner/"
            "draft-assistant scale (~425 MiB CUDA assistant weights plus host/KV), not "
            "the 16147 MiB CUDA0 Gemma 26B Q4_K_M weight buffer. size==size_vram is "
            "therefore not proof of full 26B GPU residency."
        ),
    }


def gemma_first_rung_sidecar_payload(*, original_hashes: dict[str, str] | None = None) -> dict[str, Any]:
    safety = gemma_safety_table(
        actual_complete_prompt_tokens=OBSERVED_COMPLETE_PROMPT,
        num_ctx=FAILED_NUM_CTX,
        protected_prediction=FAILED_PROTECTED_PREDICTION,
    )
    controls = gemma_control_labels(full_prompt_evaluated=True, truncation_occurred=False)
    future = future_packet_protected_prompt(DIAGNOSTIC_BYTES_DIV4)
    vram = project_calibrated_8k_vram()
    return {
        "execution_id": GEMMA_FIRST_RUNG_EXECUTION_ID,
        "original_files_rewritten": False,
        "classification": CLASSIFICATION,
        "tag": "gemma4:26b",
        "digest": "08ae7ec1744bd7f451c4a530afb39d2673ad9d07a8369b8a33a3613b41212a68",
        "quantization": "Q4_K_M",
        "packet_sha256": "4ea883765185683d0f7aae62b6b1279e0b30e1c7538a24f0dc66cf6a0aa1faf0",
        "prompt_sha256": "2716689aa039860a465a8ebe3f7e55a0b8aa2a3e75992593e51549e36ea6d851",
        "successful_full_prompt_calibration": True,
        "not_a_stable_ladder_rung": True,
        "no_performance_knee_conclusion": True,
        "nine_k_authorized": False,
        "full_prompt_evaluated": True,
        "truncation_occurred": False,
        "vram_below_ceiling": True,
        "peak_vram_gb": PEAK_VRAM_GB,
        "narration_generated": True,
        "narration_accepted_for_quality_review": False,
        "original_ambiguous_labels": {
            "truncation_occurred": "effective",
            "shift": "effective",
            "truncate": "effective",
        },
        **controls,
        "safety": safety,
        "obsolete_protected_prediction": FAILED_PROTECTED_PREDICTION,
        "do_not_enlarge_from_11757": True,
        "same_packet_calibrated_num_ctx": same_packet_calibrated_num_ctx(),
        "future_packet_estimator": future,
        "vram_projection_at_17664": vram,
        "placement_from_logs": {
            "status": "gpu_resident",
            "gemma_offloaded_layers": "31/31",
            "assistant_offloaded_layers": "5/5",
            "cuda0_model_buffer_mib": CUDA_MODEL_BUFFER_MIB,
            "cuda_host_model_buffer_mib": CUDA_HOST_MODEL_BUFFER_MIB,
            "assistant_cuda0_model_buffer_mib": ASSISTANT_CUDA_MODEL_MIB,
            "cpu_layer_offload": False,
        },
        "placement_from_api_ps": {
            "status": "unknown",
            "size": API_PS_SIZE_BYTES,
            "size_vram": API_PS_SIZE_BYTES,
            "reason": "implausible_size_equals_size_vram_is_not_26b_residency",
        },
        "docker_desktop_allowed": True,
        "original_hashes": original_hashes or {},
        "not_classified_as": [
            "truncation_occurred",
            "vram_ceiling",
            "stable_ladder_rung",
            "performance_knee",
            "accepted_narration_quality",
        ],
    }


def hash_protected_originals(run_dir: Path) -> dict[str, str]:
    names = tuple(dict.fromkeys([*PROTECTED_ORIGINAL_NAMES, *EXTRA_PROTECTED]))
    hashes: dict[str, str] = {}
    for name in names:
        path = run_dir / name
        if path.is_file():
            hashes[name] = _sha256_file(path)
    return hashes


def write_gemma_first_rung_sidecar(run_dir: Path | str | None = None) -> dict[str, Any]:
    root = Path(run_dir) if run_dir else UNC_RUN
    if not root.is_dir():
        payload = gemma_first_rung_sidecar_payload()
        REPO_SIDECAR.parent.mkdir(parents=True, exist_ok=True)
        REPO_SIDECAR.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
        return {
            "ok": True,
            "run_dir_available": False,
            "repo_sidecar": str(REPO_SIDECAR),
            "originals_unchanged": True,
            "payload": payload,
        }
    names = tuple(dict.fromkeys([*PROTECTED_ORIGINAL_NAMES, *EXTRA_PROTECTED]))
    before = {name: (root / name).read_bytes() if (root / name).is_file() else None for name in names}
    hashes = hash_protected_originals(root)
    payload = gemma_first_rung_sidecar_payload(original_hashes=hashes)
    dest = root / SIDECAR_NAME
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPO_SIDECAR.parent.mkdir(parents=True, exist_ok=True)
    REPO_SIDECAR.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    after = {name: (root / name).read_bytes() if (root / name).is_file() else None for name in names}
    if before != after:
        raise I11A0Error("Gemma first-rung sidecar mutated a protected original artifact")
    return {
        "ok": True,
        "run_dir_available": True,
        "path": str(dest),
        "repo_sidecar": str(REPO_SIDECAR),
        "originals_unchanged": True,
        "original_hashes": hashes,
        "payload": payload,
    }
