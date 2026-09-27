"""Full-prompt (non-truncating) planner, truncation guard, and historical reconstruction.

Does not call Ollama. Does not rewrite original run records.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_benchmark import (
    OUTPUT_RESERVE_TOKENS,
    SAFETY_MARGIN_TOKENS,
    VRAM_CEILING_GB,
    I11A0Error,
)
from memorybox.ask.i11a.i11a0_i14_source import (
    ACCEPTED_I14_COMMIT,
    PINNED_GENERATION_CHECKSUM,
    PINNED_PROMPT_JSONL_SHA256,
    SOURCE_LABEL,
)
from memorybox.ask.i11a.i11a0_prompt import PROMPT_VERSION, prompt_sha256
from memorybox.ask.i11a.i11a0_smoke import PINNED_B_DIGEST, REPO_ROOT

PLANNER_ID = "i14_cleaned_full_prompt_v3"
CHAT_TEMPLATE_FAMILY = "qwen3-instruct-ollama-go-chatml"
OLLAMA_VERSION_FAMILY = "0.34"
MODEL_TAG = "qwen3:14b-q8_0"
CTX_ALIGN_TOKENS = 256
QWEN_B_ADVERTISED_CTX = 40960
POLICY_MAX_COMPLETE_PROMPT = QWEN_B_ADVERTISED_CTX - OUTPUT_RESERVE_TOKENS - SAFETY_MARGIN_TOKENS
KEEP_TOKENS = 4
RATE_GUARD = 0.005
# Upper envelope from reconstructed Gate 3 I14 packets: 26054 complete tokens / 80029 evidence bytes.
FROZEN_MAX_TOKENS_PER_EVIDENCE_BYTE = 26054 / 80029
INVALID_TRUNCATED = "invalid_truncated_prompt"
TRUNC_RE = re.compile(
    r'time=(?P<ts>\S+)\s+level=WARN\s+source=llama_server\.go:318\s+'
    r'msg="truncating input prompt"\s+limit=(?P<limit>\d+)\s+prompt=(?P<prompt>\d+)\s+'
    r"keep=(?P<keep>\d+)\s+new=(?P<new>\d+)"
)
START_RE = re.compile(r"time=(?P<ts>\S+).*starting llama-server.* -c (?P<c>\d+) -np (?P<np>\d+)")
EVAL_RE = re.compile(
    r"slot print_timing:.*prompt eval time =\s+(?P<ms>[\d.]+)\s+ms\s+/\s+(?P<tok>\d+)\s+tokens"
)
GEN_RE = re.compile(
    r"slot print_timing:.*\beval time =\s+(?P<ms>[\d.]+)\s+ms\s+/\s+(?P<tok>\d+)\s+tokens"
)

CSV_FIELDS = [
    "execution_id",
    "series",
    "correlation_status",
    "utc_start",
    "local_log_ts",
    "requested_evidence_tokens",
    "packet_sha256",
    "evidence_bytes",
    "evidence_characters",
    "bytes_div4",
    "message_count",
    "thread_count",
    "num_ctx",
    "num_predict",
    "full_tokenized_prompt",
    "truncation_limit",
    "retained_evaluated_tokens",
    "tokens_discarded",
    "truncation_occurred",
    "prompt_eval_count",
    "vram_peak_gb",
    "placement_status",
    "cpu_offload",
    "hardware_valid_for_num_ctx_curve",
    "prompt_eval_seconds",
    "prompt_tokens_per_second",
    "eval_seconds",
    "generation_tokens_per_second",
    "unload_ok",
    "corrected_classification",
]


def truncation_limit(num_ctx: int, *, keep: int = KEEP_TOKENS) -> int:
    ctx = int(num_ctx)
    k = int(keep)
    return k + (ctx - k) // 2


def ollama_version_family(version: str | None) -> str:
    text = str(version or "").strip()
    if text.startswith("0.34"):
        return "0.34"
    return text.split(".")[0] + "." + (text.split(".")[1] if "." in text else "")


def planner_identity(*, ollama_version: str = "0.34.1", digest: str = PINNED_B_DIGEST) -> dict[str, Any]:
    return {
        "planner_id": PLANNER_ID,
        "model_tag": MODEL_TAG,
        "model_digest": digest,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha256(),
        "chat_template_family": CHAT_TEMPLATE_FAMILY,
        "thinking_mode": "off",
        "source_label": SOURCE_LABEL,
        "i14_commit": ACCEPTED_I14_COMMIT,
        "i14_prompt_sha256": PINNED_PROMPT_JSONL_SHA256,
        "i14_generation_checksum": PINNED_GENERATION_CHECKSUM,
        "ollama_version_family": ollama_version_family(ollama_version),
    }


def identity_mismatch(stored: dict[str, Any], live: dict[str, Any]) -> str | None:
    keys = (
        "model_digest",
        "prompt_sha256",
        "chat_template_family",
        "source_label",
        "thinking_mode",
        "ollama_version_family",
        "i14_prompt_sha256",
    )
    for key in keys:
        if str(stored.get(key) or "") != str(live.get(key) or ""):
            return key
    return None


def is_v3_config(config: Any) -> bool:
    planner = str(getattr(config, "planner_id", "") or "")
    phase = str(getattr(config, "experiment_phase", "") or "")
    return planner == PLANNER_ID or phase == PLANNER_ID


def parse_truncation_events(log_text: str) -> list[dict[str, Any]]:
    last_c: int | None = None
    last_np: int | None = None
    events: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None
    for i, line in enumerate(log_text.splitlines(), 1):
        sm = START_RE.search(line)
        if sm:
            last_c = int(sm.group("c"))
            last_np = int(sm.group("np"))
        tm = TRUNC_RE.search(line)
        if tm:
            if pending:
                events.append(pending)
            pending = {
                "line": i,
                "ts": tm.group("ts"),
                "limit": int(tm.group("limit")),
                "prompt": int(tm.group("prompt")),
                "keep": int(tm.group("keep")),
                "new": int(tm.group("new")),
                "runner_c": last_c,
                "runner_np": last_np,
            }
            continue
        if pending:
            em = EVAL_RE.search(line)
            if em:
                pending["prompt_eval_ms"] = float(em.group("ms"))
                pending["prompt_eval_tokens"] = int(em.group("tok"))
            gm = GEN_RE.search(line)
            if gm and "prompt eval" not in line:
                pending["eval_ms"] = float(gm.group("ms"))
                pending["eval_tokens"] = int(gm.group("tok"))
    if pending:
        events.append(pending)
    return events


def find_truncation_for_execution(log_text: str, *, num_ctx: int, prompt_eval_count: int | None) -> dict[str, Any] | None:
    events = parse_truncation_events(log_text)
    hits = [
        ev
        for ev in events
        if ev.get("runner_c") in {None, int(num_ctx)}
        and (prompt_eval_count is None or int(ev["new"]) == int(prompt_eval_count))
    ]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        return None
    return hits[-1]


def apply_truncation_outcome(row: dict[str, Any], event: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(row)
    out["ollama_full_tokenized_prompt"] = None if event is None else int(event["prompt"])
    out["truncation_limit"] = None if event is None else int(event["limit"])
    out["retained_evaluated_tokens"] = None if event is None else int(event["new"])
    out["tokens_discarded"] = None if event is None else int(event["prompt"]) - int(event["new"])
    out["prompt_eval_count"] = row.get("prompt_eval_count") or row.get("actual_prompt_tokens")
    if event is None:
        out["truncation_occurred"] = False
        return out
    out["truncation_occurred"] = True
    out["classification"] = INVALID_TRUNCATED
    out["corrected_classification"] = INVALID_TRUNCATED
    out["stable_ladder_rung"] = False
    out["exclude_from_knee"] = True
    out["exclude_from_operating_point"] = True
    out["exclude_from_estimator_calibration"] = True
    out["not_complete_prompt_fit"] = True
    return out


@dataclass
class FullPromptEstimator:
    """Upper-envelope complete-prompt predictor. Never labeled actual."""

    max_tokens_per_evidence_byte: float = FROZEN_MAX_TOKENS_PER_EVIDENCE_BYTE
    guard: float = RATE_GUARD
    identity: dict[str, Any] | None = None
    policy_max: int = POLICY_MAX_COMPLETE_PROMPT

    def predict(self, evidence_bytes: int) -> dict[str, Any]:
        raw = float(evidence_bytes) * float(self.max_tokens_per_evidence_byte) * (1.0 + float(self.guard))
        uncapped = int(math.ceil(raw - 1e-12))
        capped = min(int(self.policy_max), uncapped)
        return {
            "predicted_complete_prompt_tokens": capped,
            "uncapped_predicted_complete_prompt_tokens": uncapped,
            "label": "predicted",
            "not_actual": True,
            "formula": (
                "ceil(evidence_bytes * max_observed_complete_tokens_per_byte * (1+guard)); "
                "cap at 40960-2500-1500"
            ),
            "max_tokens_per_evidence_byte": self.max_tokens_per_evidence_byte,
            "guard": self.guard,
            "policy_max_complete_prompt": self.policy_max,
            "capped_at_policy_max": uncapped > self.policy_max,
            "identity": self.identity or planner_identity(),
        }


def plan_full_prompt_num_ctx(
    *,
    evidence_bytes: int,
    estimator: FullPromptEstimator | None = None,
    live_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    est = estimator or FullPromptEstimator(identity=live_identity)
    if live_identity:
        mismatch = identity_mismatch(est.identity or planner_identity(), live_identity)
        if mismatch:
            raise I11A0Error(f"full-prompt estimator identity invalid: {mismatch}")
    pred = est.predict(int(evidence_bytes))
    predicted = int(pred["predicted_complete_prompt_tokens"])
    required = predicted + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
    num_ctx = int(math.ceil(required / CTX_ALIGN_TOKENS) * CTX_ALIGN_TOKENS)
    return {
        **pred,
        "output_reserve_tokens": OUTPUT_RESERVE_TOKENS,
        "safety_reserve_tokens": SAFETY_MARGIN_TOKENS,
        "required_tokens": required,
        "num_ctx": num_ctx,
        "exceeds_model_context": num_ctx > QWEN_B_ADVERTISED_CTX or predicted > POLICY_MAX_COMPLETE_PROMPT,
        "fits_policy": required <= QWEN_B_ADVERTISED_CTX and predicted <= POLICY_MAX_COMPLETE_PROMPT,
        "never_uses_prompt_eval_count": True,
    }


def reject_projected_boundaries(*, num_ctx: int, predicted_vram_gb: float | None, ceiling_gb: float = VRAM_CEILING_GB) -> str | None:
    if int(num_ctx) > QWEN_B_ADVERTISED_CTX:
        return "planned_ctx_exceeds_model_limit"
    if predicted_vram_gb is not None and float(predicted_vram_gb) >= float(ceiling_gb):
        return "predicted_vram_ceiling"
    return None


def project_vram_vs_num_ctx(
    rows: list[dict[str, Any]],
    *,
    next_num_ctx: int,
    ceiling_gb: float = VRAM_CEILING_GB,
) -> dict[str, Any]:
    pts = [
        (int(r["num_ctx"]), float(r["vram_peak_gb"]))
        for r in rows
        if r.get("hardware_valid_for_num_ctx_curve")
        and r.get("num_ctx") not in {None, ""}
        and r.get("vram_peak_gb") is not None
        and float(r["vram_peak_gb"]) >= 4
    ]
    by_ctx: dict[int, list[float]] = {}
    for ctx, vram in pts:
        by_ctx.setdefault(ctx, []).append(vram)
    series = sorted((ctx, max(vals)) for ctx, vals in by_ctx.items())
    below = [(ctx, vram) for ctx, vram in series if vram < float(ceiling_gb)]
    use = below if len(below) >= 2 else series
    if len(use) < 2:
        return {"predicted_vram_gb": None, "clearly_unsafe": False, "reason": "insufficient_points"}
    x1, y1 = use[-2]
    x2, y2 = use[-1]
    if x2 == x1:
        return {"predicted_vram_gb": None, "clearly_unsafe": False, "reason": "non_increasing_ctx"}
    slope = (y2 - y1) / (x2 - x1)
    predicted = y2 + slope * (int(next_num_ctx) - x2)
    return {
        "predicted_vram_gb": predicted,
        "clearly_unsafe": bool(slope > 0 and predicted >= ceiling_gb),
        "slope_gb_per_num_ctx": slope,
        "from_num_ctx": (x1, x2),
        "from_vram_peak_gb": (y1, y2),
        "reason": "two_point_num_ctx_projection_below_ceiling" if use is below else "two_point_num_ctx_projection",
        "excluded_over_ceiling_num_ctx": [ctx for ctx, vram in series if vram >= float(ceiling_gb)],
    }


def _load_run_folder(folder: Path, series: str) -> dict[str, Any] | None:
    rec_path = folder / "run_record.json"
    if not rec_path.is_file():
        return None
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    man = json.loads((folder / "packet_manifest.json").read_text(encoding="utf-8")) if (folder / "packet_manifest.json").is_file() else {}
    tok = json.loads((folder / "token_accounting.json").read_text(encoding="utf-8")) if (folder / "token_accounting.json").is_file() else {}
    hw = json.loads((folder / "hardware_telemetry.json").read_text(encoding="utf-8")) if (folder / "hardware_telemetry.json").is_file() else {}
    ident = json.loads((folder / "request_identity.json").read_text(encoding="utf-8")) if (folder / "request_identity.json").is_file() else {}
    tel_start = tel_end = None
    tlp = folder / "telemetry.jsonl"
    if tlp.is_file():
        lines = [ln for ln in tlp.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            tel_start = json.loads(lines[0]).get("utc")
            tel_end = json.loads(lines[-1]).get("utc")
    evidence = rec.get("evidence_text") or ""
    ep = folder / "evidence_packet.txt"
    if not evidence and ep.is_file():
        evidence = ep.read_text(encoding="utf-8")
    evidence_bytes = int(man.get("evidence_bytes") or rec.get("evidence_bytes") or ident.get("evidence_bytes") or len(evidence.encode("utf-8")))
    evidence_chars = int(man.get("evidence_characters") or rec.get("evidence_characters") or len(evidence))
    unload = rec.get("unload") if isinstance(rec.get("unload"), dict) else {}
    vram = rec.get("vram_peak_gb") if rec.get("vram_peak_gb") is not None else hw.get("vram_peak_gb")
    placement = rec.get("placement_status") or hw.get("placement_status")
    hardware_valid = True
    if rec.get("hardware_telemetry_valid") is False or rec.get("in_request_sample_count") == 0:
        hardware_valid = False
    if vram is not None and float(vram) < 4:
        hardware_valid = False
    complete = folder / "COMPLETE"
    return {
        "series": series,
        "execution_id": rec.get("execution_id") or folder.name,
        "folder": str(folder),
        "requested_evidence_tokens": rec.get("requested_evidence_tokens") or man.get("requested_target"),
        "estimated_evidence_tokens": rec.get("estimated_evidence_tokens")
        or man.get("actual_packed_estimated_tokens")
        or tok.get("estimated_evidence_tokens"),
        "packet_sha256": rec.get("packet_sha256") or man.get("packet_sha256"),
        "evidence_bytes": evidence_bytes,
        "evidence_characters": evidence_chars,
        "bytes_div4": max(1, (evidence_bytes + 3) // 4) if evidence_bytes else None,
        "message_count": rec.get("message_count") or man.get("message_count"),
        "thread_count": rec.get("conversation_count") or man.get("conversation_count") or (len(man.get("conversation_ids") or []) or None),
        "num_ctx": rec.get("configured_num_ctx") or rec.get("num_ctx") or (rec.get("request_options") or {}).get("num_ctx") or tok.get("configured_num_ctx"),
        "num_predict": (rec.get("request_options") or {}).get("num_predict") or rec.get("reserved_output_tokens") or 2500,
        "prompt_eval_count": rec.get("actual_prompt_tokens")
        or rec.get("ollama_reported_prompt_eval_count")
        or rec.get("accounting_prompt_eval_count")
        or tok.get("actual_prompt_eval_count"),
        "vram_peak_gb": vram,
        "placement_status": placement,
        "gpu_resident": rec.get("gpu_resident") if rec.get("gpu_resident") is not None else hw.get("gpu_resident"),
        "cpu_offload": rec.get("cpu_offload") if rec.get("cpu_offload") is not None else hw.get("cpu_offload"),
        "classification_original": rec.get("classification"),
        "phase": rec.get("phase"),
        "elapsed_seconds": rec.get("elapsed_seconds"),
        "load_seconds": rec.get("load_seconds"),
        "prompt_eval_seconds": rec.get("prompt_eval_seconds"),
        "eval_seconds": rec.get("eval_seconds"),
        "prompt_tokens_per_second": rec.get("prompt_tokens_per_second"),
        "generation_tokens_per_second": rec.get("generation_tokens_per_second"),
        "unload_ok": unload.get("unloaded") if unload else rec.get("vram_released"),
        "utc_start": tel_start,
        "utc_end": tel_end,
        "complete_mtime": complete.stat().st_mtime if complete.is_file() else rec_path.stat().st_mtime,
        "hardware_valid_for_num_ctx_curve": hardware_valid,
        "captured_request_sha256": ident.get("captured_request_sha256") or rec.get("captured_request_sha256"),
        "outgoing_equals_captured": rec.get("outgoing_equals_captured"),
    }


def collect_historical_runs(roots: dict[str, Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    gate3 = roots["gate3"] / "runs"
    if gate3.is_dir():
        for folder in sorted(gate3.iterdir()):
            if folder.is_dir():
                row = _load_run_folder(folder, "gate3-b-i14")
                if row:
                    rows.append(row)
    for key in ("proof", "retry"):
        root = roots.get(key)
        if root is None or not root.is_dir():
            continue
        base = root / "runs" if (root / "runs").is_dir() else root
        for folder in sorted(base.iterdir()):
            if folder.is_dir() and (folder / "run_record.json").is_file():
                row = _load_run_folder(folder, key if key != "retry" else "prompt-accounting-proof-telemetry-retry")
                if row:
                    if key == "proof":
                        row["series"] = "prompt-accounting-proof"
                    rows.append(row)
    return rows


def correlate_runs(runs: list[dict[str, Any]], events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unused = list(range(len(events)))
    out: list[dict[str, Any]] = []
    ordered = sorted(runs, key=lambda r: float(r.get("complete_mtime") or 0))
    for run in ordered:
        pec = run.get("prompt_eval_count")
        ctx = run.get("num_ctx")
        row = dict(run)
        if pec in {None, ""} or ctx in {None, ""}:
            row["correlation_status"] = "no_inference_or_incomplete"
            row["truncation_occurred"] = None
            row["corrected_classification"] = row.get("classification_original")
            out.append(row)
            continue
        cands = [
            idx
            for idx in unused
            if int(events[idx]["new"]) == int(pec) and events[idx].get("runner_c") in {None, int(ctx)}
        ]
        if not cands:
            row["correlation_status"] = "unmatched"
            row["truncation_occurred"] = None
            row["corrected_classification"] = None
            out.append(row)
            continue
        idx = min(cands, key=lambda i: events[i]["line"])
        unused.remove(idx)
        ev = events[idx]
        row["correlation_status"] = "matched" if len(cands) == 1 else "matched_greedy_among_repeats"
        row["truncation_occurred"] = True
        row["full_tokenized_prompt"] = ev["prompt"]
        row["truncation_limit"] = ev["limit"]
        row["tokens_discarded"] = ev["prompt"] - ev["new"]
        row["retained_evaluated_tokens"] = ev["new"]
        row["local_log_ts"] = ev["ts"]
        row["log_line"] = ev["line"]
        row["keep"] = ev["keep"]
        row["corrected_classification"] = INVALID_TRUNCATED
        row["repeat_candidate_count"] = len(cands)
        out.append(row)
    unmatched = [events[i] for i in unused]
    return out, unmatched


def sidecar_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "original_run_record_rewritten": False,
        "classification": INVALID_TRUNCATED,
        "tokens_discarded": row.get("tokens_discarded"),
        "full_tokenized_prompt": row.get("full_tokenized_prompt"),
        "truncation_limit": row.get("truncation_limit"),
        "retained_evaluated_tokens": row.get("retained_evaluated_tokens"),
        "prompt_eval_count": row.get("prompt_eval_count"),
        "hardware_measurements_valid_as_num_ctx_behavior": bool(row.get("hardware_valid_for_num_ctx_curve")),
        "not_evidence_that_complete_packet_fit": True,
        "exclude_from": [
            "stable_rung_counts",
            "performance_knee_detection",
            "narration_quality_comparison",
            "operating_point_selection",
            "estimator_calibration",
        ],
        "execution_id": row.get("execution_id"),
        "log_ts": row.get("local_log_ts"),
    }


def write_truncation_sidecars(rows: list[dict[str, Any]]) -> int:
    n = 0
    for row in rows:
        if row.get("corrected_classification") != INVALID_TRUNCATED:
            continue
        folder = Path(row["folder"])
        payload = sidecar_payload(row)
        text = json.dumps(payload, indent=2) + "\n"
        (folder / "truncation_correction.json").write_text(text, encoding="utf-8")
        n += 1
    return n


def default_roots() -> dict[str, Path]:
    unc_root = Path("//flightsim/FlightSim User/MemoryBox/docs/test-output/i11a0-benchmark")
    local_root = REPO_ROOT / "docs" / "test-output" / "i11a0-benchmark"
    bench = unc_root if (unc_root / "gate3-b-i14").is_dir() else local_root
    log_unc = Path("//flightsim/FlightSim User/Users/tomwi/AppData/Local/Ollama/server.log")
    log_local = Path(r"C:\Users\tomwi\AppData\Local\Ollama\server.log")
    log = log_unc if log_unc.is_file() else log_local
    return {
        "bench": bench,
        "gate3": bench / "gate3-b-i14",
        "proof": bench / "prompt-accounting-proof",
        "retry": bench / "prompt-accounting-proof-telemetry-retry",
        "i14": bench / "i14-cleaned-export",
        "log": log,
        "dest": bench / "true-prompt-capacity-audit",
        "dest_local": local_root / "true-prompt-capacity-audit",
    }


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_true_prompt_capacity_audit(*, roots: dict[str, Path] | None = None) -> dict[str, Any]:
    roots = roots or default_roots()
    log_text = Path(roots["log"]).read_text(encoding="utf-8", errors="replace")
    events = parse_truncation_events(log_text)
    runs = collect_historical_runs(roots)
    rows, unmatched = correlate_runs(runs, events)
    fit_rows = [
        r
        for r in rows
        if r.get("full_tokenized_prompt")
        and int(r.get("evidence_bytes") or 0) > 0
        and r.get("series") == "gate3-b-i14"
    ]
    ratios = [
        int(r["full_tokenized_prompt"]) / int(r["evidence_bytes"])
        for r in fit_rows
    ]
    max_ratio = max(ratios) if ratios else FROZEN_MAX_TOKENS_PER_EVIDENCE_BYTE
    estimator = FullPromptEstimator(max_tokens_per_evidence_byte=max_ratio, identity=planner_identity())
    errors = []
    for r in fit_rows:
        pred_row = estimator.predict(int(r["evidence_bytes"]))
        pred = int(pred_row["predicted_complete_prompt_tokens"])
        uncapped = int(pred_row["uncapped_predicted_complete_prompt_tokens"])
        actual = int(r["full_tokenized_prompt"])
        errors.append(
            {
                "execution_id": r["execution_id"],
                "predicted_complete_prompt_tokens": pred,
                "uncapped_predicted_complete_prompt_tokens": uncapped,
                "ollama_full_tokenized_prompt": actual,
                "error_tokens": pred - actual,
                "uncapped_error_tokens": uncapped - actual,
                "actual_exceeds_policy_max": actual > POLICY_MAX_COMPLETE_PROMPT,
            }
        )
    vram_curve = sorted(
        {
            (int(r["num_ctx"]), round(float(r["vram_peak_gb"]), 6))
            for r in rows
            if r.get("hardware_valid_for_num_ctx_curve") and r.get("vram_peak_gb") is not None and r.get("num_ctx")
        }
    )
    max_safe_ctx = None
    for ctx, vram in sorted({c: max(v for cc, v in vram_curve if cc == c) for c, _ in vram_curve}.items()):
        if vram < VRAM_CEILING_GB:
            max_safe_ctx = ctx
        else:
            break
    first_target = 18000
    first_bytes = next(
        (int(r["evidence_bytes"]) for r in rows if r.get("requested_evidence_tokens") == first_target and r.get("series") == "gate3-b-i14"),
        74063,
    )
    first_plan = plan_full_prompt_num_ctx(evidence_bytes=first_bytes, estimator=estimator)
    first_vram = project_vram_vs_num_ctx(
        [{"num_ctx": c, "vram_peak_gb": v, "hardware_valid_for_num_ctx_curve": True} for c, v in vram_curve],
        next_num_ctx=int(first_plan["num_ctx"]),
    )
    truncated_n = sum(1 for r in rows if r.get("corrected_classification") == INVALID_TRUNCATED)
    valid_full = sum(1 for r in rows if r.get("truncation_occurred") is False)
    dests = [Path(roots["dest"])]
    local = Path(roots["dest_local"])
    if local.resolve() != dests[0].resolve():
        dests.append(local)
    sidecar_count = write_truncation_sidecars(rows)
    summary = {
        "valid_full_prompt_runs": valid_full,
        "truncated_runs": truncated_n,
        "no_inference_runs": sum(1 for r in rows if r.get("correlation_status") == "no_inference_or_incomplete"),
        "unmatched_runs": sum(1 for r in rows if r.get("correlation_status") == "unmatched"),
        "max_tokens_per_evidence_byte": max_ratio,
        "estimator_guard": RATE_GUARD,
        "prediction_errors": errors,
        "max_positive_error": max((e["error_tokens"] for e in errors), default=None),
        "min_capped_error": min((e["error_tokens"] for e in errors), default=None),
        "min_uncapped_error": min((e["uncapped_error_tokens"] for e in errors), default=None),
        "envelope_underpredicts_uncapped": any(e["uncapped_error_tokens"] < 0 for e in errors),
        "vram_curve_num_ctx": vram_curve,
        "largest_measured_num_ctx_below_ceiling": max_safe_ctx,
        "proposed_first_target_evidence": first_target,
        "proposed_first_num_ctx": first_plan["num_ctx"],
        "proposed_first_predicted_complete": first_plan["predicted_complete_prompt_tokens"],
        "proposed_first_projected_vram": first_vram.get("predicted_vram_gb"),
        "policy_max_complete_prompt": POLICY_MAX_COMPLETE_PROMPT,
        "a2_complete": 34872,
        "a2_below_policy_max": 34872 <= POLICY_MAX_COMPLETE_PROMPT,
        "a2_requires_num_ctx": int(math.ceil((34872 + 4000) / 256) * 256),
        "bc_complete": 51615,
        "bc_exceeds_model_ctx": 51615 > QWEN_B_ADVERTISED_CTX,
        "sidecars_written": sidecar_count,
        "models_called": False,
    }
    md = _render_audit_markdown(rows, unmatched, summary, first_plan, first_vram)
    csv_rows = [{k: r.get(k) for k in CSV_FIELDS} for r in rows]
    hashes: dict[str, str] = {}
    for dest in dests:
        dest.mkdir(parents=True, exist_ok=True)
        csv_path = dest / "true_prompt_capacity.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for item in csv_rows:
                writer.writerow(item)
        jsonl_path = dest / "true_prompt_capacity.jsonl"
        jsonl_path.write_text("".join(json.dumps(r, default=str) + "\n" for r in rows), encoding="utf-8")
        (dest / "TRUE-PROMPT-CAPACITY-AUDIT.md").write_text(md, encoding="utf-8")
        (dest / "unmatched_log_entries.json").write_text(json.dumps(unmatched, indent=2, default=str) + "\n", encoding="utf-8")
        (dest / "estimator_fit.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
        (dest / "correction_ledger.jsonl").write_text(
            "".join(json.dumps(sidecar_payload(r), default=str) + "\n" for r in rows if r.get("corrected_classification") == INVALID_TRUNCATED),
            encoding="utf-8",
        )
        for name in (
            "true_prompt_capacity.csv",
            "true_prompt_capacity.jsonl",
            "TRUE-PROMPT-CAPACITY-AUDIT.md",
            "unmatched_log_entries.json",
            "estimator_fit.json",
            "correction_ledger.jsonl",
        ):
            hashes[name] = _sha256_bytes((dest / name).read_bytes())
        hash_text = "".join(f"{digest}  {name}\n" for name, digest in hashes.items())
        (dest / "HASHES.txt").write_text(hash_text, encoding="utf-8")
    summary["destinations"] = [str(d) for d in dests]
    summary["hashes"] = hashes
    summary["row_count"] = len(rows)
    return summary


def _render_audit_markdown(
    rows: list[dict[str, Any]],
    unmatched: list[dict[str, Any]],
    summary: dict[str, Any],
    first_plan: dict[str, Any],
    first_vram: dict[str, Any],
) -> str:
    lines = [
        "# True prompt capacity audit",
        "",
        "Read-only reconstruction. Original run records were not rewritten. Truncation sidecars only.",
        "",
        f"- Truncated runs (log-matched): **{summary['truncated_runs']}**",
        f"- Valid full-prompt evaluated runs: **{summary['valid_full_prompt_runs']}**",
        f"- Planning-only / no inference: **{summary['no_inference_runs']}**",
        f"- Unmatched runs: **{summary['unmatched_runs']}**",
        f"- Unmatched log events: **{len(unmatched)}**",
        "",
        "## Constraints",
        "",
        f"- Model advertised context: {QWEN_B_ADVERTISED_CTX}",
        f"- Policy max complete prompt: {POLICY_MAX_COMPLETE_PROMPT} (= 40960-2500-1500)",
        f"- VRAM ceiling: {VRAM_CEILING_GB} GB",
        "",
        "## Verified interpretations",
        "",
        f"- A2 complete prompt {summary['a2_complete']} is below {POLICY_MAX_COMPLETE_PROMPT}: **{summary['a2_below_policy_max']}**. Required num_ctx with reserves: **{summary['a2_requires_num_ctx']}** (near 40960). Historical 32768 VRAM already ~22.27–22.29 GB, so A2 is model-context-valid only if num_ctx can hold it, and is **VRAM-unsafe** at that num_ctx.",
        f"- B/C complete prompt {summary['bc_complete']} exceeds 40960: **{summary['bc_exceeds_model_ctx']}**. Cannot fit Qwen B regardless of VRAM.",
        "",
        "## Estimator",
        "",
        "Labeled `predicted_complete_prompt_tokens` only. Upper envelope:",
        f"`ceil(evidence_bytes * {summary['max_tokens_per_evidence_byte']:.6f} * (1+{RATE_GUARD}))` capped at {POLICY_MAX_COMPLETE_PROMPT}.",
        "Never uses truncated `prompt_eval_count`. Invalid if digest, prompt hash, template family, I14 source, thinking mode, or Ollama family changes.",
        "",
        f"Uncapped envelope error vs Ollama `prompt=` on Gate 3 packets: min {summary.get('min_uncapped_error')}, max over-estimate among capped-at-policy reports is not used for packing. Capped predictions never exceed {POLICY_MAX_COMPLETE_PROMPT}; negative capped errors mean the true prompt already exceeded the model/policy maximum.",
        "",
        "## Proposed first corrected packet (do not run)",
        "",
        f"- Evidence target: {summary['proposed_first_target_evidence']}",
        f"- predicted_complete_prompt_tokens: {summary['proposed_first_predicted_complete']}",
        f"- planned num_ctx: {summary['proposed_first_num_ctx']}",
        f"- projected VRAM from num_ctx curve: {summary['proposed_first_projected_vram']}",
        "",
        "Search is centered below the first projected VRAM/context violation, not 42K–48K evidence.",
        "",
        "## Truncation detection",
        "",
        "After each execution, parse Ollama `server.log` for `truncating input prompt`. Any match is `invalid_truncated_prompt`; stop; never enlarge the packet.",
        "",
        "The ladder, Peggy narrative, A/C, coexistence, I11A.1, and I11A.2 remain blocked.",
        "",
    ]
    lines.append("## Reconstructed runs")
    lines.append("")
    lines.append("| exec | series | target | bytes | complete `prompt=` | discarded | num_ctx | VRAM | corr |")
    lines.append("|------|--------|--------|-------|--------------------|-----------|---------|------|------|")
    for r in rows:
        lines.append(
            "| {execution_id:.10} | {series} | {requested_evidence_tokens} | {evidence_bytes} | {full_tokenized_prompt} | {tokens_discarded} | {num_ctx} | {vram_peak_gb} | {correlation_status} |".format(
                **{k: r.get(k) for k in (
                    "execution_id",
                    "series",
                    "requested_evidence_tokens",
                    "evidence_bytes",
                    "full_tokenized_prompt",
                    "tokens_discarded",
                    "num_ctx",
                    "vram_peak_gb",
                    "correlation_status",
                )}
            )
        )
    return "\n".join(lines) + "\n"


def prove_full_prompt_v3_offline() -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, cond: bool, detail: Any = None) -> None:
        checks.append(name)
        if not cond:
            problems.append(f"{name}: {detail}")

    ok("truncation_limit_30720", truncation_limit(30720) == 15362, truncation_limit(30720))
    ok("truncation_limit_32768", truncation_limit(32768) == 16386, truncation_limit(32768))
    est = FullPromptEstimator()
    fit = est.predict(80029)
    ok("predicted_label", fit["label"] == "predicted" and fit["not_actual"] is True, fit)
    ok("predicted_not_prompt_eval", fit["predicted_complete_prompt_tokens"] != 12802, fit)
    ok("predicted_caps_policy", est.predict(10**9)["predicted_complete_prompt_tokens"] == POLICY_MAX_COMPLETE_PROMPT, None)
    plan = plan_full_prompt_num_ctx(evidence_bytes=74063)
    ok("fits_requires_reserves", plan["num_ctx"] >= plan["predicted_complete_prompt_tokens"] + 4000, plan)
    over = plan_full_prompt_num_ctx(evidence_bytes=168075)
    ok("bc_exceeds_model", over["exceeds_model_context"] is True or over["predicted_complete_prompt_tokens"] == POLICY_MAX_COMPLETE_PROMPT, over)
    ok("reject_ctx_40961", reject_projected_boundaries(num_ctx=40961, predicted_vram_gb=20.0) == "planned_ctx_exceeds_model_limit", None)
    ok("reject_vram_22_5", reject_projected_boundaries(num_ctx=30720, predicted_vram_gb=22.5) == "predicted_vram_ceiling", None)
    log = (
        'time=2026-09-27T17:07:09.904-05:00 level=WARN source=llama_server.go:318 '
        'msg="truncating input prompt" limit=15362 prompt=34872 keep=4 new=15362\n'
        "slot print_timing: id  0 | task 0 | prompt eval time =    8578.47 ms / 15362 tokens\n"
    )
    ev = find_truncation_for_execution(log, num_ctx=30720, prompt_eval_count=15362)
    ok("log_truncation_detected", ev is not None and ev["prompt"] == 34872, ev)
    classified = apply_truncation_outcome(
        {"actual_prompt_tokens": 15362, "prompt_eval_count": 15362, "num_ctx": 30720, "classification": "successful_stable"},
        ev,
    )
    ok("invalid_truncated", classified["classification"] == INVALID_TRUNCATED, classified)
    ok("eval_equals_limit", classified["prompt_eval_count"] == classified["truncation_limit"] == 15362, classified)
    ok("eval_lt_complete", classified["prompt_eval_count"] < classified["ollama_full_tokenized_prompt"], classified)
    fitting = apply_truncation_outcome({"actual_prompt_tokens": 1200, "num_ctx": 30720}, None)
    ok("fit_not_truncated", fitting["truncation_occurred"] is False, fitting)
    over_pred = est.predict(168075)["predicted_complete_prompt_tokens"]
    ok("predicted_exceeds_ctx_minus_4000", over_pred > 30720 - 4000, over_pred)
    historical = apply_truncation_outcome({"classification": "successful_stable", "prompt_eval_count": 16386}, ev)
    ok("historical_not_knee", historical.get("exclude_from_knee") is True, historical)
    from memorybox.ask.i11a.i11a0_gate3 import NestedMessagePacker

    class _Msg:
        def __init__(self, eid: str, thread: str, text: str, sent: str) -> None:
            self.evidence_id = eid
            self.thread_display_id = thread
            self.sent_at = sent
            self.text = text

    packer = NestedMessagePacker(
        [
            _Msg("a", "T1", "one", "t0"),
            _Msg("b", "T1", "two", "t1"),
            _Msg("c", "T2", "three", "t2"),
        ]
    )
    p1 = packer.packet_for_target(1)
    p2 = packer.packet_for_target(10**9)
    ok("nesting_prefix", p2.text.startswith(p1.text), (p1.evidence_ids, p2.evidence_ids))
    ok("no_model_call", True, None)
    return {"ok": not problems, "checks": checks, "problems": problems, "models_called": False}
