"""Reserve-equation full-prompt planner (v5).

A2 proved a 24,174-token prompt evaluates at num_ctx=28416 with truncate=false
and shift=false. The v4 half-window preflight is retired.
Live rungs require founder-authorized ops JSON and FlightSim --confirm-benchmark.
This module does not call Ollama from prove.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_benchmark import (
    I11A0Error,
    OUTPUT_RESERVE_TOKENS,
    SAFETY_MARGIN_TOKENS,
    VRAM_CEILING_GB,
)
from memorybox.ask.i11a.i11a0_full_prompt_v3 import (
    CTX_ALIGN_TOKENS,
    FROZEN_MAX_TOKENS_PER_EVIDENCE_BYTE,
    QWEN_B_ADVERTISED_CTX,
    RATE_GUARD,
)
from memorybox.ask.i11a.i11a0_full_prompt_v4 import (
    PLANNER_ID as V4_PLANNER_ID,
    align_ctx,
    i14_export_candidates,
    predicted_complete_prompt_tokens,
    project_vram_for_num_ctx,
)
from memorybox.ask.i11a.i11a0_smoke import PINNED_B_DIGEST, REPO_ROOT

PLANNER_ID = "i14_cleaned_full_prompt_v5"


def v5_artifact_dir(results_dir: Path | str) -> Path:
    path = Path(results_dir) / "planning" / PLANNER_ID
    path.mkdir(parents=True, exist_ok=True)
    return path
A2_EXECUTION_ID = "292642bad1a27cb4bed1e9817ab8658640fc74adc2900a0db74976a935513cf9"
A2_PACKET_SHA256 = "51f891938ba3ab5910fb20ce8fe457dace74bfb5f9b5b380da28a52f24e73902"
A2_OBSERVED_COMPLETE_TOKENS = 24174
A2_DOCUMENTED_PREDICTION = 24109
A2_NUM_CTX = 28416
A2_PEAK_VRAM_GB = 20.2392578125
B_EXECUTION_ID = "4800ee4b3b4a6130fd9c75ccb4e72a301ae7ca4c5997d3985f6f25d57199d8d3"
ESTIMATOR_ABS_TOLERANCE_TOKENS = 80
PACKET_TARGETS_START = 18000
PACKET_TARGETS_STOP_AFTER_INELIGIBLE = 3
COARSE_INCREMENT = 1000
A2_PACKED_EVIDENCE_TOKENS = 18516
A2_EVIDENCE_BYTES = 74063
TWENTY_TWO_K_NOMINAL = 22000
TWENTY_TWO_K_PLANNED_NUM_CTX = 33536
V5_LIVE_RUNGS = (
    {
        "nominal": 19000,
        "packed": 19386,
        "num_ctx": 29440,
        "sha_prefix": "351bb581c725e687",
    },
    {
        "nominal": 20000,
        "packed": 20008,
        "num_ctx": 30208,
        "sha_prefix": "a7c6737d54474cdf",
    },
    {
        "nominal": 21000,
        "packed": 21288,
        "num_ctx": 32000,
        "sha_prefix": "22d951e5e1d676db",
    },
)


def is_v5_config(config: Any) -> bool:
    planner = str(getattr(config, "planner_id", "") or "")
    phase = str(getattr(config, "experiment_phase", "") or "")
    return planner == PLANNER_ID or phase == PLANNER_ID


def is_retired_v4_config(config: Any) -> bool:
    planner = str(getattr(config, "planner_id", "") or "")
    phase = str(getattr(config, "experiment_phase", "") or "")
    return planner == V4_PLANNER_ID or phase == V4_PLANNER_ID


def minimum_num_ctx_for_reserves(predicted: int) -> int:
    return int(predicted) + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS


def estimator_underestimate(*, predicted: int, observed_complete: int) -> bool:
    extra = int(observed_complete) - int(predicted)
    rel = max(ESTIMATOR_ABS_TOLERANCE_TOKENS, int(math.ceil(float(predicted) * RATE_GUARD)))
    return extra > rel


def plan_reserve_aware_run(
    *,
    evidence_bytes: int,
    ceiling_gb: float = VRAM_CEILING_GB,
    model_context_limit: int = QWEN_B_ADVERTISED_CTX,
) -> dict[str, Any]:
    predicted = predicted_complete_prompt_tokens(int(evidence_bytes))
    min_res = minimum_num_ctx_for_reserves(predicted)
    planned = align_ctx(min_res)
    vram = project_vram_for_num_ctx(planned, ceiling_gb=ceiling_gb)
    reserve_check = predicted + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS <= planned
    model_check = planned <= int(model_context_limit)
    vram_check = bool(vram.get("vram_projection_check"))
    eligible = reserve_check and model_check and vram_check
    reason = None
    if not model_check:
        reason = "planned_ctx_exceeds_model_limit"
    elif not reserve_check:
        reason = "reserves_not_satisfied"
    elif not vram_check:
        reason = str(vram.get("reason") or "predicted_vram_ceiling")
    a2_note = None
    if int(evidence_bytes) == 74063:
        a2_note = {
            "first_valid_full_prompt_hardware_measurement": A2_EXECUTION_ID,
            "observed_complete_prompt_tokens": A2_OBSERVED_COMPLETE_TOKENS,
            "measured_peak_vram_gb": A2_PEAK_VRAM_GB,
            "measured_num_ctx": A2_NUM_CTX,
        }
    return {
        "planner_id": PLANNER_ID,
        "planning_equation": "predicted_complete_prompt_tokens + 2500 + 1500 <= num_ctx",
        "half_window_preflight_retired": True,
        "predicted_complete_prompt_tokens": predicted,
        "output_reserve_tokens": OUTPUT_RESERVE_TOKENS,
        "safety_margin_tokens": SAFETY_MARGIN_TOKENS,
        "minimum_num_ctx_for_reserves": min_res,
        "planned_num_ctx": planned,
        "model_context_limit": int(model_context_limit),
        "projected_peak_vram_gb": vram.get("projected_peak_vram_gb"),
        "vram_projection_basis": vram.get("reason"),
        "vram_projection": vram,
        "reserve_check": reserve_check,
        "model_context_check": model_check,
        "vram_projection_check": vram_check,
        "eligible": eligible,
        "rejection_reason": reason,
        "truncate": False,
        "shift": False,
        "post_run_log_verification_required": True,
        "full_gpu_residency_required": True,
        "never_uses_half_window_preflight": True,
        "a2_anchor": a2_note,
        "frozen_rate": FROZEN_MAX_TOKENS_PER_EVIDENCE_BYTE,
        "rate_guard": RATE_GUARD,
        "ctx_align": CTX_ALIGN_TOKENS,
        "historical_truncated_vram_curve_is_not_a_ladder_rung": True,
    }


def build_v5_packet_table(*, export_dir: Path | str | None = None) -> dict[str, Any]:
    from memorybox.ask.i11a.i11a0_gate3 import NestedMessagePacker, next_coarse_grid_target
    from memorybox.ask.i11a.i11a0_i14_source import load_frozen_prompt_messages, verify_pinned_i14_export

    root = Path(export_dir) if export_dir else next((p for p in i14_export_candidates() if p.is_dir()), None)
    if root is None:
        raise I11A0Error("pinned I14 cleaned export is not available for v5 packet planning")
    verify_pinned_i14_export(root)
    packer = NestedMessagePacker(load_frozen_prompt_messages(root))
    rows: list[dict[str, Any]] = []
    target = PACKET_TARGETS_START
    ineligible_streak = 0
    seen: set[str] = set()
    while ineligible_streak < PACKET_TARGETS_STOP_AFTER_INELIGIBLE:
        packet = packer.packet_for_target(int(target))
        if packet.sha256 in seen:
            break
        seen.add(packet.sha256)
        plan = plan_reserve_aware_run(evidence_bytes=int(packet.evidence_bytes))
        overshoot = int(packet.estimated_evidence_tokens) > int(target)
        role = "already_measured_a2" if packet.sha256 == A2_PACKET_SHA256 else "proposed"
        if packet.sha256 == A2_PACKET_SHA256:
            eligibility = "measured_valid_full_prompt_hardware_rung"
            reject = None
        elif plan.get("eligible"):
            eligibility = "eligible_pending_founder_authorization"
            reject = None
        else:
            eligibility = "rejected"
            reject = plan.get("rejection_reason")
        row = {
            "nominal_target_estimated_evidence": int(target),
            "actual_estimated_evidence_tokens": int(packet.estimated_evidence_tokens),
            "overshoot": overshoot,
            "evidence_bytes": int(packet.evidence_bytes),
            "evidence_characters": int(packet.evidence_characters),
            "message_count": packet.message_count,
            "thread_count": len(packet.conversation_ids),
            "partial_context": bool(packet.partial_context),
            "packet_sha256": packet.sha256,
            "predicted_complete_prompt_tokens": plan["predicted_complete_prompt_tokens"],
            "planned_num_ctx": plan["planned_num_ctx"],
            "projected_peak_vram_gb": plan["projected_peak_vram_gb"],
            "vram_projection_basis": plan["vram_projection_basis"],
            "reserve_check": plan["reserve_check"],
            "model_context_check": plan["model_context_check"],
            "vram_projection_check": plan["vram_projection_check"],
            "eligible": plan.get("eligible") if packet.sha256 != A2_PACKET_SHA256 else True,
            "eligibility_or_rejection": eligibility if packet.sha256 == A2_PACKET_SHA256 or plan.get("eligible") else reject,
            "rejection_reason": reject,
            "rung_role": role,
            "truncate": False,
            "shift": False,
        }
        rows.append(row)
        if packet.sha256 != A2_PACKET_SHA256 and not plan.get("eligible"):
            ineligible_streak += 1
        else:
            ineligible_streak = 0
        if packet.exhausted:
            break
        target = next_coarse_grid_target(int(packet.estimated_evidence_tokens), increment=COARSE_INCREMENT)
    eligible = [r for r in rows if r.get("eligible") and r.get("rung_role") != "already_measured_a2"]
    return {
        "planner_id": PLANNER_ID,
        "half_window_preflight_retired": True,
        "planning_equation": "predicted_complete_prompt_tokens + 2500 + 1500 <= num_ctx",
        "num_ctx_max": QWEN_B_ADVERTISED_CTX,
        "vram_ceiling_gb": VRAM_CEILING_GB,
        "a2_first_valid_full_prompt_hardware_measurement": A2_EXECUTION_ID,
        "a2_packet_sha256": A2_PACKET_SHA256,
        "do_not_reuse_truncated_historical_runs": True,
        "ladder_not_executed": True,
        "live_ladder_authorized": False,
        "digest": PINNED_B_DIGEST,
        "rows": rows,
        "next_proposed_live_rung": eligible[0] if eligible else None,
        "export_dir": str(root),
    }


def write_v5_packet_plan(table: dict[str, Any]) -> Path:
    dest = REPO_ROOT / "docs" / "prd" / "p2-i11a0" / "I11A0-FULL-PROMPT-V5-PACKET-PLAN.json"
    dest.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8", newline="\n")
    return dest


def project_valid_full_prompt_vram(
    points: list[tuple[int, float]],
    num_ctx: int,
    *,
    ceiling_gb: float = VRAM_CEILING_GB,
) -> dict[str, Any]:
    """Linear peak-VRAM vs num_ctx from valid full-prompt rungs only."""
    usable = [(int(c), float(v)) for c, v in points if c and v is not None]
    historical = project_vram_for_num_ctx(int(num_ctx), ceiling_gb=ceiling_gb)
    if len(usable) < 2:
        return {
            "ok": False,
            "reason": "need_at_least_two_valid_full_prompt_vram_points",
            "target_num_ctx": int(num_ctx),
            "points": usable,
            "historical_occupancy": historical,
            "conservative_gb": None,
            "below_ceiling": False,
        }
    n = float(len(usable))
    mean_x = sum(p[0] for p in usable) / n
    mean_y = sum(p[1] for p in usable) / n
    var_x = sum((p[0] - mean_x) ** 2 for p in usable)
    if var_x <= 0:
        slope = 0.0
    else:
        slope = sum((p[0] - mean_x) * (p[1] - mean_y) for p in usable) / var_x
    intercept = mean_y - slope * mean_x
    fitted = intercept + slope * float(num_ctx)
    residuals = [p[1] - (intercept + slope * p[0]) for p in usable]
    max_abs = max(abs(r) for r in residuals)
    margin = max(0.20, 1.5 * max_abs)
    conservative = fitted + margin
    return {
        "ok": True,
        "reason": "linear_fit_valid_full_prompt_peaks",
        "target_num_ctx": int(num_ctx),
        "points": [{"num_ctx": c, "peak_vram_gb": v} for c, v in usable],
        "slope_gb_per_ctx": slope,
        "intercept_gb": intercept,
        "fitted_gb": fitted,
        "residual_margin_gb": margin,
        "conservative_gb": conservative,
        "below_ceiling": conservative < float(ceiling_gb),
        "ceiling_gb": float(ceiling_gb),
        "historical_occupancy": historical,
        "historical_is_comparison_only": True,
        "a2_measured_vs_historical_28416": {
            "measured_gb": A2_PEAK_VRAM_GB,
            "historical_gb": 21.603516,
        },
    }


def decide_22k(projection: dict[str, Any], *, ceiling_gb: float = VRAM_CEILING_GB) -> dict[str, Any]:
    conservative = projection.get("conservative_gb")
    if conservative is None or float(conservative) >= float(ceiling_gb):
        return {
            "run_22k": False,
            "classification": "predicted_vram_boundary",
            "stop_reason": "predicted_vram_ceiling",
            "not_a_performance_knee": True,
            "proposed_num_ctx": TWENTY_TWO_K_PLANNED_NUM_CTX,
            "projection": projection,
            "founder_authorization_required_to_run": False,
            "note": "Conservative valid-run projection is at or above 22.5 GB. Do not run 22K.",
        }
    return {
        "run_22k": False,
        "classification": "awaiting_founder_authorization_22k",
        "stop_reason": "founder_review_22k",
        "not_a_performance_knee": True,
        "proposed_num_ctx": TWENTY_TWO_K_PLANNED_NUM_CTX,
        "projection": projection,
        "founder_authorization_required_to_run": True,
        "note": "Valid-run projection is below 22.5 GB. Stop for founder authorization before 22K.",
    }


def imported_a2_rung_row() -> dict[str, Any]:
    return {
        "execution_id": A2_EXECUTION_ID,
        "test_case_id": "imported-a2-first-valid-full-prompt-rung",
        "phase": "imported_a2",
        "requested_evidence_tokens": 18000,
        "estimated_evidence_tokens": A2_PACKED_EVIDENCE_TOKENS,
        "actual_prompt_tokens": A2_OBSERVED_COMPLETE_TOKENS,
        "configured_num_ctx": A2_NUM_CTX,
        "predicted_complete_prompt_tokens": 24233,
        "planned_num_ctx": A2_NUM_CTX,
        "packet_sha256": A2_PACKET_SHA256,
        "classification": "complete_prompt_evaluated",
        "no_truncation_proven": True,
        "truncation_occurred": False,
        "complete_log_tokens": A2_OBSERVED_COMPLETE_TOKENS,
        "prompt_eval_count": A2_OBSERVED_COMPLETE_TOKENS,
        "final_safety_result": "passed",
        "gpu_resident": True,
        "cpu_offload": False,
        "placement_status": "gpu_resident",
        "vram_peak_gb": A2_PEAK_VRAM_GB,
        "vram_baseline_gb": 1.2607421875,
        "vram_final_gb": 1.2607421875,
        "vram_released": True,
        "unload_recorded": True,
        "stable_ladder_rung": True,
        "imported_not_rerun": True,
        "do_not_rerun": True,
        "exclude_from_knee": True,
        "exclude_from_operating_point": False,
        "truncated_historical_run": False,
        "planner_id": PLANNER_ID,
        "truncate": False,
        "shift": False,
        "digest": PINNED_B_DIGEST,
        "tag": "qwen3:14b-q8_0",
        "not_a_performance_knee": True,
        "source_artifact": (
            "docs/test-output/i11a0-benchmark/no-truncation-diagnostic/"
            + A2_EXECUTION_ID
        ),
    }


def prove_full_prompt_v5_offline() -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, cond: bool, detail: Any = None) -> None:
        checks.append(name)
        if not cond:
            problems.append(f"{name}: {detail}")

    plan_18k = plan_reserve_aware_run(evidence_bytes=74063)
    ok("v5_18k_uses_reserve_equation", plan_18k["planned_num_ctx"] == 28416, plan_18k)
    ok("v5_18k_eligible_without_half_window", plan_18k["eligible"] is True, plan_18k)
    ok("v5_never_uses_half_window", plan_18k["never_uses_half_window_preflight"] is True, None)
    ok("v5_predicted_is_formula_not_half_window", plan_18k["predicted_complete_prompt_tokens"] == 24233, plan_18k)
    vram_rej = project_vram_for_num_ctx(33536)
    ok("v5_vram_adjacent_ceiling_rejects", vram_rej["vram_projection_check"] is False, vram_rej)
    over = plan_reserve_aware_run(evidence_bytes=115031)
    ok("v5_ctx_over_40960_rejected", over["eligible"] is False and over["rejection_reason"] == "planned_ctx_exceeds_model_limit", over)
    ok("a2_underestimate_vs_24109_is_65", A2_OBSERVED_COMPLETE_TOKENS - A2_DOCUMENTED_PREDICTION == 65, None)
    ok(
        "formula_prediction_did_not_underestimate_a2",
        estimator_underestimate(predicted=24233, observed_complete=24174) is False,
        None,
    )
    ok(
        "underestimate_stops",
        estimator_underestimate(predicted=24109, observed_complete=25000) is True,
        None,
    )
    from memorybox.ask.i11a.i11a0_gate3 import Gate3Config

    ok("v5_config_detected", is_v5_config(Gate3Config(planner_id=PLANNER_ID)))
    ok("v4_config_is_retired", is_retired_v4_config(Gate3Config(planner_id=V4_PLANNER_ID)))
    try:
        table = build_v5_packet_table()
        write_v5_packet_plan(table)
        first = table["rows"][0]
        ok("v5_table_starts_at_18k_a2_packet", first["packet_sha256"] == A2_PACKET_SHA256, first)
        ok("v5_table_has_next_rung", table.get("next_proposed_live_rung") is not None, table.get("next_proposed_live_rung"))
        ok("v5_planning_table_does_not_execute", table.get("ladder_not_executed") is True, None)
    except I11A0Error as exc:
        ok("v5_table_built", False, str(exc))
    ops = json.loads((REPO_ROOT / "docs" / "ops" / "i11a0_gate3.b.full-prompt-v5.json").read_text(encoding="utf-8"))
    ok("v5_ops_live_authorized", ops.get("live_ladder_authorized") is True and ops.get("start_evidence_tokens") == 19000, ops)
    fit = project_valid_full_prompt_vram([(28416, 20.239), (29440, 20.5)], 32000)
    ok("valid_run_vram_fit_uses_two_points", fit.get("ok") is True and fit.get("historical_is_comparison_only") is True, fit)
    boundary = decide_22k({"conservative_gb": 22.6, "ok": True})
    ok("conservative_22k_is_vram_boundary_not_knee", boundary["classification"] == "predicted_vram_boundary" and boundary["not_a_performance_knee"] is True, boundary)
    wait = decide_22k({"conservative_gb": 21.9, "ok": True})
    ok("sub_ceiling_22k_waits_for_founder", wait["founder_authorization_required_to_run"] is True and wait["run_22k"] is False, wait)
    imported = imported_a2_rung_row()
    ok("a2_import_is_not_a_rerun", imported["do_not_rerun"] is True and imported["execution_id"] == A2_EXECUTION_ID, imported)
    return {"ok": not problems, "checks": checks, "problems": problems, "models_called": False, "ladder_resumed": False}
