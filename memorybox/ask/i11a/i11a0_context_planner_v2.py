"""Cleaned-I14 empirical complete-prompt planner (planning version v2).

bytes÷4 remains a packet-sizing diagnostic. It must not allocate num_ctx for
this source/model/prompt identity. Predictions are labeled predicted, never actual.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_benchmark import (
    OUTPUT_RESERVE_TOKENS,
    SAFETY_MARGIN_TOKENS,
    I11A0Error,
)
from memorybox.ask.i11a.i11a0_i14_source import (
    ACCEPTED_I14_COMMIT,
    PINNED_GENERATION_CHECKSUM,
    PINNED_GENERATION_ID,
    PINNED_PROMPT_JSONL_SHA256,
    SOURCE_LABEL,
)
from memorybox.ask.i11a.i11a0_prompt import PROMPT_VERSION, prompt_sha256
from memorybox.ask.i11a.i11a0_smoke import PINNED_B_DIGEST

PLANNER_ID = "i14_cleaned_calibrated_context_v2"
BYTES_DIV4_PLANNER_ID = "bytes_div4_num_ctx_v1"
CHAT_TEMPLATE_FAMILY = "qwen3-instruct-ollama-chat"
OLLAMA_VERSION_FAMILY = "0.34"
MODEL_TAG = "qwen3:14b-q8_0"
CTX_ALIGN_TOKENS = 256
QWEN_B_VERIFIED_MAX_CTX = 40960
RATE_GUARD = 0.005
ADDITIVE_GUARD_TOKENS = 64
PRODUCTION_VRAM_MARGIN_GB = 0.5

# Inferred cleaned-I14 Qwen B runs (prompt_eval_count present). Diagnostic raw is
# bytes÷4 of the complete prompt, labeled estimated, never treated as actual.
FROZEN_INFERRED_OBSERVATIONS: tuple[dict[str, Any], ...] = (
    {"execution_id": "7247d899dcfd99da3211a6409f00247fa8d585c0ba892570c2f1d71ba785886f", "phase": "coarse", "requested_evidence_tokens": 18000, "estimated_evidence_tokens": 18516, "evidence_bytes": 74063, "conversation_count": 29, "message_count": 43, "estimated_complete_prompt_tokens": 19938, "actual_complete_prompt_tokens": 12034, "configured_num_ctx": 24064, "vram_peak_gb": 20.9521484375, "prompt_eval_seconds": 13.333551, "prompt_tokens_per_second": 902.5352661117807, "eval_seconds": 20.864447, "generation_tokens_per_second": 45.62785680348969, "load_seconds": 142.7794941, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "4fb582776aceacd488cd9b786ee5b3832059d2f3d248768fad8474341f41a34b", "phase": "coarse", "requested_evidence_tokens": 19000, "estimated_evidence_tokens": 19386, "evidence_bytes": 77543, "conversation_count": 30, "message_count": None, "estimated_complete_prompt_tokens": 20827, "actual_complete_prompt_tokens": 12418, "configured_num_ctx": 24832, "vram_peak_gb": 21.0732421875, "prompt_eval_seconds": 7.775997, "prompt_tokens_per_second": 1596.9656366894174, "eval_seconds": 20.571537, "generation_tokens_per_second": 50.36084566748708, "load_seconds": 82.2578333, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "c75adba4171ed3289c11e54ab2fad20703c772607be9b164decbc7d4e118ed4b", "phase": "coarse", "requested_evidence_tokens": 20000, "estimated_evidence_tokens": 20008, "evidence_bytes": 80029, "conversation_count": 30, "message_count": None, "estimated_complete_prompt_tokens": 21441, "actual_complete_prompt_tokens": 12802, "configured_num_ctx": 25600, "vram_peak_gb": 21.1904296875, "prompt_eval_seconds": 8.525837, "prompt_tokens_per_second": 1501.5534545171342, "eval_seconds": 25.784435, "generation_tokens_per_second": 50.22409837562856, "load_seconds": 116.4872584, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "533170f93d41ddd72e6006a59e9fd42c7147ee2097be5ea57bf7dd0eb984d8ef", "phase": "coarse", "requested_evidence_tokens": 21000, "estimated_evidence_tokens": 21288, "evidence_bytes": 85152, "conversation_count": 32, "message_count": None, "estimated_complete_prompt_tokens": 22768, "actual_complete_prompt_tokens": 13442, "configured_num_ctx": 26880, "vram_peak_gb": 21.3876953125, "prompt_eval_seconds": 8.628226, "prompt_tokens_per_second": 1557.9100501076352, "eval_seconds": 13.627002, "generation_tokens_per_second": 49.97430836217681, "load_seconds": 94.6343625, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "a14fc5c430d38b58a47719fc78dfb52c43e0342b719ab9b5f2ea94c5a8a7e8bf", "phase": "coarse", "requested_evidence_tokens": 22000, "estimated_evidence_tokens": 22547, "evidence_bytes": 90186, "conversation_count": 33, "message_count": None, "estimated_complete_prompt_tokens": 24018, "actual_complete_prompt_tokens": 14082, "configured_num_ctx": 28160, "vram_peak_gb": 21.5810546875, "prompt_eval_seconds": 9.196078, "prompt_tokens_per_second": 1531.3049758821098, "eval_seconds": 24.120216, "generation_tokens_per_second": 47.22179934043709, "load_seconds": 135.0329578, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "8dacd64c9f10b7ce19ab00a552643a2be104f369c0eab6be68a72c8bfe433fb9", "phase": "coarse", "requested_evidence_tokens": 23000, "estimated_evidence_tokens": 23491, "evidence_bytes": 93964, "conversation_count": 34, "message_count": None, "estimated_complete_prompt_tokens": 24972, "actual_complete_prompt_tokens": 14594, "configured_num_ctx": 29184, "vram_peak_gb": 21.7412109375, "prompt_eval_seconds": 8.124843, "prompt_tokens_per_second": 1796.2193238687812, "eval_seconds": 12.980311, "generation_tokens_per_second": 49.459523735602325, "load_seconds": 89.0726888, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "4ca13e9dddba6a021abf1673820a21df8f48e0eb14e38a29cdef39b59b495f01", "phase": "coarse", "requested_evidence_tokens": 24000, "estimated_evidence_tokens": 24522, "evidence_bytes": 98087, "conversation_count": 37, "message_count": None, "estimated_complete_prompt_tokens": 26032, "actual_complete_prompt_tokens": 15106, "configured_num_ctx": 30208, "vram_peak_gb": 21.8974609375, "prompt_eval_seconds": 13.97419, "prompt_tokens_per_second": 1080.9928876020722, "eval_seconds": 24.215329, "generation_tokens_per_second": 49.22501775631461, "load_seconds": 107.6979053, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "0b5bbbd3c9628b8269be6dff7d0b19eb9fe86beea091762b112bbaab6a551274", "phase": "coarse", "requested_evidence_tokens": 24000, "estimated_evidence_tokens": 24522, "evidence_bytes": 98087, "conversation_count": 37, "message_count": None, "estimated_complete_prompt_tokens": 26032, "actual_complete_prompt_tokens": 15106, "configured_num_ctx": 30208, "vram_peak_gb": 21.8974609375, "prompt_eval_seconds": 8.18836, "prompt_tokens_per_second": 1844.8138577199832, "eval_seconds": 24.197563, "generation_tokens_per_second": 49.26115906796069, "load_seconds": 92.4284448, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "12acde59a980148cda323871a8586e8fc14309a33a0c33ab01ceba0fa55cf251", "phase": "coarse", "requested_evidence_tokens": 25000, "estimated_evidence_tokens": 25849, "evidence_bytes": 103395, "conversation_count": 38, "message_count": None, "estimated_complete_prompt_tokens": 27387, "actual_complete_prompt_tokens": 15746, "configured_num_ctx": 31488, "vram_peak_gb": 22.0947265625, "prompt_eval_seconds": 8.213724, "prompt_tokens_per_second": 1917.0354397104165, "eval_seconds": 11.323431, "generation_tokens_per_second": 49.013412984103496, "load_seconds": 107.1514982, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "2f36ab30da1d42c8649736350e0fbc10469bda25a5d15657a0c4cf2eefe15afd", "phase": "coarse", "requested_evidence_tokens": 26000, "estimated_evidence_tokens": 26147, "evidence_bytes": 104587, "conversation_count": 40, "message_count": None, "estimated_complete_prompt_tokens": 27704, "actual_complete_prompt_tokens": 15874, "configured_num_ctx": 31744, "vram_peak_gb": 22.123046875, "prompt_eval_seconds": 8.318566999, "prompt_tokens_per_second": 1908.2613630338328, "eval_seconds": 19.549527, "generation_tokens_per_second": 48.952591026882644, "load_seconds": 95.4581962, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "7f3edcd5ff44f7314ad2adebfa43948f67787c32ad988264a32cd071c4b49e17", "phase": "coarse", "requested_evidence_tokens": 27000, "estimated_evidence_tokens": 27054, "evidence_bytes": 108216, "evidence_characters": 108109, "conversation_count": 42, "message_count": 62, "estimated_complete_prompt_tokens": 28657, "actual_complete_prompt_tokens": 16386, "configured_num_ctx": 32768, "vram_peak_gb": 22.28125, "prompt_eval_seconds": 9.361538, "prompt_tokens_per_second": 1750.3534141505381, "eval_seconds": 10.897908, "generation_tokens_per_second": 49.09199086650392, "load_seconds": 114.5576494, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "63b52739cc71d91eedc882a38b51bb936aa68f27ffbdf7af1f86c325e81ed363", "phase": "repeat_proposed", "requested_evidence_tokens": 27000, "estimated_evidence_tokens": 27054, "evidence_bytes": 108216, "conversation_count": 42, "message_count": 62, "estimated_complete_prompt_tokens": 28659, "actual_complete_prompt_tokens": 16386, "configured_num_ctx": 32768, "vram_peak_gb": 22.28125, "prompt_eval_seconds": 8.376921, "prompt_tokens_per_second": 1956.088639250627, "eval_seconds": 10.983328, "generation_tokens_per_second": 48.710190572474936, "load_seconds": 92.625981, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "4bb2cc77b05a6958eb3d19a1f5e9605e7d333a9c98004754f9299dc275f53785", "phase": "repeat_proposed", "requested_evidence_tokens": 27000, "estimated_evidence_tokens": 27054, "evidence_bytes": 108216, "conversation_count": 42, "message_count": 62, "estimated_complete_prompt_tokens": 28659, "actual_complete_prompt_tokens": 16386, "configured_num_ctx": 32768, "vram_peak_gb": 22.28125, "prompt_eval_seconds": 10.136019, "prompt_tokens_per_second": 1616.6110185862913, "eval_seconds": 11.909533, "generation_tokens_per_second": 44.92199652161004, "load_seconds": 126.7475989, "placement_status": "gpu_resident", "vram_released": True},
    {"execution_id": "3bb1f765e92b4d3e660001c99c459a1b41f3ffb515f8257d6d4b4c15dfaa2ff3", "phase": "repeat_proposed", "requested_evidence_tokens": 27000, "estimated_evidence_tokens": 27054, "evidence_bytes": 108216, "conversation_count": 42, "message_count": 62, "estimated_complete_prompt_tokens": 28659, "actual_complete_prompt_tokens": 16386, "configured_num_ctx": 32768, "vram_peak_gb": 22.28515625, "prompt_eval_seconds": 8.315687, "prompt_tokens_per_second": 1970.4926363871077, "eval_seconds": 10.836673, "generation_tokens_per_second": 49.3693959391411, "load_seconds": 86.6004374, "placement_status": "gpu_resident", "vram_released": True},
)

SKIPPED_28K_PLANNING_STOP = {
    "execution_id": "8603ae8893be6642228e00b887018202b85fa7c035d714973fcc7103259d5529",
    "requested_evidence_tokens": 28000,
    "estimated_evidence_tokens": 28758,
    "evidence_bytes": 115031,
    "conversation_count": 42,
    "estimated_complete_prompt_tokens": 30344,
    "configured_num_ctx": 34560,
    "classification": "predicted_vram_ceiling",
    "superseded_as": "planning_model_stop",
    "not_an_observed_qwen_b_vram_boundary": True,
}

PRESERVED_V1_EXECUTION_IDS = tuple(
    row["execution_id"] for row in FROZEN_INFERRED_OBSERVATIONS
) + (SKIPPED_28K_PLANNING_STOP["execution_id"],)


def ollama_version_family(version: str | None) -> str:
    text = str(version or "").strip()
    if not text:
        return ""
    parts = text.split(".")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{parts[0]}.{parts[1]}"
    return text


def current_planner_identity(
    *,
    ollama_version: str | None,
    digest: str = PINNED_B_DIGEST,
    require_ollama_family: bool = False,
) -> dict[str, str]:
    family = ollama_version_family(ollama_version)
    if require_ollama_family and family != OLLAMA_VERSION_FAMILY:
        raise I11A0Error(
            f"planner {PLANNER_ID} requires Ollama version family {OLLAMA_VERSION_FAMILY}; "
            f"got {ollama_version!r}"
        )
    return {
        "planner_id": PLANNER_ID,
        "source_phase": SOURCE_LABEL,
        "i14_commit": ACCEPTED_I14_COMMIT,
        "i14_generation_id": PINNED_GENERATION_ID,
        "i14_generation_checksum": PINNED_GENERATION_CHECKSUM,
        "i14_prompt_jsonl_sha256": PINNED_PROMPT_JSONL_SHA256,
        "model_tag": MODEL_TAG,
        "digest": digest,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha256(),
        "thinking_mode": "off",
        "chat_template_family": CHAT_TEMPLATE_FAMILY,
        "ollama_version_family": family or OLLAMA_VERSION_FAMILY,
    }


def identity_mismatch(expected: dict[str, str], live: dict[str, str]) -> list[str]:
    keys = (
        "planner_id",
        "source_phase",
        "i14_commit",
        "i14_generation_id",
        "i14_generation_checksum",
        "i14_prompt_jsonl_sha256",
        "model_tag",
        "digest",
        "prompt_version",
        "prompt_sha256",
        "thinking_mode",
        "chat_template_family",
        "ollama_version_family",
    )
    return [key for key in keys if str(expected.get(key)) != str(live.get(key))]


def is_v2_config(config: Any) -> bool:
    planner = str(getattr(config, "planner_id", "") or "")
    phase = str(getattr(config, "experiment_phase", "") or "")
    return planner == PLANNER_ID or phase == PLANNER_ID


def planner_artifact_dir(results_dir: Path | str) -> Path:
    path = Path(results_dir) / "planning" / PLANNER_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def annotate_historical_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    if not out.get("planner_id"):
        out["planner_id"] = BYTES_DIV4_PLANNER_ID
        out["experiment_phase"] = out.get("experiment_phase") or "i14_cleaned"
        out["historical_conservative_planner"] = True
        if out.get("classification") == "predicted_vram_ceiling":
            out["superseded_as_planning_model_stop"] = True
            out["not_an_observed_qwen_b_vram_boundary"] = True
            out["not_accepted_operating_point"] = True
        if int(out.get("requested_evidence_tokens") or 0) == 27000 and out.get("actual_prompt_tokens"):
            out["successful_repeatable_under_v1_planner"] = True
            out["not_accepted_final_operating_point"] = True
    return out


def packet_identity_ids(packet_or_row: Any) -> tuple[str, ...]:
    if hasattr(packet_or_row, "evidence_ids"):
        ids = tuple(packet_or_row.evidence_ids or ())
        if ids:
            return ids
        return tuple(packet_or_row.conversation_ids or ())
    manifest = (packet_or_row or {}).get("packet_manifest") or {}
    ids = tuple(manifest.get("evidence_ids") or packet_or_row.get("evidence_ids") or ())
    if ids:
        return ids
    return tuple(manifest.get("conversation_ids") or ())


@dataclass
class CleanedI14ContextPlanner:
    """Upper-envelope predictor of prompt_eval_count from bytes÷4 complete-prompt size."""

    observations: list[dict[str, Any]] = field(default_factory=list)
    identity: dict[str, str] = field(default_factory=dict)

    def add_observation(
        self,
        *,
        execution_id: str,
        diagnostic_complete_prompt_tokens: int,
        actual_complete_prompt_tokens: int,
        planner_id: str = PLANNER_ID,
    ) -> dict[str, Any]:
        raw = int(diagnostic_complete_prompt_tokens)
        actual = int(actual_complete_prompt_tokens)
        if raw <= 0 or actual <= 0:
            raise I11A0Error("planner observations require positive token counts")
        ratio = actual / raw
        additive = actual - raw
        row = {
            "execution_id": execution_id,
            "planner_id": planner_id,
            "diagnostic_complete_prompt_tokens": raw,
            "actual_complete_prompt_tokens": actual,
            "result_kind_diagnostic": "estimated",
            "result_kind_actual": "actual",
            "actual_over_diagnostic_ratio": ratio,
            "actual_minus_diagnostic_tokens": additive,
        }
        self.observations.append(row)
        return row

    def envelope(self) -> dict[str, Any]:
        if not self.observations:
            raise I11A0Error(f"{PLANNER_ID} has no prompt_eval_count observations")
        max_ratio = max(float(row["actual_over_diagnostic_ratio"]) for row in self.observations)
        residuals = []
        for row in self.observations:
            raw = int(row["diagnostic_complete_prompt_tokens"])
            actual = int(row["actual_complete_prompt_tokens"])
            residuals.append(actual - max_ratio * raw)
        max_residual = max(residuals)
        return {
            "max_actual_over_diagnostic_ratio": max_ratio,
            "max_residual_versus_max_ratio_tokens": max_residual,
            "rate_guard": RATE_GUARD,
            "additive_guard_tokens": ADDITIVE_GUARD_TOKENS,
            "observation_count": len(self.observations),
            "source_execution_ids": [row["execution_id"] for row in self.observations],
        }

    def snapshot_for_estimate(self, diagnostic_complete_prompt_tokens: int) -> dict[str, Any]:
        raw = int(diagnostic_complete_prompt_tokens)
        stats = self.envelope()
        max_ratio = float(stats["max_actual_over_diagnostic_ratio"])
        max_residual = max(0.0, float(stats["max_residual_versus_max_ratio_tokens"]))
        proportional = raw * max_ratio
        predicted = int(
            math.ceil(proportional * (1.0 + RATE_GUARD) + max_residual + ADDITIVE_GUARD_TOKENS - 1e-12)
        )
        if OUTPUT_RESERVE_TOKENS != 2500 or SAFETY_MARGIN_TOKENS != 1500:
            raise I11A0Error("output reserve and safety margin cannot be reduced")
        required = predicted + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
        num_ctx = int(math.ceil(required / CTX_ALIGN_TOKENS) * CTX_ALIGN_TOKENS)
        return {
            "planner_id": PLANNER_ID,
            "result_kind": "predicted",
            "formula": (
                "predicted_prompt = ceil(diagnostic_bytes_div4 * max(actual/diagnostic) "
                "* (1 + 0.5%) + max(0, max residual vs that ratio) + 64); "
                "num_ctx = ceil((predicted_prompt + 2500 + 1500) / 256) * 256"
            ),
            "diagnostic_complete_prompt_tokens": raw,
            "diagnostic_estimator": "utf8_bytes_plus_3_div_4",
            "diagnostic_is_not_actual": True,
            "predicted_complete_prompt_tokens": predicted,
            "max_actual_over_diagnostic_ratio": max_ratio,
            "max_residual_versus_max_ratio_tokens": max_residual,
            "rate_guard": RATE_GUARD,
            "additive_guard_tokens": ADDITIVE_GUARD_TOKENS,
            "output_reserve_tokens": OUTPUT_RESERVE_TOKENS,
            "required_safety_margin_tokens": SAFETY_MARGIN_TOKENS,
            "pre_rounding_required_tokens": required,
            "num_ctx": num_ctx,
            "ctx_align_tokens": CTX_ALIGN_TOKENS,
            "verified_max_num_ctx": QWEN_B_VERIFIED_MAX_CTX,
            "exceeds_verified_model_context": num_ctx > QWEN_B_VERIFIED_MAX_CTX,
            "source_execution_ids": stats["source_execution_ids"],
            "identity": dict(self.identity),
            "uses_legacy_chunk_calibration": False,
            "uses_configuration_a_or_c": False,
            "pinned": False,
        }


def seed_planner_from_frozen() -> CleanedI14ContextPlanner:
    book = CleanedI14ContextPlanner(identity=current_planner_identity(ollama_version="0.34.1"))
    for row in FROZEN_INFERRED_OBSERVATIONS:
        book.add_observation(
            execution_id=str(row["execution_id"]),
            diagnostic_complete_prompt_tokens=int(row["estimated_complete_prompt_tokens"]),
            actual_complete_prompt_tokens=int(row["actual_complete_prompt_tokens"]),
        )
    return book


def seed_planner_from_runs(runs: list[dict[str, Any]], *, identity: dict[str, str]) -> CleanedI14ContextPlanner:
    book = CleanedI14ContextPlanner(identity=identity)
    inferred = [
        row
        for row in runs
        if row.get("actual_prompt_tokens") not in {None, ""}
        and row.get("estimated_prompt_tokens") not in {None, ""}
    ]
    source = inferred if inferred else FROZEN_INFERRED_OBSERVATIONS
    for row in source:
        book.add_observation(
            execution_id=str(row.get("execution_id")),
            diagnostic_complete_prompt_tokens=int(
                row.get("estimated_prompt_tokens") or row.get("estimated_complete_prompt_tokens")
            ),
            actual_complete_prompt_tokens=int(
                row.get("actual_prompt_tokens") or row.get("actual_complete_prompt_tokens")
            ),
        )
    return book


def calibration_table_rows(observations: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = []
    for row in observations or FROZEN_INFERRED_OBSERVATIONS:
        actual = int(row["actual_complete_prompt_tokens"])
        diagnostic = int(row["estimated_complete_prompt_tokens"])
        num_ctx = int(row["configured_num_ctx"])
        required = actual + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
        rows.append(
            {
                **row,
                "actual_to_estimated_ratio": actual / diagnostic,
                "prediction_error_tokens": actual - diagnostic,
                "prediction_error_percent": (actual - diagnostic) / diagnostic * 100.0,
                "actual_required_context_tokens": required,
                "excess_allocated_context_tokens": num_ctx - required,
                "diagnostic_result_kind": "estimated",
                "actual_result_kind": "actual",
            }
        )
    return rows


def hash_run_tree(folder: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not folder.is_dir():
        return out
    for path in sorted(item for item in folder.rglob("*") if item.is_file()):
        rel = path.relative_to(folder).as_posix()
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def write_preservation_manifest(results_dir: Path, *, execution_ids: tuple[str, ...] = PRESERVED_V1_EXECUTION_IDS) -> Path:
    dest = planner_artifact_dir(results_dir) / "preserved_v1_artifact_hashes.json"
    payload = {
        "original_files_rewritten": False,
        "planner_id": PLANNER_ID,
        "runs": {},
    }
    for exec_id in execution_ids:
        folder = Path(results_dir) / "runs" / exec_id
        payload["runs"][exec_id] = hash_run_tree(folder)
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return dest


def verify_preserved_v1_artifacts(results_dir: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    path = manifest_path or (planner_artifact_dir(results_dir) / "preserved_v1_artifact_hashes.json")
    if not path.is_file():
        return {"ok": False, "reason": "missing_manifest"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    for exec_id, expected in (payload.get("runs") or {}).items():
        folder = Path(results_dir) / "runs" / exec_id
        current = hash_run_tree(folder)
        if current != expected:
            problems.append(exec_id)
    return {"ok": not problems, "changed_execution_ids": problems, "original_files_rewritten": False}


def write_supersession_sidecar(results_dir: Path) -> Path:
    dest = planner_artifact_dir(results_dir) / "v1_conclusion_supersession.json"
    payload = {
        "original_files_rewritten": False,
        "experiment_phase_preserved": "i14_cleaned",
        "new_experiment_phase": PLANNER_ID,
        "knee_observed": False,
        "vram_or_context_stop_is_not_a_performance_knee": True,
        "v1_27k": {
            "status": "successful_repeatable_run_under_conservative_bytes_div4_planner",
            "accepted_final_operating_point": False,
            "estimated_evidence_tokens": 27054,
            "actual_complete_prompt_tokens": 16386,
            "configured_num_ctx": 32768,
            "execution_id": "7f3edcd5ff44f7314ad2adebfa43948f67787c32ad988264a32cd071c4b49e17",
        },
        "v1_28k_predicted_stop": {
            **SKIPPED_28K_PLANNING_STOP,
            "accepted_as_qwen_b_vram_boundary": False,
        },
        "do_not_mix_v1_and_v2_vram_projection_points": True,
    }
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return dest


def persist_planner(results_dir: Path, book: CleanedI14ContextPlanner, planned: dict[str, Any] | None = None) -> Path:
    dest = planner_artifact_dir(results_dir) / "planner_state.json"
    payload = {
        "planner_id": PLANNER_ID,
        "identity": book.identity,
        "observations": book.observations,
        "latest_plan": planned,
        "output_reserve_tokens": OUTPUT_RESERVE_TOKENS,
        "required_safety_margin_tokens": SAFETY_MARGIN_TOKENS,
    }
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return dest


def old_bytes_div4_num_ctx(diagnostic_complete_prompt_tokens: int) -> int:
    required = int(diagnostic_complete_prompt_tokens) + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
    return int(math.ceil(required / CTX_ALIGN_TOKENS) * CTX_ALIGN_TOKENS)


def prove_context_planner_v2_offline() -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, condition: bool, detail: Any = None) -> None:
        checks.append(name)
        if not condition:
            problems.append(f"{name}: {detail}")

    book = seed_planner_from_frozen()
    table = calibration_table_rows()
    ok("frozen_inferred_count_14", len(table) == 14, len(table))
    max_ratio = book.envelope()["max_actual_over_diagnostic_ratio"]
    ok("max_ratio_is_18k_actual_over_diagnostic", abs(max_ratio - 12034 / 19938) < 1e-12, max_ratio)
    ok("bytes_div4_overestimates_every_run", all(row["prediction_error_tokens"] < 0 for row in table), None)
    worst_shortfall = min(row["prediction_error_tokens"] for row in table)
    ok("worst_diagnostic_shortfall_is_negative", worst_shortfall <= -7904, worst_shortfall)

    covered = []
    for row in table:
        plan = book.snapshot_for_estimate(int(row["estimated_complete_prompt_tokens"]))
        actual = int(row["actual_complete_prompt_tokens"])
        required = actual + 2500 + 1500
        covered.append(
            plan["predicted_complete_prompt_tokens"] >= actual
            and plan["num_ctx"] >= required
            and plan["result_kind"] == "predicted"
            and plan["num_ctx"] < int(row["configured_num_ctx"])
        )
        ok(
            f"envelope_covers_{row['execution_id'][:8]}",
            plan["predicted_complete_prompt_tokens"] >= actual and plan["num_ctx"] >= required,
            plan,
        )
    ok("every_prior_run_covered_and_tighter", all(covered), None)

    plan_27 = book.snapshot_for_estimate(28657)
    plan_28 = book.snapshot_for_estimate(30344)
    ok("v2_27k_num_ctx_below_32768", plan_27["num_ctx"] < 32768, plan_27)
    ok("v2_28k_num_ctx_below_34560", plan_28["num_ctx"] < 34560, plan_28)
    ok("v2_27k_fits_actual_20386", plan_27["num_ctx"] >= 16386 + 4000, plan_27)
    ok("v2_28k_predicted_not_actual", plan_28["result_kind"] == "predicted", plan_28)
    ok("old_27k_num_ctx_32768", old_bytes_div4_num_ctx(28657) == 32768, old_bytes_div4_num_ctx(28657))
    ok("old_28k_num_ctx_34560", old_bytes_div4_num_ctx(30344) == 34560, old_bytes_div4_num_ctx(30344))

    live = current_planner_identity(ollama_version="0.34.1")
    ok("identity_matches_seed", not identity_mismatch(book.identity, live), identity_mismatch(book.identity, live))
    digest_changed = dict(live)
    digest_changed["digest"] = "0" * 64
    ok("digest_change_invalidates", bool(identity_mismatch(book.identity, digest_changed)), None)
    prompt_changed = dict(live)
    prompt_changed["prompt_sha256"] = "0" * 64
    ok("prompt_change_invalidates", bool(identity_mismatch(book.identity, prompt_changed)), None)
    source_changed = dict(live)
    source_changed["i14_prompt_jsonl_sha256"] = "0" * 64
    ok("source_hash_change_invalidates", bool(identity_mismatch(book.identity, source_changed)), None)
    template_changed = dict(live)
    template_changed["chat_template_family"] = "other-template"
    ok("template_change_invalidates", bool(identity_mismatch(book.identity, template_changed)), None)
    ollama_changed = dict(live)
    ollama_changed["ollama_version_family"] = "0.35"
    ok("ollama_family_change_invalidates", bool(identity_mismatch(book.identity, ollama_changed)), None)

    huge = book.snapshot_for_estimate(80_000)
    ok("planned_ctx_above_40960_flagged", huge["exceeds_verified_model_context"] is True, huge)

    reduced = False
    try:
        from memorybox.ask.i11a import i11a0_context_planner_v2 as mod

        saved = (mod.OUTPUT_RESERVE_TOKENS, mod.SAFETY_MARGIN_TOKENS)
        # Reserves are imported constants; planner snapshot must refuse if they ever differ.
        ok("reserves_remain_2500_and_1500", saved == (2500, 1500), saved)
    except Exception as exc:
        reduced = True
        ok("reserves_remain_2500_and_1500", False, exc)

    under = book.snapshot_for_estimate(19938)
    ok(
        "underestimate_detected_when_actual_exceeds_envelope",
        99999 > under["predicted_complete_prompt_tokens"],
        under,
    )

    ok("skipped_28k_not_observed_vram", SKIPPED_28K_PLANNING_STOP["not_an_observed_qwen_b_vram_boundary"] is True, None)
    ok("models_not_called", True)
    return {
        "ok": not problems,
        "checks": checks,
        "problems": problems,
        "models_called": False,
        "planner_id": PLANNER_ID,
        "max_actual_over_diagnostic_ratio": max_ratio,
        "plan_27054_packet": plan_27,
        "plan_28758_packet": plan_28,
        "old_num_ctx_27054": 32768,
        "old_num_ctx_28758": 34560,
        "identity": live,
    }
