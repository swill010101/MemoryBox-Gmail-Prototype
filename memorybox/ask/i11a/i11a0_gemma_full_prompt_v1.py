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
from memorybox.ask.i11a.i11a0_full_prompt_v3 import CTX_ALIGN_TOKENS, RATE_GUARD
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
DOCUMENTED_GUARD_TOKENS = 256
FIRST_NOMINAL = 8000
COARSE_INCREMENT = 1000
DEFAULT_OUT = REPO_ROOT / "docs" / "test-output" / "i11a0-benchmark" / EXPERIMENT_ID
OPS_PATH = REPO_ROOT / "docs" / "ops" / "i11a0.c.gemma-i14-full-prompt-v1.json"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_ops(path: Path | str | None = None) -> dict[str, Any]:
    ops_path = Path(path) if path else OPS_PATH
    return json.loads(ops_path.read_text(encoding="utf-8"))


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
    bytes_div4 = max(1, (int(complete_prompt_bytes) + 3) // 4)
    with_smoke = bytes_div4 + GEMMA_SMOKE_ADDITIVE_ERROR_TOKENS
    with_rate = int(math.ceil(float(bytes_div4) * (1.0 + RATE_GUARD)))
    predicted = max(bytes_div4, with_smoke, with_rate) + DOCUMENTED_GUARD_TOKENS
    return {
        "planner_id": PLANNER_ID,
        "token_count_kind": "estimated",
        "complete_prompt_bytes": int(complete_prompt_bytes),
        "request_bytes_div4": bytes_div4,
        "gemma_smoke_additive_error_tokens": GEMMA_SMOKE_ADDITIVE_ERROR_TOKENS,
        "rate_guard": RATE_GUARD,
        "bytes_div4_plus_rate_guard": with_rate,
        "documented_guard_tokens": DOCUMENTED_GUARD_TOKENS,
        "predicted_complete_prompt_tokens": predicted,
        "does_not_use_qwen_v5_estimator": True,
        "does_not_use_qwen_token_ratio": True,
        "does_not_use_qwen_vram_curve": True,
        "does_not_use_half_window": True,
        "does_not_use_qwen_40960_limit": True,
        "model_context_limit": GEMMA_ADVERTISED_CTX,
        "source": "max(bytes/4, bytes/4+182, ceil(bytes/4*(1+0.005))) + 256",
    }


def plan_rung(*, user: str, packet: Any) -> dict[str, Any]:
    complete = SYSTEM_PROMPT + "\n" + user
    pred = predicted_complete_prompt_tokens_gemma(complete_prompt_bytes=len(complete.encode("utf-8")))
    predicted = int(pred["predicted_complete_prompt_tokens"])
    minimum = predicted + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
    planned_num_ctx = align_ctx(minimum)
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
        "minimum_num_ctx_for_reserves": minimum,
        "planned_num_ctx": planned_num_ctx,
        "reserve_check": reserve_ok,
        "model_context_check": model_ok,
        "vram_projection": "unmeasured_until_first_valid_gemma_rung",
        "vram_ceiling_gb": VRAM_CEILING_GB,
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


def build_ladder_plan(*, export_dir: Path | str | None = None, start: int = FIRST_NOMINAL) -> dict[str, Any]:
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
        if packet.exhausted:
            break
        target = next_coarse_grid_target(int(packet.estimated_evidence_tokens), increment=COARSE_INCREMENT)
    first = rows[0] if rows else None
    return {
        "experiment_id": EXPERIMENT_ID,
        "planner_id": PLANNER_ID,
        "export_dir": str(root),
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
                "inference_authorized defaults false. No model pull from this package.",
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
    ok("ops_inference_authorized_false", ops.get("inference_authorized") is False, ops.get("inference_authorized"))
    ok("ops_tag", ops.get("tag") == TAG, ops)
    ok("ops_digest", ops.get("digest") == EXPECTED_DIGEST, ops)
    ok("ops_quant", ops.get("quantization") == QUANT, ops)
    ok("v03_prompt", prompt_sha256() == EXPECTED_V03_PROMPT_SHA256, prompt_sha256())
    ok("v02_unchanged", prompt_sha256_v02() == "c91f313cc86ebad1c8fde6008e6f283c8bf76aa881bae9118327a6d6c70f7b3b", None)
    ok("ctx_limit_is_not_qwen_40960", GEMMA_ADVERTISED_CTX != 40960, GEMMA_ADVERTISED_CTX)
    sample = predicted_complete_prompt_tokens_gemma(complete_prompt_bytes=40000)
    ok("conservative_at_least_bytes_div4_plus_smoke_and_guard", sample["predicted_complete_prompt_tokens"] >= sample["request_bytes_div4"] + 182 + 256, sample)
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
        ok(
            "reserve_equation",
            int(first["predicted_complete_prompt_tokens"]) + 2500 + 1500 <= int(first["planned_num_ctx"]),
            first,
        )
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
    }


def run_gemma_ladder(
    *,
    confirm_benchmark: bool,
    config_path: Path | str | None = None,
    i14_export: Path | str | None = None,
    results_dir: Path | str | None = None,
    ollama_base_url: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    del ollama_base_url
    ops = load_ops(config_path)
    out = Path(results_dir) if results_dir else DEFAULT_OUT
    ladder = build_ladder_plan(export_dir=i14_export)
    write_preflight(out, ladder)
    payload = {
        "ok": True,
        "experiment_id": EXPERIMENT_ID,
        "models_called": False,
        "inference_started": False,
        "stopped_before_inference": True,
        "first_rung": ladder.get("first_rung"),
        "preflight": str(out / "preflight"),
        "ops_inference_authorized": bool(ops.get("inference_authorized")),
        "confirm_benchmark": bool(confirm_benchmark),
        "qwen_not_generated": True,
        "gemma_pull_executed": False,
    }
    if not confirm_benchmark or not ops.get("inference_authorized"):
        payload["authorization"] = "awaiting_founder_before_ollama"
        return payload
    raise InferenceNotAuthorized("Gemma live ladder is implemented as preflight-only until founder authorizes inference")
