"""Post-unload /api/ps + nvidia-smi polling. Does not overwrite in-request VRAM peak."""
from __future__ import annotations

import time
from typing import Any, Callable

from memorybox.ask.i11a.i11a0_host import read_nvidia_snapshot
from memorybox.ask.i11a.i11a0_placement import read_ollama_ps
from memorybox.ask.i11a.i11a0_smoke import VRAM_RELEASE_SLACK_GB, _unload, _vram_released

UNLOAD_POLL_SECONDS = 2.0
UNLOAD_POLL_MAX_SECONDS = 120.0


def model_present_in_ps(payload: dict[str, Any] | None, tag: str) -> bool:
    models = list((payload or {}).get("models") or [])
    needle = str(tag or "").lower()
    for item in models:
        name = str(item.get("name") or item.get("model") or "").lower()
        if needle and needle == name:
            return True
        if needle and needle in name:
            return True
    return False


def verify_unload(
    *,
    base_url: str,
    tag: str,
    in_request_peak_vram_gb: float | None,
    pre_load_baseline_vram_gb: float | None,
    pre_unload_vram_gb: float | None,
    unload_fn: Callable[[str, str], float] | None = None,
    ps_fn: Callable[[str], dict[str, Any]] | None = None,
    nvidia_fn: Callable[[], dict[str, Any]] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    poll_seconds: float = UNLOAD_POLL_SECONDS,
    max_seconds: float = UNLOAD_POLL_MAX_SECONDS,
    slack_gb: float = VRAM_RELEASE_SLACK_GB,
) -> dict[str, Any]:
    unload = unload_fn or (lambda url, model: _unload(url, model))
    ps = ps_fn or read_ollama_ps
    nvidia = nvidia_fn or read_nvidia_snapshot
    sleeper = sleep_fn or time.sleep
    started = time.monotonic()
    unload_http_s = unload(base_url, tag)
    immediate = nvidia()
    ps_payload = ps(base_url)
    present = model_present_in_ps(ps_payload, tag)
    samples: list[dict[str, Any]] = [
        {
            "phase": "immediate_post_unload",
            "elapsed_s": 0.0,
            "vram_used_gb": immediate.get("memory_used_gb"),
            "ps_model_present": present,
            "ps": ps_payload,
            "nvidia": immediate,
        }
    ]
    if (not present) and _vram_released(pre_load_baseline_vram_gb, immediate.get("memory_used_gb")):
        model_absent_at = 0.0
    else:
        deadline = started + float(max_seconds)
        model_absent_at = None if present else 0.0
        while time.monotonic() < deadline:
            sleeper(float(poll_seconds))
            elapsed = time.monotonic() - started
            snap = nvidia()
            ps_payload = ps(base_url)
            present = model_present_in_ps(ps_payload, tag)
            used = snap.get("memory_used_gb")
            samples.append(
                {
                    "phase": "poll",
                    "elapsed_s": elapsed,
                    "vram_used_gb": used,
                    "ps_model_present": present,
                    "ps": ps_payload,
                    "nvidia": snap,
                }
            )
            if not present and model_absent_at is None:
                model_absent_at = elapsed
            if not present and _vram_released(pre_load_baseline_vram_gb, used):
                break
    settled = samples[-1]
    settled_vram = settled.get("vram_used_gb")
    model_absent = model_absent_at is not None or settled.get("ps_model_present") is False
    vram_returned = _vram_released(pre_load_baseline_vram_gb, settled_vram)
    delayed = bool(model_absent and not vram_returned)
    still_loaded = not model_absent
    if still_loaded:
        kind = "model_still_loaded"
    elif delayed:
        kind = "delayed_or_unreleased_vram"
    elif vram_returned:
        kind = "clean_unload_settled_vram"
    else:
        kind = "unload_vram_not_returned"
    return {
        "unload_http_seconds": unload_http_s,
        "poll_seconds": float(poll_seconds),
        "max_seconds": float(max_seconds),
        "vram_release_slack_gb": float(slack_gb),
        "vram_return_to_baseline_equation": "settled_vram <= pre_load_baseline + 2.0",
        "pre_load_baseline_vram_gb": pre_load_baseline_vram_gb,
        "in_request_peak_vram_gb": in_request_peak_vram_gb,
        "pre_unload_vram_gb": pre_unload_vram_gb,
        "immediate_post_unload_vram_gb": samples[0].get("vram_used_gb"),
        "settled_post_unload_vram_gb": settled_vram,
        "peak_not_overwritten_by_post_unload": True,
        "model_absent_from_api_ps": model_absent,
        "model_absent_after_seconds": model_absent_at,
        "vram_returned_to_baseline": vram_returned,
        "high_system_ram_is_not_cpu_offload": True,
        "classification": kind,
        "samples": samples,
        "unload_recorded": True,
        "vram_released": bool(vram_returned and model_absent),
        "vram_final_gb": settled_vram,
    }
