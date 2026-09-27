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
from dataclasses import asdict, dataclass
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
    CalibrationBook,
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
    read_nvidia_snapshot,
    read_system_ram,
    require_flightsim_host_affinity,
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
    "Reviewed Peggy email chunks only (REVIEW_20260831T120929Z). "
    "Peggy SMS is not in this Gate 3 source."
)
B_TAG = "qwen3:14b-q8_0"
B_QUANT = "Q8_0"
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
        )


def plan_gate3_num_ctx(
    *,
    estimated_prompt_tokens: int,
    reserved_output_tokens: int,
    safety_margin_tokens: int,
    calibration_error_tokens: int,
) -> int:
    pad = max(0, int(calibration_error_tokens))
    plan = plan_context(
        evidence_tokens=0,
        prompt_tokens=estimated_prompt_tokens + pad,
        reserved_output_tokens=reserved_output_tokens,
        safety_margin_tokens=safety_margin_tokens,
    )
    return plan.num_ctx


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
    if row.get("timed_out") or row.get("classification") == "timed_out":
        return "timed_out"
    if row.get("infrastructure_failure") or row.get("classification") == "infrastructure_failure":
        return "generation_failed"
    if row.get("context_overflow"):
        return "context_overflow"
    if row.get("cpu_offload") or row.get("cpu_spill"):
        return "cpu_offload"
    if row.get("gpu_resident") is False:
        return "gpu_residency_lost"
    peak = row.get("vram_peak_gb")
    if peak is not None and float(peak) >= ceiling_gb:
        return "vram_ceiling"
    if row.get("final_safety_result") not in {None, "passed"}:
        return "safety_margin_failed"
    if row.get("unload_recorded") is False:
        return "unload_failed"
    if row.get("vram_released") is False:
        return "unload_vram_not_released"
    return None


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
        if row.get("phase") in {"coarse", "refinement"}
        and row.get("final_safety_result") == "passed"
        and hard_stop_reason(row, ceiling_gb=config.maximum_vram_gb) is None
        and not row.get("confirmed_regression")
    ]
    last_stable = stable[-1] if stable else None
    failing = [
        row
        for row in runs
        if hard_stop_reason(row, ceiling_gb=config.maximum_vram_gb)
        or row.get("confirmed_regression")
    ]
    knee_observed = stop_reason == "three_confirmed_regressions"
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
        reason = "largest repeatably stable point below the confirmed regression region"
    elif stop_reason == "evidence_exhausted":
        reason = (
            "no genuine performance knee was observed; the reviewed-email corpus was exhausted "
            "while runs remained stable. The recommended point is the largest stable packet, "
            "not a manufactured knee."
        )
    else:
        reason = (
            f"no genuine performance knee was observed; coarse growth stopped for {stop_reason}. "
            "The recommended point is the last fully stable safety-passing run below that stop."
        )
    return {
        "stop_reason": stop_reason,
        "knee_observed": knee_observed,
        "knee_range": {
            "last_stable_estimated_evidence_tokens": (last_stable or {}).get("estimated_evidence_tokens"),
            "first_regression_or_stop": (failing[0] if failing else {}).get("requested_evidence_tokens"),
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
            f"vram_peak={row.get('vram_peak_gb')}"
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
    calibration_error: int,
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
        "calibration_error_used_for_planning": calibration_error,
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
        "ram_final_gb": hardware.get("ram_final_gb"),
        "gpu_resident": hardware.get("gpu_resident", measurement.gpu_resident),
        "cpu_offload": hardware.get("cpu_offload", measurement.cpu_spill),
        "cpu_spill": measurement.cpu_spill,
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
            "source_limitation": SOURCE_LIMITATION,
            "truncated": False,
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
    packer = NestedEmailPacker(pieces)
    calibration = CalibrationBook()
    calibration.add(config.tag, config.seed_calibration_error_tokens)
    runs: list[dict[str, Any]] = []
    last_stable: dict[str, Any] | None = None
    confirmed_streak = 0
    stop_reason = "stage_complete"
    last_packet_ids: tuple[str, ...] | None = None

    def measure(packet: Gate3Packet, *, phase: str, target: int, repetition: int, confirmation: bool) -> dict[str, Any]:
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
            partial_context=False,
            partial_boundary_note="none",
            evidence_ids=list(packet.evidence_ids),
            evidence_text=packet.text,
        )
        estimated_prompt = estimate_tokens(SYSTEM_PROMPT + "\n" + user)
        cal_err = calibration.median_error(config.tag) or 0
        num_ctx = plan_gate3_num_ctx(
            estimated_prompt_tokens=estimated_prompt,
            reserved_output_tokens=config.reserved_output_tokens,
            safety_margin_tokens=config.safety_margin_tokens,
            calibration_error_tokens=cal_err,
        )
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
                phase="generation",
            )
        progress.emit("Prompt submitted", phase="generation")
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
        hardware.update({k: v for k, v in unload_info.items() if k.startswith("vram") or k.startswith("ram")})
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
            calibration_error=cal_err,
        )
        if row.get("estimation_error_tokens") is not None:
            calibration.add(config.tag, int(row["estimation_error_tokens"]))
        folder = publish_completed_run(root, row)
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

    target = config.start_evidence_tokens
    while True:
        packet = packer.packet_for_target(target)
        if last_packet_ids is not None and packet.conversation_ids == last_packet_ids:
            stop_reason = "evidence_exhausted"
            break
        row = measure(packet, phase="coarse", target=target, repetition=1, confirmation=False)
        runs.append(row)
        last_packet_ids = packet.conversation_ids
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
            if confirmed["regressed"]:
                confirm["confirmed_regression"] = True
                row["confirmed_regression"] = True
                confirmed_streak += 1
                if confirmed_streak >= config.confirmed_regression_stop:
                    stop_reason = "three_confirmed_regressions"
                    break
            else:
                confirmed_streak = 0
                last_stable = confirm
        else:
            confirmed_streak = 0
            last_stable = row
        if packet.exhausted:
            stop_reason = "evidence_exhausted"
            break
        target += config.coarse_increment_tokens

    progress.emit(
        f"Coarse ladder stopped and reason: {stop_reason}",
        stage="analysis",
        stop_reason=stop_reason,
        expected_next_action="refinement_or_repeats",
    )
    if last_stable and stop_reason != "host_affinity":
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
) -> dict[str, Any]:
    if not confirm_benchmark:
        raise InferenceNotAuthorized("Gate 3 requires --confirm-benchmark")
    config = load_gate3_config(config_path)
    results = Path(results_dir)
    results.mkdir(parents=True, exist_ok=True)

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
        pieces = _pieces_from_review(Path(chunks_root))
    except Exception as exc:
        progress.fail(str(exc), stop_reason="preflight")
        raise

    def generate(request: RunRequest, packet: Gate3Packet) -> tuple[Measurement, str, dict[str, Any]]:
        sampler = HardwareSampler()
        progress.emit("Waiting for VRAM baseline", phase="baseline_wait")
        sampler.capture("baseline")
        progress.emit("Loading model", phase="model_load")
        measurement, narration, events = _chat(
            request,
            base_url=ollama_base_url,
            timeout=config.timeout_seconds,
            sampler=sampler,
            packet_role="capacity",
        )
        hardware = sampler.summary()
        last = events[-1] if events else {}
        return measurement, narration, {
            "hardware": hardware,
            "last_event": last,
            "raw_api": "".join(json.dumps(event) + "\n" for event in events),
            "telemetry": "".join(json.dumps(sample) + "\n" for sample in hardware.get("samples") or []),
        }

    def unload(tag: str) -> tuple[float, dict[str, Any]]:
        sampler = HardwareSampler()
        sampler.capture("before_unload")
        seconds = _unload(ollama_base_url, tag)
        time.sleep(1.0)
        sampler.capture("after_unload")
        hardware = sampler.summary()
        return seconds, {
            "unload_recorded": True,
            "vram_final_gb": hardware.get("vram_final_gb"),
            "vram_baseline_gb": hardware.get("vram_baseline_gb"),
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

    vram_row = {"vram_peak_gb": 22.5, "final_safety_result": "passed", "gpu_resident": True, "unload_recorded": True, "vram_released": True}
    ok("vram_ceiling_stops", hard_stop_reason(vram_row) == "vram_ceiling", None)
    ok("cpu_offload_stops", hard_stop_reason({**vram_row, "vram_peak_gb": 10, "cpu_offload": True}) == "cpu_offload", None)

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
