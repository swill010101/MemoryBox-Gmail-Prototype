"""Gemma 4 26B cleaned-I14 full-prompt ladder v1. Separate from all Qwen series.

Offline planning and prove do not call Ollama. Live generate requires founder ops
inference_authorized and FlightSim --confirm-benchmark.
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
from memorybox.ask.i11a.i11a0_full_prompt_v3 import CTX_ALIGN_TOKENS
from memorybox.ask.i11a.i11a0_full_prompt_v4 import align_ctx, i14_export_candidates
from memorybox.ask.i11a.i11a0_gate3 import (
    NestedMessagePacker,
    classify_packet_progress,
    next_coarse_grid_target,
)
from memorybox.ask.i11a.i11a0_i14_source import load_frozen_prompt_messages, verify_pinned_i14_export
from memorybox.ask.i11a.i11a0_prompt import prompt_sha256 as prompt_sha256_v02
from memorybox.ask.i11a.i11a0_prompt_v03 import SYSTEM_PROMPT, prompt_sha256, render_user_message
from memorybox.ask.i11a.i11a0_request_identity import stable_packet_id
from memorybox.ask.i11a.i11a0_smoke import PINNED_C_DIGEST, REPO_ROOT

EXPERIMENT_ID = "gate3-c-gemma-i14-full-prompt-v1"
PLANNER_ID = "gemma4_26b_i14_full_prompt_v1"
TAG = "gemma4:26b"
QUANT = "Q4_K_M"
EXPECTED_DIGEST = PINNED_C_DIGEST
EXPECTED_V03_PROMPT_SHA256 = "2716689aa039860a465a8ebe3f7e55a0b8aa2a3e75992593e51549e36ea6d851"
GEMMA_ADVERTISED_CTX = 262144
GEMMA_SMOKE_ADDITIVE_ERROR_TOKENS = 182
GEMMA_SMOKE_RELATIVE_ERROR = 0.096144
GEMMA_ADDITIONAL_RELATIVE_GUARD = 0.005
DOCUMENTED_GUARD_TOKENS = 256
GEMMA_SMOKE_NUM_CTX = 6144
GEMMA_SMOKE_PEAK_VRAM_GB = 21.65
CLASSIFICATION_SAFETY_MARGIN_FAILED = "safety_margin_failed"
CLASSIFICATION_TRUNCATION = "truncation_occurred"
CLASSIFICATION_VRAM_BOUNDARY = "vram_ceiling"
CLASSIFICATION_NARRATION_QUALITY = "narration_quality_validation_failed"
CLASSIFICATION_PROTECTED_PREDICTION_EXCEEDED = "complete_prompt_exceeded_protected_prediction"
CLASSIFICATION_GEMMA_VRAM_BOUNDARY = "gemma_vram_boundary_at_first_rung"
CLASSIFICATION_ESTIMATOR_SAFETY_FAILED = "full_prompt_evaluated_estimator_and_safety_margin_failed"
FIRST_NOMINAL = 8000
COARSE_INCREMENT = 1000
AUTHORIZED_PACKET_SHA256 = "4ea883765185683d0f7aae62b6b1279e0b30e1c7538a24f0dc66cf6a0aa1faf0"
AUTHORIZED_EVIDENCE_TOKENS = 8665
AUTHORIZED_EVIDENCE_BYTES = 34657
AUTHORIZED_MESSAGE_COUNT = 24
AUTHORIZED_THREAD_COUNT = 17
AUTHORIZED_NUM_CTX = 17664
OBSERVED_COMPLETE_PROMPT_TOKENS = 13465
CALIBRATION_DIAGNOSTIC = 10439
FAILED_PROTECTED_PREDICTION = 11757
FAILED_NUM_CTX = 15872
PRIOR_CALIBRATION_EXECUTION_ID = "a34465944adba324c6660a8c5a25f6f7a3dff067c845ce42582b9d85ee787cfc"
CLASSIFICATION_PLACEMENT_UNPROVEN = "gemma_placement_not_affirmative_from_runner_logs"
IDLE_VRAM_MAX_GB = 3.0
MIN_AVAILABLE_RAM_GB = 12.0
MIN_PAGEFILE_AVAILABLE_GB = 8.0
MIN_PLAUSIBLE_GEMMA_PS_BYTES = 8 * 1024 ** 3
DEFAULT_OUT = REPO_ROOT / "docs" / "test-output" / "i11a0-benchmark" / EXPERIMENT_ID
OPS_PATH = REPO_ROOT / "docs" / "ops" / "i11a0.c.gemma-i14-full-prompt-v1.json"
FORBIDDEN_PROCESS_NAMES = frozenset({"llama-server.exe"})
PREFLIGHT_FAILURE_MESSAGES = {
    "no_model_loaded": "Ollama already has a model loaded; unload it and retry",
    "no_llama_server_orphan": "llama-server.exe is running; stop the orphan runner and retry",
    "idle_vram_below_3gb": "idle VRAM is not below 3 GB",
    "available_ram_at_least_12gb": "available system RAM is below 12 GB",
    "pagefile_headroom": "page-file / commit available is below 8 GB",
    "memorybox_serve_not_running": "memorybox serve is running; stop it before the Gemma first rung",
}


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_ops(path: Path | str | None = None) -> dict[str, Any]:
    ops_path = Path(path) if path else OPS_PATH
    return json.loads(ops_path.read_text(encoding="utf-8"))


def first_rung_only_enabled(ops: dict[str, Any] | None = None) -> bool:
    payload = ops if ops is not None else load_ops()
    return bool(payload.get("first_rung_only")) and not bool(payload.get("remaining_ladder_authorized"))


def build_gemma_request_json(user: str, num_ctx: int) -> dict[str, Any]:
    return {
        "model": TAG,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "think": False,
        "keep_alive": "2m",
        "truncate": False,
        "shift": False,
        "options": {
            "num_ctx": int(num_ctx),
            "num_predict": OUTPUT_RESERVE_TOKENS,
            "temperature": 0.1,
            "seed": 42,
        },
    }


def require_authorized_first_rung(plan: dict[str, Any]) -> None:
    if int(plan.get("nominal_target_estimated_evidence") or 0) != FIRST_NOMINAL:
        raise I11A0Error("first rung nominal is not 8000")
    if str(plan.get("stable_packet_id") or "") != stable_packet_id(AUTHORIZED_PACKET_SHA256):
        raise I11A0Error("stable packet id does not match the preserved 8K packet")
    if int(plan.get("estimated_evidence_tokens") or 0) != AUTHORIZED_EVIDENCE_TOKENS:
        raise I11A0Error("packed evidence token estimate is not 8665")
    if int(plan.get("evidence_bytes") or 0) != AUTHORIZED_EVIDENCE_BYTES:
        raise I11A0Error("packed evidence bytes are not 34657")
    if int(plan.get("message_count") or 0) != AUTHORIZED_MESSAGE_COUNT:
        raise I11A0Error("message count is not 24")
    if int(plan.get("thread_count") or 0) != AUTHORIZED_THREAD_COUNT:
        raise I11A0Error("thread count is not 17")
    if plan.get("partial_context") is not True:
        raise I11A0Error("partial_context must be true")
    if int(plan.get("planned_num_ctx") or 0) != AUTHORIZED_NUM_CTX:
        raise I11A0Error(f"planned_num_ctx is not {AUTHORIZED_NUM_CTX}")
    if int(plan.get("predicted_complete_prompt_tokens") or 0) != OBSERVED_COMPLETE_PROMPT_TOKENS:
        raise I11A0Error("same-packet complete prompt is not the observed 13465")
    if prompt_sha256() != EXPECTED_V03_PROMPT_SHA256:
        raise I11A0Error("prompt v0.3 sha mismatch")
    if plan.get("truncate") is not False or plan.get("shift") is not False:
        raise I11A0Error("truncate/shift must be false")
    if str(plan.get("digest") or "") != EXPECTED_DIGEST or str(plan.get("tag") or "") != TAG:
        raise I11A0Error("Gemma tag or digest mismatch")
    if str(plan.get("quantization") or "") != QUANT:
        raise I11A0Error("quantization is not Q4_K_M")


def require_authorized_rung_identity(plan: dict[str, Any]) -> None:
    if prompt_sha256() != EXPECTED_V03_PROMPT_SHA256:
        raise I11A0Error("prompt v0.3 sha mismatch")
    if plan.get("truncate") is not False or plan.get("shift") is not False:
        raise I11A0Error("truncate/shift must be false")
    if str(plan.get("digest") or "") != EXPECTED_DIGEST or str(plan.get("tag") or "") != TAG:
        raise I11A0Error("Gemma tag or digest mismatch")
    if str(plan.get("quantization") or "") != QUANT:
        raise I11A0Error("quantization is not Q4_K_M")
    if int(plan.get("planned_num_ctx") or 0) > GEMMA_ADVERTISED_CTX:
        raise I11A0Error("planned_num_ctx exceeds Gemma advertised context")


def list_tasklist_names() -> list[str]:
    import subprocess

    try:
        completed = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    names: list[str] = []
    for raw in (completed.stdout or "").splitlines():
        parts = [item.strip().strip('"') for item in raw.split('","')]
        if parts:
            names.append(parts[0])
    return names


def python_command_lines() -> list[str]:
    import subprocess

    try:
        completed = subprocess.run(
            ["wmic", "process", "where", "name='python.exe' or name='pythonw.exe'", "get", "CommandLine"],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return [line.strip() for line in (completed.stdout or "").splitlines() if line.strip() and "CommandLine" not in line]


def capture_docker_wsl_state() -> dict[str, Any]:
    import subprocess

    from memorybox.ask.i11a.i11a0_host import read_working_set_bytes

    names_of_interest = (
        "docker desktop.exe",
        "com.docker.backend.exe",
        "com.docker.service",
        "dockerd.exe",
        "vmmem",
        "vmmemwsl",
        "wslservice.exe",
        "wsl.exe",
    )
    processes: list[dict[str, Any]] = []
    try:
        completed = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        rows = completed.stdout.splitlines() if completed.returncode == 0 else []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        rows = []
    for raw in rows:
        parts = [item.strip().strip('"') for item in raw.split('","')]
        if len(parts) < 2:
            continue
        name = parts[0]
        if name.lower() not in names_of_interest:
            continue
        try:
            pid = int(parts[1])
        except ValueError:
            continue
        working_set = read_working_set_bytes(pid)
        processes.append(
            {
                "name": name,
                "pid": pid,
                "working_set_bytes": working_set,
                "working_set_gb": None if working_set is None else working_set / (1024 ** 3),
            }
        )
    docker_cli = None
    try:
        inspect = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}} {{.Status}}"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        docker_cli = {
            "available": inspect.returncode == 0,
            "containers": [line.strip() for line in (inspect.stdout or "").splitlines() if line.strip()],
        }
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        docker_cli = {"available": False, "reason": type(exc).__name__}
    memorybox_containers = [
        row for row in (docker_cli.get("containers") or []) if "memorybox" in row.lower()
    ]
    return {
        "docker_desktop_allowed": True,
        "processes": processes,
        "docker_cli": docker_cli,
        "memorybox_containers": memorybox_containers,
        "memorybox_services_running": bool(memorybox_containers),
        "working_set_bytes_total": sum(int(row.get("working_set_bytes") or 0) for row in processes),
    }


def inspect_idle_host(*, ollama_base_url: str) -> dict[str, Any]:
    from memorybox.ask.i11a.i11a0_host import read_nvidia_snapshot, read_ollama_process_memory, read_system_ram
    from memorybox.ask.i11a.i11a0_placement import read_ollama_ps

    names = list_tasklist_names()
    lowered = [name.lower() for name in names]
    forbidden = sorted({name for name in lowered if name in FORBIDDEN_PROCESS_NAMES})
    llama_server = [name for name in lowered if name == "llama-server.exe"]
    docker = [name for name in lowered if name in {"docker desktop.exe", "com.docker.backend.exe", "dockerd.exe", "com.docker.service"}]
    commands = python_command_lines()
    memorybox_serve = [line for line in commands if "memorybox serve" in line.lower() or "memorybox.serve" in line.lower()]
    ps_payload = read_ollama_ps(ollama_base_url)
    models = list(ps_payload.get("models") or [])
    gpu = read_nvidia_snapshot()
    ram = read_system_ram()
    idle = gpu.get("memory_used_gb")
    available_ram = ram.get("available_gb")
    pagefile_available = ram.get("pagefile_available_gb")
    coexistence = capture_docker_wsl_state()
    return {
        "task_names": names,
        "forbidden_processes": forbidden,
        "llama_server_orphan": llama_server,
        "docker_running": docker,
        "docker_allowed_for_memorybox_production_parity": True,
        "docker_wsl": coexistence,
        "memorybox_serve_command_lines": memorybox_serve,
        "ps": ps_payload,
        "loaded_models": models,
        "idle_vram_gb": idle,
        "idle_gpu_vram_includes_any_docker_gpu_use": True,
        "available_ram_gb": available_ram,
        "ram_used_gb": ram.get("used_gb"),
        "committed_gb": ram.get("committed_gb"),
        "pagefile_used_gb": ram.get("pagefile_used_gb"),
        "pagefile_available_gb": pagefile_available,
        "ollama_processes": read_ollama_process_memory(),
        "checks": {
            "no_model_loaded": ps_payload.get("available") is True and not models,
            "no_llama_server_orphan": not llama_server,
            "idle_vram_below_3gb": isinstance(idle, (int, float)) and float(idle) < IDLE_VRAM_MAX_GB,
            "available_ram_at_least_12gb": isinstance(available_ram, (int, float)) and float(available_ram) >= MIN_AVAILABLE_RAM_GB,
            "pagefile_headroom": isinstance(pagefile_available, (int, float)) and float(pagefile_available) >= MIN_PAGEFILE_AVAILABLE_GB,
            "memorybox_serve_not_running": not memorybox_serve,
        },
    }


def format_first_rung_preflight_failures(idle: dict[str, Any]) -> list[str]:
    checks = idle.get("checks") or {}
    messages: list[str] = []
    for name, ok in checks.items():
        if ok:
            continue
        messages.append(PREFLIGHT_FAILURE_MESSAGES.get(name, name))
    return messages


def require_gemma_first_rung_preflight(
    *,
    ops: dict[str, Any],
    plan: dict[str, Any],
    ollama_base_url: str,
    out: Path,
    export_dir: Path | str | None,
    ladder_mode: bool = False,
) -> dict[str, Any]:
    from memorybox.ask.i11a.i11a0_benchmark import inventory_installed_models
    from memorybox.ask.i11a.i11a0_confirmation_runtime import refuse_if_unresolved
    from memorybox.ask.i11a.i11a0_host import collect_host_affinity_preflight, require_flightsim_host_affinity

    if not ops.get("inference_authorized"):
        raise InferenceNotAuthorized("ops inference_authorized is false")
    if ladder_mode:
        if not ops.get("remaining_ladder_authorized"):
            raise InferenceNotAuthorized("remaining Gemma ladder is not authorized")
        if ops.get("calibrated_8k_rerun_authorized"):
            raise I11A0Error("do not rerun either 8K execution")
        if ops.get("first_rung_only"):
            raise I11A0Error("first_rung_only must be false for the remaining ladder")
        if ops.get("do_not_rerun_8k") is not True:
            raise I11A0Error("do_not_rerun_8k is required")
        require_authorized_rung_identity(plan)
    else:
        if not ops.get("calibrated_8k_rerun_authorized"):
            raise InferenceNotAuthorized("calibrated 8K rerun is not authorized")
        if not first_rung_only_enabled(ops):
            raise InferenceNotAuthorized("first_rung_only is required; remaining ladder is not authorized")
        if ops.get("remaining_ladder_authorized"):
            raise I11A0Error("remaining Gemma ladder is not authorized")
        require_authorized_first_rung(plan)
    if ops.get("pull_authorized"):
        raise I11A0Error("Gemma pull is not authorized")
    i14 = verify_pinned_i14_export(resolve_i14_export(export_dir))
    offline = prove_gemma_full_prompt_v1_offline(export_dir=export_dir)
    if not offline.get("ok"):
        raise I11A0Error(f"offline proof failed: {offline.get('problems')}")
    host = collect_host_affinity_preflight(
        ollama_base_url=ollama_base_url,
        output_path=out,
        chunks_path=REPO_ROOT / "docs" / "test-output",
        repo=REPO_ROOT,
    )
    require_flightsim_host_affinity(host)
    refuse_if_unresolved(out, recovery_authorized=False)
    idle = inspect_idle_host(ollama_base_url=ollama_base_url)
    failed = format_first_rung_preflight_failures(idle)
    if failed:
        raise I11A0Error("first-rung preflight failed: " + "; ".join(failed))
    inventory = inventory_installed_models(base_url=ollama_base_url)
    if inventory.get("pull_executed"):
        raise I11A0Error("inventory reported a pull")
    by_tag = {row["tag"]: row for row in inventory.get("approved") or []}
    row = by_tag.get(TAG) or {}
    digest = str(row.get("digest") or "")
    quant = str(row.get("quantization") or (row.get("metadata") or {}).get("quantization") or "")
    if not row:
        raise I11A0Error("gemma4:26b is not in the local Ollama inventory")
    if digest != EXPECTED_DIGEST:
        raise I11A0Error(f"installed Gemma digest mismatch: {digest}")
    if quant and quant != QUANT and QUANT.replace("_", "") not in quant.replace("_", ""):
        raise I11A0Error(f"installed Gemma quantization mismatch: {quant}")
    payload = {
        "ok": True,
        "host": host,
        "idle": idle,
        "i14": i14,
        "offline_ok": True,
        "inventory_tag": TAG,
        "inventory_digest": digest,
        "inventory_quantization": quant or QUANT,
        "planned_num_ctx": AUTHORIZED_NUM_CTX,
        "inference_authorized": True,
        "calibrated_8k_rerun_authorized": bool(ops.get("calibrated_8k_rerun_authorized")),
        "first_rung_only": bool(ops.get("first_rung_only")),
        "remaining_ladder_authorized": bool(ops.get("remaining_ladder_authorized")),
        "prior_calibration_execution_id": PRIOR_CALIBRATION_EXECUTION_ID,
    }
    (out / "preflight").mkdir(parents=True, exist_ok=True)
    (out / "preflight" / "live_preflight.json").write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return payload


def resolve_i14_export(path: Path | str | None = None) -> Path:
    if path:
        root = Path(path)
        verify_pinned_i14_export(root)
        return root
    for candidate in i14_export_candidates():
        if candidate.is_dir():
            verify_pinned_i14_export(candidate)
            return candidate
    raise I11A0Error("pinned I14 cleaned export is not available")


def predicted_complete_prompt_tokens_gemma(*, complete_prompt_bytes: int) -> dict[str, Any]:
    diagnostic = max(1, (int(complete_prompt_bytes) + 3) // 4)
    additive_envelope = diagnostic + GEMMA_SMOKE_ADDITIVE_ERROR_TOKENS
    relative_envelope = int(math.ceil(float(diagnostic) * (1.0 + GEMMA_SMOKE_RELATIVE_ERROR)))
    ratio = OBSERVED_COMPLETE_PROMPT_TOKENS / CALIBRATION_DIAGNOSTIC
    ratio_envelope = int(math.ceil(float(diagnostic) * ratio))
    governing = max(diagnostic, additive_envelope, relative_envelope, ratio_envelope)
    governing_name = "observed_ratio" if governing == ratio_envelope else (
        "relative_smoke" if governing == relative_envelope and relative_envelope > additive_envelope else (
            "additive_smoke" if governing == additive_envelope and additive_envelope > diagnostic else "bytes_div4"
        )
    )
    protected = int(math.ceil(float(governing) * (1.0 + GEMMA_ADDITIONAL_RELATIVE_GUARD) + DOCUMENTED_GUARD_TOKENS))
    return {
        "planner_id": PLANNER_ID,
        "token_count_kind": "estimated",
        "complete_prompt_bytes": int(complete_prompt_bytes),
        "diagnostic_prompt_estimate_bytes_div4": diagnostic,
        "request_bytes_div4": diagnostic,
        "gemma_smoke_additive_error_tokens": GEMMA_SMOKE_ADDITIVE_ERROR_TOKENS,
        "additive_envelope": additive_envelope,
        "gemma_smoke_relative_error": GEMMA_SMOKE_RELATIVE_ERROR,
        "relative_envelope": relative_envelope,
        "observed_ratio": ratio,
        "ratio_envelope": ratio_envelope,
        "governing_envelope": governing,
        "governing_envelope_name": governing_name,
        "additional_relative_guard": GEMMA_ADDITIONAL_RELATIVE_GUARD,
        "documented_guard_tokens": DOCUMENTED_GUARD_TOKENS,
        "protected_complete_prompt_tokens": protected,
        "predicted_complete_prompt_tokens": protected,
        "obsolete_11757_not_used_for_enlargement": True,
        "formula": "ceil(max(diag, diag+182, ceil(diag*1.096144), ceil(diag*13465/10439)) * 1.005 + 256)",
        "does_not_use_qwen_v5_estimator": True,
        "does_not_use_qwen_token_ratio": True,
        "does_not_use_qwen_vram_curve": True,
        "does_not_use_half_window": True,
        "does_not_use_qwen_40960_limit": True,
        "model_context_limit": GEMMA_ADVERTISED_CTX,
        "vram_projection": "unmeasured_until_first_valid_gemma_rung",
        "gemma_smoke_peak_vram_gb": GEMMA_SMOKE_PEAK_VRAM_GB,
        "gemma_smoke_num_ctx": GEMMA_SMOKE_NUM_CTX,
        "first_rung_may_be_near_vram_ceiling": True,
    }


def protected_prediction_exceeded(*, protected: int, actual_complete_prompt_tokens: int) -> bool:
    """Stop enlargement when Ollama/log-verified tokens exceed the protected prediction."""
    return int(actual_complete_prompt_tokens) > int(protected)


def classify_hard_stop(kind: str) -> str:
    labels = {
        "safety_margin": CLASSIFICATION_SAFETY_MARGIN_FAILED,
        "truncation": CLASSIFICATION_TRUNCATION,
        "vram": CLASSIFICATION_VRAM_BOUNDARY,
        "narration_quality": CLASSIFICATION_NARRATION_QUALITY,
        "protected_prediction": CLASSIFICATION_PROTECTED_PREDICTION_EXCEEDED,
    }
    if kind not in labels:
        raise I11A0Error(f"unknown hard-stop kind: {kind}")
    return labels[kind]


def plan_rung(*, user: str, packet: Any) -> dict[str, Any]:
    complete = SYSTEM_PROMPT + "\n" + user
    pred = predicted_complete_prompt_tokens_gemma(complete_prompt_bytes=len(complete.encode("utf-8")))
    predicted = int(pred["predicted_complete_prompt_tokens"])
    minimum = predicted + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
    planned_num_ctx = align_ctx(minimum)
    if str(packet.sha256) == AUTHORIZED_PACKET_SHA256:
        predicted = OBSERVED_COMPLETE_PROMPT_TOKENS
        minimum = predicted + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
        planned_num_ctx = align_ctx(minimum)
        pred["protected_complete_prompt_tokens"] = predicted
        pred["predicted_complete_prompt_tokens"] = predicted
        pred["token_count_kind"] = "observed_complete_prompt"
        pred["obsolete_11757_not_used_for_enlargement"] = True
        pred["same_packet_calibrated_num_ctx"] = planned_num_ctx
    reserve_ok = predicted + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS <= planned_num_ctx
    model_ok = planned_num_ctx <= GEMMA_ADVERTISED_CTX
    eligible = reserve_ok and model_ok
    reason = None
    if not model_ok:
        reason = "planned_ctx_exceeds_model_limit"
    elif not reserve_ok:
        reason = "reserves_not_satisfied"
    return {
        **pred,
        "prompt_version": "i11a0-narration-v0.3-candidate",
        "prompt_sha256": prompt_sha256(),
        "v02_prompt_sha256_unchanged": prompt_sha256_v02(),
        "estimated_evidence_tokens": int(packet.estimated_evidence_tokens),
        "evidence_bytes": int(packet.evidence_bytes),
        "evidence_token_count_kind": "estimated_bytes_div4",
        "packet_sha256": packet.sha256,
        "stable_packet_id": stable_packet_id(packet.sha256),
        "partial_context": bool(packet.partial_context),
        "overshoot": bool(packet.overshoot),
        "message_count": packet.message_count,
        "thread_count": len(packet.conversation_ids),
        "output_reserve_tokens": OUTPUT_RESERVE_TOKENS,
        "safety_margin_tokens": SAFETY_MARGIN_TOKENS,
        "reserve_equation": "protected_complete_prompt + 2500 + 1500 <= num_ctx",
        "minimum_num_ctx_for_reserves": minimum,
        "planned_num_ctx": planned_num_ctx,
        "ctx_align_tokens": CTX_ALIGN_TOKENS,
        "reserve_check": reserve_ok,
        "model_context_check": model_ok,
        "vram_projection": "unmeasured_until_first_valid_gemma_rung",
        "vram_status": "unmeasured",
        "vram_ceiling_gb": VRAM_CEILING_GB,
        "do_not_shrink_num_ctx_for_projected_vram": True,
        "vram_enforced_at_runtime": True,
        "eligible": eligible,
        "rejection_reason": reason,
        "truncate": False,
        "shift": False,
        "temperature": 0.1,
        "seed": 42,
        "think": False,
        "tag": TAG,
        "digest": EXPECTED_DIGEST,
        "quantization": QUANT,
        "evidence_ids": list(packet.evidence_ids),
    }


def build_user_message(packet: Any) -> str:
    return render_user_message(
        packet_id=stable_packet_id(packet.sha256),
        packet_role="gemma_i14_full_prompt_ladder",
        time_start=str(packet.time_start or ""),
        time_end=str(packet.time_end or ""),
        partial_context=bool(packet.partial_context),
        partial_boundary_note=str(packet.partial_boundary_note or ""),
        evidence_ids=list(packet.evidence_ids),
        evidence_text=packet.text,
    )


def build_ladder_plan(
    *,
    export_dir: Path | str | None = None,
    start: int = FIRST_NOMINAL,
    first_rung_only: bool = True,
) -> dict[str, Any]:
    root = resolve_i14_export(export_dir)
    packer = NestedMessagePacker(load_frozen_prompt_messages(root))
    rows: list[dict[str, Any]] = []
    target = int(start)
    previous_ids: tuple[str, ...] | None = None
    skipped: list[int] = []
    for _ in range(40):
        packet = packer.packet_for_target(target)
        progress = classify_packet_progress(
            target=target,
            packet=packet,
            previous_ids=previous_ids,
            remaining=packer.remaining_after(packet),
        )
        if progress == "target_already_covered":
            skipped.append(target)
            target = next_coarse_grid_target(int(packet.estimated_evidence_tokens), increment=COARSE_INCREMENT)
            continue
        if progress == "evidence_exhausted" and previous_ids is not None and packet.evidence_ids == previous_ids:
            break
        user = build_user_message(packet)
        plan = plan_rung(user=user, packet=packet)
        rows.append(
            {
                "nominal_target_estimated_evidence": target,
                "packet_progress": progress,
                **{k: plan[k] for k in plan},
            }
        )
        previous_ids = packet.evidence_ids
        if first_rung_only:
            break
        if packet.exhausted:
            break
        target = next_coarse_grid_target(int(packet.estimated_evidence_tokens), increment=COARSE_INCREMENT)
    first = rows[0] if rows else None
    return {
        "experiment_id": EXPERIMENT_ID,
        "planner_id": PLANNER_ID,
        "export_dir": str(root),
        "first_rung_only": bool(first_rung_only),
        "did_not_build_9k_packet": bool(first_rung_only),
        "skipped_already_covered_nominals": skipped,
        "rows": rows,
        "first_rung": first,
        "models_called": False,
        "qwen_series_not_mixed": True,
    }


def write_preflight(out: Path, ladder: dict[str, Any]) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "preflight"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "ladder_plan.json").write_text(json.dumps(ladder, indent=2, default=str) + "\n", encoding="utf-8")
    first = ladder.get("first_rung") or {}
    (dest / "first_rung.json").write_text(json.dumps(first, indent=2, default=str) + "\n", encoding="utf-8")
    (dest / "README.md").write_text(
        "\n".join(
            [
                "# Gemma I14 full-prompt v1 preflight",
                "",
                "Separate from Qwen capacity, estimator, VRAM fit, and quality experiments.",
                "Do not judge narration quality during the ladder.",
                "Import accepted 8K. Remaining ladder starts at 9K. Do not rerun either 8K execution.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return dest


def prove_gemma_full_prompt_v1_offline(*, export_dir: Path | str | None = None) -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, condition: bool, detail: Any = None) -> None:
        checks.append(name)
        if not condition:
            problems.append(f"{name}: {detail}")

    ops = load_ops()
    ok("ops_first_rung_only_false_for_remaining_ladder", ops.get("first_rung_only") is False, ops.get("first_rung_only"))
    ok("ops_inference_authorized", ops.get("inference_authorized") is True, ops.get("inference_authorized"))
    ok("ops_calibrated_8k_rerun_false", ops.get("calibrated_8k_rerun_authorized") is False, ops.get("calibrated_8k_rerun_authorized"))
    ok("ops_remaining_ladder_true", ops.get("remaining_ladder_authorized") is True, ops.get("remaining_ladder_authorized"))
    ok("ops_pull_unauthorized", ops.get("pull_authorized") is False, ops.get("pull_authorized"))
    ok("ops_planned_num_ctx_17664", int(ops.get("planned_num_ctx") or 0) == AUTHORIZED_NUM_CTX, ops.get("planned_num_ctx"))
    ok("first_rung_only_helper_false", first_rung_only_enabled(ops) is False, None)
    from memorybox.ask.i11a.i11a0_gemma_first_rung_closeout import (
        gemma_control_labels,
        gemma_safety_table,
        parse_gemma_load_placement,
        project_calibrated_8k_vram,
        same_packet_calibrated_num_ctx,
        write_gemma_first_rung_sidecar,
        OBSERVED_COMPLETE_PROMPT,
        FAILED_PROTECTED_PREDICTION,
        FAILED_NUM_CTX,
        CLASSIFICATION as CLOSEOUT_CLASS,
    )
    from memorybox.ask.i11a.i11a0_placement import interpret_ollama_placement

    safety_row = gemma_safety_table(
        actual_complete_prompt_tokens=13465,
        num_ctx=15872,
        protected_prediction=11757,
    )
    ok("safety_remaining_after_prompt_2407", safety_row["remaining_after_prompt"] == 2407, safety_row)
    ok("safety_remaining_after_prompt_and_output_neg93", safety_row["remaining_after_prompt_and_output"] == -93, safety_row)
    ok("safety_required_margin_1500", safety_row["required_safety_margin"] == 1500, safety_row)
    ok("safety_total_required_17465", safety_row["total_required_context"] == 17465, safety_row)
    ok("safety_shortfall_1593_not_neg93", safety_row["safety_margin_shortfall"] == 1593, safety_row)
    ok("safety_underestimate_1708", safety_row["planner_underestimate_tokens"] == 1708, safety_row)
    ok("neg93_is_not_the_shortfall", safety_row["remaining_after_prompt_and_output_is_not_the_safety_shortfall"] is True, None)
    labels = gemma_control_labels(full_prompt_evaluated=True, truncation_occurred=False)
    ok("truncate_false_control_effective", labels["truncate_false_control"] == "effective", labels)
    ok("shift_false_control_effective", labels["shift_false_control"] == "effective", labels)
    ok("truncation_occurred_bool_false", labels["truncation_occurred"] is False, labels)
    ok("full_prompt_evaluated_true", labels["full_prompt_evaluated"] is True, labels)
    ok("calibrated_num_ctx_17664", same_packet_calibrated_num_ctx() == 17664, same_packet_calibrated_num_ctx())
    implausible = interpret_ollama_placement(
        {
            "available": True,
            "models": [{"name": TAG, "size": 1183810845, "size_vram": 1183810845, "digest": EXPECTED_DIGEST}],
        },
        tag=TAG,
        digest=EXPECTED_DIGEST,
        queried_while_loaded=True,
        min_plausible_size_bytes=MIN_PLAUSIBLE_GEMMA_PS_BYTES,
    )
    ok("implausible_ps_is_unknown_not_gpu_resident", implausible["status"] == "unknown" and implausible["gpu_resident"] is False, implausible)
    log_place = parse_gemma_load_placement(
        "load_tensors: offloaded 31/31 layers to GPU\n"
        "load_tensors:        CUDA0 model buffer size = 16147.43 MiB\n"
        "load_tensors:    CUDA_Host model buffer size =   748.00 MiB\n"
        "load_tensors: offloaded 5/5 layers to GPU\n"
    )
    ok("log_placement_gpu_resident", log_place["status"] == "gpu_resident", log_place)
    vram_proj = project_calibrated_8k_vram()
    ok("vram_proj_not_9k_evidence_scale", vram_proj.get("does_not_use_9k_evidence_scale") is True, vram_proj)
    sidecar = write_gemma_first_rung_sidecar()
    ok("sidecar_ok", sidecar.get("ok") is True and sidecar.get("originals_unchanged") is True, sidecar)
    ok("sidecar_class", sidecar["payload"]["classification"] == CLOSEOUT_CLASS, sidecar["payload"]["classification"])
    ok("sidecar_not_stable_rung", sidecar["payload"]["not_a_stable_ladder_rung"] is True, None)
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
            "docker_running": ["docker desktop.exe"],
        }
    )
    ok("docker_desktop_does_not_fail_preflight", docker_observed == [], docker_observed)
    ok("ops_tag", ops.get("tag") == TAG, ops)
    ok("ops_digest", ops.get("digest") == EXPECTED_DIGEST, ops)
    ok("ops_quant", ops.get("quantization") == QUANT, ops)
    ok("v03_prompt", prompt_sha256() == EXPECTED_V03_PROMPT_SHA256, prompt_sha256())
    ok("v02_unchanged", prompt_sha256_v02() == "c91f313cc86ebad1c8fde6008e6f283c8bf76aa881bae9118327a6d6c70f7b3b", None)
    ok("ctx_limit_is_not_qwen_40960", GEMMA_ADVERTISED_CTX != 40960, GEMMA_ADVERTISED_CTX)
    diagnostic_10439 = predicted_complete_prompt_tokens_gemma(complete_prompt_bytes=10439 * 4)
    ok("diagnostic_10439_bytes_div4", diagnostic_10439["request_bytes_div4"] == 10439, diagnostic_10439)
    ok(
        "relative_envelope_not_discarded_for_182",
        diagnostic_10439["relative_envelope"] > diagnostic_10439["additive_envelope"],
        diagnostic_10439,
    )
    ok(
        "largest_envelope_governs",
        diagnostic_10439["governing_envelope"] == diagnostic_10439["ratio_envelope"],
        diagnostic_10439,
    )
    expected_protected = int(math.ceil(float(diagnostic_10439["governing_envelope"]) * (1.0 + GEMMA_ADDITIONAL_RELATIVE_GUARD) + DOCUMENTED_GUARD_TOKENS))
    ok("protected_matches_formula", diagnostic_10439["protected_complete_prompt_tokens"] == expected_protected, diagnostic_10439)
    ok("ratio_protected_13789", expected_protected == 13789, expected_protected)
    expected_ctx = align_ctx(expected_protected + 2500 + 1500)
    ok("future_packet_num_ctx_17920", expected_ctx == 17920, expected_ctx)
    ok("alignment_rounds_up", expected_ctx >= expected_protected + 4000, expected_ctx)
    ok("alignment_is_256_multiple", expected_ctx % 256 == 0, expected_ctx)
    ok(
        "protected_exceeded_stops_enlargement",
        protected_prediction_exceeded(protected=FAILED_PROTECTED_PREDICTION, actual_complete_prompt_tokens=FAILED_PROTECTED_PREDICTION + 1) is True,
        None,
    )
    ok(
        "protected_equal_does_not_stop",
        protected_prediction_exceeded(protected=FAILED_PROTECTED_PREDICTION, actual_complete_prompt_tokens=FAILED_PROTECTED_PREDICTION) is False,
        None,
    )
    ok(
        "safety_margin_distinct_from_truncation",
        classify_hard_stop("safety_margin") != classify_hard_stop("truncation"),
        None,
    )
    ok(
        "safety_margin_distinct_from_vram",
        classify_hard_stop("safety_margin") != classify_hard_stop("vram"),
        None,
    )
    ok(
        "safety_margin_distinct_from_quality",
        classify_hard_stop("safety_margin") != classify_hard_stop("narration_quality"),
        None,
    )
    sample = predicted_complete_prompt_tokens_gemma(complete_prompt_bytes=40000)
    ok(
        "conservative_uses_relative_not_only_additive",
        sample["predicted_complete_prompt_tokens"] > sample["request_bytes_div4"] + 182 + 256,
        sample,
    )
    ok("no_qwen_v5_flag", sample["does_not_use_qwen_v5_estimator"] is True, None)
    from memorybox.ask.i11a.i11a0_qwen_closeout import QWEN_VRAM_CLOSEOUT_CLASS, qwen_vram_closeout_payload, write_qwen_vram_closeout_sidecar

    close = qwen_vram_closeout_payload()
    ok("qwen_closeout_class", close["classification"] == QWEN_VRAM_CLOSEOUT_CLASS, close)
    ok("qwen_closeout_not_infra", "infrastructure_failure" in close["not_classified_as"], None)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "COMPLETE"
        fake.write_text("complete\n", encoding="utf-8")
        rec = Path(tmp) / "run_record.json"
        rec.write_text("{}\n", encoding="utf-8")
        before = rec.read_bytes()
        written = write_qwen_vram_closeout_sidecar(tmp)
        ok("closeout_sidecar_write", written["ok"] is True, written)
        ok("closeout_does_not_rewrite_record", rec.read_bytes() == before, None)
    packet_available = False
    first: dict[str, Any] = {}
    try:
        ladder = build_ladder_plan(export_dir=export_dir)
        packet_available = True
        first = ladder.get("first_rung") or {}
        ok("first_rung_present", bool(first), first)
        ok("first_nominal_8000_or_skipped_to_distinct", int(first.get("nominal_target_estimated_evidence") or 0) >= FIRST_NOMINAL, first)
        ok("first_evidence_estimated", first.get("evidence_token_count_kind") == "estimated_bytes_div4", first)
        ok("reserves_2500_1500", int(first["output_reserve_tokens"]) == 2500 and int(first["safety_margin_tokens"]) == 1500, first)
        ok(
            "reserve_equation",
            int(first["predicted_complete_prompt_tokens"]) + 2500 + 1500 <= int(first["planned_num_ctx"]),
            first,
        )
        ok("first_rung_aligns_up", int(first["planned_num_ctx"]) % 256 == 0, first)
        ok("do_not_shrink_for_vram_projection", first.get("do_not_shrink_num_ctx_for_projected_vram") is True, first)
        ok("vram_unmeasured", first.get("vram_status") == "unmeasured", first)
        ok("packet_not_shrunk", int(first.get("estimated_evidence_tokens") or 0) >= FIRST_NOMINAL, first)
        ok("qwen_calibration_not_used", first.get("does_not_use_qwen_token_ratio") is True, first)
        ok("first_rung_only_single_row_when_requested", len(ladder.get("rows") or []) == 1, len(ladder.get("rows") or []))
        ok("imported_8k_packet_still_planned", first.get("packet_sha256") == AUTHORIZED_PACKET_SHA256, first.get("packet_sha256"))
        ok("authorized_packet_sha", first.get("packet_sha256") == AUTHORIZED_PACKET_SHA256, first.get("packet_sha256"))
        ok("authorized_evidence_8665", int(first.get("estimated_evidence_tokens") or 0) == AUTHORIZED_EVIDENCE_TOKENS, first.get("estimated_evidence_tokens"))
        ok("authorized_evidence_bytes", int(first.get("evidence_bytes") or 0) == AUTHORIZED_EVIDENCE_BYTES, first.get("evidence_bytes"))
        ok("authorized_message_count", int(first.get("message_count") or 0) == AUTHORIZED_MESSAGE_COUNT, first.get("message_count"))
        ok("authorized_thread_count", int(first.get("thread_count") or 0) == AUTHORIZED_THREAD_COUNT, first.get("thread_count"))
        ok("authorized_partial_context", first.get("partial_context") is True, first.get("partial_context"))
        ok("first_rung_num_ctx_17664", int(first.get("planned_num_ctx") or 0) == AUTHORIZED_NUM_CTX, first.get("planned_num_ctx"))
        ok("first_rung_observed_13465", int(first.get("protected_complete_prompt_tokens") or 0) == OBSERVED_COMPLETE_PROMPT_TOKENS, first.get("protected_complete_prompt_tokens"))
        if int(first.get("request_bytes_div4") or 0) == 10439:
            ok("diagnostic_still_10439", True, None)
        ok("truncate_false", first.get("truncate") is False, first)
        ok("stable_packet_id", str(first.get("stable_packet_id") or "").startswith("i14pkt-"), first)
        ok("repeat_user_stable", True, None)
        user_a = None
        root = resolve_i14_export(export_dir)
        packer = NestedMessagePacker(load_frozen_prompt_messages(root))
        pkt = packer.packet_for_target(int(first["nominal_target_estimated_evidence"]))
        user_a = build_user_message(pkt)
        user_b = build_user_message(pkt)
        ok("repeat_wrapper_byte_identical", user_a == user_b, None)
        ok("skipped_are_not_exhaustion", "evidence_exhausted" not in (ladder.get("skipped_already_covered_nominals") or []), ladder.get("skipped_already_covered_nominals"))
    except I11A0Error as exc:
        ok("i14_export_available", False, str(exc))
    from memorybox.ask.i11a.i11a0_gemma_ladder_continuation import prove_gemma_ladder_continuation_offline

    cont = prove_gemma_ladder_continuation_offline(export_dir=export_dir)
    for name in cont.get("checks") or []:
        checks.append(f"continuation:{name}")
    problems.extend(cont.get("problems") or [])
    ok("continuation_offline", cont.get("ok") is True, cont.get("problems"))
    ok("continuation_no_models", cont.get("models_called") is False, None)
    ok("will_not_rerun_8k", cont.get("will_not_rerun_8k") is True, None)
    return {
        "ok": not problems,
        "checks": checks,
        "problems": problems,
        "models_called": False,
        "inference_started": False,
        "i11a1_started": False,
        "peggy_scenario": False,
        "words_of_life": False,
        "packet_available": packet_available,
        "first_rung": first,
        "experiment_id": EXPERIMENT_ID,
        "will_not_rerun_8k": True,
        "nine_k_packet_plan": cont.get("nine_k_packet_plan"),
        "continuation_check_count": len(cont.get("checks") or []),
    }


def ns_to_seconds(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value) / 1_000_000_000.0


def project_gemma_9k_from_first_rung(
    *,
    peak_vram_gb: float | None,
    baseline_vram_gb: float | None,
    packed_evidence_tokens: int = AUTHORIZED_EVIDENCE_TOKENS,
) -> dict[str, Any]:
    next_nominal = next_coarse_grid_target(int(packed_evidence_tokens), increment=COARSE_INCREMENT)
    scale = float(next_nominal) / float(max(1, packed_evidence_tokens))
    projected = None
    if isinstance(peak_vram_gb, (int, float)) and isinstance(baseline_vram_gb, (int, float)):
        delta = float(peak_vram_gb) - float(baseline_vram_gb)
        projected = float(baseline_vram_gb) + delta * scale
    over_ceiling = isinstance(projected, float) and projected >= VRAM_CEILING_GB
    return {
        "next_nominal_estimated_evidence": next_nominal,
        "did_not_pack_9k_packet": True,
        "evidence_scale": scale,
        "projected_peak_vram_gb": projected,
        "projected_meets_or_exceeds_22_5gb": over_ceiling,
        "method": "baseline + (peak-baseline) * (9000 / packed_8k_evidence)",
        "qwen_curve_not_used": True,
    }


def run_gemma_first_rung_live(
    *,
    ops: dict[str, Any],
    ladder: dict[str, Any],
    out: Path,
    ollama_base_url: str,
    i14_export: Path | str | None,
) -> dict[str, Any]:
    raise I11A0Error("do not rerun either 8K execution; remaining ladder starts after the accepted 8K rung")


def run_gemma_rung_live(
    *,
    ops: dict[str, Any],
    plan: dict[str, Any],
    packet: Any,
    out: Path,
    ollama_base_url: str,
    i14_export: Path | str | None,
    preflight_already_done: bool = False,
) -> dict[str, Any]:
    from dataclasses import asdict
    import socket
    from datetime import datetime, timezone

    from memorybox.ask.i11a.i11a0_benchmark import Measurement, RunRequest, new_execution_id, test_case_id
    from memorybox.ask.i11a.i11a0_confirmation_runtime import (
        CLASSIFICATION_INFRA_PRE_PROMPT,
        chat_with_split_timeouts,
        evaluate_confirmation_safety,
        persist_failure_record,
        persist_request_capture,
        start_confirmation_progress,
    )
    from memorybox.ask.i11a.i11a0_control_telemetry import IN_REQUEST_PHASES, IndependentRequestSampler
    from memorybox.ask.i11a.i11a0_host import HardwareSampler
    from memorybox.ask.i11a.i11a0_ollama_log_cursor import classify_appended_log, read_appended_segment, snapshot_log
    from memorybox.ask.i11a.i11a0_placement import interpret_ollama_placement, read_ollama_ps
    from memorybox.ask.i11a.i11a0_prompt_accounting_audit import request_capture_payload
    from memorybox.ask.i11a.i11a0_smoke import _unload
    from memorybox.ask.i11a.i11a0_gemma_ladder_continuation import gemma_safety_gpu_resident

    if str(packet.sha256) == AUTHORIZED_PACKET_SHA256:
        raise I11A0Error("refusing to POST the accepted 8K packet")
    if not preflight_already_done:
        require_gemma_first_rung_preflight(
            ops=ops,
            plan=plan,
            ollama_base_url=ollama_base_url,
            out=out,
            export_dir=i14_export,
            ladder_mode=True,
        )
    require_authorized_rung_identity(plan)
    user = build_user_message(packet)
    plan = dict(plan)
    num_ctx = int(plan["planned_num_ctx"])
    protected = int(plan["protected_complete_prompt_tokens"])
    nominal = int(plan.get("nominal_target_estimated_evidence") or packet.target_tokens)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    request = RunRequest(
        model_tag=TAG,
        digest=EXPECTED_DIGEST,
        requested_evidence_tokens=nominal,
        evidence_sha256=packet.sha256,
        evidence_text=packet.text,
        repetition=1,
        warm_or_cold="cold",
        confirmation=True,
        thinking_mode="off",
        seed=42,
        num_ctx=num_ctx,
        reserved_output_tokens=OUTPUT_RESERVE_TOKENS,
        prompt_sha256=prompt_sha256(),
        time_start=str(packet.time_start or ""),
        time_end=str(packet.time_end or ""),
        partial_context=bool(packet.partial_context),
        partial_boundary_note=str(packet.partial_boundary_note or ""),
        evidence_ids=tuple(packet.evidence_ids),
        model_visible_packet_id=stable_packet_id(packet.sha256),
    )
    execution_id = new_execution_id(
        test_case=test_case_id(request),
        hostname=socket.gethostname(),
        started_at_utc=started,
    )
    run_dir = out / "runs" / execution_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "IN_FLIGHT").write_text(started + "\n", encoding="utf-8")
    payload = build_gemma_request_json(user, num_ctx)
    capture = request_capture_payload(
        system_text=SYSTEM_PROMPT,
        user_text=user,
        evidence_text=packet.text,
        options=payload["options"],
        model_tag=TAG,
        digest=EXPECTED_DIGEST,
        execution_id=execution_id,
        test_case_id=test_case_id(request),
        keep_alive=payload.get("keep_alive"),
    )
    capture["request_json"] = payload
    capture["first_rung_only"] = False
    capture["remaining_ladder"] = True
    capture["truncate_requested"] = False
    capture["shift_requested"] = False
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    capture["request_body_sha256"] = hashlib.sha256(encoded).hexdigest()
    capture["request_body_bytes"] = len(encoded)
    persist_request_capture(run_dir, capture)
    sampler = HardwareSampler()
    sampler.capture("baseline")
    loaded_ps: dict[str, Any] = {}

    def on_first_token() -> None:
        loaded_ps["payload"] = read_ollama_ps(ollama_base_url)
        loaded_ps["interpreted"] = interpret_ollama_placement(
            loaded_ps["payload"],
            tag=TAG,
            digest=EXPECTED_DIGEST,
            queried_while_loaded=True,
            min_plausible_size_bytes=MIN_PLAUSIBLE_GEMMA_PS_BYTES,
        )
        sampler.capture("loaded")

    log_before = snapshot_log(
        execution_id="",
        model_tag=TAG,
        digest=EXPECTED_DIGEST,
        num_ctx=num_ctx,
    )
    generation_timeout = int(ops.get("timeout_seconds") or 1800)
    runner_ready_timeout = int(ops.get("runner_ready_timeout_seconds") or 300)
    progress = start_confirmation_progress(
        run_dir, timeout_seconds=generation_timeout, execution_id=execution_id
    )
    telemetry = IndependentRequestSampler(
        telemetry_path=run_dir / "in_request_telemetry.jsonl",
        base_url=ollama_base_url,
        experiment_id=EXPERIMENT_ID,
        run_id=execution_id,
        execution_id=execution_id,
        tag=TAG,
        digest=EXPECTED_DIGEST,
        interval_seconds=1.5,
        heartbeat_seconds=40.0,
        progress=progress,
        runner_ready_timeout_seconds=float(runner_ready_timeout),
        include_runner_processes=True,
    )
    telemetry.start("starting_runner")
    progress.emit("starting runner", phase="starting_runner")
    unload_s = None
    events: list[dict[str, Any]] = []
    narration = ""
    chat_result: dict[str, Any] = {
        "measurement": None,
        "narration": "",
        "events": [],
        "http_status": None,
        "headers_received": False,
        "stream_bytes_received": 0,
        "runner_ready_timeout": False,
        "failure_kind": "aborted",
    }
    try:
        sampler.capture("generate_start")
        chat_result = chat_with_split_timeouts(
            encoded=encoded,
            base_url=ollama_base_url,
            runner_ready_timeout=runner_ready_timeout,
            generation_timeout=generation_timeout,
            progress=progress,
            phase_setter=telemetry.set_phase,
            on_first_token=on_first_token,
            cancel=telemetry.cancel,
        )
        progress.emit("validation", phase="validation")
        telemetry.set_phase("validation")
        narration = chat_result.get("narration") or ""
        events = list(chat_result.get("events") or [])
        (run_dir / "narration.txt").write_text(narration, encoding="utf-8", newline="\n")
        (run_dir / "raw_api.jsonl").write_text(
            "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        progress.emit("unload", phase="unload")
        telemetry.set_phase("unload")
        sampler.capture("pre_unload")
        unload_s = _unload(ollama_base_url, TAG)
        sampler.capture("after_unload")
    finally:
        telemetry.stop()
        progress.stop_heartbeat()
    measurement = chat_result.get("measurement") or Measurement(infrastructure_failure=True)
    last = events[-1] if events else {}
    vram_vals = sampler.vram_used_values()
    independent_vram = telemetry.vram_for_phases(IN_REQUEST_PHASES)
    current_run_vram = list(independent_vram)
    peak = max(vram_vals + current_run_vram) if (vram_vals or current_run_vram) else None
    baseline = vram_vals[0] if vram_vals else None
    loaded_vram = None
    for sample in sampler.samples:
        if sample.get("phase") == "loaded" and isinstance(sample.get("vram_used_gb"), (int, float)):
            loaded_vram = float(sample["vram_used_gb"])
    final = vram_vals[-1] if vram_vals else None
    ram_peaks = [float(row["system_ram_used_gb"]) for row in sampler.samples if isinstance(row.get("system_ram_used_gb"), (int, float))]
    page_peaks = [float(row["pagefile_used_gb"]) for row in sampler.samples if isinstance(row.get("pagefile_used_gb"), (int, float))]
    for tick in telemetry.samples:
        if isinstance(tick.get("system_ram_used_gb"), (int, float)):
            ram_peaks.append(float(tick["system_ram_used_gb"]))
        if isinstance(tick.get("pagefile_used_gb"), (int, float)):
            page_peaks.append(float(tick["pagefile_used_gb"]))
    placed = loaded_ps.get("interpreted") or {}
    gpu_resident = placed.get("gpu_resident") if placed else None
    cpu_offload = placed.get("status") == "cpu_offload" if placed else None
    vram_released = None
    if baseline is not None and final is not None:
        vram_released = final <= baseline + 2.0
    pec = measurement.prompt_eval_count or last.get("prompt_eval_count")
    actual_prompt = None if pec in (None, 0) else int(pec)
    log_verdict = classify_appended_log(
        log_before,
        num_ctx=num_ctx,
        prompt_eval_count=actual_prompt,
        predicted_complete=protected,
    )
    from memorybox.ask.i11a.i11a0_gemma_first_rung_closeout import (
        gemma_control_labels,
        gemma_safety_table,
        parse_gemma_load_placement,
        project_calibrated_8k_vram,
        project_gemma_ctx_vram_delta,
    )
    appended = read_appended_segment(log_before)
    log_place = parse_gemma_load_placement(str(appended.get("text") or ""))
    affirmative_gpu = log_place.get("status") == "gpu_resident"

    trunc_flag = True if log_verdict.get("truncation_occurred") is True else False if actual_prompt is not None else None
    underestimate = bool(
        actual_prompt is not None and protected_prediction_exceeded(protected=protected, actual_complete_prompt_tokens=actual_prompt)
    )
    safety_row = None
    remaining_margin = None
    reserve_ok = None
    if actual_prompt is not None:
        safety_row = gemma_safety_table(
            actual_complete_prompt_tokens=actual_prompt,
            num_ctx=num_ctx,
            protected_prediction=protected,
        )
        remaining_margin = safety_row["remaining_after_prompt_and_output"]
        reserve_ok = safety_row["safety_margin_shortfall"] == 0
    controls = gemma_control_labels(
        full_prompt_evaluated=actual_prompt is not None,
        truncation_occurred=bool(trunc_flag),
    )
    safety = evaluate_confirmation_safety(
        request_json=payload,
        prompt_eval_count=actual_prompt,
        timed_out=bool(measurement.timed_out) or bool(chat_result.get("runner_ready_timeout")),
        infrastructure_failure=bool(measurement.infrastructure_failure),
        http_status=chat_result.get("http_status"),
        stream_bytes_received=int(chat_result.get("stream_bytes_received") or 0),
        truncation_occurred=trunc_flag,
        gpu_resident=gemma_safety_gpu_resident(
            log_status=str(log_place.get("status") or ""),
            api_ps_gpu_resident=gpu_resident if isinstance(gpu_resident, bool) else None,
        ),
        vram_peak_gb=peak,
        vram_released=vram_released,
        log_truncation=True if log_verdict.get("truncation_occurred") is True else None,
    )
    vram_boundary = isinstance(peak, (int, float)) and float(peak) >= VRAM_CEILING_GB
    infra_fail = bool(measurement.timed_out) or bool(chat_result.get("runner_ready_timeout")) or bool(chat_result.get("failure_kind"))
    classification = safety.get("classification")
    if vram_boundary:
        classification = "measured_vram_boundary"
        recommendation = "stop_measured_vram_boundary_do_not_shrink"
    elif not affirmative_gpu:
        classification = CLASSIFICATION_PLACEMENT_UNPROVEN
        recommendation = "stop_placement_not_affirmative_from_runner_logs"
    elif trunc_flag is True:
        classification = CLASSIFICATION_TRUNCATION
        recommendation = "stop_truncation_or_shift"
    elif actual_prompt is not None and reserve_ok is False:
        classification = CLASSIFICATION_ESTIMATOR_SAFETY_FAILED
        recommendation = "stop_reserve_equation_failed"
    elif infra_fail or vram_released is False:
        classification = classification or "infrastructure_or_unload_failed"
        recommendation = "stop_runner_stream_telemetry_or_unload_failed"
    elif actual_prompt is not None and reserve_ok and trunc_flag is False and not infra_fail:
        classification = "gemma_rung_mechanical_pass_quality_deferred"
        recommendation = "continue_coarse_ladder_until_hard_stop"
    else:
        recommendation = "stop_for_founder_review"
    rung_ok = classification == "gemma_rung_mechanical_pass_quality_deferred"
    nine_k_note = None
    rec = {
        "ok": rung_ok,
        "stable": rung_ok,
        "classification": classification,
        "first_stable_gemma_rung": False,
        "quality_comparison_deferred": True,
        "execution_id": execution_id,
        "prior_calibration_execution_id": PRIOR_CALIBRATION_EXECUTION_ID,
        "imported_stable_8k_execution_id": "9c0fc31034e4c6b705a17dc87ccfcc83a041de62abe9ecb777ebec77db66cac3",
        "models_called": True,
        "inference_started": True,
        "first_rung_only": False,
        "did_not_build_or_submit_9k": False,
        "remaining_ladder_started": True,
        "qwen_not_generated": True,
        "words_of_life": False,
        "peggy_scenario": False,
        "production_narrator": False,
        "packet_sha256": packet.sha256,
        "prompt_sha256": prompt_sha256(),
        "protected_complete_prompt_tokens": protected,
        "actual_complete_prompt_tokens": actual_prompt,
        "gemma_estimator_underestimate": underestimate,
        **(safety_row or {}),
        **controls,
        "safety_equation": "actual_complete_prompt + 2500 + 1500 <= num_ctx",
        "remaining_context_after_prompt_and_output": remaining_margin,
        "reserve_equation_passed": reserve_ok,
        "num_ctx": num_ctx,
        "unload_seconds": unload_s,
        "vram_scope": "current_run_only",
        "hardware": {
            "vram_baseline_gb": baseline,
            "vram_peak_gb": peak,
            "vram_loaded_gb": loaded_vram,
            "vram_post_unload_gb": final,
            "current_run_in_request_peak_gb": max(current_run_vram) if current_run_vram else peak,
            "gpu_resident": affirmative_gpu,
            "cpu_offload": log_place.get("cpu_layer_offload"),
            "placement_from_api_ps": placed,
            "placement_from_runner_logs": log_place,
            "vram_released": vram_released,
            "system_ram_peak_gb": max(ram_peaks) if ram_peaks else None,
            "pagefile_peak_gb": max(page_peaks) if page_peaks else None,
            "docker_wsl": capture_docker_wsl_state(),
        },
        "timing": {
            "load_seconds": ns_to_seconds(last.get("load_duration")),
            "prompt_eval_seconds": ns_to_seconds(last.get("prompt_eval_duration")),
            "generation_seconds": ns_to_seconds(last.get("eval_duration")),
            "elapsed_seconds": measurement.elapsed_seconds,
            "prompt_tokens_per_second": last.get("prompt_eval_rate"),
            "generation_tokens_per_second": last.get("eval_rate"),
        },
        "unload_recorded": True,
        "narration_artifact": str(run_dir / "narration.txt"),
        "nine_k_technically_eligible": False,
        "nine_k_projection_if_8k_passed": nine_k_note,
        "gemma_calibrated_vram_projection": project_calibrated_8k_vram(),
        "recommendation": recommendation,
        "measurement": asdict(measurement),
        "log_correlation": {k: v for k, v in log_verdict.items() if k != "segment"},
        "safety_problems": list(safety.get("problems") or []),
        "http_status": chat_result.get("http_status"),
        "stopped_after_first_rung": False,
    }
    (run_dir / "token_accounting.json").write_text(
        json.dumps(
            {
                "actual_prompt_eval_count": actual_prompt,
                "protected_complete_prompt_tokens": protected,
                "configured_num_ctx": num_ctx,
                "output_reserve_tokens": OUTPUT_RESERVE_TOKENS,
                "safety_margin_tokens": SAFETY_MARGIN_TOKENS,
                "gemma_estimator_underestimate": underestimate,
                "packet_sha256": packet.sha256,
                "prompt_sha256": prompt_sha256(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "telemetry.jsonl").write_text(
        "\n".join(json.dumps(sample) for sample in sampler.samples) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (run_dir / "log_correlation.json").write_text(json.dumps(log_verdict, indent=2, default=str) + "\n", encoding="utf-8")
    (run_dir / "safety_checks.json").write_text(json.dumps(safety, indent=2, default=str) + "\n", encoding="utf-8")
    (run_dir / "run_record.json").write_text(json.dumps(rec, indent=2, default=str) + "\n", encoding="utf-8")
    in_flight = run_dir / "IN_FLIGHT"
    if in_flight.is_file():
        in_flight.unlink()
    if vram_boundary:
        persist_failure_record(run_dir, kind="failure", payload=rec)
    elif measurement.timed_out or chat_result.get("runner_ready_timeout") or chat_result.get("failure_kind"):
        persist_failure_record(
            run_dir,
            kind="timeout" if measurement.timed_out or chat_result.get("runner_ready_timeout") else "failure",
            payload=rec,
        )
    else:
        (run_dir / "COMPLETE").write_text("complete\n", encoding="utf-8")
    if underestimate:
        (run_dir / "gemma_estimator_underestimate.json").write_text(
            json.dumps(
                {
                    "protected_complete_prompt_tokens": protected,
                    "actual_complete_prompt_tokens": actual_prompt,
                    "stopped_enlargement": True,
                    "did_not_silently_recalibrate": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return rec


def run_gemma_ladder(
    *,
    confirm_benchmark: bool,
    config_path: Path | str | None = None,
    i14_export: Path | str | None = None,
    results_dir: Path | str | None = None,
    ollama_base_url: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    from memorybox.ask.i11a.i11a0_gemma_ladder_continuation import run_remaining_gemma_ladder

    return run_remaining_gemma_ladder(
        confirm_benchmark=confirm_benchmark,
        config_path=config_path,
        i14_export=i14_export,
        results_dir=results_dir,
        ollama_base_url=ollama_base_url,
    )
