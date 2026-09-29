"""Qwen B 27K/39424 VRAM closeout sidecar. Never rewrites protected run files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_benchmark import I11A0Error
from memorybox.ask.i11a.i11a0_confirmation_runtime import PROTECTED_ORIGINAL_NAMES

QWEN_VRAM_CLOSEOUT_CLASS = "full_prompt_valid_vram_ceiling_stop_before_accepted_narration"
QWEN_VRAM_CLOSEOUT_EXECUTION_ID = "425769b621ee5ecaeec3d1b56d1c0b507c5ee064ca33d50f0d8d79eaa34e34fa"
SIDECAR_NAME = "qwen_vram_closeout.sidecar.json"


def qwen_vram_closeout_payload() -> dict[str, Any]:
    return {
        "execution_id": QWEN_VRAM_CLOSEOUT_EXECUTION_ID,
        "original_files_rewritten": False,
        "classification": QWEN_VRAM_CLOSEOUT_CLASS,
        "tag": "qwen3:14b-q8_0",
        "digest": "304bf7349c71ad37a07eec8be67212b3f05b0f243f4a6f7c98e90dd2f3009f48",
        "complete_prompt_tokens_log": 35333,
        "num_ctx": 39424,
        "truncate": False,
        "shift": False,
        "truncation_occurred": False,
        "above_historical_half_window": True,
        "prompt_evaluated_intact": True,
        "peak_vram_gb": 23.1376953125,
        "vram_ceiling_gb": 22.5,
        "vram_ceiling_exceeded": True,
        "generation_output_accepted": False,
        "generation_output_reviewed": False,
        "narration_quality_conclusion": None,
        "not_classified_as": [
            "infrastructure_failure",
            "model_quality_failure",
            "truncation_failure",
            "capacity_result_invalidation",
        ],
        "preserve": {
            "accepted_27k_capacity_as_laboratory_evidence": True,
            "failed_and_lost_v03_attempts": True,
            "sidecars_and_hashes": True,
            "historical_capacity_vs_production_operating_suitability": True,
        },
        "production_conclusion": (
            "Qwen B at the 27K / 39424-context operating point lacks adequate "
            "operational VRAM headroom on FlightSim. Do not generate Qwen again."
        ),
        "do_not_retry_qwen": True,
        "do_not_start_gemma_from_this_sidecar": True,
    }


def write_qwen_vram_closeout_sidecar(run_dir: Path | str) -> dict[str, Any]:
    root = Path(run_dir)
    before = {
        name: (root / name).read_bytes() if (root / name).is_file() else None
        for name in PROTECTED_ORIGINAL_NAMES
    }
    dest = root / SIDECAR_NAME
    body = qwen_vram_closeout_payload()
    dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8", newline="\n")
    after = {
        name: (root / name).read_bytes() if (root / name).is_file() else None
        for name in PROTECTED_ORIGINAL_NAMES
    }
    if before != after:
        raise I11A0Error("Qwen closeout sidecar mutated a protected original artifact")
    return {"ok": True, "path": str(dest), "originals_unchanged": True, "payload": body}
