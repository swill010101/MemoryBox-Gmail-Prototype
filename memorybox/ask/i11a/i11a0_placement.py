"""Gate 3 GPU/CPU placement classification. Requires contemporaneous loaded-model evidence."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_benchmark import _sha256_text

PRESERVED_FALSE_OFFLOAD_EXECUTION_ID = (
    "3994d3f2eb5a3f2e30b324e8650fdb6cd0e8f12732f25813b95590abf9be0c86"
)
FAULTY_CPU_OFFLOAD_EXPRESSION = (
    "cpu_offload = bool(peak_vram is not None and baseline_vram is not None "
    "and (peak_vram - baseline_vram) < 4.0)"
)
VRAM_RESIDENCY_DELTA_GB = 4.0
SIZE_MATCH_TOLERANCE = 0.02


def read_ollama_ps(base_url: str, *, timeout: float = 5.0) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/ps"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "queried_while_model_expected_loaded": True,
            "reason": f"{type(exc).__name__}:{exc}",
            "models": [],
        }
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    payload["available"] = True
    payload["models"] = list(payload.get("models") or [])
    return payload


def _bytes_to_gb(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value) / (1024.0 ** 3)


def interpret_ollama_placement(
    ps_payload: dict[str, Any] | None,
    *,
    tag: str,
    digest: str | None = None,
    queried_while_loaded: bool,
    min_plausible_size_bytes: int | None = None,
) -> dict[str, Any]:
    """Normalize /api/ps. Missing post-unload models are unknown, not CPU offload."""
    raw = dict(ps_payload or {})
    models = list(raw.get("models") or [])
    match = None
    for row in models:
        name = str(row.get("name") or row.get("model") or "")
        row_digest = str(row.get("digest") or "")
        if name == tag or name.startswith(f"{tag}") or (digest and row_digest == digest):
            match = row
            break
    size = None if match is None else match.get("size")
    size_vram = None if match is None else match.get("size_vram")
    processor = None
    if match is not None:
        processor = match.get("processor") or (match.get("details") or {}).get("processor")
    size_gb = _bytes_to_gb(size)
    vram_gb = _bytes_to_gb(size_vram)
    cpu_offload = False
    gpu_resident = False
    status = "unknown"
    reason = "no_affirmative_loaded_placement_evidence"
    if not queried_while_loaded:
        status = "unknown"
        reason = "placement_was_not_queried_while_the_model_was_loaded"
    elif not raw.get("available", True):
        status = "unknown"
        reason = f"ollama_ps_unavailable:{raw.get('reason')}"
    elif match is None:
        status = "unknown"
        reason = (
            "model_absent_from_api_ps_while_expected_loaded_is_not_cpu_offload"
            if queried_while_loaded
            else "model_absent_from_api_ps_after_unload_is_not_cpu_offload"
        )
    elif size in {None, 0} and size_vram in {None, 0}:
        status = "unknown"
        reason = "ollama_ps_matched_model_but_size_fields_were_missing"
    else:
        size_n = float(size or 0)
        vram_n = float(size_vram or 0)
        if processor and "cpu" in str(processor).lower() and "gpu" not in str(processor).lower():
            status = "cpu_offload"
            cpu_offload = True
            reason = f"processor_placement_reported_cpu:{processor}"
        elif size_n > 0 and vram_n <= 0:
            status = "cpu_offload"
            cpu_offload = True
            reason = "model_size_positive_and_size_vram_zero_while_loaded"
        elif size_n > 0 and vram_n < size_n * (1.0 - SIZE_MATCH_TOLERANCE):
            status = "cpu_offload"
            cpu_offload = True
            reason = (
                f"size_vram {vram_n} < model size {size_n} while loaded "
                "(partial GPU assignment)"
            )
        elif (
            min_plausible_size_bytes is not None
            and size_n > 0
            and size_n < float(min_plausible_size_bytes)
            and vram_n >= size_n * (1.0 - SIZE_MATCH_TOLERANCE)
        ):
            status = "unknown"
            reason = (
                "api_ps_size_equals_size_vram_but_size_is_implausible_for_full_model;"
                " not affirmative gpu_resident"
            )
        elif size_n > 0 and vram_n >= size_n * (1.0 - SIZE_MATCH_TOLERANCE):
            status = "gpu_resident"
            gpu_resident = True
            reason = "size_vram_matches_model_size_while_loaded"
        else:
            status = "unknown"
            reason = "ollama_ps_fields_were_internally_inconsistent"
    return {
        "status": status,
        "gpu_resident": gpu_resident,
        "cpu_offload": cpu_offload,
        "queried_while_loaded": queried_while_loaded,
        "tag": tag,
        "digest": digest,
        "matched_model": None if match is None else {
            "name": match.get("name") or match.get("model"),
            "digest": match.get("digest"),
            "size": size,
            "size_vram": size_vram,
            "size_gb": size_gb,
            "size_vram_gb": vram_gb,
            "processor": processor,
        },
        "reason": reason,
        "high_system_ram_is_not_cpu_offload": True,
        "missing_ps_is_not_cpu_offload": True,
        "post_unload_absence_is_not_cpu_offload": True,
        "vram_delta_heuristic_is_not_cpu_offload": True,
        "faulty_legacy_expression": FAULTY_CPU_OFFLOAD_EXPRESSION,
        "raw": raw,
    }


def classify_from_vram_delta_only(peak: float | None, baseline: float | None) -> dict[str, Any]:
    """Legacy Gate 2 heuristic. Must not be used as Gate 3 cpu_offload proof."""
    if peak is None or baseline is None:
        return {"legacy_cpu_offload": False, "usable": False}
    return {
        "legacy_cpu_offload": bool((float(peak) - float(baseline)) < VRAM_RESIDENCY_DELTA_GB),
        "usable": False,
        "expression": FAULTY_CPU_OFFLOAD_EXPRESSION,
    }


def parse_heartbeat_vram(log_text: str) -> list[float]:
    values: list[float] = []
    for line in log_text.splitlines():
        if "HEARTBEAT" not in line or "vram_gb=" not in line:
            continue
        try:
            token = [part for part in line.split() if part.startswith("vram_gb=")][0]
            raw = token.split("=", 1)[1]
            if raw not in {"None", "null", ""}:
                values.append(float(raw))
        except (IndexError, ValueError):
            continue
    return values


def aggregate_vram(
    *,
    sampler_samples: list[dict[str, Any]] | None,
    heartbeat_vram: list[float] | None,
    pre_unload_vram_gb: float | None = None,
    post_unload_vram_gb: float | None = None,
) -> dict[str, Any]:
    samples = list(sampler_samples or [])
    in_run: list[tuple[str, float]] = []
    for row in samples:
        phase = str(row.get("phase") or "")
        if phase in {"after_unload"}:
            continue
        value = row.get("vram_used_gb")
        if isinstance(value, (int, float)):
            in_run.append((phase, float(value)))
    for value in heartbeat_vram or []:
        in_run.append(("heartbeat", float(value)))
    if pre_unload_vram_gb is not None:
        in_run.append(("pre_unload", float(pre_unload_vram_gb)))
    baseline = None
    for phase, value in in_run:
        if phase in {"baseline", "generate_start"}:
            baseline = value
            break
    if baseline is None and in_run:
        baseline = in_run[0][1]
    peak = max((value for _phase, value in in_run), default=None)
    if peak is not None and any(value >= 10 for _phase, value in in_run) and peak < 4 and heartbeat_vram:
        peak = max(heartbeat_vram)
    return {
        "vram_baseline_gb": baseline,
        "vram_peak_gb": peak,
        "vram_pre_unload_gb": pre_unload_vram_gb,
        "vram_post_unload_gb": post_unload_vram_gb,
        "heartbeat_vram_included": bool(heartbeat_vram),
        "in_run_sample_count": len(in_run),
        "true_maximum_source": "heartbeat_and_in_run_samples",
    }


def finalize_hardware(
    *,
    sampler_hardware: dict[str, Any],
    heartbeat_vram: list[float] | None,
    placement: dict[str, Any],
    pre_unload_vram_gb: float | None = None,
    post_unload_vram_gb: float | None = None,
    ram_final_gb: float | None = None,
) -> dict[str, Any]:
    hardware = dict(sampler_hardware or {})
    vram = aggregate_vram(
        sampler_samples=list(hardware.get("samples") or []),
        heartbeat_vram=heartbeat_vram,
        pre_unload_vram_gb=pre_unload_vram_gb,
        post_unload_vram_gb=post_unload_vram_gb,
    )
    if vram.get("vram_peak_gb") is not None:
        hardware["vram_peak_gb"] = vram["vram_peak_gb"]
    if vram.get("vram_baseline_gb") is not None:
        hardware["vram_baseline_gb"] = vram["vram_baseline_gb"]
    hardware["vram_pre_unload_gb"] = vram.get("vram_pre_unload_gb")
    hardware["vram_post_unload_gb"] = vram.get("vram_post_unload_gb")
    if post_unload_vram_gb is not None:
        hardware["vram_final_gb"] = post_unload_vram_gb
    if ram_final_gb is not None:
        hardware["ram_final_gb"] = ram_final_gb
    hardware["placement"] = placement
    hardware["gpu_resident"] = bool(placement.get("gpu_resident"))
    hardware["cpu_offload"] = bool(placement.get("cpu_offload"))
    hardware["placement_status"] = placement.get("status")
    hardware["placement_reason"] = placement.get("reason")
    hardware["vram_delta_not_used_for_cpu_offload"] = True
    hardware["legacy_vram_delta"] = classify_from_vram_delta_only(
        vram.get("vram_peak_gb"), vram.get("vram_baseline_gb")
    )
    return hardware


def write_hardware_sidecar(root: Path, row: dict[str, Any], correction: dict[str, Any]) -> Path:
    folder = Path(row.get("_artifact_dir") or (root / "runs" / str(row["execution_id"])))
    original_hashes: dict[str, str] = {}
    for name in (
        "run_record.json",
        "token_accounting.json",
        "telemetry.jsonl",
        "raw_api.jsonl",
        "hardware_telemetry.json",
        "HASHES.txt",
    ):
        path = folder / name
        if path.is_file():
            original_hashes[name] = hashlib_file(path)
    payload = {
        "supersession_kind": "hardware_classification_correction",
        "original_execution_id": row.get("execution_id"),
        "original_files_rewritten": False,
        "original_hashes": original_hashes,
        "original_cpu_offload": row.get("cpu_offload"),
        "original_gpu_resident": row.get("gpu_resident"),
        "original_vram_peak_gb": row.get("vram_peak_gb"),
        "faulty_expression": FAULTY_CPU_OFFLOAD_EXPRESSION,
        "stop_was": correction.get("stop_was"),
        **correction,
    }
    cal_dir = root / "calibration"
    cal_dir.mkdir(parents=True, exist_ok=True)
    path = cal_dir / f"{row.get('execution_id')}.hardware_supersession.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path


def hashlib_file(path: Path) -> str:
    return _sha256_text(path.read_text(encoding="utf-8", errors="replace"))


def correct_false_cpu_offload_row(
    row: dict[str, Any],
    *,
    heartbeat_vram: list[float],
) -> dict[str, Any]:
    vram = aggregate_vram(
        sampler_samples=list((row.get("hardware") or {}).get("samples") or []),
        heartbeat_vram=heartbeat_vram,
        post_unload_vram_gb=row.get("vram_final_gb"),
    )
    placement = interpret_ollama_placement(
        None,
        tag=str(row.get("model_identity", {}).get("tag") or "qwen3:14b-q8_0"),
        digest=str(row.get("model_identity", {}).get("digest") or ""),
        queried_while_loaded=False,
    )
    if heartbeat_vram and max(heartbeat_vram) >= 10 and (row.get("vram_peak_gb") or 0) < 4:
        placement["reason"] = (
            "in_run_nvidia_samples_and_heartbeats_contradict; no /api/ps while loaded; "
            "cpu_offload_not_affirmative"
        )
        placement["status"] = "unknown"
        placement["cpu_offload"] = False
        placement["gpu_resident"] = False
    return {
        "corrected_cpu_offload": False,
        "corrected_gpu_resident": False,
        "corrected_placement_status": "unknown",
        "corrected_vram_peak_gb": vram.get("vram_peak_gb"),
        "heartbeat_vram_gb": heartbeat_vram,
        "placement": placement,
        "stop_was": "false_or_indeterminate",
        "not_a_stable_ladder_rung": True,
        "not_affirmative_cpu_offload": True,
        "not_affirmative_gpu_residency": True,
        "high_system_ram_not_used_as_offload": True,
    }


def apply_hardware_correction(row: dict[str, Any], correction: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["cpu_offload"] = bool(correction.get("corrected_cpu_offload"))
    updated["cpu_spill"] = bool(correction.get("corrected_cpu_offload"))
    updated["gpu_resident"] = bool(correction.get("corrected_gpu_resident"))
    if correction.get("corrected_vram_peak_gb") is not None:
        updated["vram_peak_gb"] = correction["corrected_vram_peak_gb"]
    updated["placement_status"] = correction.get("corrected_placement_status") or "unknown"
    updated["placement_reason"] = (correction.get("placement") or {}).get("reason")
    updated["hardware_classification_superseded"] = True
    updated["stable_ladder_rung"] = False
    return updated


def needs_gpu_placement_validation(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in reversed(runs):
        status = row.get("placement_status")
        if status == "gpu_resident" and row.get("final_safety_result") == "passed":
            return None
        if row.get("hardware_classification_superseded") or (
            row.get("cpu_offload") and not (row.get("placement") or {}).get("queried_while_loaded")
        ):
            if status != "gpu_resident":
                return row
        if status == "unknown":
            return row
    return None
