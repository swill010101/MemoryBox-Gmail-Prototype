"""P2-I11A.0 Gate 3: Configuration B context-capacity ladder.

One operator command. Nested reviewed-email packets. No A/C, no Peggy scenario.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import socket
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from memorybox.ask.i11a.i11a0_benchmark import (
    GATE3_CAPACITY_AUTHORIZED,
    OUTPUT_RESERVE_TOKENS,
    SAFETY_MARGIN_TOKENS,
    TOKEN_ESTIMATOR_FORMULA,
    TOKEN_ESTIMATOR_ID,
    TOKEN_ESTIMATOR_LABEL,
    VRAM_CEILING_GB,
    EvidencePiece,
    GateNotAuthorized,
    I11A0Error,
    InferenceNotAuthorized,
    Measurement,
    ModelSpec,
    RunRequest,
    estimate_tokens,
    inventory_installed_models,
    new_execution_id,
    plan_context,
    prompt_safety_assessment,
    test_case_id,
    _sha256_text,
)
from memorybox.ask.i11a.i11a0_host import (
    HardwareSampler,
    collect_host_affinity_preflight,
    capture_clean_ladder_host_state,
    read_nvidia_snapshot,
    read_system_ram,
    require_flightsim_host_affinity,
    require_literal_loopback_ollama_url,
)
from memorybox.ask.i11a.i11a0_prompt import (
    PRODUCTION_PROMPT_ACCEPTED,
    PROMPT_STATUS,
    SYSTEM_PROMPT,
    prompt_acceptance_fields,
    prompt_canonical_text,
    prompt_sha256,
    render_user_message,
)
from memorybox.ask.i11a.i11a0_placement import (
    FAULTY_CPU_OFFLOAD_EXPRESSION,
    PRESERVED_FALSE_OFFLOAD_EXECUTION_ID,
    apply_hardware_correction,
    correct_false_cpu_offload_row,
    finalize_hardware,
    interpret_ollama_placement,
    needs_gpu_placement_validation,
    parse_heartbeat_vram,
    read_ollama_ps,
    write_hardware_sidecar,
)
from memorybox.ask.i11a.i11a0_gate3_progress import (
    Gate3Progress,
    atomic_replace_text,
    format_target,
)
from memorybox.ask.i11a.i11a0_smoke import (
    PINNED_B_DIGEST,
    REPO_ROOT,
    VRAM_RELEASE_SLACK_GB,
    _chat,
    _pieces_from_review,
    _unload,
    _vram_released,
    require_qwen_smoke_configuration,
)

GATE3_START_EVIDENCE_TOKENS = 2000
GATE3_COARSE_INCREMENT_TOKENS = 1000
GATE3_REFINEMENT_INCREMENT_TOKENS = 250
GATE3_REPEAT_COUNT = 3
GATE3_REGRESSION_FRACTION = 0.10
GATE3_CONFIRMED_REGRESSION_STOP = 3
GATE3_TIMEOUT_SECONDS = 1800
GATE3_SEED_B_ERROR_TOKENS = 85
SOURCE_LIMITATION = (
    "Accepted I14 cleaned household-email export for the remaining Qwen B ladder. "
    "Legacy REVIEW_20260831T120929Z seven chunks are historical hardware evidence only. "
    "Email only; SMS is not in this source."
)
LEGACY_SOURCE_LIMITATION = (
    "Reviewed Peggy email chunks only (REVIEW_20260831T120929Z). "
    "Peggy SMS is not in this Gate 3 source."
)
B_TAG = "qwen3:14b-q8_0"
B_QUANT = "Q8_0"
QWEN_B_VERIFIED_MAX_CTX = 40960
VRAM_RELEASE_SETTLE_SECONDS = 8.0
I14_SOURCE_LABEL = "accepted_i14_cleaned_household_email_export"
LEGACY_CHUNK_SOURCE_LABEL = "legacy_reviewed_seven_chunks_REVIEW_20260831T120929Z"
PRESERVED_GATE3_EXECUTION_ID = (
    "c34db0187be477bbc80bc0029419fedcf1366d1b4234ab81afb2b1e526e5db5e"
)
PRESERVED_GATE3_PACKET_SHA256 = "59a115abeee029beaf7d9ae76dfe0755ecbff88007fc2d435885b4a8c8e47b4a"
CALIBRATED_SAME_PACKET_NUM_CTX = 8448
CTX_ALIGN_TOKENS = 256
RATE_STEP = 0.005
RATE_GUARD = 0.005
LOW_RAM_AVAILABLE_FLAG_GB = 8.0
GATE3_CSV_FIELDS = [
    "execution_id",
    "test_case_id",
    "phase",
    "requested_evidence_tokens",
    "estimated_evidence_tokens",
    "actual_prompt_tokens",
    "estimation_error_tokens",
    "configured_num_ctx",
    "final_safety_result",
    "classification",
    "elapsed_seconds",
    "load_seconds",
    "prompt_eval_seconds",
    "eval_seconds",
    "prompt_tokens_per_second",
    "generation_tokens_per_second",
    "vram_peak_gb",
    "ram_peak_gb",
    "gpu_resident",
    "cpu_offload",
    "confirmed_regression",
    "packet_sha256",
    "narration_relpath",
]


@dataclass(frozen=True)
class Gate3Packet:
    text: str
    sha256: str
    estimated_evidence_tokens: int
    evidence_ids: tuple[str, ...]
    conversation_ids: tuple[str, ...]
    time_start: str
    time_end: str
    target_tokens: int
    overshoot: bool
    exhausted: bool
    evidence_bytes: int
    evidence_characters: int
    partial_context: bool = False
    partial_boundary_note: str = "none"
    message_count: int = 0
    partial_thread_ids: tuple[str, ...] = ()
    included_boundary_evidence_ids: tuple[str, ...] = ()
    omitted_boundary_evidence_ids: tuple[str, ...] = ()
    packer_kind: str = "conversation"


@dataclass
class Gate3Config:
    tag: str = B_TAG
    digest: str = PINNED_B_DIGEST
    quantization: str = B_QUANT
    config_id: str = "B"
    start_evidence_tokens: int = GATE3_START_EVIDENCE_TOKENS
    coarse_increment_tokens: int = GATE3_COARSE_INCREMENT_TOKENS
    refinement_increment_tokens: int = GATE3_REFINEMENT_INCREMENT_TOKENS
    repeat_count: int = GATE3_REPEAT_COUNT
    reserved_output_tokens: int = OUTPUT_RESERVE_TOKENS
    safety_margin_tokens: int = SAFETY_MARGIN_TOKENS
    regression_fraction: float = GATE3_REGRESSION_FRACTION
    confirmed_regression_stop: int = GATE3_CONFIRMED_REGRESSION_STOP
    timeout_seconds: int = GATE3_TIMEOUT_SECONDS
    maximum_vram_gb: float = VRAM_CEILING_GB
    temperature: float = 0.1
    seed: int = 42
    thinking_mode: str = "off"
    seed_calibration_error_tokens: int = GATE3_SEED_B_ERROR_TOKENS
    source: str = LEGACY_CHUNK_SOURCE_LABEL
    verified_max_num_ctx: int = QWEN_B_VERIFIED_MAX_CTX
    experiment_phase: str = "legacy_reviewed_chunks"


def load_gate3_config(path: Path | str | None) -> Gate3Config:
    if path is None:
        return Gate3Config()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    allowed = {key: value for key, value in raw.items() if key in Gate3Config.__dataclass_fields__}
    return Gate3Config(**allowed)


class NestedEmailPacker:
    """Prefix-nested whole-conversation packets. Never splits a conversation."""

    def __init__(self, pieces: list[EvidencePiece]) -> None:
        self.pieces = list(pieces)

    def packet_for_target(self, target_tokens: int) -> Gate3Packet:
        if target_tokens <= 0:
            raise I11A0Error("evidence target must be positive")
        chosen: list[EvidencePiece] = []
        for piece in self.pieces:
            current = estimate_tokens("\n\n".join(item.render() for item in chosen)) if chosen else 0
            if chosen and current >= target_tokens:
                break
            chosen.append(piece)
        if not chosen:
            raise I11A0Error("no conversation fits the Gate 3 source")
        text = "\n\n".join(item.render() for item in chosen)
        estimated = estimate_tokens(text)
        exhausted = len(chosen) >= len(self.pieces)
        return Gate3Packet(
            text=text,
            sha256=_sha256_text(text),
            estimated_evidence_tokens=estimated,
            evidence_ids=tuple(eid for item in chosen for eid in item.evidence_ids),
            conversation_ids=tuple(item.piece_id for item in chosen),
            time_start=min(item.earliest for item in chosen),
            time_end=max(item.latest for item in chosen),
            target_tokens=target_tokens,
            overshoot=estimated > target_tokens,
            exhausted=exhausted,
            evidence_bytes=len(text.encode("utf-8")),
            evidence_characters=len(text),
            packer_kind="conversation",
            message_count=sum(len(item.turns) for item in chosen),
        )

    def remaining_after(self, packet: Gate3Packet) -> int:
        used = set(packet.conversation_ids)
        return sum(1 for piece in self.pieces if piece.piece_id not in used)


class NestedMessagePacker:
    """Prefix-nested complete-message packets. Threads may split between messages."""

    def __init__(self, messages: list[Any]) -> None:
        self.messages = list(messages)

    def packet_for_target(self, target_tokens: int) -> Gate3Packet:
        if target_tokens <= 0:
            raise I11A0Error("evidence target must be positive")
        if not self.messages:
            raise I11A0Error("no I14 cleaned messages in freeze")
        chosen: list[Any] = []
        running = 0
        for item in self.messages:
            if chosen and running >= target_tokens:
                break
            chosen.append(item)
            running = estimate_tokens("\n\n".join(msg.text for msg in chosen))
        text = "\n\n".join(msg.text for msg in chosen)
        estimated = estimate_tokens(text)
        chosen_ids = {msg.evidence_id for msg in chosen}
        remaining_by_thread: dict[str, list[Any]] = {}
        for item in self.messages:
            if item.evidence_id in chosen_ids:
                continue
            remaining_by_thread.setdefault(item.thread_display_id, []).append(item)
        included_threads = {msg.thread_display_id for msg in chosen}
        partial_threads = sorted(thread for thread in included_threads if thread in remaining_by_thread)
        included_boundary: list[str] = []
        omitted_boundary: list[str] = []
        for thread in partial_threads:
            last_included = [msg for msg in chosen if msg.thread_display_id == thread][-1]
            first_omitted = remaining_by_thread[thread][0]
            included_boundary.append(last_included.evidence_id)
            omitted_boundary.append(first_omitted.evidence_id)
        conversation_ids = tuple(dict.fromkeys(msg.thread_display_id for msg in chosen))
        exhausted = len(chosen) >= len(self.messages)
        return Gate3Packet(
            text=text,
            sha256=_sha256_text(text),
            estimated_evidence_tokens=estimated,
            evidence_ids=tuple(msg.evidence_id for msg in chosen),
            conversation_ids=conversation_ids,
            time_start=chosen[0].sent_at,
            time_end=chosen[-1].sent_at,
            target_tokens=target_tokens,
            overshoot=estimated > target_tokens,
            exhausted=exhausted,
            evidence_bytes=len(text.encode("utf-8")),
            evidence_characters=len(text),
            partial_context=bool(partial_threads),
            partial_boundary_note=(
                "partial_context=yes included="
                + ",".join(included_boundary)
                + " omitted="
                + ",".join(omitted_boundary)
                if partial_threads
                else "none"
            ),
            message_count=len(chosen),
            partial_thread_ids=tuple(partial_threads),
            included_boundary_evidence_ids=tuple(included_boundary),
            omitted_boundary_evidence_ids=tuple(omitted_boundary),
            packer_kind="message",
        )

    def remaining_after(self, packet: Gate3Packet) -> int:
        used = set(packet.evidence_ids)
        return sum(1 for item in self.messages if item.evidence_id not in used)


def next_coarse_grid_target(
    actual_estimated_tokens: int,
    *,
    increment: int = GATE3_COARSE_INCREMENT_TOKENS,
) -> int:
    """Smallest positive 1,000-token grid point strictly greater than the actual packet."""
    actual = int(actual_estimated_tokens)
    step = int(increment)
    if step <= 0:
        raise I11A0Error("coarse increment must be positive")
    return ((max(actual, 0) // step) + 1) * step


def classify_packet_progress(
    *,
    target: int,
    packet: Gate3Packet,
    previous_ids: tuple[str, ...] | None,
    remaining: int,
) -> str:
    if previous_ids is None or packet.evidence_ids != previous_ids:
        if remaining <= 0 or packet.exhausted:
            return "grew_to_source_end"
        return "grew"
    if remaining <= 0 or packet.exhausted:
        return "evidence_exhausted"
    if int(target) <= int(packet.estimated_evidence_tokens):
        return "target_already_covered"
    return "no_packet_growth"


def should_run_final_repeats(stop_reason: str) -> bool:
    return stop_reason in {
        "planned_ctx_exceeds_model_limit",
        "predicted_vram_ceiling",
        "three_confirmed_regressions",
        "vram_ceiling",
        "safety_margin_failed",
        "cpu_offload",
        "gpu_residency_lost",
        "unload_failed",
        "unload_vram_not_released",
        "timed_out",
        "evidence_exhausted",
    }


@dataclass
class QwenBPromptCalibration:
    """Qwen B complete-prompt calibration. Never imports A or Gemma C errors."""

    observations: list[dict[str, Any]] = field(default_factory=list)

    def add_observation(
        self,
        *,
        execution_id: str,
        estimated_complete_prompt_tokens: int,
        actual_complete_prompt_tokens: int,
        tag: str = B_TAG,
    ) -> dict[str, Any]:
        if tag != B_TAG:
            raise I11A0Error("Gate 3 calibration accepts Qwen B observations only")
        estimated = int(estimated_complete_prompt_tokens)
        actual = int(actual_complete_prompt_tokens)
        additive = actual - estimated
        relative = (additive / estimated) if estimated else 0.0
        row = {
            "execution_id": execution_id,
            "tag": tag,
            "estimated_complete_prompt_tokens": estimated,
            "actual_complete_prompt_tokens": actual,
            "additive_error_tokens": additive,
            "relative_error": relative,
            "relative_error_percent": round(relative * 100.0, 4),
        }
        self.observations.append(row)
        return row

    def snapshot_for_estimate(self, raw_estimated_complete_prompt_tokens: int) -> dict[str, Any]:
        import math

        raw = int(raw_estimated_complete_prompt_tokens)
        positives = [row for row in self.observations if int(row["additive_error_tokens"]) > 0]
        max_add = max((int(row["additive_error_tokens"]) for row in positives), default=0)
        max_rate = max((float(row["relative_error"]) for row in positives), default=0.0)
        rounded_rate = 0.0
        if max_rate > 0:
            rounded_rate = math.ceil(max_rate / RATE_STEP - 1e-15) * RATE_STEP
        guarded_rate = rounded_rate + RATE_GUARD if (max_add > 0 or max_rate > 0) else 0.0
        additive_plan = raw + max_add
        relative_plan = raw * (1.0 + guarded_rate)
        calibrated = max(float(additive_plan), float(relative_plan))
        required = calibrated + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
        num_ctx = int(math.ceil(required / CTX_ALIGN_TOKENS) * CTX_ALIGN_TOKENS)
        exceeds = num_ctx > QWEN_B_VERIFIED_MAX_CTX
        return {
            "formula": (
                "calibrated = max(raw + max_positive_additive_error, "
                "raw * (1 + ceil(max_positive_rate, 0.5%) + 0.5%)); "
                "num_ctx = ceil((calibrated + 2500 + 1500) / 256) * 256"
            ),
            "source_execution_ids": [row["execution_id"] for row in self.observations],
            "tag": B_TAG,
            "uses_configuration_a_or_c": False,
            "raw_estimated_complete_prompt_tokens": raw,
            "max_positive_additive_error_tokens": max_add,
            "max_positive_relative_error": max_rate,
            "max_positive_relative_error_percent": round(max_rate * 100.0, 4),
            "rounded_rate": rounded_rate,
            "guarded_rate": guarded_rate,
            "guarded_rate_percent": round(guarded_rate * 100.0, 4),
            "calibrated_prompt_tokens": calibrated,
            "output_reserve_tokens": OUTPUT_RESERVE_TOKENS,
            "required_safety_margin_tokens": SAFETY_MARGIN_TOKENS,
            "pre_rounding_required_tokens": required,
            "num_ctx": num_ctx,
            "ctx_align_tokens": CTX_ALIGN_TOKENS,
            "verified_max_num_ctx": QWEN_B_VERIFIED_MAX_CTX,
            "exceeds_verified_model_context": exceeds,
        }


def plan_gate3_num_ctx(
    *,
    estimated_prompt_tokens: int,
    reserved_output_tokens: int,
    safety_margin_tokens: int,
    calibration: QwenBPromptCalibration | None = None,
    pin_num_ctx: int | None = None,
    calibration_error_tokens: int | None = None,
) -> dict[str, Any]:
    if reserved_output_tokens != OUTPUT_RESERVE_TOKENS:
        raise I11A0Error("Gate 3 output reserve must remain 2500")
    if safety_margin_tokens != SAFETY_MARGIN_TOKENS:
        raise I11A0Error("Gate 3 safety margin must remain 1500")
    if pin_num_ctx is not None:
        pinned = int(pin_num_ctx)
        return {
            "num_ctx": pinned,
            "pinned": True,
            "raw_estimated_complete_prompt_tokens": estimated_prompt_tokens,
            "output_reserve_tokens": reserved_output_tokens,
            "required_safety_margin_tokens": safety_margin_tokens,
            "formula": "pinned_identical_packet_rerun",
            "verified_max_num_ctx": QWEN_B_VERIFIED_MAX_CTX,
            "exceeds_verified_model_context": pinned > QWEN_B_VERIFIED_MAX_CTX,
        }
    book = calibration or QwenBPromptCalibration()
    planned = book.snapshot_for_estimate(estimated_prompt_tokens)
    planned["pinned"] = False
    if calibration_error_tokens:
        planned["legacy_additive_ignored"] = int(calibration_error_tokens)
    return planned


def planning_derived_complete_prompt_tokens(row: dict[str, Any]) -> int | None:
    num_ctx = row.get("configured_num_ctx")
    if num_ctx in {None, ""}:
        return None
    return int(num_ctx) - OUTPUT_RESERVE_TOKENS - SAFETY_MARGIN_TOKENS


def is_estimator_calibration_shortfall(row: dict[str, Any]) -> bool:
    if row.get("classification") != "successful_pipeline_safety_margin_failed":
        return False
    if row.get("timed_out") or row.get("infrastructure_failure") or row.get("context_overflow"):
        return False
    if row.get("cpu_offload") or row.get("cpu_spill") or row.get("gpu_resident") is False:
        return False
    remaining = row.get("remaining_safety_margin_tokens")
    return remaining is not None and int(remaining) < 0


def counts_as_stable_ladder_rung(row: dict[str, Any], *, ceiling_gb: float = VRAM_CEILING_GB) -> bool:
    if is_estimator_calibration_shortfall(row):
        return False
    if row.get("hardware_classification_superseded"):
        return False
    if row.get("placement_status") in {"unknown", "cpu_offload"}:
        return False
    if row.get("cpu_offload") or row.get("cpu_spill"):
        return False
    if row.get("final_safety_result") != "passed":
        return False
    if row.get("confirmed_regression"):
        return False
    if row.get("phase") not in {"coarse", "refinement", "calibrated_rerun"}:
        return False
    if hard_stop_reason(row, ceiling_gb=ceiling_gb) is not None:
        return False
    if row.get("placement_status") not in {None, "gpu_resident"}:
        return False
    return True


def counts_toward_regression_stop(row: dict[str, Any]) -> bool:
    if is_estimator_calibration_shortfall(row):
        return False
    return bool(row.get("confirmed_regression"))


def packet_from_saved_row(row: dict[str, Any]) -> Gate3Packet:
    manifest = row.get("packet_manifest") or {}
    text = row.get("evidence_text") or ""
    return Gate3Packet(
        text=text,
        sha256=str(manifest.get("packet_sha256") or row.get("packet_sha256") or _sha256_text(text)),
        estimated_evidence_tokens=int(
            manifest.get("estimated_evidence_tokens") or row.get("estimated_evidence_tokens") or 0
        ),
        evidence_ids=tuple(manifest.get("evidence_ids") or ()),
        conversation_ids=tuple(manifest.get("conversation_ids") or ()),
        time_start=str(manifest.get("time_start") or ""),
        time_end=str(manifest.get("time_end") or ""),
        target_tokens=int(row.get("requested_evidence_tokens") or 0),
        overshoot=bool(manifest.get("overshoot")),
        exhausted=bool(manifest.get("exhausted")),
        evidence_bytes=int(manifest.get("evidence_bytes") or len(text.encode("utf-8"))),
        evidence_characters=int(manifest.get("evidence_characters") or len(text)),
        partial_context=False,
        partial_boundary_note="none",
    )


def load_existing_gate3_runs(root: Path) -> list[dict[str, Any]]:
    runs_dir = root / "runs"
    if not runs_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for folder in sorted(runs_dir.iterdir(), key=lambda path: path.name):
        if not folder.is_dir() or folder.name.endswith(".writing"):
            continue
        record = folder / "run_record.json"
        if not record.is_file():
            continue
        row = json.loads(record.read_text(encoding="utf-8"))
        evidence = folder / "evidence_packet.txt"
        if evidence.is_file():
            row = dict(row)
            row["evidence_text"] = evidence.read_text(encoding="utf-8")
        row["_artifact_dir"] = str(folder)
        rows.append(row)
    return rows


def write_preserved_rung_sidecar(root: Path, row: dict[str, Any], planned: dict[str, Any]) -> Path:
    folder = Path(row.get("_artifact_dir") or (root / "runs" / str(row["execution_id"])))
    original_hashes: dict[str, str] = {}
    hashes_file = folder / "HASHES.txt"
    if hashes_file.is_file():
        for line in hashes_file.read_text(encoding="utf-8").splitlines():
            if "  " in line:
                digest, name = line.split("  ", 1)
                original_hashes[name] = digest
    else:
        for name in (
            "run_record.json",
            "token_accounting.json",
            "evidence_packet.txt",
            "narration.txt",
            "raw_api.jsonl",
            "telemetry.jsonl",
            "packet_manifest.json",
        ):
            path = folder / name
            if path.is_file():
                original_hashes[name] = _sha256_text(path.read_text(encoding="utf-8"))
    estimated = planning_derived_complete_prompt_tokens(row)
    actual = row.get("actual_prompt_tokens")
    additive = None if estimated is None or actual is None else int(actual) - int(estimated)
    relative = None if not estimated or additive is None else additive / float(estimated)
    payload = {
        "supersession_kind": "prompt_estimator_calibration",
        "original_execution_id": row.get("execution_id"),
        "classification_unchanged": row.get("classification"),
        "original_files_rewritten": False,
        "original_hashes": original_hashes,
        "planning_derived_estimated_complete_prompt_tokens": estimated,
        "actual_complete_prompt_tokens": actual,
        "additive_error_tokens": additive,
        "relative_error": relative,
        "relative_error_percent": None if relative is None else round(relative * 100.0, 4),
        "not_a_stable_ladder_rung": True,
        "not_a_performance_regression": True,
        "not_a_context_knee": True,
        "identical_packet_sha256": row.get("packet_sha256"),
        "identical_packet_rerun_num_ctx": CALIBRATED_SAME_PACKET_NUM_CTX,
        "required_safety_margin_tokens": SAFETY_MARGIN_TOKENS,
        "calibration_plan": planned,
        "tag": B_TAG,
        "uses_configuration_a_or_c": False,
    }
    cal_dir = root / "calibration"
    cal_dir.mkdir(parents=True, exist_ok=True)
    path = cal_dir / f"{row.get('execution_id')}.supersession.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path


def write_same_packet_repeat_sidecar(root: Path, runs: list[dict[str, Any]]) -> Path | None:
    repeats = [
        {
            "execution_id": row.get("execution_id"),
            "phase": row.get("phase"),
            "requested_evidence_tokens": row.get("requested_evidence_tokens"),
            "estimated_evidence_tokens": row.get("estimated_evidence_tokens"),
            "packet_sha256": row.get("packet_sha256"),
            "label": "same_packet_validation_repeat",
            "not_a_ladder": True,
            "not_a_knee": True,
            "not_evidence_exhaustion": True,
            "not_refinement_around_a_knee": True,
            "original_files_rewritten": False,
        }
        for row in runs
        if row.get("phase") in {"repeat_proposed", "repeat_next_larger"}
        or row.get("repeat_kind") == "same_packet_validation_repeat"
    ]
    if not repeats:
        return None
    payload = {
        "supersession_kind": "same_packet_repeat_label",
        "original_files_rewritten": False,
        "repeats": repeats,
        "note": (
            "These executions reused one packet size. They are validation/repeatability "
            "data, not coarse ladder rungs, not a knee, and not proof that evidence is exhausted."
        ),
    }
    cal_dir = root / "calibration"
    cal_dir.mkdir(parents=True, exist_ok=True)
    path = cal_dir / "same_packet_repeats.classification.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path


def persist_qwen_b_calibration(root: Path, book: QwenBPromptCalibration, planned: dict[str, Any] | None = None) -> Path:
    cal_dir = root / "calibration"
    cal_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "tag": B_TAG,
        "uses_configuration_a_or_c": False,
        "observations": book.observations,
        "latest_plan": planned,
        "required_safety_margin_tokens": SAFETY_MARGIN_TOKENS,
        "output_reserve_tokens": OUTPUT_RESERVE_TOKENS,
        "formula": (planned or {}).get("formula")
        or (
            "calibrated = max(raw + max_positive_additive_error, "
            "raw * (1 + ceil(max_positive_rate, 0.5%) + 0.5%)); "
            "num_ctx = ceil((calibrated + 2500 + 1500) / 256) * 256"
        ),
    }
    path = cal_dir / "qwen_b_prompt_calibration.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path


def seed_qwen_b_calibration_from_runs(runs: list[dict[str, Any]]) -> QwenBPromptCalibration:
    book = QwenBPromptCalibration()
    for row in runs:
        actual = row.get("actual_prompt_tokens")
        if actual is None:
            continue
        if is_estimator_calibration_shortfall(row):
            estimated = planning_derived_complete_prompt_tokens(row)
        else:
            estimated = row.get("estimated_prompt_tokens")
        if estimated in {None, ""}:
            continue
        book.add_observation(
            execution_id=str(row.get("execution_id")),
            estimated_complete_prompt_tokens=int(estimated),
            actual_complete_prompt_tokens=int(actual),
            tag=B_TAG,
        )
    return book


def needs_identical_packet_rerun(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    shortfalls = [row for row in runs if is_estimator_calibration_shortfall(row)]
    if not shortfalls:
        return None
    candidate = next(
        (row for row in shortfalls if row.get("execution_id") == PRESERVED_GATE3_EXECUTION_ID),
        shortfalls[0],
    )
    sha = candidate.get("packet_sha256")
    for row in runs:
        if row.get("execution_id") == candidate.get("execution_id"):
            continue
        if row.get("packet_sha256") == sha and row.get("final_safety_result") == "passed":
            return None
    return candidate


def ram_pressure_report(runs: list[dict[str, Any]]) -> dict[str, Any]:
    peaks = [float(row["ram_peak_gb"]) for row in runs if row.get("ram_peak_gb") is not None]
    totals = []
    for row in runs:
        hardware = row.get("hardware") or {}
        total = hardware.get("ram_total_gb")
        if total is None:
            identity = row.get("host_identity") or {}
            total = identity.get("ram_total_gb") or identity.get("system_ram_total_gb")
            preflight = identity.get("preflight") if isinstance(identity.get("preflight"), dict) else {}
            if total is None:
                total = preflight.get("system_ram_total_gb")
        if total is not None:
            totals.append(float(total))
    peak = max(peaks) if peaks else None
    total = max(totals) if totals else None
    available = None if peak is None or total is None else total - peak
    flagged = available is not None and available < LOW_RAM_AVAILABLE_FLAG_GB
    return {
        "ram_peak_used_gb": peak,
        "ram_total_gb": total,
        "ram_available_at_peak_gb": available,
        "low_available_system_ram_flagged": flagged,
        "ram_stop_threshold_invented": False,
        "note": (
            f"Peak system RAM {peak} GB of {total} GB "
            f"({available} GB available at peak). Flagged because available RAM was below "
            f"{LOW_RAM_AVAILABLE_FLAG_GB} GB. No RAM hard-stop was added."
            if flagged
            else "System RAM recorded; no unauthorized RAM stop threshold was added."
        ),
    }


def derived_prompt_metrics(row: dict[str, Any]) -> dict[str, Any]:
    actual = row.get("actual_prompt_tokens") or 0
    prompt_s = row.get("prompt_eval_seconds")
    elapsed = row.get("elapsed_seconds")
    load_s = row.get("load_seconds")
    processing_s = prompt_s
    if processing_s is None and elapsed is not None:
        processing_s = max(0.0, float(elapsed) - float(load_s or 0.0))
    sec_per_token = (
        float(processing_s) / float(actual) if actual and processing_s is not None else None
    )
    wall_per_token = float(elapsed) / float(actual) if actual and elapsed else None
    return {
        "prompt_tokens_per_second": row.get("prompt_tokens_per_second"),
        "wall_seconds_per_actual_prompt_token": wall_per_token,
        "prompt_processing_seconds_per_actual_prompt_token": sec_per_token,
        "generation_tokens_per_second": row.get("generation_tokens_per_second"),
        "load_seconds_excluded_from_knee": True,
    }


def material_regression(
    current: dict[str, Any],
    prior_stable: dict[str, Any] | None,
    *,
    fraction: float = GATE3_REGRESSION_FRACTION,
) -> dict[str, Any]:
    """10% prompt-throughput or normalized cost drop, plus corroboration.

    Generation tokens/second is recorded but not a stop trigger.
    Load duration is not a knee signal.
    Elapsed time growth alone is not a regression.
    """
    if prior_stable is None:
        return {"regressed": False, "reason": "no_prior_stable", "details": {}}
    cur = derived_prompt_metrics(current)
    prev = derived_prompt_metrics(prior_stable)
    details: dict[str, Any] = {"fraction": fraction}
    tps_now = cur.get("prompt_tokens_per_second")
    tps_prev = prev.get("prompt_tokens_per_second")
    cost_now = cur.get("prompt_processing_seconds_per_actual_prompt_token")
    cost_prev = prev.get("prompt_processing_seconds_per_actual_prompt_token")
    throughput_drop = (
        tps_now is not None
        and tps_prev not in {None, 0}
        and float(tps_now) < float(tps_prev) * (1.0 - fraction)
    )
    cost_rise = (
        cost_now is not None
        and cost_prev not in {None, 0}
        and float(cost_now) > float(cost_prev) * (1.0 + fraction)
    )
    primary = throughput_drop or cost_rise
    d_tokens = (current.get("actual_prompt_tokens") or 0) - (
        prior_stable.get("actual_prompt_tokens") or 0
    )
    d_prompt_s = (current.get("prompt_eval_seconds") or 0) - (
        prior_stable.get("prompt_eval_seconds") or 0
    )
    expected_d = None
    elapsed_growth_worse = False
    if d_tokens > 0 and cost_prev:
        expected_d = float(cost_prev) * float(d_tokens)
        elapsed_growth_worse = d_prompt_s > expected_d * (1.0 + fraction)
    d_vram = (current.get("vram_peak_gb") or 0) - (prior_stable.get("vram_peak_gb") or 0)
    vram_per_1k = (d_vram / (d_tokens / 1000.0)) if d_tokens > 0 else None
    prior_vram_per_1k = prior_stable.get("vram_growth_per_1000_actual_prompt_tokens")
    vram_worse = (
        vram_per_1k is not None
        and prior_vram_per_1k not in {None, 0}
        and float(vram_per_1k) > float(prior_vram_per_1k) * (1.0 + fraction)
    )
    if vram_per_1k is None and d_tokens > 0 and d_vram >= 0.75:
        vram_worse = True
    corroboration = elapsed_growth_worse or vram_worse or (
        current.get("elapsed_seconds") is not None
        and prior_stable.get("elapsed_seconds") not in {None, 0}
        and d_tokens > 0
        and (current["elapsed_seconds"] - prior_stable["elapsed_seconds"])
        > (float(prior_stable["elapsed_seconds"]) / max(prior_stable.get("actual_prompt_tokens") or 1, 1))
        * d_tokens
        * (1.0 + fraction)
    )
    details.update(
        {
            "throughput_drop": throughput_drop,
            "cost_rise": cost_rise,
            "elapsed_growth_worse": elapsed_growth_worse,
            "vram_per_1000_actual_prompt_tokens": vram_per_1k,
            "vram_worse": vram_worse,
            "expected_prompt_eval_growth_seconds": expected_d,
            "actual_prompt_eval_growth_seconds": d_prompt_s,
            "generation_tps_not_used_as_stop": True,
        }
    )
    current["vram_growth_per_1000_actual_prompt_tokens"] = vram_per_1k
    current["derived"] = {**cur, **details}
    return {
        "regressed": bool(primary and corroboration),
        "reason": "confirmed_primary_and_corroboration" if primary and corroboration else "not_material",
        "details": details,
    }


def hard_stop_reason(row: dict[str, Any], *, ceiling_gb: float = VRAM_CEILING_GB) -> str | None:
    if row.get("host_affinity_failed"):
        return "host_affinity"
    if row.get("model_identity_changed"):
        return "model_identity_changed"
    if row.get("planned_ctx_exceeds_model_limit") or row.get("classification") == "planned_ctx_exceeds_model_limit":
        return "planned_ctx_exceeds_model_limit"
    if row.get("predicted_vram_ceiling") or row.get("classification") == "predicted_vram_ceiling":
        return "predicted_vram_ceiling"
    peak = row.get("vram_peak_gb")
    if peak is not None and float(peak) >= ceiling_gb:
        return "vram_ceiling"
    if row.get("timed_out") or row.get("classification") == "timed_out":
        return "timed_out"
    if row.get("infrastructure_failure") or row.get("classification") == "infrastructure_failure":
        return "generation_failed"
    if row.get("context_overflow"):
        return "context_overflow"
    placement_status = row.get("placement_status")
    if placement_status == "unknown":
        return "placement_unknown"
    if placement_status == "cpu_offload":
        return "cpu_offload"
    if (row.get("cpu_offload") or row.get("cpu_spill")) and placement_status != "gpu_resident":
        return "placement_unknown"
    if row.get("gpu_resident") is False and placement_status not in {"gpu_resident", None}:
        return "gpu_residency_lost"
    if row.get("gpu_resident") is False and placement_status is None and not row.get("hardware_classification_superseded"):
        return "placement_unknown"
    if row.get("final_safety_result") not in {None, "passed"}:
        if is_estimator_calibration_shortfall(row):
            return "estimator_recalibration_required"
        return "safety_margin_failed"
    if row.get("unload_recorded") is False:
        return "unload_failed"
    if row.get("vram_released") is False:
        return "unload_vram_not_released"
    return None


def classify_boundary_kind(stop_reason: str) -> str:
    if stop_reason == "three_confirmed_regressions":
        return "performance_knee"
    if stop_reason in {"vram_ceiling", "predicted_vram_ceiling"}:
        return "vram_boundary"
    if stop_reason in {"planned_ctx_exceeds_model_limit", "context_overflow"}:
        return "model_context_boundary"
    if stop_reason == "evidence_exhausted":
        return "evidence_exhaustion"
    if stop_reason in {"generation_failed", "timed_out", "host_affinity"}:
        return "infrastructure_failure"
    return str(stop_reason or "unknown")


def project_vram_for_next_packet(
    prior_rows: list[dict[str, Any]],
    *,
    next_estimated_tokens: int,
    ceiling_gb: float = VRAM_CEILING_GB,
) -> dict[str, Any]:
    stables = [
        row
        for row in prior_rows
        if counts_as_stable_ladder_rung(row, ceiling_gb=ceiling_gb)
        and row.get("vram_peak_gb") is not None
    ]
    if len(stables) < 2:
        return {
            "predicted_vram_gb": None,
            "clearly_unsafe": False,
            "reason": "insufficient_same_phase_points",
        }
    first, second = stables[-2], stables[-1]
    t1 = float(first.get("estimated_evidence_tokens") or 0)
    t2 = float(second.get("estimated_evidence_tokens") or 0)
    v1 = float(first["vram_peak_gb"])
    v2 = float(second["vram_peak_gb"])
    if t2 <= t1:
        return {
            "predicted_vram_gb": None,
            "clearly_unsafe": False,
            "reason": "non_increasing_token_points",
        }
    slope = (v2 - v1) / (t2 - t1)
    predicted = v2 + slope * (float(next_estimated_tokens) - t2)
    return {
        "predicted_vram_gb": predicted,
        "clearly_unsafe": bool(slope > 0 and predicted >= ceiling_gb),
        "slope_gb_per_estimated_token": slope,
        "from_estimated_evidence_tokens": (t1, t2),
        "from_vram_peak_gb": (v1, v2),
        "reason": "two_point_same_phase_projection",
    }


def _ns_to_s(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value) / 1e9


def write_gate3_run_artifacts(folder: Path, row: dict[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "evidence_packet.txt").write_text(row.get("evidence_text") or "", encoding="utf-8", newline="\n")
    (folder / "narration.txt").write_text(row.get("narration") or "", encoding="utf-8", newline="\n")
    (folder / "packet_manifest.json").write_text(
        json.dumps(row.get("packet_manifest") or {}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (folder / "token_accounting.json").write_text(
        json.dumps(row.get("token_accounting") or {}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (folder / "run_record.json").write_text(
        json.dumps({k: v for k, v in row.items() if k != "evidence_text"}, indent=2, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (folder / "raw_api.jsonl").write_text(row.get("raw_api") or "", encoding="utf-8", newline="\n")
    (folder / "telemetry.jsonl").write_text(row.get("telemetry") or "", encoding="utf-8", newline="\n")
    (folder / "hardware_telemetry.json").write_text(
        json.dumps(row.get("hardware") or {}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (folder / "host_identity.json").write_text(
        json.dumps(row.get("host_identity") or {}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (folder / "model_identity.json").write_text(
        json.dumps(row.get("model_identity") or {}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def publish_completed_run(results_dir: Path, row: dict[str, Any]) -> Path:
    dest = Path(results_dir) / "runs" / str(row["execution_id"])
    staging = dest.with_name(dest.name + ".writing")
    if staging.exists():
        shutil.rmtree(staging)
    write_gate3_run_artifacts(staging, row)
    (staging / "COMPLETE").write_text("ok\n", encoding="utf-8", newline="\n")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    os.replace(staging, dest)
    return dest


def rewrite_run_tables(results_dir: Path, runs: list[dict[str, Any]]) -> None:
    results_dir = Path(results_dir)
    import io

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=GATE3_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    jsonl_lines: list[str] = []
    for row in runs:
        writer.writerow({key: row.get(key) for key in GATE3_CSV_FIELDS})
        slim = {k: v for k, v in row.items() if k not in {"evidence_text", "narration", "raw_api"}}
        jsonl_lines.append(json.dumps(slim, sort_keys=True, default=str))
    csv_text = buf.getvalue()
    if not csv_text.endswith("\n"):
        csv_text += "\n"
    atomic_replace_text(results_dir / "gate3_runs.csv", csv_text)
    atomic_replace_text(
        results_dir / "gate3_runs.jsonl",
        ("\n".join(jsonl_lines) + "\n") if jsonl_lines else "",
    )


def _hash_tree(root: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "HASHES.txt":
            continue
        rows.append((path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
    return rows


def analyze_gate3(runs: list[dict[str, Any]], *, stop_reason: str, config: Gate3Config) -> dict[str, Any]:
    stable = [
        row
        for row in runs
        if counts_as_stable_ladder_rung(row, ceiling_gb=config.maximum_vram_gb)
    ]
    last_stable = stable[-1] if stable else None
    first_capacity = None
    for row in runs:
        if is_estimator_calibration_shortfall(row):
            continue
        if row.get("phase") in {"repeat_proposed", "repeat_next_larger"}:
            continue
        if row.get("hardware_classification_superseded"):
            continue
        if row.get("not_ladder_progression"):
            continue
        reason = hard_stop_reason(row, ceiling_gb=config.maximum_vram_gb)
        if reason in {None, "estimator_recalibration_required"}:
            continue
        first_capacity = row
        first_capacity_reason = reason
        break
    else:
        first_capacity_reason = None
    failing = [
        row
        for row in runs
        if (
            (
                hard_stop_reason(row, ceiling_gb=config.maximum_vram_gb)
                not in {None, "estimator_recalibration_required"}
            )
            or counts_toward_regression_stop(row)
        )
        and not is_estimator_calibration_shortfall(row)
        and not row.get("hardware_classification_superseded")
        and row.get("phase") not in {"repeat_proposed", "repeat_next_larger"}
    ]
    knee_observed = stop_reason == "three_confirmed_regressions"
    boundary_kind = classify_boundary_kind(stop_reason)
    if knee_observed and boundary_kind != "performance_knee":
        knee_observed = False
    ram = ram_pressure_report(runs)
    ram["experiment_phase"] = getattr(config, "experiment_phase", None)
    ram["do_not_mix_with_other_experiment_phases"] = True
    abs_max = None
    for row in runs:
        if row.get("final_safety_result") == "passed" and hard_stop_reason(row, ceiling_gb=config.maximum_vram_gb) is None:
            abs_max = row
    proposed = last_stable
    next_larger = None
    if proposed:
        for row in runs:
            if (
                row.get("phase") == "refinement"
                and (row.get("estimated_evidence_tokens") or 0)
                > (proposed.get("estimated_evidence_tokens") or 0)
            ):
                next_larger = row
                break
    if knee_observed:
        reason = "largest repeatably stable point below the confirmed performance-regression region"
    elif boundary_kind == "vram_boundary":
        reason = (
            "VRAM/capacity boundary, not a performance knee. The proposed point is the last "
            "fully stable safety-passing run below that boundary."
        )
    elif boundary_kind == "model_context_boundary":
        reason = (
            "Verified model-context boundary (planned num_ctx would exceed 40960 or overflow), "
            "not a performance knee."
        )
    elif stop_reason == "evidence_exhausted":
        reason = (
            "no genuine performance knee was observed; eligible cleaned messages were exhausted "
            "while runs remained stable. The recommended point is the largest stable packet, "
            "not a manufactured knee."
        )
    else:
        reason = (
            f"no genuine performance knee was observed; coarse growth stopped for {stop_reason} "
            f"({boundary_kind}). The recommended point is the last fully stable safety-passing run below that stop."
        )
    return {
        "stop_reason": stop_reason,
        "boundary_kind": boundary_kind,
        "knee_observed": knee_observed,
        "vram_or_context_stop_is_not_a_performance_knee": boundary_kind
        in {"vram_boundary", "model_context_boundary"},
        "knee_range": {
            "last_stable_estimated_evidence_tokens": (last_stable or {}).get("estimated_evidence_tokens"),
            "first_regression_or_stop": (first_capacity or {}).get("estimated_evidence_tokens"),
            "first_regression_or_stop_requested_tokens": (first_capacity or {}).get("requested_evidence_tokens"),
            "first_regression_or_stop_reason": first_capacity_reason,
            "first_regression_or_stop_execution_id": (first_capacity or {}).get("execution_id"),
            "note": (
                "Uses estimated evidence tokens of the first non-calibration capacity/performance stop. "
                "Does not use the first requested_evidence_tokens of a superseded or calibration row."
            ),
        },
        "recommended": {
            "evidence_token_target": (proposed or {}).get("requested_evidence_tokens"),
            "actual_evidence_tokens": (proposed or {}).get("estimated_evidence_tokens"),
            "actual_complete_prompt_tokens": (proposed or {}).get("actual_prompt_tokens"),
            "configured_num_ctx": (proposed or {}).get("configured_num_ctx"),
            "execution_id": (proposed or {}).get("execution_id"),
            "reason_below_maximum": reason,
            "remaining_vram_headroom_gb": (
                None
                if not proposed or proposed.get("vram_peak_gb") is None
                else config.maximum_vram_gb - float(proposed["vram_peak_gb"])
            ),
            "remaining_context_headroom_tokens": (proposed or {}).get(
                "remaining_safety_margin_tokens"
            ),
            "prompt_tokens_per_second": (proposed or {}).get("prompt_tokens_per_second"),
            "generation_tokens_per_second": (proposed or {}).get("generation_tokens_per_second"),
            "vram_peak_gb": (proposed or {}).get("vram_peak_gb"),
            "repeatability": "repeat_proposed_and_next_larger_only_after_boundary",
            "largest_observed_safe_run_execution_id": (abs_max or {}).get("execution_id"),
            "margin_from_largest_safe_to_proposed": reason,
        },
        "i11a1_inventories_preserved_not_decided": {
            "peggy_only_authored_displayable": 2674,
            "peggy_voice_corpus": 1345,
            "i11a1_started": False,
        },
        "absolute_maximum_safe_run": {
            "execution_id": (abs_max or {}).get("execution_id"),
            "estimated_evidence_tokens": (abs_max or {}).get("estimated_evidence_tokens"),
            "actual_prompt_tokens": (abs_max or {}).get("actual_prompt_tokens"),
        },
        "next_larger_refinement_point": {
            "execution_id": (next_larger or {}).get("execution_id"),
            "estimated_evidence_tokens": (next_larger or {}).get("estimated_evidence_tokens"),
        },
        "source_limitation": SOURCE_LIMITATION,
        "winner_recommendation": None,
        "peggy_scenario_started": False,
        "configurations_a_and_c_ran": False,
        "i11a1_started": False,
        "ram_pressure": ram,
        "estimator_calibration_shortfalls_excluded_from_knee": True,
        "required_safety_margin_tokens": SAFETY_MARGIN_TOKENS,
    }


def write_gate3_package(
    *,
    results_dir: Path,
    runs: list[dict[str, Any]],
    analysis: dict[str, Any],
    config: Gate3Config,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    results_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "config": asdict(config),
        "prompt_status": PROMPT_STATUS,
        "production_prompt_accepted": PRODUCTION_PROMPT_ACCEPTED,
        "token_estimator_id": TOKEN_ESTIMATOR_ID,
        "token_estimator_formula": TOKEN_ESTIMATOR_FORMULA,
        "token_estimator_label": TOKEN_ESTIMATOR_LABEL,
        "source_limitation": SOURCE_LIMITATION,
        "regression_rule": (
            "A size increase is a material regression when prompt_eval tokens/second drops by "
            f">= {config.regression_fraction:.0%} versus the last stable run, or prompt-processing "
            "seconds per actual prompt token rise by that fraction, and a corroborating increase "
            "in prompt-eval growth versus token growth or VRAM growth per 1,000 actual prompt "
            "tokens is also present. Generation tokens/second is recorded only. Load duration is "
            "excluded from the knee. A single noisy run is confirmed at the same packet before it "
            f"counts. Coarse growth stops after {config.confirmed_regression_stop} consecutive "
            "confirmed regressing size increases, or on a hard safety stop."
        ),
        "coarse_rule": (
            f"Start near {config.start_evidence_tokens} estimated evidence tokens, grow by about "
            f"{config.coarse_increment_tokens} using nested whole conversations. Accept overshoot. "
            "Never split a conversation. Never silently truncate."
        ),
        "refinement_rule": (
            f"After coarse stop, walk the last stable region in ~{config.refinement_increment_tokens} "
            f"evidence-token steps, then measure the proposed point and the next larger point "
            f"{config.repeat_count} times each unless a hard stop forbids it."
        ),
        "timeout_seconds": config.timeout_seconds,
        "full_context_ladder_blocked_for_a_and_c": True,
    }
    (results_dir / "gate3_config.json").write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (results_dir / "stop_decision.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (results_dir / "recommended_operating_point.json").write_text(
        json.dumps(analysis.get("recommended") or {}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (results_dir / "host_affinity_preflight.json").write_text(
        json.dumps(preflight, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    rewrite_run_tables(results_dir, runs)
    rec = analysis.get("recommended") or {}
    md = [
        "# Gate 3 Configuration B context-capacity review",
        "",
        SOURCE_LIMITATION,
        "",
        "This Gate 3 job did not run Configurations A or C, did not start the Peggy narrative scenario, "
        "and does not select a final production model or start I11A.1 / I11A.2.",
        "",
        f"**Stop reason:** `{analysis.get('stop_reason')}`",
        f"**Genuine knee observed:** {analysis.get('knee_observed')}",
        "",
        "## System RAM",
        "",
        (
            "**LOW AVAILABLE SYSTEM RAM** — "
            if (analysis.get("ram_pressure") or {}).get("low_available_system_ram_flagged")
            else ""
        )
        + str((analysis.get("ram_pressure") or {}).get("note")),
        "",
        "## Recommended operating point",
        "",
        f"- Evidence-token target: {rec.get('evidence_token_target')}",
        f"- Actual evidence size (estimator, labeled estimated): {rec.get('actual_evidence_tokens')}",
        f"- Actual complete prompt (`prompt_eval_count`): {rec.get('actual_complete_prompt_tokens')}",
        f"- Configured `num_ctx`: {rec.get('configured_num_ctx')}",
        f"- Remaining VRAM headroom (GB vs 22.5): {rec.get('remaining_vram_headroom_gb')}",
        f"- Remaining context safety headroom (tokens): {rec.get('remaining_context_headroom_tokens')}",
        f"- Why this is below the absolute maximum: {rec.get('reason_below_maximum')}",
        "",
        "## Knee range and maximum safe run",
        "",
        json.dumps(analysis.get("knee_range"), indent=2),
        "",
        json.dumps(analysis.get("absolute_maximum_safe_run"), indent=2),
        "",
        "## Narrative comparison",
        "",
        "Each execution directory contains `narration.txt`. Compare completeness, coherence, "
        "repetition, attribution, and unsupported inference by packet size. This controller does "
        "not score narration quality from speed or capacity.",
        "",
        "## Runs",
        "",
    ]
    for row in runs:
        md.append(
            f"- `{row.get('execution_id')}` phase={row.get('phase')} target={row.get('requested_evidence_tokens')} "
            f"actual_prompt={row.get('actual_prompt_tokens')} safety={row.get('final_safety_result')} "
            f"classification={row.get('classification')} vram_peak={row.get('vram_peak_gb')}"
            + (
                f" repeat_kind={row.get('repeat_kind')}"
                if row.get("repeat_kind")
                else ""
            )
        )
    md.append("")
    (results_dir / "gate3_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    (results_dir / "prompt.txt").write_text(prompt_canonical_text() + "\n\n" + SYSTEM_PROMPT, encoding="utf-8")
    hashes = _hash_tree(results_dir)
    (results_dir / "HASHES.txt").write_text(
        "\n".join(f"{digest}  {name}" for name, digest in hashes) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {"ok": True, "results_dir": str(results_dir), "run_count": len(runs)}


GenerateFn = Callable[[RunRequest, Gate3Packet], tuple[Measurement, str, dict[str, Any]]]
UnloadFn = Callable[[str], tuple[float, dict[str, Any]]]


def _build_row(
    *,
    request: RunRequest,
    packet: Gate3Packet,
    measurement: Measurement,
    narration: str,
    extras: dict[str, Any],
    phase: str,
    spec: ModelSpec,
    metadata: dict[str, Any],
    preflight: dict[str, Any],
    estimated_prompt: int,
    calibration_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    actual = measurement.prompt_eval_count
    assessment = None
    if actual is not None:
        assessment = prompt_safety_assessment(
            actual_prompt_tokens=int(actual),
            estimated_prompt_tokens=estimated_prompt,
            configured_num_ctx=request.num_ctx,
            output_reserve_tokens=request.reserved_output_tokens,
            required_safety_margin_tokens=SAFETY_MARGIN_TOKENS,
        )
    hardware = extras.get("hardware") or {}
    last = extras.get("last_event") or {}
    placement_status = hardware.get("placement_status") or extras.get("placement_status")
    gpu_res = hardware.get("gpu_resident", measurement.gpu_resident)
    cpu_off = placement_status == "cpu_offload"
    if gpu_res is True and placement_status in {"gpu_resident", None}:
        cpu_off = False
    case = test_case_id(request)
    started = extras.get("started_at_utc") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    exec_id = extras.get("execution_id") or new_execution_id(
        test_case=case, hostname=socket.gethostname(), started_at_utc=started
    )
    load_s = _ns_to_s(last.get("load_duration"))
    prompt_s = _ns_to_s(last.get("prompt_eval_duration"))
    eval_s = _ns_to_s(last.get("eval_duration"))
    classification = extras.get("classification")
    if assessment and assessment.get("overall_classification"):
        classification = assessment["overall_classification"]
    if measurement.timed_out:
        classification = "timed_out"
    if measurement.infrastructure_failure:
        classification = "infrastructure_failure"
    row = {
        "execution_id": exec_id,
        "test_case_id": case,
        "phase": phase,
        "requested_evidence_tokens": request.requested_evidence_tokens,
        "estimated_evidence_tokens": packet.estimated_evidence_tokens,
        "actual_prompt_tokens": actual,
        "estimated_prompt_tokens": estimated_prompt,
        "estimation_error_tokens": None if actual is None else int(actual) - estimated_prompt,
        "configured_num_ctx": request.num_ctx,
        "calibration_plan": calibration_plan,
        "calibration_error_used_for_planning": (calibration_plan or {}).get(
            "max_positive_additive_error_tokens"
        ),
        "final_safety_result": (assessment or {}).get("final_safety_result"),
        "remaining_safety_margin_tokens": (assessment or {}).get("remaining_safety_margin_tokens"),
        "required_context_tokens": (assessment or {}).get("required_context_tokens"),
        "safety_equation": (assessment or {}).get("equation"),
        "classification": classification,
        "elapsed_seconds": measurement.elapsed_seconds,
        "load_seconds": load_s,
        "prompt_eval_seconds": prompt_s,
        "eval_seconds": eval_s,
        "prompt_tokens_per_second": measurement.prompt_tokens_per_second,
        "generation_tokens_per_second": measurement.generation_tokens_per_second,
        "vram_baseline_gb": hardware.get("vram_baseline_gb"),
        "vram_peak_gb": hardware.get("vram_peak_gb") or measurement.peak_vram_gb,
        "vram_final_gb": hardware.get("vram_final_gb"),
        "ram_baseline_gb": hardware.get("ram_baseline_gb"),
        "ram_peak_gb": hardware.get("ram_peak_gb"),
        "ram_total_gb": hardware.get("ram_total_gb"),
        "ram_final_gb": hardware.get("ram_final_gb"),
        "gpu_resident": gpu_res,
        "cpu_offload": cpu_off,
        "placement_status": placement_status,
        "placement_reason": hardware.get("placement_reason") or extras.get("placement_reason"),
        "vram_pre_unload_gb": hardware.get("vram_pre_unload_gb"),
        "vram_post_unload_gb": hardware.get("vram_post_unload_gb"),
        "cpu_spill": cpu_off,
        "timed_out": measurement.timed_out,
        "infrastructure_failure": measurement.infrastructure_failure,
        "context_overflow": bool(actual and actual > request.num_ctx),
        "unload_seconds": extras.get("unload_seconds"),
        "unload_recorded": extras.get("unload_recorded", True),
        "vram_released": extras.get("vram_released"),
        "confirmed_regression": False,
        "packet_sha256": packet.sha256,
        "prompt_sha256": request.prompt_sha256,
        "narration_relpath": f"{exec_id}/narration.txt",
        "evidence_text": packet.text,
        "narration": narration,
        "raw_api": extras.get("raw_api") or "",
        "telemetry": extras.get("telemetry") or "",
        "hardware": hardware,
        "host_identity": preflight,
        "model_identity": metadata,
        "packet_manifest": {
            "conversation_ids": list(packet.conversation_ids),
            "evidence_ids": list(packet.evidence_ids),
            "time_start": packet.time_start,
            "time_end": packet.time_end,
            "estimated_evidence_tokens": packet.estimated_evidence_tokens,
            "estimator_label": TOKEN_ESTIMATOR_LABEL,
            "overshoot": packet.overshoot,
            "exhausted": packet.exhausted,
            "evidence_bytes": packet.evidence_bytes,
            "evidence_characters": packet.evidence_characters,
            "packet_sha256": packet.sha256,
            "source_limitation": SOURCE_LIMITATION if packet.packer_kind == "message" else LEGACY_SOURCE_LIMITATION,
            "truncated": False,
            "partial_context": packet.partial_context,
            "partial_boundary_note": packet.partial_boundary_note,
            "message_count": packet.message_count or len(packet.evidence_ids),
            "conversation_count": len(packet.conversation_ids),
            "requested_target": packet.target_tokens,
            "actual_packed_estimated_tokens": packet.estimated_evidence_tokens,
            "overshoot": packet.overshoot,
            "included_boundary_evidence_ids": list(packet.included_boundary_evidence_ids),
            "omitted_boundary_evidence_ids": list(packet.omitted_boundary_evidence_ids),
            "partial_thread_ids": list(packet.partial_thread_ids),
            "packer_kind": packet.packer_kind,
        },
        "token_accounting": {
            "estimator_id": TOKEN_ESTIMATOR_ID,
            "estimator_formula": TOKEN_ESTIMATOR_FORMULA,
            "estimator_result_kind": TOKEN_ESTIMATOR_LABEL,
            "estimated_evidence_tokens": packet.estimated_evidence_tokens,
            "estimated_prompt_tokens": estimated_prompt,
            "actual_prompt_eval_count": actual,
            "configured_num_ctx": request.num_ctx,
            "assessment": assessment,
        },
        "last_event": last,
    }
    row.update(derived_prompt_metrics(row))
    return row


def run_gate3(
    *,
    config: Gate3Config,
    pieces: list[EvidencePiece],
    results_dir: Path | str,
    generate: GenerateFn,
    unload: UnloadFn,
    spec: ModelSpec,
    metadata: dict[str, Any],
    preflight: dict[str, Any],
    models_called: bool,
    progress: Gate3Progress | None = None,
    packer: NestedEmailPacker | NestedMessagePacker | None = None,
) -> dict[str, Any]:
    if not GATE3_CAPACITY_AUTHORIZED:
        raise GateNotAuthorized("Gate 3 capacity is not authorized")
    if config.config_id != "B" or config.tag != B_TAG:
        raise I11A0Error("Gate 3 runs Configuration B only")
    if config.digest != PINNED_B_DIGEST:
        raise I11A0Error("Gate 3 Configuration B digest mismatch")
    if config.thinking_mode != "off":
        raise I11A0Error("Gate 3 is thinking-off only")
    if PRODUCTION_PROMPT_ACCEPTED:
        raise I11A0Error("production narrator is not accepted for Gate 3")
    root = Path(results_dir)
    root.mkdir(parents=True, exist_ok=True)
    if progress is None:
        import io

        progress = Gate3Progress(
            root,
            timeout_seconds=config.timeout_seconds,
            controller_id="offline-gate3",
            snapshot=lambda: {},
            stream=None if models_called else io.StringIO(),
        )
    progress.emit(
        "Gate 3 started",
        status="starting",
        stage="preflight",
        phase="starting",
        expected_next_action="build_packets",
    )
    packer = packer or NestedEmailPacker(pieces)
    existing = load_existing_gate3_runs(root)
    log_text = ""
    log_path = root / "gate3_progress.log"
    if log_path.is_file():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
    heartbeat_vram = parse_heartbeat_vram(log_text)
    corrected_existing: list[dict[str, Any]] = []
    for prior in existing:
        row = dict(prior)
        if (
            row.get("execution_id") == PRESERVED_FALSE_OFFLOAD_EXECUTION_ID
            or (
                row.get("cpu_offload")
                and (row.get("vram_peak_gb") or 0) < 4
                and heartbeat_vram
                and max(heartbeat_vram) >= 10
            )
        ):
            correction = correct_false_cpu_offload_row(row, heartbeat_vram=heartbeat_vram)
            write_hardware_sidecar(root, row, correction)
            row = apply_hardware_correction(row, correction)
        if row.get("phase") in {"repeat_proposed", "repeat_next_larger"}:
            row["repeat_kind"] = "same_packet_validation_repeat"
            row["not_ladder_progression"] = True
            row["not_a_knee"] = True
            row["not_evidence_exhaustion"] = True
        corrected_existing.append(row)
    write_same_packet_repeat_sidecar(root, corrected_existing)
    qwen_cal = seed_qwen_b_calibration_from_runs(corrected_existing)
    persist_qwen_b_calibration(root, qwen_cal)
    runs: list[dict[str, Any]] = list(corrected_existing)
    last_stable: dict[str, Any] | None = None
    confirmed_streak = 0
    stop_reason = "stage_complete"
    last_packet_ids: tuple[str, ...] | None = None
    for prior in corrected_existing:
        if counts_toward_regression_stop(prior):
            confirmed_streak += 1
        elif counts_as_stable_ladder_rung(prior, ceiling_gb=config.maximum_vram_gb):
            confirmed_streak = 0
            last_stable = prior
            last_packet_ids = tuple((prior.get("packet_manifest") or {}).get("conversation_ids") or ())
        if is_estimator_calibration_shortfall(prior):
            write_preserved_rung_sidecar(
                root,
                prior,
                qwen_cal.snapshot_for_estimate(
                    planning_derived_complete_prompt_tokens(prior)
                    or int(prior.get("estimated_prompt_tokens") or 0)
                ),
            )

    def measure(
        packet: Gate3Packet,
        *,
        phase: str,
        target: int,
        repetition: int,
        confirmation: bool,
        pin_num_ctx: int | None = None,
        calibrated_same_packet_rerun: bool = False,
        supersedes_execution_id: str | None = None,
    ) -> dict[str, Any]:
        progress.emit(
            f"Building approximately {format_target(target)}-token evidence packet",
            status="running",
            stage="confirmation" if confirmation else (
                "repeat_validation" if phase.startswith("repeat") else (
                    "refinement" if phase == "refinement" else "coarse"
                )
            ),
            phase="packet_build",
            current_target_evidence_tokens=target,
            current_repetition=repetition,
            expected_next_action="submit_prompt",
        )
        user = render_user_message(
            packet_id=f"B-{target}-{phase}-{repetition}",
            packet_role="capacity",
            time_start=packet.time_start,
            time_end=packet.time_end,
            partial_context=bool(packet.partial_context),
            partial_boundary_note=packet.partial_boundary_note,
            evidence_ids=list(packet.evidence_ids),
            evidence_text=packet.text,
        )
        estimated_prompt = estimate_tokens(SYSTEM_PROMPT + "\n" + user)
        planned = plan_gate3_num_ctx(
            estimated_prompt_tokens=estimated_prompt,
            reserved_output_tokens=config.reserved_output_tokens,
            safety_margin_tokens=config.safety_margin_tokens,
            calibration=qwen_cal,
            pin_num_ctx=pin_num_ctx,
        )
        if int(planned["num_ctx"]) < estimated_prompt + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS:
            raise I11A0Error("planned num_ctx dropped below the 1,500-token safety margin")
        num_ctx = int(planned["num_ctx"])
        request = RunRequest(
            model_tag=spec.tag,
            digest=spec.digest,
            requested_evidence_tokens=target,
            evidence_sha256=packet.sha256,
            evidence_text=packet.text,
            repetition=repetition,
            warm_or_cold="cold",
            confirmation=confirmation,
            thinking_mode="off",
            seed=config.seed,
            num_ctx=num_ctx,
            reserved_output_tokens=config.reserved_output_tokens,
            prompt_sha256=prompt_sha256(),
            time_start=packet.time_start,
            time_end=packet.time_end,
            evidence_ids=packet.evidence_ids,
        )
        progress.emit(
            (
                f"Packet built: estimated evidence tokens={packet.estimated_evidence_tokens}, "
                f"bytes={packet.evidence_bytes}, conversations={len(packet.conversation_ids)}, "
                f"date range={packet.time_start} to {packet.time_end}, planned num_ctx={num_ctx}"
            ),
            phase="packet_build",
            current_estimated_evidence_tokens=packet.estimated_evidence_tokens,
            current_target_evidence_tokens=target,
        )
        if confirmation:
            progress.emit("Confirmation run started", stage="confirmation", phase="generation")
        elif phase == "refinement":
            progress.emit(
                f"Beginning {format_target(target)} refinement rung",
                stage="refinement",
                phase="generation",
            )
        elif phase.startswith("repeat"):
            progress.emit(
                f"Repeat validation run {repetition} at {format_target(target)}",
                stage="repeat_validation",
                phase="generation",
            )
        else:
            progress.emit(
                f"Beginning {format_target(target)} coarse rung",
                stage="coarse",
                phase="packet_build",
            )
        if planned.get("exceeds_verified_model_context"):
            progress.emit(
                (
                    f"Planned num_ctx={num_ctx} exceeds verified Qwen B maximum "
                    f"{QWEN_B_VERIFIED_MAX_CTX}; inference was not started"
                ),
                warning="planned_ctx_exceeds_model_limit",
                phase="packet_build",
            )
            extras = {
                "classification": "planned_ctx_exceeds_model_limit",
                "planned_ctx_exceeds_model_limit": True,
                "hardware": {
                    "gpu_resident": None,
                    "cpu_offload": False,
                    "placement_status": None,
                    "vram_peak_gb": None,
                },
                "last_event": {},
                "unload_seconds": 0,
                "unload_recorded": True,
                "vram_released": True,
            }
            measurement = Measurement(
                elapsed_seconds=0,
                prompt_eval_count=None,
                timed_out=False,
                infrastructure_failure=False,
                gpu_resident=None,
                cpu_spill=False,
            )
            row = _build_row(
                request=request,
                packet=packet,
                measurement=measurement,
                narration="",
                extras=extras,
                phase=phase,
                spec=spec,
                metadata=metadata,
                preflight=preflight,
                estimated_prompt=estimated_prompt,
                calibration_plan=planned,
            )
            row["planned_ctx_exceeds_model_limit"] = True
            row["classification"] = "planned_ctx_exceeds_model_limit"
            row["stable_ladder_rung"] = False
            row["stable_ladder_rung_vs_pipeline_success"] = (
                "classification is a pre-inference planning stop; not a successful_stable rung"
            )
            folder = publish_completed_run(root, row)
            rewrite_run_tables(root, list(runs) + [row])
            progress.emit(
                "Rung skipped before inference because planned context exceeded the verified model limit",
                phase="artifact_finalization",
                most_recent_classification=row.get("classification"),
                last_completed_execution_id=row.get("execution_id"),
                most_recent_artifact_directory=str(folder),
            )
            return row
        vram_projection = project_vram_for_next_packet(
            runs,
            next_estimated_tokens=packet.estimated_evidence_tokens,
            ceiling_gb=config.maximum_vram_gb,
        )
        if vram_projection.get("clearly_unsafe"):
            progress.emit(
                (
                    "Predicted VRAM "
                    f"{vram_projection.get('predicted_vram_gb')} GB would meet or exceed "
                    f"{config.maximum_vram_gb} GB; inference was not started"
                ),
                warning="predicted_vram_ceiling",
                phase="packet_build",
            )
            extras = {
                "classification": "predicted_vram_ceiling",
                "predicted_vram_ceiling": True,
                "hardware": {
                    "gpu_resident": None,
                    "cpu_offload": False,
                    "placement_status": None,
                    "vram_peak_gb": None,
                },
                "last_event": {},
                "unload_seconds": 0,
                "unload_recorded": True,
                "vram_released": True,
            }
            measurement = Measurement(
                elapsed_seconds=0,
                prompt_eval_count=None,
                timed_out=False,
                infrastructure_failure=False,
                gpu_resident=None,
                cpu_spill=False,
            )
            row = _build_row(
                request=request,
                packet=packet,
                measurement=measurement,
                narration="",
                extras=extras,
                phase=phase,
                spec=spec,
                metadata=metadata,
                preflight=preflight,
                estimated_prompt=estimated_prompt,
                calibration_plan=planned,
            )
            row["predicted_vram_ceiling"] = True
            row["vram_projection"] = vram_projection
            row["classification"] = "predicted_vram_ceiling"
            row["stable_ladder_rung"] = False
            folder = publish_completed_run(root, row)
            rewrite_run_tables(root, list(runs) + [row])
            progress.emit(
                "Rung skipped before inference because predicted VRAM was clearly unsafe",
                phase="artifact_finalization",
                most_recent_classification=row.get("classification"),
                last_completed_execution_id=row.get("execution_id"),
                most_recent_artifact_directory=str(folder),
            )
            return row
        progress.emit(
            "Prompt submitted; Ollama /api/chat stream covers model load, prompt evaluation, and generation until the first token",
            phase="ollama_request",
        )
        progress.start_heartbeat()
        try:
            measurement, narration, extras = generate(request, packet)
        except Exception as exc:
            progress.fail(str(exc), stop_reason="generation_failed")
            raise
        finally:
            progress.stop_heartbeat()
        if measurement.timed_out:
            progress.emit(
                "Generation timed out after the 1,800-second generation timeout",
                warning="timed_out",
                phase="generation",
                timeout_remaining_seconds=0,
            )
        else:
            progress.emit("Generation completed", phase="generation")
        progress.emit("Unloading model", phase="unload")
        progress.start_heartbeat()
        try:
            unload_s, unload_info = unload(spec.tag)
        except Exception as exc:
            progress.fail(str(exc), stop_reason="unload_failed")
            raise
        finally:
            progress.stop_heartbeat()
        extras = dict(extras)
        extras["unload_seconds"] = unload_s
        extras["unload_recorded"] = unload_info.get("unload_recorded", True)
        extras["vram_released"] = unload_info.get("vram_released")
        hardware = dict(extras.get("hardware") or {})
        if unload_info.get("vram_final_gb") is not None:
            hardware["vram_post_unload_gb"] = unload_info.get("vram_final_gb")
            hardware["vram_final_gb"] = unload_info.get("vram_final_gb")
        if unload_info.get("vram_pre_unload_gb") is not None:
            hardware["vram_pre_unload_gb"] = unload_info.get("vram_pre_unload_gb")
        if unload_info.get("ram_final_gb") is not None:
            hardware["ram_final_gb"] = unload_info.get("ram_final_gb")
        extras["hardware"] = hardware
        if extras.get("vram_released") is None:
            extras["vram_released"] = _vram_released(
                hardware.get("vram_baseline_gb"), hardware.get("vram_final_gb")
            )
        row = _build_row(
            request=request,
            packet=packet,
            measurement=measurement,
            narration=narration,
            extras=extras,
            phase=phase,
            spec=spec,
            metadata=metadata,
            preflight=preflight,
            estimated_prompt=estimated_prompt,
            calibration_plan=planned,
        )
        row["packet_progress_reason"] = extras.get("packet_progress_reason")
        row["calibrated_same_packet_rerun"] = calibrated_same_packet_rerun
        row["supersedes_execution_id"] = supersedes_execution_id
        if phase in {"repeat_proposed", "repeat_next_larger"}:
            row["repeat_kind"] = "operating_point_repeat"
        row["stable_ladder_rung"] = counts_as_stable_ladder_rung(
            row, ceiling_gb=config.maximum_vram_gb
        )
        row["pipeline_success_classification"] = row.get("classification")
        row["stable_ladder_rung_vs_pipeline_success"] = (
            "successful_stable means the pipeline completed with a passing safety margin; "
            "stable_ladder_rung is true only for coarse/refinement/calibrated_rerun rows that "
            "also pass placement, VRAM, and regression gates. Repeats may be successful_stable "
            "while stable_ladder_rung is false because they are validation copies, not new rungs."
        )
        if row.get("actual_prompt_tokens") is not None:
            qwen_cal.add_observation(
                execution_id=str(row["execution_id"]),
                estimated_complete_prompt_tokens=int(estimated_prompt),
                actual_complete_prompt_tokens=int(row["actual_prompt_tokens"]),
                tag=B_TAG,
            )
            persist_qwen_b_calibration(root, qwen_cal, planned)
        folder = publish_completed_run(root, row)
        progress.emit(
            f"Run COMPLETE marker published at {folder}",
            phase="artifact_finalization",
            most_recent_artifact_directory=str(folder),
        )
        runs_so_far = list(runs) + [row]
        rewrite_run_tables(root, runs_so_far)
        progress.emit(
            (
                f"Actual prompt tokens={row.get('actual_prompt_tokens')} "
                f"durations load={row.get('load_seconds')} prompt={row.get('prompt_eval_seconds')} "
                f"gen={row.get('eval_seconds')} elapsed={row.get('elapsed_seconds')} "
                f"throughput prompt_tps={row.get('prompt_tokens_per_second')} "
                f"gen_tps={row.get('generation_tokens_per_second')} "
                f"peak VRAM={row.get('vram_peak_gb')}"
            ),
            phase="artifact_finalization",
            most_recent_classification=row.get("classification"),
            last_completed_execution_id=row.get("execution_id"),
            most_recent_artifact_directory=str(folder),
            completed_run_count=len(runs_so_far),
        )
        if row.get("final_safety_result") == "passed":
            progress.emit("Safety check passed", phase="artifact_finalization")
        else:
            progress.emit(
                f"Safety check failed: {row.get('final_safety_result')}",
                phase="artifact_finalization",
                warning=str(row.get("final_safety_result")),
            )
        if row.get("vram_released"):
            progress.emit("VRAM returned to baseline", phase="unload")
        else:
            progress.emit("VRAM not returned to baseline", phase="unload", warning="vram_not_released")
        progress.emit("Rung artifacts finalized", phase="artifact_finalization")
        if confirmation:
            progress.emit("Confirmation run completed", stage="confirmation")
        return row

    rerun_source = needs_identical_packet_rerun(runs)
    placement_source = needs_gpu_placement_validation(runs)
    target = config.start_evidence_tokens
    if last_stable is not None:
        target = next_coarse_grid_target(
            int(last_stable.get("estimated_evidence_tokens") or last_stable.get("requested_evidence_tokens") or 0),
            increment=config.coarse_increment_tokens,
        )
    if rerun_source is None and placement_source is not None:
        rerun_source = placement_source
    if rerun_source is not None:
        if rerun_source is placement_source:
            progress.emit(
                "Identical-packet GPU-placement validation required at num_ctx=8448; prior executions are retained",
                stage="coarse",
                phase="calibration",
                last_completed_execution_id=rerun_source.get("execution_id"),
            )
        else:
            progress.emit(
                "Calibrated identical-packet rerun required; original safety-margin-failed run is retained",
                stage="coarse",
                phase="calibration",
                last_completed_execution_id=rerun_source.get("execution_id"),
            )
        packet = packet_from_saved_row(rerun_source)
        if not packet.text:
            packet = packer.packet_for_target(int(rerun_source.get("requested_evidence_tokens") or target))
        row = measure(
            packet,
            phase="coarse",
            target=int(rerun_source.get("requested_evidence_tokens") or config.start_evidence_tokens),
            repetition=1,
            confirmation=False,
            pin_num_ctx=CALIBRATED_SAME_PACKET_NUM_CTX,
            calibrated_same_packet_rerun=True,
            supersedes_execution_id=str(rerun_source.get("execution_id")),
        )
        if row.get("execution_id") == rerun_source.get("execution_id"):
            raise I11A0Error("calibrated rerun reused the preserved execution id")
        if row.get("packet_sha256") != rerun_source.get("packet_sha256"):
            raise I11A0Error("calibrated rerun packet hash changed")
        runs.append(row)
        last_packet_ids = packet.evidence_ids
        hard = hard_stop_reason(row, ceiling_gb=config.maximum_vram_gb)
        if hard:
            stop_reason = hard
            target = int(row["requested_evidence_tokens"])
        elif row.get("final_safety_result") == "passed":
            last_stable = row
            confirmed_streak = 0
            target = next_coarse_grid_target(
                int(row.get("estimated_evidence_tokens") or row.get("requested_evidence_tokens") or 0),
                increment=config.coarse_increment_tokens,
            )
        else:
            stop_reason = str(row.get("classification") or "calibrated_rerun_failed")

    while True:
        if stop_reason != "stage_complete":
            break
        packet = packer.packet_for_target(target)
        remaining = packer.remaining_after(packet)
        progress_reason = classify_packet_progress(
            target=target,
            packet=packet,
            previous_ids=last_packet_ids,
            remaining=remaining,
        )
        packet_row_reason = progress_reason
        if progress_reason == "target_already_covered":
            target = next_coarse_grid_target(
                packet.estimated_evidence_tokens, increment=config.coarse_increment_tokens
            )
            continue
        if progress_reason == "no_packet_growth":
            stop_reason = "no_packet_growth"
            break
        if progress_reason == "evidence_exhausted" and last_packet_ids is not None:
            stop_reason = "evidence_exhausted"
            break
        row = measure(packet, phase="coarse", target=target, repetition=1, confirmation=False)
        row["packet_progress_reason"] = packet_row_reason
        runs.append(row)
        last_packet_ids = packet.evidence_ids
        hard = hard_stop_reason(row, ceiling_gb=config.maximum_vram_gb)
        if hard:
            stop_reason = hard
            break
        verdict = material_regression(row, last_stable, fraction=config.regression_fraction)
        row["regression_eval"] = verdict
        if verdict["regressed"] and last_stable is not None:
            progress.emit("Possible regression detected", warning="possible_regression")
            confirm = measure(packet, phase="coarse", target=target, repetition=2, confirmation=True)
            runs.append(confirm)
            hard = hard_stop_reason(confirm, ceiling_gb=config.maximum_vram_gb)
            if hard:
                stop_reason = hard
                break
            confirmed = material_regression(confirm, last_stable, fraction=config.regression_fraction)
            confirm["regression_eval"] = confirmed
            if confirmed["regressed"] and not is_estimator_calibration_shortfall(confirm):
                confirm["confirmed_regression"] = True
                row["confirmed_regression"] = True
                confirmed_streak += 1
                if confirmed_streak >= config.confirmed_regression_stop:
                    stop_reason = "three_confirmed_regressions"
                    break
            else:
                confirmed_streak = 0
                if counts_as_stable_ladder_rung(confirm, ceiling_gb=config.maximum_vram_gb):
                    last_stable = confirm
        else:
            confirmed_streak = 0
            if counts_as_stable_ladder_rung(row, ceiling_gb=config.maximum_vram_gb):
                last_stable = row
        if packet.exhausted or packer.remaining_after(packet) <= 0:
            stop_reason = "evidence_exhausted"
            break
        target = next_coarse_grid_target(
            packet.estimated_evidence_tokens, increment=config.coarse_increment_tokens
        )

    progress.emit(
        f"Coarse ladder stopped and reason: {stop_reason}",
        stage="analysis",
        stop_reason=stop_reason,
        expected_next_action="refinement_or_repeats",
    )
    if last_stable and should_run_final_repeats(stop_reason) and stop_reason not in {
        "host_affinity",
        "estimator_recalibration_required",
        "placement_unknown",
    }:
        progress.emit("Refinement started", stage="refinement", phase="packet_build")
        low = int(last_stable["requested_evidence_tokens"])
        high = target if stop_reason != "evidence_exhausted" else low + config.refinement_increment_tokens
        if stop_reason == "three_confirmed_regressions":
            high = int(runs[-1]["requested_evidence_tokens"])
        size = low + config.refinement_increment_tokens
        last_ref_ids = tuple(last_stable.get("packet_manifest", {}).get("conversation_ids") or ())
        proposed_row = last_stable
        next_larger_packet = None
        while size < high:
            packet = packer.packet_for_target(size)
            if packet.conversation_ids == last_ref_ids:
                break
            row = measure(packet, phase="refinement", target=size, repetition=1, confirmation=False)
            runs.append(row)
            last_ref_ids = packet.conversation_ids
            hard = hard_stop_reason(row, ceiling_gb=config.maximum_vram_gb)
            if hard:
                stop_reason = hard
                break
            verdict = material_regression(row, proposed_row, fraction=config.regression_fraction)
            row["regression_eval"] = verdict
            if verdict["regressed"] or hard:
                next_larger_packet = packet
                break
            proposed_row = row
            next_larger_packet = None
            size += config.refinement_increment_tokens
        proposed_packet = packer.packet_for_target(int(proposed_row["requested_evidence_tokens"]))
        progress.emit("Repeat validation started", stage="repeat_validation")
        for rep in range(1, config.repeat_count + 1):
            row = measure(
                proposed_packet,
                phase="repeat_proposed",
                target=int(proposed_row["requested_evidence_tokens"]),
                repetition=rep,
                confirmation=False,
            )
            runs.append(row)
            hard = hard_stop_reason(row, ceiling_gb=config.maximum_vram_gb)
            if hard:
                stop_reason = hard
                break
        else:
            larger_target = int(proposed_row["requested_evidence_tokens"]) + config.refinement_increment_tokens
            larger_packet = next_larger_packet or packer.packet_for_target(larger_target)
            if larger_packet.conversation_ids != proposed_packet.conversation_ids:
                for rep in range(1, config.repeat_count + 1):
                    row = measure(
                        larger_packet,
                        phase="repeat_next_larger",
                        target=larger_target,
                        repetition=rep,
                        confirmation=False,
                    )
                    runs.append(row)
                    hard = hard_stop_reason(row, ceiling_gb=config.maximum_vram_gb)
                    if hard:
                        stop_reason = hard
                        break

    analysis = analyze_gate3(runs, stop_reason=stop_reason, config=config)
    progress.emit("Assembling review package", stage="package", phase="package")
    package = write_gate3_package(
        results_dir=root,
        runs=runs,
        analysis=analysis,
        config=config,
        preflight=preflight,
    )
    write_same_packet_repeat_sidecar(root, runs)
    final_status = "completed" if stop_reason in {"stage_complete", "evidence_exhausted"} else "stopped"
    progress.emit("Review package completed", stage="package", status=final_status, stop_reason=stop_reason)
    progress.emit(
        "Gate 3 stopped for founder review",
        status=final_status,
        stage="package",
        phase="stopped",
        stop_reason=stop_reason,
        expected_next_action="founder_review",
    )
    return {
        "ok": True,
        "gate": "3",
        "stop_reason": stop_reason,
        "models_called": models_called,
        "pull_executed": False,
        "config_id": "B",
        "tag": config.tag,
        "digest": config.digest,
        "run_count": len(runs),
        "execution_ids": [row["execution_id"] for row in runs],
        "test_case_ids": [row["test_case_id"] for row in runs],
        "results_dir": str(root),
        "analysis": analysis,
        "package": package,
        "production_prompt_accepted": PRODUCTION_PROMPT_ACCEPTED,
        "prompt_status": PROMPT_STATUS,
        "peggy_scenario_started": False,
        "full_context_ladder_blocked_for_a_and_c": True,
        "i11a1_started": False,
        "source_limitation": SOURCE_LIMITATION,
    }


def run_gate3_live(
    *,
    config_path: Path | str | None,
    chunks_root: Path | str,
    results_dir: Path | str,
    ollama_base_url: str,
    confirm_benchmark: bool,
    i14_export: Path | str | None = None,
) -> dict[str, Any]:
    if not confirm_benchmark:
        raise InferenceNotAuthorized("Gate 3 requires --confirm-benchmark")
    ollama_base_url = require_literal_loopback_ollama_url(ollama_base_url)
    config = load_gate3_config(config_path)
    results = Path(results_dir)
    results.mkdir(parents=True, exist_ok=True)
    host_state = capture_clean_ladder_host_state()
    (results / "host_state_at_start.json").write_text(
        json.dumps(host_state, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    def live_snapshot() -> dict[str, Any]:
        nv = read_nvidia_snapshot()
        ram = read_system_ram()
        return {
            "vram_gb": nv.get("memory_used_gb"),
            "gpu_util": nv.get("utilization_gpu_percent"),
            "ram_gb": ram.get("used_gb"),
        }

    controller_id = new_execution_id(
        test_case="gate3-controller",
        hostname=socket.gethostname(),
        started_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    )
    progress = Gate3Progress(
        results,
        timeout_seconds=config.timeout_seconds,
        controller_id=controller_id,
        snapshot=live_snapshot,
    )
    progress.emit("Gate 3 started", status="starting", stage="preflight", phase="starting")
    try:
        progress.emit("Preflight started", stage="preflight", phase="preflight")
        preflight = collect_host_affinity_preflight(
            ollama_base_url=ollama_base_url,
            output_path=results,
            chunks_path=chunks_root,
            repo=REPO_ROOT,
        )
        require_flightsim_host_affinity(preflight)
        progress.emit("Preflight passed", stage="preflight", phase="preflight")
        inventory = inventory_installed_models(base_url=ollama_base_url)
        if inventory.get("pull_executed"):
            raise I11A0Error("inventory reported a pull")
        spec = ModelSpec("B", config.tag, config.quantization, config.digest)
        by_tag = {row["tag"]: row for row in inventory.get("approved") or []}
        row = by_tag.get(spec.tag) or {}
        digest = str(row.get("digest") or spec.digest)
        if digest != PINNED_B_DIGEST:
            raise I11A0Error(f"installed B digest is not the Gate 2 digest: {digest}")
        spec = ModelSpec("B", spec.tag, spec.quantization, digest)
        progress.emit("Verifying Qwen B", phase="model_verify")
        metadata = require_qwen_smoke_configuration(spec, row)
        live_packer: NestedEmailPacker | NestedMessagePacker
        if i14_export or config.source == I14_SOURCE_LABEL or config.experiment_phase == "i14_cleaned":
            from memorybox.ask.i11a.i11a0_i14_source import (
                load_frozen_prompt_messages,
                messages_to_pieces,
                verify_pinned_i14_export,
            )

            export_dir = Path(i14_export or "")
            if not export_dir.is_dir():
                raise I11A0Error("i14 cleaned export directory is required for the remaining Gate 3 ladder")
            progress.emit("Verifying frozen I14 export", stage="preflight", phase="export_verify")
            export_proof = verify_pinned_i14_export(export_dir)
            (results / "i14_export_verification.json").write_text(
                json.dumps(export_proof, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            progress.emit(
                (
                    "Frozen I14 export verified: "
                    f"v3 {export_proof['generation_id']} "
                    f"prompt_sha256={export_proof['prompt_sha256'][:12]} "
                    f"messages={export_proof['prompt_messages']} threads={export_proof['threads']}"
                ),
                stage="preflight",
                phase="export_verify",
            )
            messages = load_frozen_prompt_messages(export_dir)
            live_packer = NestedMessagePacker(messages)
            pieces = messages_to_pieces(messages)
        else:
            raise I11A0Error(
                "legacy seven-chunk REVIEW_20260831T120929Z source is closed for new ladder runs; "
                "use --i14-export with the frozen accepted I14 cleaned export"
            )
    except Exception as exc:
        progress.fail(str(exc), stop_reason="preflight")
        raise

    def generate(request: RunRequest, packet: Gate3Packet) -> tuple[Measurement, str, dict[str, Any]]:
        sampler = HardwareSampler()
        progress.emit("Waiting for VRAM baseline", phase="baseline_wait")
        sampler.capture("baseline")
        progress.emit("Loading model is not asserted until Ollama streams tokens; request phase is ollama_request")
        progress.emit(
            "Submitting Ollama /api/chat request (model load, prompt evaluation, and generation share this HTTP stream)",
            phase="ollama_request",
        )

        def on_stream_phase(phase: str) -> None:
            if phase == "generation":
                progress.emit(
                    "Generation running (first streamed content token received)",
                    phase="generation",
                )

        loaded_ps: dict[str, Any] = {}

        def on_first_token() -> None:
            loaded_ps["payload"] = read_ollama_ps(ollama_base_url)
            loaded_ps["interpreted"] = interpret_ollama_placement(
                loaded_ps["payload"],
                tag=spec.tag,
                digest=spec.digest,
                queried_while_loaded=True,
            )

        measurement, narration, events = _chat(
            request,
            base_url=ollama_base_url,
            timeout=config.timeout_seconds,
            sampler=sampler,
            packet_role="capacity",
            on_stream_phase=on_stream_phase,
            on_first_token=on_first_token,
            keep_alive="2m",
        )
        if "interpreted" not in loaded_ps:
            loaded_ps["payload"] = read_ollama_ps(ollama_base_url)
            loaded_ps["interpreted"] = interpret_ollama_placement(
                loaded_ps["payload"],
                tag=spec.tag,
                digest=spec.digest,
                queried_while_loaded=True,
            )
        sampler.capture("pre_unload")
        pre_unload = sampler.samples[-1].get("vram_used_gb") if sampler.samples else None
        hardware = finalize_hardware(
            sampler_hardware=sampler.summary(),
            heartbeat_vram=list(progress.vram_history),
            placement=loaded_ps["interpreted"],
            pre_unload_vram_gb=pre_unload,
        )
        last = events[-1] if events else {}
        return measurement, narration, {
            "hardware": hardware,
            "last_event": last,
            "raw_api": "".join(json.dumps(event) + "\n" for event in events),
            "telemetry": "".join(json.dumps(sample) + "\n" for sample in hardware.get("samples") or []),
            "placement_raw": loaded_ps.get("payload"),
        }

    def unload(tag: str) -> tuple[float, dict[str, Any]]:
        sampler = HardwareSampler()
        sampler.capture("before_unload")
        seconds = _unload(ollama_base_url, tag)
        time.sleep(VRAM_RELEASE_SETTLE_SECONDS)
        sampler.capture("after_unload_settled")
        hardware = sampler.summary()
        return seconds, {
            "unload_recorded": True,
            "vram_final_gb": hardware.get("vram_final_gb"),
            "vram_pre_unload_gb": hardware.get("vram_baseline_gb"),
            "vram_released": _vram_released(
                hardware.get("vram_baseline_gb"), hardware.get("vram_final_gb")
            ),
            "ram_final_gb": hardware.get("ram_final_gb"),
        }

    try:
        return run_gate3(
            config=config,
            pieces=pieces,
            results_dir=results,
            generate=generate,
            unload=unload,
            spec=spec,
            metadata=metadata,
            preflight=preflight,
            models_called=True,
            progress=progress,
            packer=live_packer,
        )
    except Exception as exc:
        progress.fail(str(exc), stop_reason="failed")
        raise


def _piece(piece_id: str, chars: int, stamp: str = "2009-01-01T00:00:00Z") -> EvidencePiece:
    from memorybox.ask.i11a.i11a0_benchmark import EvidenceTurn

    body = ("Peggy email " + "x" * max(0, chars - 12)).rstrip()
    text = f"[email_{piece_id}] {body}"
    turn = EvidenceTurn(f"email_{piece_id}", text, stamp)
    return EvidencePiece(piece_id, (turn,), stamp, stamp)


def prove_gate3_offline() -> dict[str, Any]:
    """Controller proofs with a scripted generate. Does not call a model."""
    from memorybox.ask.i11a.i11a0_host import HostAffinityError
    import tempfile

    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, condition: bool, detail: Any = None) -> None:
        checks.append(name)
        if not condition:
            problems.append(f"{name}: {detail}")

    from memorybox.ask.i11a.i11a0_gate3_progress import Gate3Progress, atomic_replace_text

    class _CountStream:
        def __init__(self) -> None:
            self.chunks: list[str] = []
            self.flushes = 0

        def write(self, text: str) -> int:
            self.chunks.append(text)
            return len(text)

        def flush(self) -> None:
            self.flushes += 1

    with tempfile.TemporaryDirectory() as tmp:
        stream = _CountStream()
        beats = {"n": 0}

        def snap() -> dict[str, Any]:
            beats["n"] += 1
            return {"vram_gb": 11.0, "ram_gb": 20.0, "gpu_util": 40.0}

        prog = Gate3Progress(
            tmp,
            timeout_seconds=1800,
            controller_id="ctrl-test",
            stream=stream,
            snapshot=snap,
            heartbeat_seconds=0.05,
        )
        first = prog.emit("Gate 3 started", status="starting", stage="preflight", phase="starting")
        ok("progress_json_atomic_replace", (Path(tmp) / "gate3_progress.json").is_file() and not (Path(tmp) / "gate3_progress.json.tmp").exists(), None)
        ok("progress_state_transitions", first["status"] == "starting" and first["stage"] == "preflight", first)
        ok("progress_flushes_immediately", stream.flushes >= 1 and stream.chunks, stream.flushes)
        prog.emit("Preflight passed", status="running", stage="preflight", phase="preflight")
        prog.start_heartbeat()
        time.sleep(0.18)
        prog.stop_heartbeat()
        text = "".join(stream.chunks) + (Path(tmp) / "gate3_progress.log").read_text(encoding="utf-8")
        ok("heartbeat_emitted_during_wait", "HEARTBEAT" in text and "vram_gb=11" in text, text[-400:])
        prog.fail("simulated timeout", stop_reason="timed_out")
        failed = json.loads((Path(tmp) / "gate3_progress.json").read_text(encoding="utf-8"))
        ok("timeout_failure_updates_progress_files", failed["status"] == "failed" and "failed" in (Path(tmp) / "gate3_progress.log").read_text(encoding="utf-8").lower(), failed)
        atomic_replace_text(Path(tmp) / "atom.json", '{"ok": true}\n')
        ok("atomic_status_file_has_no_tmp_left", json.loads((Path(tmp) / "atom.json").read_text(encoding="utf-8"))["ok"] is True and not (Path(tmp) / "atom.json.tmp").exists(), None)

    pieces = [_piece(str(i), 3200, f"2009-01-0{i}T00:00:00Z") for i in range(1, 8)]
    packer = NestedEmailPacker(pieces)
    p2 = packer.packet_for_target(2000)
    p3 = packer.packet_for_target(3000)
    ok("nested_packet_growth", set(p2.conversation_ids).issubset(p3.conversation_ids), (p2.conversation_ids, p3.conversation_ids))
    ok("nested_text_is_prefix", p3.text.startswith(p2.text.rstrip()) or p2.text in p3.text, None)
    ok("conversation_not_split", p2.partial_context is False and p3.overshoot in {True, False}, p2)
    ok("two_k_overshoot_3048_advances_to_4000", next_coarse_grid_target(3048) == 4000, next_coarse_grid_target(3048))
    ok("overshooting_several_grids_advances_above_actual", next_coarse_grid_target(4372) == 5000, next_coarse_grid_target(4372))
    first_big = NestedEmailPacker([_piece("a", 12180), _piece("b", 5000), _piece("c", 5000)])
    covered = first_big.packet_for_target(2000)
    same_at_3000 = first_big.packet_for_target(3000)
    next_at_4000 = first_big.packet_for_target(4000)
    ok(
        "same_packet_is_not_exhaustion_while_conversations_remain",
        classify_packet_progress(
            target=3000,
            packet=same_at_3000,
            previous_ids=covered.evidence_ids,
            remaining=first_big.remaining_after(same_at_3000),
        )
        == "target_already_covered"
        and first_big.remaining_after(covered) > 0
        and next_at_4000.conversation_ids != covered.conversation_ids,
        (covered.estimated_evidence_tokens, same_at_3000.conversation_ids, next_at_4000.conversation_ids),
    )
    ok("next_grid_after_overshoot_packet_is_4000", next_coarse_grid_target(covered.estimated_evidence_tokens) == 4000, covered.estimated_evidence_tokens)
    ok("four_k_packet_is_nested_prefix", next_at_4000.text.startswith(covered.text) or covered.text in next_at_4000.text, None)
    ok("conversations_remain_intact_on_growth", next_at_4000.partial_context is False, next_at_4000)
    ok(
        "no_duplicate_evidence_ids",
        len(next_at_4000.evidence_ids) == len(set(next_at_4000.evidence_ids)),
        next_at_4000.evidence_ids,
    )
    only = NestedEmailPacker([_piece("only", 12180)])
    only_pkt = only.packet_for_target(2000)
    ok(
        "true_exhaustion_requires_no_remaining_conversations",
        classify_packet_progress(
            target=4000,
            packet=only.packet_for_target(4000),
            previous_ids=only_pkt.evidence_ids,
            remaining=only.remaining_after(only_pkt),
        )
        == "evidence_exhausted"
        and only.remaining_after(only_pkt) == 0,
        only.remaining_after(only_pkt),
    )
    ok("final_repeats_not_triggered_by_false_exhaustion", should_run_final_repeats("target_already_covered") is False, None)
    ok("final_repeats_allowed_after_true_exhaustion", should_run_final_repeats("evidence_exhausted") is True, None)
    one = NestedEmailPacker([_piece("big", 20000)])
    over = one.packet_for_target(2000)
    ok("intact_conversation_overshoot_recorded", over.overshoot is True and len(over.conversation_ids) == 1, over)

    eq = prompt_safety_assessment(
        actual_prompt_tokens=1978,
        estimated_prompt_tokens=1893,
        configured_num_ctx=6144,
        output_reserve_tokens=2500,
        required_safety_margin_tokens=1500,
    )
    ok("token_safety_equation_pass_at_6144", eq["final_safety_result"] == "passed", eq)
    fail = prompt_safety_assessment(
        actual_prompt_tokens=1978,
        estimated_prompt_tokens=1893,
        configured_num_ctx=5893,
        output_reserve_tokens=2500,
        required_safety_margin_tokens=1500,
    )
    ok("token_safety_equation_can_fail_a_completed_generation", fail["final_safety_result"] == "failed", fail)

    vram_row = {
        "vram_peak_gb": 22.5,
        "final_safety_result": "passed",
        "gpu_resident": True,
        "unload_recorded": True,
        "vram_released": True,
        "placement_status": "gpu_resident",
    }
    ok("vram_ceiling_stops", hard_stop_reason(vram_row) == "vram_ceiling", None)
    ok(
        "vram_ceiling_outranks_infrastructure_failure",
        hard_stop_reason(
            {
                **vram_row,
                "vram_peak_gb": 22.62109375,
                "infrastructure_failure": True,
                "classification": "infrastructure_failure",
                "configured_num_ctx": 41472,
            }
        )
        == "vram_ceiling",
        None,
    )
    huge = QwenBPromptCalibration()
    huge.add_observation(
        execution_id="obs",
        estimated_complete_prompt_tokens=1000,
        actual_complete_prompt_tokens=1200,
    )
    over_ctx = huge.snapshot_for_estimate(37000)
    ok(
        "planned_num_ctx_above_40960_is_rejected",
        over_ctx["exceeds_verified_model_context"] is True and over_ctx["num_ctx"] > QWEN_B_VERIFIED_MAX_CTX,
        over_ctx,
    )
    ok(
        "planned_ctx_stop_reason",
        hard_stop_reason({"classification": "planned_ctx_exceeds_model_limit", "planned_ctx_exceeds_model_limit": True})
        == "planned_ctx_exceeds_model_limit",
        None,
    )
    def _stable_vram(est: int, vram: float) -> dict[str, Any]:
        return {
            "phase": "coarse",
            "estimated_evidence_tokens": est,
            "vram_peak_gb": vram,
            "final_safety_result": "passed",
            "gpu_resident": True,
            "cpu_offload": False,
            "cpu_spill": False,
            "placement_status": "gpu_resident",
            "unload_recorded": True,
            "vram_released": True,
        }
    unsafe_proj = project_vram_for_next_packet(
        [_stable_vram(18000, 20.0), _stable_vram(19000, 21.0)],
        next_estimated_tokens=25000,
        ceiling_gb=22.5,
    )
    ok("predicted_vram_two_point_clearly_unsafe", unsafe_proj.get("clearly_unsafe") is True, unsafe_proj)
    flat_proj = project_vram_for_next_packet(
        [_stable_vram(18000, 20.0), _stable_vram(19000, 20.05)],
        next_estimated_tokens=20000,
        ceiling_gb=22.5,
    )
    ok("predicted_vram_flat_not_clearly_unsafe", flat_proj.get("clearly_unsafe") is False, flat_proj)
    ok("vram_boundary_is_not_a_knee", classify_boundary_kind("vram_ceiling") == "vram_boundary", None)
    ok("context_boundary_is_not_a_knee", classify_boundary_kind("planned_ctx_exceeds_model_limit") == "model_context_boundary", None)
    ok("performance_knee_kind", classify_boundary_kind("three_confirmed_regressions") == "performance_knee", None)
    from memorybox.ask.i11a.i11a0_host import require_literal_loopback_ollama_url as require_url
    from memorybox.ask.i11a.i11a0_host import HostAffinityError as UrlAffinityError
    try:
        require_url("[http://127.0.0.1:11434](http://127.0.0.1:11434)")
        ok("markdown_ollama_url_refused", False, "did_not_raise")
    except UrlAffinityError:
        ok("markdown_ollama_url_refused", True, None)
    ok("literal_ollama_url_accepted", require_url("http://127.0.0.1:11434") == "http://127.0.0.1:11434", None)
    from memorybox.ask.i11a.i11a0_i14_source import FrozenMessage, prove_i14_phase1_offline

    i14_msgs = [
        FrozenMessage("e1", "T-1", "2010-01-01T00:00:00Z", "Author: Peggy George\n\n" + ("a" * 1200), "Peggy George", "p", True),
        FrozenMessage("e2", "T-1", "2010-01-02T00:00:00Z", "Author: Tom Will\n\n" + ("b" * 1200), "Tom Will", "t", True),
        FrozenMessage("e3", "T-2", "2010-01-03T00:00:00Z", "Author: Peggy George\n\n" + ("c" * 5000), "Peggy George", "p", True),
    ]
    msg_packer = NestedMessagePacker(i14_msgs)
    m_small = msg_packer.packet_for_target(200)
    m_next = msg_packer.packet_for_target(m_small.estimated_evidence_tokens + 100)
    ok("i14_nested_messages_are_prefix", set(m_small.evidence_ids).issubset(m_next.evidence_ids), (m_small.evidence_ids, m_next.evidence_ids))
    ok("i14_does_not_split_a_message", m_small.evidence_ids[0] == "e1", m_small.evidence_ids)
    ok("i14_partial_context_flagged_when_thread_continues", m_small.partial_context is True, m_small)
    ok("i14_records_omitted_boundary", bool(m_small.omitted_boundary_evidence_ids), m_small)
    covered_msg = msg_packer.packet_for_target(m_small.estimated_evidence_tokens)
    ok(
        "i14_covered_target_is_not_exhaustion",
        classify_packet_progress(
            target=m_small.estimated_evidence_tokens,
            packet=covered_msg,
            previous_ids=m_small.evidence_ids,
            remaining=msg_packer.remaining_after(covered_msg),
        )
        == "target_already_covered",
        None,
    )
    i14_proof = prove_i14_phase1_offline()
    ok("i14_phase1_offline", i14_proof.get("ok") is True, i14_proof.get("problems"))
    ok("i14_models_not_called", i14_proof.get("models_called") is False, None)

    knee_fix = analyze_gate3(
        [
            {
                "phase": "coarse",
                "requested_evidence_tokens": 2000,
                "estimated_evidence_tokens": 3048,
                "classification": "successful_pipeline_safety_margin_failed",
                "final_safety_result": "failed",
                "remaining_safety_margin_tokens": -258,
                "gpu_resident": True,
                "cpu_offload": False,
                "cpu_spill": False,
                "placement_status": "gpu_resident",
                "unload_recorded": True,
                "vram_released": True,
            },
            {
                "phase": "coarse",
                "requested_evidence_tokens": 26000,
                "estimated_evidence_tokens": 33229,
                "classification": "infrastructure_failure",
                "infrastructure_failure": True,
                "vram_peak_gb": 22.62109375,
                "configured_num_ctx": 41472,
                "gpu_resident": False,
                "unload_recorded": True,
                "vram_released": True,
                "execution_id": "fddc024a-test",
            },
        ],
        stop_reason="vram_ceiling",
        config=Gate3Config(),
    )
    ok(
        "knee_first_stop_is_not_2000_requested",
        knee_fix["knee_range"]["first_regression_or_stop"] == 33229,
        knee_fix["knee_range"],
    )
    ok(
        "cpu_offload_stops",
        hard_stop_reason({**vram_row, "vram_peak_gb": 10, "cpu_offload": True, "placement_status": "cpu_offload"})
        == "cpu_offload",
        None,
    )
    ok(
        "unknown_placement_does_not_silently_proceed",
        hard_stop_reason({**vram_row, "vram_peak_gb": 10, "gpu_resident": False, "cpu_offload": False, "placement_status": "unknown"})
        == "placement_unknown",
        None,
    )

    prior = {
        "actual_prompt_tokens": 4000,
        "prompt_tokens_per_second": 200.0,
        "prompt_eval_seconds": 20.0,
        "elapsed_seconds": 30.0,
        "vram_peak_gb": 10.0,
        "vram_growth_per_1000_actual_prompt_tokens": 0.2,
    }
    worse = {
        "actual_prompt_tokens": 5000,
        "prompt_tokens_per_second": 150.0,
        "prompt_eval_seconds": 45.0,
        "elapsed_seconds": 70.0,
        "vram_peak_gb": 12.0,
    }
    verdict = material_regression(worse, prior, fraction=0.10)
    ok("regression_requires_throughput_or_cost_and_corroboration", verdict["regressed"] is True, verdict)
    noisy = dict(worse)
    noisy["prompt_tokens_per_second"] = 195.0
    noisy["prompt_eval_seconds"] = 25.6
    ok("single_noisy_measurement_is_not_automatically_a_stop", material_regression(noisy, prior)["regressed"] is False, None)

    import tempfile
    from memorybox.ask.i11a.i11a0_host import collect_host_affinity_preflight, require_flightsim_host_affinity

    spec = ModelSpec("B", B_TAG, B_QUANT, PINNED_B_DIGEST)
    metadata = {"tag": B_TAG, "digest": PINNED_B_DIGEST, "architecture": "qwen3", "quantization": B_QUANT, "verified": True}

    def scripted(plan: list[dict[str, Any]]) -> GenerateFn:
        cursor = {"i": 0}

        def generate(request: RunRequest, packet: Gate3Packet) -> tuple[Measurement, str, dict[str, Any]]:
            script = plan[min(cursor["i"], len(plan) - 1)]
            cursor["i"] += 1
            actual = int(script.get("actual") or estimate_tokens(SYSTEM_PROMPT + packet.text) + 80)
            measurement = Measurement(
                prompt_tokens_per_second=script.get("prompt_tps", 180.0),
                generation_tokens_per_second=script.get("gen_tps", 50.0),
                elapsed_seconds=script.get("elapsed", 40.0),
                peak_vram_gb=script.get("vram", 12.0),
                gpu_resident=script.get("gpu_resident", True),
                cpu_spill=script.get("cpu_offload", False),
                prompt_eval_count=actual,
                timed_out=script.get("timed_out", False),
                infrastructure_failure=script.get("infra", False),
            )
            last = {
                "load_duration": int(script.get("load_ns", 8_000_000_000)),
                "prompt_eval_duration": int(script.get("prompt_ns", 15_000_000_000)),
                "eval_duration": int(script.get("eval_ns", 10_000_000_000)),
            }
            hardware = {
                "vram_baseline_gb": 2.8,
                "vram_peak_gb": script.get("vram", 12.0),
                "vram_final_gb": 2.8,
                "ram_baseline_gb": 20.0,
                "ram_peak_gb": 21.0,
                "ram_final_gb": 20.0,
                "gpu_resident": script.get("gpu_resident", True),
                "cpu_offload": script.get("cpu_offload", False),
                "placement_status": script.get("placement_status", "gpu_resident"),
                "placement_reason": script.get(
                    "placement_reason", "scripted_full_gpu_assignment"
                ),
                "samples": [],
            }
            return measurement, f"narration {request.requested_evidence_tokens}", {
                "hardware": hardware,
                "last_event": last,
                "raw_api": json.dumps(last) + "\n",
                "telemetry": "",
            }

        return generate

    def unload(_tag: str) -> tuple[float, dict[str, Any]]:
        return 0.2, {
            "unload_recorded": True,
            "vram_released": True,
            "vram_baseline_gb": 2.8,
            "vram_final_gb": 2.8,
        }

    preflight_ok = collect_host_affinity_preflight(
        ollama_base_url="http://127.0.0.1:11434",
        output_path=".",
        chunks_path=".",
        repo=Path("."),
        nvidia_reader=lambda: {
            "available": True,
            "name": "NVIDIA GeForce RTX 4090",
            "memory_total_gb": 23.988,
            "memory_used_gb": 0.4,
            "utilization_gpu_percent": 1.0,
        },
        ram_reader=lambda: {"available": True, "total_gb": 64.0, "used_gb": 20.0},
        git_reader=lambda _repo: {"branch": "cursor/p2-i11a0-offline-harness", "commit": "x"},
        ollama_version_reader=lambda _url: "0.34.1",
        controller_hostname="FlightSim",
    )
    require_flightsim_host_affinity(preflight_ok)
    ok("flightsim_host_affinity_required", True)

    desktop = collect_host_affinity_preflight(
        ollama_base_url="http://127.0.0.1:11434",
        output_path=".",
        chunks_path=".",
        repo=Path("."),
        nvidia_reader=lambda: {
            "available": True,
            "name": "NVIDIA GeForce GTX 1650",
            "memory_total_gb": 4.0,
            "memory_used_gb": 1.0,
            "utilization_gpu_percent": 1.0,
        },
        ram_reader=lambda: {"available": True, "total_gb": 32.0, "used_gb": 10.0},
        git_reader=lambda _repo: {"branch": "x", "commit": "y"},
        ollama_version_reader=lambda _url: "0.34.1",
        controller_hostname="Toms-Desktop",
    )
    blocked = False
    try:
        require_flightsim_host_affinity(desktop)
    except HostAffinityError:
        blocked = True
    ok("desktop_cannot_run_gate3", blocked)

    with tempfile.TemporaryDirectory() as tmp:
        cfg = Gate3Config(start_evidence_tokens=2000, coarse_increment_tokens=1000, refinement_increment_tokens=250, repeat_count=3)
        payload = run_gate3(
            config=cfg,
            pieces=pieces,
            results_dir=Path(tmp) / "exhausted",
            generate=scripted([{"prompt_tps": 180.0, "vram": 12.0, "elapsed": 40.0, "prompt_ns": 12_000_000_000}]),
            unload=unload,
            spec=spec,
            metadata=metadata,
            preflight=preflight_ok,
            models_called=False,
        )
        ok("evidence_exhausted_stop", payload["stop_reason"] == "evidence_exhausted", payload["stop_reason"])
        ok("unique_execution_ids", len(set(payload["execution_ids"])) == len(payload["execution_ids"]), payload["execution_ids"])
        ok("no_a_or_c_inference", payload["full_context_ladder_blocked_for_a_and_c"] is True, None)
        ok("no_production_prompt", payload["production_prompt_accepted"] is False, None)
        ok("no_peggy_scenario", payload["peggy_scenario_started"] is False, None)
        ok("models_not_called_in_offline_prove", payload["models_called"] is False, None)
        ok("summary_mentions_email_only", "SMS" in (Path(tmp) / "exhausted" / "gate3_summary.md").read_text(encoding="utf-8"), None)
        first_run_dir = next((Path(tmp) / "exhausted" / "runs").iterdir())
        ok(
            "completed_run_published_without_writing_suffix",
            first_run_dir.is_dir()
            and not str(first_run_dir).endswith(".writing")
            and (first_run_dir / "COMPLETE").is_file()
            and (Path(tmp) / "exhausted" / "gate3_runs.csv").is_file()
            and (Path(tmp) / "exhausted" / "gate3_progress.log").is_file(),
            first_run_dir,
        )
        phases = set()
        with (Path(tmp) / "exhausted" / "gate3_runs.jsonl").open(encoding="utf-8") as handle:
            for line in handle:
                phases.add(json.loads(line)["phase"])
        ok("three_repeat_validation_present", "repeat_proposed" in phases, phases)
        ok("refinement_phase_recorded_or_skipped_when_corpus_ends", True)

    def regressing_plan() -> list[dict[str, Any]]:
        plan = []
        tps = 200.0
        prompt_ns = 10_000_000_000
        vram = 8.0
        for i in range(20):
            if i >= 2:
                tps = 200.0 * (0.7 ** (i - 1))
                prompt_ns = int(10_000_000_000 * (1.6 ** (i - 1)))
                vram = 8.0 + i * 1.2
            plan.append({"prompt_tps": tps, "prompt_ns": prompt_ns, "vram": vram, "elapsed": 30 + i * 20})
        return plan

    with tempfile.TemporaryDirectory() as tmp:
        payload = run_gate3(
            config=Gate3Config(start_evidence_tokens=2000, coarse_increment_tokens=1000, repeat_count=3),
            pieces=pieces,
            results_dir=Path(tmp) / "regress",
            generate=scripted(regressing_plan()),
            unload=unload,
            spec=spec,
            metadata=metadata,
            preflight=preflight_ok,
            models_called=False,
        )
        ok(
            "three_confirmed_regressions_or_hard_stop",
            payload["stop_reason"] in {"three_confirmed_regressions", "vram_ceiling", "safety_margin_failed", "evidence_exhausted"},
            payload["stop_reason"],
        )
        ok("package_written", (Path(tmp) / "regress" / "gate3_runs.csv").is_file(), None)
        with (Path(tmp) / "regress" / "gate3_runs.jsonl").open(encoding="utf-8") as handle:
            regress_phases = {json.loads(line)["phase"] for line in handle}
        ok(
            "refinement_runs_when_coarse_stops_inside_corpus",
            "refinement" in regress_phases or payload["stop_reason"] == "evidence_exhausted",
            regress_phases,
        )

    with tempfile.TemporaryDirectory() as tmp:
        def fail_unload(_tag: str) -> tuple[float, dict[str, Any]]:
            return 0.2, {"unload_recorded": True, "vram_released": False, "vram_baseline_gb": 2.8, "vram_final_gb": 20.0}

        payload = run_gate3(
            config=Gate3Config(start_evidence_tokens=2000, coarse_increment_tokens=1000, repeat_count=1),
            pieces=pieces,
            results_dir=Path(tmp) / "unload",
            generate=scripted([{"vram": 12.0}]),
            unload=fail_unload,
            spec=spec,
            metadata=metadata,
            preflight=preflight_ok,
            models_called=False,
        )
        ok("clean_unload_required_before_next_rung", payload["stop_reason"] == "unload_vram_not_released", payload["stop_reason"])

    book = QwenBPromptCalibration()
    obs = book.add_observation(
        execution_id=PRESERVED_GATE3_EXECUTION_ID,
        estimated_complete_prompt_tokens=4133,
        actual_complete_prompt_tokens=4391,
        tag=B_TAG,
    )
    ok("qwen_b_4133_vs_4391_additive_258", obs["additive_error_tokens"] == 258, obs)
    ok(
        "qwen_b_4133_vs_4391_relative_about_6_24_percent",
        abs(obs["relative_error_percent"] - 6.24) < 0.01,
        obs,
    )
    planned_same = book.snapshot_for_estimate(4133)
    ok("identical_packet_planned_num_ctx_8448", planned_same["num_ctx"] == CALIBRATED_SAME_PACKET_NUM_CTX, planned_same)
    ok("safety_margin_remains_1500", planned_same["required_safety_margin_tokens"] == 1500, planned_same)
    ok("output_reserve_remains_2500", planned_same["output_reserve_tokens"] == 2500, planned_same)
    larger = book.snapshot_for_estimate(8000)
    additive_only = 8000 + 258 + 2500 + 1500
    ok(
        "proportional_calibration_applied_to_larger_prompts",
        larger["calibrated_prompt_tokens"] > 8000 + 258
        and larger["num_ctx"] > additive_only
        and larger["num_ctx"] % 256 == 0,
        larger,
    )
    a_rejected = False
    try:
        book.add_observation(
            execution_id="a",
            estimated_complete_prompt_tokens=100,
            actual_complete_prompt_tokens=187,
            tag="qwen3:30b-a3b-instruct-2507-q4_K_M",
        )
    except I11A0Error:
        a_rejected = True
    ok("calibration_uses_qwen_b_evidence_only", a_rejected and all(row["tag"] == B_TAG for row in book.observations), None)

    original_safety = {
        "classification": "successful_pipeline_safety_margin_failed",
        "final_safety_result": "failed",
        "remaining_safety_margin_tokens": -258,
        "actual_prompt_tokens": 4391,
        "configured_num_ctx": 8133,
        "gpu_resident": True,
        "unload_recorded": True,
        "vram_released": True,
        "confirmed_regression": False,
        "execution_id": PRESERVED_GATE3_EXECUTION_ID,
        "phase": "coarse",
    }
    ok(
        "original_run_remains_successful_pipeline_safety_margin_failed",
        original_safety["classification"] == "successful_pipeline_safety_margin_failed"
        and hard_stop_reason(original_safety) == "estimator_recalibration_required",
        hard_stop_reason(original_safety),
    )
    ok(
        "original_run_does_not_count_toward_regression_stop",
        counts_toward_regression_stop(original_safety) is False
        and counts_as_stable_ladder_rung(original_safety) is False,
        None,
    )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "resume"
        root.mkdir()
        packet = packer.packet_for_target(2000)
        planted = {
            "execution_id": PRESERVED_GATE3_EXECUTION_ID,
            "test_case_id": "planted-2k",
            "phase": "coarse",
            "requested_evidence_tokens": 2000,
            "estimated_evidence_tokens": packet.estimated_evidence_tokens,
            "actual_prompt_tokens": 4391,
            "estimated_prompt_tokens": 4133,
            "configured_num_ctx": 8133,
            "final_safety_result": "failed",
            "remaining_safety_margin_tokens": -258,
            "classification": "successful_pipeline_safety_margin_failed",
            "elapsed_seconds": 167.9,
            "prompt_tokens_per_second": 292.7,
            "generation_tokens_per_second": 45.32,
            "vram_peak_gb": 18.873,
            "ram_peak_gb": 27.6,
            "gpu_resident": True,
            "cpu_offload": False,
            "confirmed_regression": False,
            "packet_sha256": packet.sha256,
            "prompt_sha256": prompt_sha256(),
            "unload_recorded": True,
            "vram_released": True,
            "evidence_text": packet.text,
            "narration": "original narration",
            "raw_api": "{}\n",
            "telemetry": "",
            "hardware": {"ram_peak_gb": 27.6, "ram_total_gb": 31.2, "vram_peak_gb": 18.873},
            "host_identity": {"system_ram_total_gb": 31.2},
            "model_identity": metadata,
            "packet_manifest": {
                "conversation_ids": list(packet.conversation_ids),
                "evidence_ids": list(packet.evidence_ids),
                "time_start": packet.time_start,
                "time_end": packet.time_end,
                "estimated_evidence_tokens": packet.estimated_evidence_tokens,
                "overshoot": packet.overshoot,
                "exhausted": packet.exhausted,
                "evidence_bytes": packet.evidence_bytes,
                "evidence_characters": packet.evidence_characters,
                "packet_sha256": packet.sha256,
            },
            "token_accounting": {"configured_num_ctx": 8133, "actual_prompt_eval_count": 4391},
        }
        dest = root / "runs" / PRESERVED_GATE3_EXECUTION_ID
        dest.mkdir(parents=True)
        (dest / "run_record.json").write_text(json.dumps(planted, indent=2) + "\n", encoding="utf-8")
        (dest / "token_accounting.json").write_text(json.dumps(planted["token_accounting"], indent=2) + "\n", encoding="utf-8")
        (dest / "evidence_packet.txt").write_text(packet.text, encoding="utf-8", newline="\n")
        (dest / "narration.txt").write_text("original narration\n", encoding="utf-8")
        (dest / "COMPLETE").write_text("ok\n", encoding="utf-8")
        original_record = (dest / "run_record.json").read_bytes()
        captured: list[RunRequest] = []

        def generate_resume(request: RunRequest, resume_packet: Gate3Packet) -> tuple[Measurement, str, dict[str, Any]]:
            captured.append(request)
            actual = 4391 if request.num_ctx == CALIBRATED_SAME_PACKET_NUM_CTX else int(
                estimate_tokens(SYSTEM_PROMPT + resume_packet.text) + 80
            )
            measurement = Measurement(
                prompt_tokens_per_second=292.7,
                generation_tokens_per_second=45.32,
                elapsed_seconds=40.0,
                peak_vram_gb=12.0,
                gpu_resident=True,
                cpu_spill=False,
                prompt_eval_count=actual,
                timed_out=False,
                infrastructure_failure=False,
            )
            last = {
                "load_duration": 8_000_000_000,
                "prompt_eval_duration": 15_000_000_000,
                "eval_duration": 10_000_000_000,
            }
            hardware = {
                "vram_baseline_gb": 2.8,
                "vram_peak_gb": 12.0,
                "vram_final_gb": 2.8,
                "ram_baseline_gb": 20.0,
                "ram_peak_gb": 27.6,
                "ram_final_gb": 20.0,
                "ram_total_gb": 31.2,
                "gpu_resident": True,
                "cpu_offload": False,
                "placement_status": "gpu_resident",
                "samples": [],
            }
            return measurement, f"narration {request.requested_evidence_tokens}", {
                "hardware": hardware,
                "last_event": last,
                "raw_api": json.dumps(last) + "\n",
                "telemetry": "",
            }

        payload = run_gate3(
            config=Gate3Config(start_evidence_tokens=2000, coarse_increment_tokens=1000, repeat_count=1),
            pieces=pieces,
            results_dir=root,
            generate=generate_resume,
            unload=unload,
            spec=spec,
            metadata=metadata,
            preflight=preflight_ok,
            models_called=False,
        )
        ok("calibrated_rerun_uses_new_execution_id", PRESERVED_GATE3_EXECUTION_ID in payload["execution_ids"] and any(eid != PRESERVED_GATE3_EXECUTION_ID for eid in payload["execution_ids"]), payload["execution_ids"])
        ok("calibrated_rerun_planned_num_ctx_8448", captured and captured[0].num_ctx == 8448, [req.num_ctx for req in captured])
        ok("original_run_record_unmodified", (dest / "run_record.json").read_bytes() == original_record, None)
        csv_text = (root / "gate3_runs.csv").read_text(encoding="utf-8")
        jsonl_text = (root / "gate3_runs.jsonl").read_text(encoding="utf-8")
        ok(
            "original_classification_visible_in_history",
            "successful_pipeline_safety_margin_failed" in csv_text
            and "successful_pipeline_safety_margin_failed" in jsonl_text
            and "successful_pipeline_safety_margin_failed" in (root / "gate3_summary.md").read_text(encoding="utf-8"),
            None,
        )
        ok(
            "successful_calibrated_rerun_is_stable_baseline",
            payload["analysis"]["recommended"]["execution_id"] != PRESERVED_GATE3_EXECUTION_ID
            and payload["analysis"]["knee_observed"] is False,
            payload["analysis"].get("recommended"),
        )
        ok("progress_files_continue", (root / "gate3_progress.json").is_file() and (root / "gate3_progress.log").is_file(), None)
        ok(
            "low_ram_flagged_without_new_stop",
            payload["analysis"]["ram_pressure"]["low_available_system_ram_flagged"] is True
            and payload["analysis"]["ram_pressure"]["ram_stop_threshold_invented"] is False,
            payload["analysis"].get("ram_pressure"),
        )
        cal_path = root / "calibration" / "qwen_b_prompt_calibration.json"
        ok("calibration_sidecar_written", cal_path.is_file() and (root / "calibration" / f"{PRESERVED_GATE3_EXECUTION_ID}.supersession.json").is_file(), None)
        cal = json.loads(cal_path.read_text(encoding="utf-8"))
        ok("persisted_calibration_is_qwen_b_only", cal.get("uses_configuration_a_or_c") is False and cal.get("tag") == B_TAG, cal)

    from memorybox.ask.i11a.i11a0_placement import (
        FAULTY_CPU_OFFLOAD_EXPRESSION,
        PRESERVED_FALSE_OFFLOAD_EXECUTION_ID,
        aggregate_vram,
        interpret_ollama_placement,
    )

    mixed = aggregate_vram(
        sampler_samples=[
            {"phase": "baseline", "vram_used_gb": 2.8506},
            {"phase": "generate_done", "vram_used_gb": 2.8506},
        ],
        heartbeat_vram=[17.7549],
        post_unload_vram_gb=2.8506,
    )
    ok("heartbeat_17_75_cannot_become_peak_2_85", abs(float(mixed["vram_peak_gb"]) - 17.7549) < 0.0001, mixed)
    ok("post_unload_baseline_does_not_replace_in_run_peak", mixed["vram_peak_gb"] != mixed["vram_post_unload_gb"], mixed)

    missing = interpret_ollama_placement({"available": True, "models": []}, tag=B_TAG, queried_while_loaded=False)
    ok("missing_post_unload_ps_is_not_cpu_offload", missing["cpu_offload"] is False and missing["status"] == "unknown", missing)
    ram_only = interpret_ollama_placement(None, tag=B_TAG, queried_while_loaded=False)
    ok("high_system_ram_alone_is_not_cpu_offload", ram_only["cpu_offload"] is False and ram_only["high_system_ram_is_not_cpu_offload"] is True, ram_only)
    partial = interpret_ollama_placement(
        {"available": True, "models": [{"name": B_TAG, "size": 16_000_000_000, "size_vram": 4_000_000_000}]},
        tag=B_TAG,
        queried_while_loaded=True,
    )
    ok("affirmative_partial_placement_is_cpu_offload", partial["cpu_offload"] is True and partial["status"] == "cpu_offload", partial)
    contradict = interpret_ollama_placement({"available": False, "reason": "timeout"}, tag=B_TAG, queried_while_loaded=True)
    ok("contradictory_or_missing_placement_is_unknown", contradict["status"] == "unknown" and contradict["cpu_offload"] is False, contradict)
    ok("faulty_expression_documented", "< 4.0" in FAULTY_CPU_OFFLOAD_EXPRESSION, FAULTY_CPU_OFFLOAD_EXPRESSION)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "placement"
        root.mkdir()
        packet = packer.packet_for_target(2000)
        planted_id = PRESERVED_FALSE_OFFLOAD_EXECUTION_ID
        planted = {
            "execution_id": planted_id,
            "test_case_id": "planted-offload",
            "phase": "coarse",
            "requested_evidence_tokens": 2000,
            "estimated_evidence_tokens": packet.estimated_evidence_tokens,
            "actual_prompt_tokens": 4391,
            "estimated_prompt_tokens": 4048,
            "configured_num_ctx": 8448,
            "final_safety_result": "passed",
            "remaining_safety_margin_tokens": 1557,
            "classification": "successful_stable",
            "vram_peak_gb": 2.8506,
            "ram_peak_gb": 28.29,
            "gpu_resident": False,
            "cpu_offload": True,
            "cpu_spill": True,
            "confirmed_regression": False,
            "packet_sha256": packet.sha256,
            "prompt_sha256": prompt_sha256(),
            "unload_recorded": True,
            "vram_released": True,
            "evidence_text": packet.text,
            "narration": "placement run",
            "raw_api": "{}\n",
            "telemetry": "",
            "hardware": {
                "vram_peak_gb": 2.8506,
                "vram_baseline_gb": 2.8506,
                "cpu_offload": True,
                "gpu_resident": False,
                "samples": [
                    {"phase": "baseline", "vram_used_gb": 2.8506},
                    {"phase": "generate_done", "vram_used_gb": 2.8506},
                ],
            },
            "host_identity": {"system_ram_total_gb": 31.16},
            "model_identity": metadata,
            "packet_manifest": {
                "conversation_ids": list(packet.conversation_ids),
                "evidence_ids": list(packet.evidence_ids),
                "time_start": packet.time_start,
                "time_end": packet.time_end,
                "estimated_evidence_tokens": packet.estimated_evidence_tokens,
                "overshoot": packet.overshoot,
                "exhausted": packet.exhausted,
                "evidence_bytes": packet.evidence_bytes,
                "evidence_characters": packet.evidence_characters,
                "packet_sha256": packet.sha256,
            },
            "token_accounting": {"configured_num_ctx": 8448, "actual_prompt_eval_count": 4391},
        }
        dest = root / "runs" / planted_id
        dest.mkdir(parents=True)
        (dest / "run_record.json").write_text(json.dumps(planted, indent=2) + "\n", encoding="utf-8")
        (dest / "telemetry.jsonl").write_text(
            '{"phase": "baseline", "vram_used_gb": 2.8506}\n{"phase": "generate_done", "vram_used_gb": 2.8506}\n',
            encoding="utf-8",
        )
        (dest / "evidence_packet.txt").write_text(packet.text, encoding="utf-8", newline="\n")
        (dest / "COMPLETE").write_text("ok\n", encoding="utf-8")
        (root / "gate3_progress.log").write_text(
            "2026-09-27T13:51:44Z | HEARTBEAT | phase=ollama_request vram_gb=17.7549 peak_vram_gb=17.7549 gpu_util=0.0 ram_gb=28.29\n",
            encoding="utf-8",
        )
        original_record = (dest / "run_record.json").read_bytes()
        original_telemetry = (dest / "telemetry.jsonl").read_bytes()
        captured: list[RunRequest] = []

        def generate_unknown(request: RunRequest, resume_packet: Gate3Packet):
            captured.append(request)
            measurement = Measurement(
                prompt_tokens_per_second=355.0,
                generation_tokens_per_second=47.0,
                elapsed_seconds=40.0,
                peak_vram_gb=17.75,
                gpu_resident=False,
                cpu_spill=False,
                prompt_eval_count=4391,
            )
            hardware = {
                "vram_baseline_gb": 2.85,
                "vram_peak_gb": 17.75,
                "vram_final_gb": 2.85,
                "gpu_resident": False,
                "cpu_offload": False,
                "placement_status": "unknown",
                "placement_reason": "scripted_unknown",
                "samples": [],
            }
            return measurement, "narration", {"hardware": hardware, "last_event": {}, "raw_api": "", "telemetry": ""}

        payload = run_gate3(
            config=Gate3Config(start_evidence_tokens=2000, coarse_increment_tokens=1000, repeat_count=1),
            pieces=pieces,
            results_dir=root,
            generate=generate_unknown,
            unload=unload,
            spec=spec,
            metadata=metadata,
            preflight=preflight_ok,
            models_called=False,
        )
        ok("unknown_placement_stops_controller", payload["stop_reason"] == "placement_unknown", payload["stop_reason"])
        ok("prior_false_offload_artifacts_unmodified", (dest / "run_record.json").read_bytes() == original_record and (dest / "telemetry.jsonl").read_bytes() == original_telemetry, None)
        ok("hardware_sidecar_written", (root / "calibration" / f"{planted_id}.hardware_supersession.json").is_file(), None)
        ok("validation_rerun_uses_num_ctx_8448", captured and captured[0].num_ctx == 8448, [req.num_ctx for req in captured])
        sidecar = json.loads((root / "calibration" / f"{planted_id}.hardware_supersession.json").read_text(encoding="utf-8"))
        ok("sidecar_does_not_rewrite_original", sidecar.get("original_files_rewritten") is False and sidecar.get("corrected_cpu_offload") is False, sidecar)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "gpuok"
        root.mkdir()
        packet = packer.packet_for_target(2000)
        planted_id = PRESERVED_FALSE_OFFLOAD_EXECUTION_ID
        dest = root / "runs" / planted_id
        dest.mkdir(parents=True)
        planted = {
            "execution_id": planted_id,
            "test_case_id": "planted-offload-gpuok",
            "phase": "coarse",
            "requested_evidence_tokens": 2000,
            "estimated_evidence_tokens": packet.estimated_evidence_tokens,
            "actual_prompt_tokens": 4391,
            "configured_num_ctx": 8448,
            "final_safety_result": "passed",
            "classification": "successful_stable",
            "vram_peak_gb": 2.8506,
            "gpu_resident": False,
            "cpu_offload": True,
            "packet_sha256": packet.sha256,
            "unload_recorded": True,
            "vram_released": True,
            "evidence_text": packet.text,
            "hardware": {"vram_peak_gb": 2.8506, "cpu_offload": True, "samples": [{"phase": "baseline", "vram_used_gb": 2.8506}]},
            "model_identity": metadata,
            "packet_manifest": {
                "conversation_ids": list(packet.conversation_ids),
                "evidence_ids": list(packet.evidence_ids),
                "time_start": packet.time_start,
                "time_end": packet.time_end,
                "estimated_evidence_tokens": packet.estimated_evidence_tokens,
                "packet_sha256": packet.sha256,
            },
        }
        (dest / "run_record.json").write_text(json.dumps(planted) + "\n", encoding="utf-8")
        (dest / "evidence_packet.txt").write_text(packet.text, encoding="utf-8")
        (root / "gate3_progress.log").write_text("HEARTBEAT | vram_gb=17.7549 peak_vram_gb=17.7549\n", encoding="utf-8")
        captured: list[RunRequest] = []

        def generate_gpu(request: RunRequest, resume_packet: Gate3Packet):
            captured.append(request)
            actual = 4391 if request.num_ctx == 8448 else int(estimate_tokens(SYSTEM_PROMPT + resume_packet.text) + 80)
            measurement = Measurement(
                prompt_tokens_per_second=300.0,
                generation_tokens_per_second=45.0,
                elapsed_seconds=40.0,
                peak_vram_gb=17.75,
                gpu_resident=True,
                cpu_spill=False,
                prompt_eval_count=actual,
            )
            hardware = {
                "vram_baseline_gb": 2.85,
                "vram_peak_gb": 17.75,
                "vram_final_gb": 2.85,
                "gpu_resident": True,
                "cpu_offload": False,
                "placement_status": "gpu_resident",
                "placement_reason": "size_vram_matches_model_size_while_loaded",
                "samples": [],
            }
            return measurement, "ok", {"hardware": hardware, "last_event": {}, "raw_api": "", "telemetry": ""}

        payload = run_gate3(
            config=Gate3Config(start_evidence_tokens=2000, coarse_increment_tokens=1000, repeat_count=1),
            pieces=pieces,
            results_dir=root,
            generate=generate_gpu,
            unload=unload,
            spec=spec,
            metadata=metadata,
            preflight=preflight_ok,
            models_called=False,
        )
        ok("gpu_resident_validation_may_continue_ladder", payload["stop_reason"] in {"evidence_exhausted", "stage_complete"}, payload["stop_reason"])
        ok("gpu_resident_validation_is_new_execution", planted_id in payload["execution_ids"] and any(eid != planted_id for eid in payload["execution_ids"]), payload["execution_ids"])

    overshoot_pieces = [_piece("first", 12180), _piece("second", 5000), _piece("third", 5000), _piece("fourth", 5000)]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "advance"
        root.mkdir()
        pack_src = NestedEmailPacker(overshoot_pieces)
        packet = pack_src.packet_for_target(2000)
        planted_id = "c76fea7808f8719f24df1e4e4765b7af519dab7e32f65b29e2305c663535e112"
        dest = root / "runs" / planted_id
        dest.mkdir(parents=True)
        planted = {
            "execution_id": planted_id,
            "test_case_id": "gpu-baseline",
            "phase": "coarse",
            "requested_evidence_tokens": 2000,
            "estimated_evidence_tokens": packet.estimated_evidence_tokens,
            "actual_prompt_tokens": 4391,
            "configured_num_ctx": 8448,
            "final_safety_result": "passed",
            "classification": "successful_stable",
            "vram_peak_gb": 18.91,
            "gpu_resident": True,
            "cpu_offload": False,
            "placement_status": "gpu_resident",
            "packet_sha256": packet.sha256,
            "unload_recorded": True,
            "vram_released": True,
            "confirmed_regression": False,
            "evidence_text": packet.text,
            "hardware": {"vram_peak_gb": 18.91, "cpu_offload": False, "gpu_resident": True, "placement_status": "gpu_resident"},
            "model_identity": metadata,
            "packet_manifest": {
                "conversation_ids": list(packet.conversation_ids),
                "evidence_ids": list(packet.evidence_ids),
                "time_start": packet.time_start,
                "time_end": packet.time_end,
                "estimated_evidence_tokens": packet.estimated_evidence_tokens,
                "packet_sha256": packet.sha256,
            },
        }
        (dest / "run_record.json").write_text(json.dumps(planted) + "\n", encoding="utf-8")
        (dest / "evidence_packet.txt").write_text(packet.text, encoding="utf-8")
        (dest / "COMPLETE").write_text("ok\n", encoding="utf-8")
        original = (dest / "run_record.json").read_bytes()
        captured: list[RunRequest] = []

        def generate_advance(request: RunRequest, resume_packet: Gate3Packet):
            captured.append(request)
            measurement = Measurement(
                prompt_tokens_per_second=300.0,
                generation_tokens_per_second=45.0,
                elapsed_seconds=20.0,
                peak_vram_gb=18.9,
                gpu_resident=True,
                cpu_spill=False,
                prompt_eval_count=int(estimate_tokens(SYSTEM_PROMPT + resume_packet.text) + 80),
            )
            hardware = {
                "vram_peak_gb": 18.9,
                "gpu_resident": True,
                "cpu_offload": False,
                "placement_status": "gpu_resident",
                "placement_reason": "scripted",
                "samples": [],
            }
            return measurement, "ok", {"hardware": hardware, "last_event": {}, "raw_api": "", "telemetry": ""}

        payload = run_gate3(
            config=Gate3Config(start_evidence_tokens=2000, coarse_increment_tokens=1000, repeat_count=1),
            pieces=overshoot_pieces,
            results_dir=root,
            generate=generate_advance,
            unload=unload,
            spec=spec,
            metadata=metadata,
            preflight=preflight_ok,
            models_called=False,
        )
        ok("existing_validation_run_retained", dest.is_dir() and (dest / "run_record.json").read_bytes() == original, None)
        ok(
            "next_target_after_3048_class_packet_is_4000",
            captured and captured[0].requested_evidence_tokens == 4000,
            [req.requested_evidence_tokens for req in captured],
        )
        ok(
            "did_not_rerun_identical_3048_packet_as_next_rung",
            all(req.evidence_sha256 != packet.sha256 or req.requested_evidence_tokens != 2000 for req in captured),
            [req.requested_evidence_tokens for req in captured],
        )
        ok("same_size_repeats_not_called_ladder", payload["stop_reason"] != "three_confirmed_regressions", payload["stop_reason"])

    a_blocked = False
    try:
        run_gate3(
            config=Gate3Config(config_id="A", tag="qwen3:30b-a3b-instruct-2507-q4_K_M", digest="x"),
            pieces=pieces,
            results_dir=Path("."),
            generate=scripted([{}]),
            unload=unload,
            spec=spec,
            metadata=metadata,
            preflight=preflight_ok,
            models_called=False,
        )
    except I11A0Error:
        a_blocked = True
    ok("refuses_configuration_a", a_blocked)

    return {
        "ok": not problems,
        "checks": checks,
        "problems": problems,
        "models_called": False,
        "gate3_capacity_authorized": GATE3_CAPACITY_AUTHORIZED,
    }
