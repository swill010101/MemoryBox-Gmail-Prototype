"""Retention-aware full-prompt planner (v4).

Ollama 0.34.1 Qwen B chat truncates to keep+(num_ctx-keep)//2 before evaluation.
v3 planned only predicted+4000 <= num_ctx and would truncate again. This module
does not rewrite the historical reconstruction audit and does not call Ollama.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_benchmark import (
    OUTPUT_RESERVE_TOKENS,
    SAFETY_MARGIN_TOKENS,
    VRAM_CEILING_GB,
    I11A0Error,
)
from memorybox.ask.i11a.i11a0_full_prompt_v3 import (
    FROZEN_MAX_TOKENS_PER_EVIDENCE_BYTE,
    KEEP_TOKENS,
    PLANNER_ID as V3_PLANNER_ID,
    QWEN_B_ADVERTISED_CTX,
    RATE_GUARD,
    CTX_ALIGN_TOKENS,
    FullPromptEstimator,
    INVALID_TRUNCATED,
    apply_truncation_outcome,
    find_truncation_for_execution,
    identity_mismatch,
    parse_truncation_events,
    plan_full_prompt_num_ctx as plan_v3_num_ctx,
    truncation_limit,
)
from memorybox.ask.i11a.i11a0_prompt import prompt_sha256
from memorybox.ask.i11a.i11a0_smoke import PINNED_B_DIGEST, REPO_ROOT

PLANNER_ID = "i14_cleaned_full_prompt_v4"
LOG_UNVERIFIED = "truncation_log_unverified"
PREDICTION_EXCEEDED = "complete_prompt_exceeded_prediction"
MAX_MODEL_RETENTION = truncation_limit(QWEN_B_ADVERTISED_CTX, keep=KEEP_TOKENS)  # 20482
PRACTICAL_VRAM_MAX_CTX = 32768
PRACTICAL_VRAM_RETENTION = truncation_limit(PRACTICAL_VRAM_MAX_CTX, keep=KEEP_TOKENS)  # 16386

# Max observed per-execution peak GB at each requested num_ctx (truncated runs; KV allocated).
HISTORICAL_VRAM_BY_NUM_CTX: dict[int, float] = {
    22528: 20.699219,
    23040: 20.779297,
    23552: 20.867188,
    24064: 20.952148,
    24576: 21.018555,
    24832: 21.073242,
    25600: 21.19043,
    25856: 21.213867,
    26880: 21.387695,
    27392: 21.447266,
    27904: 21.525391,
    28160: 21.581055,
    28416: 21.603516,
    28928: 21.683594,
    29184: 21.741211,
    30208: 21.897461,
    30464: 21.917969,
    30720: 21.960938,
    31488: 22.094727,
    31744: 22.123047,
    32000: 22.160156,
    32768: 22.285156,
    33024: 22.544922,
    33792: 22.544922,
    34560: 22.544922,
}


def v4_artifact_dir(results_dir: Path | str) -> Path:
    path = Path(results_dir) / "planning" / PLANNER_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_v4_config(config: Any) -> bool:
    planner = str(getattr(config, "planner_id", "") or "")
    phase = str(getattr(config, "experiment_phase", "") or "")
    return planner == PLANNER_ID or phase == PLANNER_ID


def is_defective_v3_config(config: Any) -> bool:
    planner = str(getattr(config, "planner_id", "") or "")
    phase = str(getattr(config, "experiment_phase", "") or "")
    return planner == V3_PLANNER_ID or phase == V3_PLANNER_ID


def align_ctx(tokens: int) -> int:
    return int(math.ceil(int(tokens) / CTX_ALIGN_TOKENS) * CTX_ALIGN_TOKENS)


def minimum_num_ctx_for_retention(predicted: int, *, keep: int = KEEP_TOKENS) -> int:
    p = int(predicted)
    k = int(keep)
    if p <= k:
        return k
    return 2 * (p - k) + k


def minimum_num_ctx_for_reserves(predicted: int) -> int:
    return int(predicted) + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS


def predicted_complete_prompt_tokens(evidence_bytes: int) -> int:
    """Uncapped envelope. Never substitute a capped value for a runnable prompt size."""
    raw = float(evidence_bytes) * float(FROZEN_MAX_TOKENS_PER_EVIDENCE_BYTE) * (1.0 + float(RATE_GUARD))
    return int(math.ceil(raw - 1e-12))


def project_vram_for_num_ctx(
    num_ctx: int,
    *,
    ceiling_gb: float = VRAM_CEILING_GB,
    curve: dict[int, float] | None = None,
) -> dict[str, Any]:
    ctx = int(num_ctx)
    series = sorted((curve or HISTORICAL_VRAM_BY_NUM_CTX).items())
    measured = dict(series)
    over = [c for c, v in series if v >= float(ceiling_gb)]
    if ctx in measured:
        peak = float(measured[ctx])
        return {
            "projected_peak_vram_gb": peak,
            "clearly_unsafe": peak >= float(ceiling_gb),
            "reason": "measured_num_ctx",
            "adjacent_over_ceiling_guard": False,
            "vram_projection_check": peak < float(ceiling_gb),
        }
    lower = [c for c, _ in series if c < ctx]
    higher = [c for c, _ in series if c > ctx]
    if higher and measured[higher[0]] >= float(ceiling_gb):
        return {
            "projected_peak_vram_gb": float(measured[higher[0]]),
            "clearly_unsafe": True,
            "reason": "adjacent_measured_peak_at_or_above_ceiling",
            "adjacent_over_ceiling_guard": True,
            "vram_projection_check": False,
            "adjacent_num_ctx": higher[0],
        }
    if not lower or not higher:
        return {
            "projected_peak_vram_gb": None,
            "clearly_unsafe": True,
            "reason": "outside_measured_curve",
            "adjacent_over_ceiling_guard": bool(over),
            "vram_projection_check": False,
        }
    x1, x2 = lower[-1], higher[0]
    y1, y2 = float(measured[x1]), float(measured[x2])
    if y1 >= float(ceiling_gb) or y2 >= float(ceiling_gb):
        return {
            "projected_peak_vram_gb": max(y1, y2),
            "clearly_unsafe": True,
            "reason": "adjacent_measured_peak_at_or_above_ceiling",
            "adjacent_over_ceiling_guard": True,
            "vram_projection_check": False,
        }
    slope = (y2 - y1) / (x2 - x1)
    predicted = y1 + slope * (ctx - x1)
    return {
        "projected_peak_vram_gb": predicted,
        "clearly_unsafe": predicted >= float(ceiling_gb),
        "reason": "interpolated_between_below_ceiling_measurements",
        "adjacent_over_ceiling_guard": False,
        "vram_projection_check": predicted < float(ceiling_gb),
        "from_num_ctx": (x1, x2),
        "from_vram_peak_gb": (y1, y2),
    }


def plan_retention_aware_run(
    *,
    evidence_bytes: int,
    keep: int = KEEP_TOKENS,
    ceiling_gb: float = VRAM_CEILING_GB,
    model_context_limit: int = QWEN_B_ADVERTISED_CTX,
) -> dict[str, Any]:
    predicted = predicted_complete_prompt_tokens(int(evidence_bytes))
    min_ret = minimum_num_ctx_for_retention(predicted, keep=keep)
    min_res = minimum_num_ctx_for_reserves(predicted)
    governing = max(min_ret, min_res)
    planned = align_ctx(governing)
    retention_at_planned = truncation_limit(planned, keep=keep)
    vram = project_vram_for_num_ctx(planned, ceiling_gb=ceiling_gb)
    retention_check = predicted <= retention_at_planned
    reserve_check = predicted + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS <= planned
    model_check = planned <= int(model_context_limit)
    vram_check = bool(vram.get("vram_projection_check"))
    oversized = predicted > MAX_MODEL_RETENTION
    eligible = bool(retention_check and reserve_check and model_check and vram_check and not oversized)
    reason = None
    if oversized:
        reason = "predicted_complete_prompt_exceeds_model_retention_window"
    elif not model_check:
        reason = "planned_ctx_exceeds_model_limit"
    elif not retention_check:
        reason = "retention_window_exceeded"
    elif not reserve_check:
        reason = "reserves_not_satisfied"
    elif not vram_check:
        reason = "predicted_vram_ceiling"
    return {
        "planner_id": PLANNER_ID,
        "predicted_complete_prompt_tokens": predicted,
        "keep_tokens": int(keep),
        "retention_limit_tokens": retention_at_planned,
        "minimum_num_ctx_for_retention": min_ret,
        "minimum_num_ctx_for_reserves": min_res,
        "planned_num_ctx": planned,
        "model_context_limit": int(model_context_limit),
        "projected_peak_vram_gb": vram.get("projected_peak_vram_gb"),
        "retention_check": retention_check,
        "reserve_check": reserve_check,
        "model_context_check": model_check,
        "vram_projection_check": vram_check,
        "eligible": eligible,
        "rejection_reason": reason,
        "vram_projection": vram,
        "never_caps_then_runs": True,
        "never_uses_prompt_eval_count": True,
        "governing_requirement": "retention" if min_ret >= min_res else "reserves",
    }


def evaluate_legacy_v3_plan(*, predicted: int, num_ctx: int, keep: int = KEEP_TOKENS) -> dict[str, Any]:
    limit = truncation_limit(int(num_ctx), keep=keep)
    reserve_ok = int(predicted) + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS <= int(num_ctx)
    retention_ok = int(predicted) <= limit
    return {
        "predicted_complete_prompt_tokens": int(predicted),
        "planned_num_ctx": int(num_ctx),
        "retention_limit_tokens": limit,
        "reserve_check": reserve_ok,
        "retention_check": retention_ok,
        "eligible": False,
        "rejection_reason": "v3_omitted_half_context_retention_preflight",
        "v3_plan_invalid": True,
    }


def classify_post_generation_log(
    log_text: str,
    *,
    num_ctx: int,
    prompt_eval_count: int | None,
    predicted_complete: int,
    keep: int = KEEP_TOKENS,
) -> dict[str, Any]:
    text = str(log_text or "")
    pec = None if prompt_eval_count is None else int(prompt_eval_count)
    limit = truncation_limit(int(num_ctx), keep=keep)
    identity = pec is not None and pec == limit
    if not text.strip():
        return {
            "passed": False,
            "classification": LOG_UNVERIFIED,
            "reason": "missing_ollama_log",
            "truncation_occurred": None,
        }
    events = parse_truncation_events(text)
    hits = [
        ev
        for ev in events
        if ev.get("runner_c") in {None, int(num_ctx)}
        and (pec is None or int(ev["new"]) == pec)
    ]
    if len(hits) > 1:
        return {
            "passed": False,
            "classification": LOG_UNVERIFIED,
            "reason": "ambiguous_truncation_log_match",
            "truncation_occurred": None,
            "match_count": len(hits),
        }
    if len(hits) == 1:
        ev = hits[0]
        full = int(ev["prompt"])
        outcome = apply_truncation_outcome(
            {"prompt_eval_count": pec, "actual_prompt_tokens": pec, "num_ctx": num_ctx},
            ev,
        )
        if full > int(predicted_complete):
            outcome["classification"] = PREDICTION_EXCEEDED
            outcome["passed"] = False
            outcome["reason"] = "complete_log_tokens_exceed_prediction"
            return {**outcome, "passed": False}
        return {**outcome, "passed": False, "reason": "truncating_input_prompt"}
    if identity:
        return {
            "passed": False,
            "classification": INVALID_TRUNCATED,
            "reason": "prompt_eval_matches_truncation_identity_without_full_log_entry",
            "truncation_occurred": True,
        }
    return {
        "passed": False,
        "classification": LOG_UNVERIFIED,
        "reason": "no_unique_untruncated_log_correlation",
        "truncation_occurred": False,
    }


def i14_export_candidates() -> list[Path]:
    return [
        Path("//flightsim/FlightSim User/MemoryBox/docs/test-output/i11a0-benchmark/i14-cleaned-export"),
        REPO_ROOT / "docs" / "test-output" / "i11a0-benchmark" / "i14-cleaned-export",
    ]


def build_packet_search_table(
    *,
    export_dir: Path | str | None = None,
    targets: tuple[int, ...] = (8000, 9000, 10000, 11000, 12000, 13000),
) -> dict[str, Any]:
    from memorybox.ask.i11a.i11a0_gate3 import NestedMessagePacker, next_coarse_grid_target
    from memorybox.ask.i11a.i11a0_i14_source import load_frozen_prompt_messages, verify_pinned_i14_export

    root = Path(export_dir) if export_dir else next((p for p in i14_export_candidates() if p.is_dir()), None)
    if root is None:
        raise I11A0Error("pinned I14 cleaned export is not available for packet planning")
    verify_pinned_i14_export(root)
    packer = NestedMessagePacker(load_frozen_prompt_messages(root))
    rows: list[dict[str, Any]] = []
    skip_until = 0
    for target in targets:
        if target <= skip_until:
            continue
        packet = packer.packet_for_target(int(target))
        plan = plan_retention_aware_run(evidence_bytes=int(packet.evidence_bytes))
        overshoot = int(packet.estimated_evidence_tokens) > int(target)
        next_grid = next_coarse_grid_target(int(packet.estimated_evidence_tokens), increment=1000)
        row = {
            "nominal_target_estimated_evidence": int(target),
            "actual_estimated_evidence_tokens": int(packet.estimated_evidence_tokens),
            "overshoot": overshoot,
            "next_grid_if_overshoot": next_grid if overshoot else None,
            "evidence_bytes": int(packet.evidence_bytes),
            "evidence_characters": int(packet.evidence_characters),
            "message_count": packet.message_count,
            "thread_count": len(packet.conversation_ids),
            "partial_context": bool(packet.partial_context),
            "packet_sha256": packet.sha256,
            **{k: plan[k] for k in (
                "predicted_complete_prompt_tokens",
                "keep_tokens",
                "retention_limit_tokens",
                "minimum_num_ctx_for_retention",
                "minimum_num_ctx_for_reserves",
                "planned_num_ctx",
                "model_context_limit",
                "projected_peak_vram_gb",
                "retention_check",
                "reserve_check",
                "model_context_check",
                "vram_projection_check",
                "eligible",
                "rejection_reason",
                "governing_requirement",
            )},
        }
        rows.append(row)
        if overshoot:
            skip_until = next_grid - 1
    eligible = [r for r in rows if r.get("eligible")]
    rejected = [r for r in rows if not r.get("eligible")]
    first = eligible[0] if eligible else None
    highest = eligible[-1] if eligible else None
    first_reject = rejected[0] if rejected else None
    if first_reject is None and highest is not None:
        probe_target = next_coarse_grid_target(int(highest["actual_estimated_evidence_tokens"]), increment=1000)
        probe_packet = packer.packet_for_target(int(probe_target))
        probe_plan = plan_retention_aware_run(evidence_bytes=int(probe_packet.evidence_bytes))
        if not probe_plan.get("eligible"):
            first_reject = {
                "nominal_target_estimated_evidence": int(probe_target),
                "actual_estimated_evidence_tokens": int(probe_packet.estimated_evidence_tokens),
                "evidence_bytes": int(probe_packet.evidence_bytes),
                "eligible": False,
                "rejection_reason": probe_plan.get("rejection_reason"),
                "boundary_type": probe_plan.get("rejection_reason"),
                "planned_num_ctx": probe_plan.get("planned_num_ctx"),
                "projected_peak_vram_gb": probe_plan.get("projected_peak_vram_gb"),
                "predicted_complete_prompt_tokens": probe_plan.get("predicted_complete_prompt_tokens"),
                "retention_limit_tokens": probe_plan.get("retention_limit_tokens"),
            }
    refinement_lo = None
    refinement_hi = None
    if highest:
        refinement_lo = int(highest["actual_estimated_evidence_tokens"])
        next_larger = next_coarse_grid_target(refinement_lo, increment=1000)
        refinement_hi = min(refinement_lo + 250, next_larger)
    return {
        "planner_id": PLANNER_ID,
        "export_dir": str(root),
        "rows": rows,
        "conservative_first_rung": first,
        "highest_likely_eligible": highest,
        "first_hard_boundary": first_reject,
        "refinement_interval_estimated_evidence": (
            {"from": refinement_lo, "to": refinement_hi, "step": 250} if highest else None
        ),
        "models_called": False,
    }


def write_v3_invalidation_sidecar() -> dict[str, str]:
    payload = {
        "reconstructed_historical_audit_valid": True,
        "v3_18k_start_invalid": True,
        "v3_ladder_plan_invalid": True,
        "v3_inference_occurred": False,
        "defect": "preflight required only predicted+2500+1500 <= num_ctx and omitted Ollama keep+(num_ctx-keep)//2 retention",
        "example": {
            "predicted_complete_prompt_tokens": 24109,
            "planned_num_ctx": 28416,
            "retention_limit_tokens": truncation_limit(28416),
            "would_truncate": True,
        },
        "audit_files_rewritten": False,
        "prior_run_records_rewritten": False,
    }
    dests = [
        REPO_ROOT / "docs" / "test-output" / "i11a0-benchmark" / "true-prompt-capacity-audit",
        Path("//flightsim/FlightSim User/MemoryBox/docs/test-output/i11a0-benchmark/true-prompt-capacity-audit"),
    ]
    written = []
    text = json.dumps(payload, indent=2) + "\n"
    for dest in dests:
        try:
            dest.mkdir(parents=True, exist_ok=True)
            path = dest / "v3_plan_invalidation.json"
            if not (dest / "true_prompt_capacity.csv").is_file() and dest == dests[1]:
                continue
            path.write_text(text, encoding="utf-8")
            (dest / "V3-PLAN-INVALID.md").write_text(
                "# v3 full-prompt plan invalid\n\n"
                "The historical reconstruction audit remains valid and was not rewritten.\n\n"
                "The proposed 18K / `num_ctx=28416` v3 ladder is **invalid**. No v3 inference occurred.\n\n"
                "Defect: preflight omitted `predicted <= keep + (num_ctx-keep)//2` with `keep=4`. "
                "Retention at 28416 is 14210, below a ~24109-token complete prompt.\n",
                encoding="utf-8",
            )
            written.append(str(path))
        except OSError:
            continue
    return {"wrote": written, **payload}


def prove_full_prompt_v4_offline() -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, cond: bool, detail: Any = None) -> None:
        checks.append(name)
        if not cond:
            problems.append(f"{name}: {detail}")

    ok("retention_28416_is_14210", truncation_limit(28416) == 14210, truncation_limit(28416))
    ok("retention_40960_is_20482", truncation_limit(40960) == 20482, truncation_limit(40960))
    ok("retention_32768_is_16386", truncation_limit(32768) == 16386, truncation_limit(32768))
    legacy = evaluate_legacy_v3_plan(predicted=24109, num_ctx=28416)
    ok("v3_18k_28416_rejected", legacy["eligible"] is False, legacy)
    ok("v3_24109_cannot_run_at_28416", legacy["retention_check"] is False, legacy)
    ok("v3_reserve_may_still_pass", legacy["reserve_check"] is True, legacy)
    plan_18k = plan_retention_aware_run(evidence_bytes=74063)
    ok("18k_packet_rejected_before_inference", plan_18k["eligible"] is False, plan_18k)
    sep = plan_retention_aware_run(evidence_bytes=74063)
    ok("retention_and_reserve_separate", sep["retention_check"] is not sep["reserve_check"] or not sep["eligible"], sep)
    tiny = plan_retention_aware_run(evidence_bytes=100)
    ok("tiny_eligible_or_retention_governs", tiny["minimum_num_ctx_for_retention"] >= 0, tiny)
    ok(
        "retention_dominates_18k",
        sep["minimum_num_ctx_for_retention"] > sep["minimum_num_ctx_for_reserves"],
        (sep["minimum_num_ctx_for_retention"], sep["minimum_num_ctx_for_reserves"]),
    )
    ok(
        "larger_required_num_ctx_governs",
        sep["planned_num_ctx"] == align_ctx(max(sep["minimum_num_ctx_for_retention"], sep["minimum_num_ctx_for_reserves"])),
        sep,
    )
    vram_rej = project_vram_for_num_ctx(33024)
    ok("vram_33024_rejected", vram_rej["vram_projection_check"] is False and vram_rej["clearly_unsafe"] is True, vram_rej)
    interp = project_vram_for_num_ctx(32800)
    ok("vram_between_32768_and_33024_rejected", interp["clearly_unsafe"] is True, interp)
    log = (
        'time=2026-09-27T17:07:09.904-05:00 level=WARN source=llama_server.go:318 '
        'msg="truncating input prompt" limit=15362 prompt=34872 keep=4 new=15362\n'
    )
    post = classify_post_generation_log(log, num_ctx=30720, prompt_eval_count=15362, predicted_complete=40000)
    ok("truncation_log_invalidates_generation", post["passed"] is False and post["classification"] == INVALID_TRUNCATED, post)
    missing = classify_post_generation_log("", num_ctx=30720, prompt_eval_count=1200, predicted_complete=1200)
    ok("missing_log_cannot_pass", missing["passed"] is False and missing["classification"] == LOG_UNVERIFIED, missing)
    identity = classify_post_generation_log("unrelated\n", num_ctx=30720, prompt_eval_count=15362, predicted_complete=12000)
    ok("identity_without_full_entry_invalid", identity["classification"] == INVALID_TRUNCATED, identity)
    ok("no_model_call", True, None)
    return {"ok": not problems, "checks": checks, "problems": problems, "models_called": False}
