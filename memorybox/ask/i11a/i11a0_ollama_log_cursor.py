"""Ollama server.log cursor: inspect only bytes appended after a request snapshot.

Does not call Ollama. Does not rewrite run artifacts.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_full_prompt_v3 import KEEP_TOKENS, TRUNC_RE, truncation_limit

DEFAULT_OLLAMA_LOG = Path(r"C:\Users\tomwi\AppData\Local\Ollama\server.log")
LOG_UNVERIFIED = "truncation_log_unverified"
LOG_MISSING = "ollama_log_missing"
LOG_ROTATED = "ollama_log_rotated_or_replaced"
LOG_INACCESSIBLE = "ollama_log_inaccessible"
LOG_AMBIGUOUS = "ollama_log_ambiguous"
INVALID_TRUNCATED = "invalid_truncated_prompt"
COMPLETE_EVALUATED = "complete_prompt_evaluated"
COMPLETE_INFRA = "complete_prompt_evaluated_infrastructure_unload_or_log_verification_failure"

N_TOKENS_RE = re.compile(
    r"n_ctx_slot = (?P<ctx>\d+), n_keep = (?P<keep>\d+), task\.n_tokens = (?P<tokens>\d+)"
)
TRUNCATED_EQ_RE = re.compile(r"truncated = (?P<tr>\d+)")
PROMPT_EVAL_RE = re.compile(
    r"prompt eval time =\s+(?P<ms>[\d.]+)\s+ms\s+/\s+(?P<tok>\d+)\s+tokens"
)
START_RE = re.compile(r"starting llama-server.* -c (?P<c>\d+) -np (?P<np>\d+)")


def default_ollama_log_path() -> Path:
    env = os.environ.get("MEMORYBOX_OLLAMA_SERVER_LOG")
    if env:
        return Path(env)
    unc = Path("//flightsim/FlightSim User/Users/tomwi/AppData/Local/Ollama/server.log")
    if unc.is_file():
        return unc
    return DEFAULT_OLLAMA_LOG


def snapshot_log(*, path: Path | str | None = None, execution_id: str = "", model_tag: str = "", digest: str = "", num_ctx: int | None = None, request_hash: str = "") -> dict[str, Any]:
    log_path = Path(path) if path else default_ollama_log_path()
    utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    identity = {
        "ollama_log_path": str(log_path),
        "execution_id": execution_id,
        "model_tag": model_tag,
        "digest": digest,
        "planned_num_ctx": num_ctx,
        "request_hash": request_hash,
        "request_start_utc": utc,
    }
    try:
        st = log_path.stat()
    except OSError as exc:
        return {
            **identity,
            "available": False,
            "status": LOG_INACCESSIBLE if log_path.exists() else LOG_MISSING,
            "error": f"{type(exc).__name__}:{exc}",
            "byte_offset": None,
            "size_bytes": None,
            "mtime_ns": None,
            "inode_or_file_id": None,
        }
    file_id = f"{getattr(st, 'st_dev', 0)}:{getattr(st, 'st_ino', 0)}:{st.st_mtime_ns}:{st.st_size}"
    return {
        **identity,
        "available": True,
        "status": "snapshot",
        "byte_offset": int(st.st_size),
        "size_bytes": int(st.st_size),
        "mtime_ns": int(st.st_mtime_ns),
        "inode_or_file_id": file_id,
        "path_sha256": hashlib.sha256(str(log_path).encode("utf-8")).hexdigest(),
    }


def read_appended_segment(snapshot: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(snapshot.get("ollama_log_path") or ""))
    prior = snapshot.get("byte_offset")
    prior_id = snapshot.get("inode_or_file_id")
    if not snapshot.get("available") or prior is None:
        return {
            "inspected": False,
            "status": snapshot.get("status") or LOG_MISSING,
            "text": "",
            "bytes_read": 0,
        }
    try:
        st = path.stat()
    except OSError as exc:
        return {
            "inspected": False,
            "status": LOG_INACCESSIBLE,
            "error": f"{type(exc).__name__}:{exc}",
            "text": "",
            "bytes_read": 0,
        }
    new_id = f"{getattr(st, 'st_dev', 0)}:{getattr(st, 'st_ino', 0)}:{st.st_mtime_ns}:{st.st_size}"
    if int(st.st_size) < int(prior):
        return {
            "inspected": False,
            "status": LOG_ROTATED,
            "reason": "size_shrank_below_snapshot_offset",
            "text": "",
            "bytes_read": 0,
            "prior_file_id": prior_id,
            "current_file_id": new_id,
        }
    prior_ino = str(prior_id or "").split(":")[1] if prior_id and ":" in str(prior_id) else "0"
    cur_ino = str(getattr(st, "st_ino", 0))
    if prior_ino not in {"0", ""} and cur_ino not in {"0", ""} and prior_ino != cur_ino:
        return {
            "inspected": False,
            "status": LOG_ROTATED,
            "reason": "inode_or_file_identity_changed",
            "text": "",
            "bytes_read": 0,
            "prior_file_id": prior_id,
            "current_file_id": new_id,
        }
    try:
        with path.open("rb") as handle:
            handle.seek(int(prior))
            blob = handle.read()
    except OSError as exc:
        return {
            "inspected": False,
            "status": LOG_INACCESSIBLE,
            "error": f"{type(exc).__name__}:{exc}",
            "text": "",
            "bytes_read": 0,
        }
    text = blob.decode("utf-8", errors="replace")
    return {
        "inspected": True,
        "status": "appended_segment",
        "text": text,
        "bytes_read": len(blob),
        "no_truncation_claim_allowed": True,
    }


def parse_complete_prompt_evidence(text: str) -> dict[str, Any]:
    trunc_warns = [m.groupdict() | {"raw": m.group(0)} for m in TRUNC_RE.finditer(text)]
    n_token_hits = [m.groupdict() | {"raw": m.group(0)} for m in N_TOKENS_RE.finditer(text)]
    truncated_eq = [m.groupdict() | {"raw": m.group(0)} for m in TRUNCATED_EQ_RE.finditer(text)]
    prompt_evals = [m.groupdict() | {"raw": m.group(0)} for m in PROMPT_EVAL_RE.finditer(text)]
    starts = [m.groupdict() | {"raw": m.group(0)[:240]} for m in START_RE.finditer(text)]
    return {
        "truncating_input_prompt_lines": trunc_warns,
        "n_tokens_hits": n_token_hits,
        "truncated_eq_hits": truncated_eq,
        "prompt_eval_hits": prompt_evals,
        "runner_starts": starts,
    }


def classify_appended_log(
    snapshot: dict[str, Any],
    *,
    num_ctx: int,
    prompt_eval_count: int | None,
    predicted_complete: int | None = None,
    keep: int = KEEP_TOKENS,
) -> dict[str, Any]:
    segment = read_appended_segment(snapshot)
    if not segment.get("inspected"):
        return {
            "passed": False,
            "classification": segment.get("status") or LOG_UNVERIFIED,
            "reason": segment.get("reason") or segment.get("status"),
            "truncation_occurred": None,
            "segment_inspected": False,
            "no_truncation_proven": False,
            "above_half_context_not_automatic_truncation": True,
            "log_cursor": snapshot,
            "segment": {k: v for k, v in segment.items() if k != "text"},
        }
    text = str(segment.get("text") or "")
    verdict = classify_log_segment(
        text,
        num_ctx=num_ctx,
        prompt_eval_count=prompt_eval_count,
        predicted_complete=predicted_complete,
        keep=keep,
    )
    verdict["segment_inspected"] = True
    verdict["log_cursor"] = {k: v for k, v in snapshot.items() if k != "text"}
    verdict["bytes_read"] = segment.get("bytes_read")
    return verdict


def classify_log_segment(
    text: str,
    *,
    num_ctx: int,
    prompt_eval_count: int | None,
    predicted_complete: int | None = None,
    keep: int = KEEP_TOKENS,
) -> dict[str, Any]:
    pec = None if prompt_eval_count is None else int(prompt_eval_count)
    half = truncation_limit(int(num_ctx), keep=keep)
    parsed = parse_complete_prompt_evidence(text)
    warns = parsed["truncating_input_prompt_lines"]
    if len(warns) > 1:
        return {
            "passed": False,
            "classification": LOG_AMBIGUOUS,
            "reason": "multiple_truncating_input_prompt_lines_in_appended_segment",
            "segment_inspected": True,
            "no_truncation_proven": False,
            "truncation_occurred": True,
            "match_count": len(warns),
            "parsed": parsed,
        }
    if len(warns) == 1:
        ev = warns[0]
        return {
            "passed": False,
            "classification": INVALID_TRUNCATED,
            "reason": "truncating_input_prompt",
            "segment_inspected": True,
            "no_truncation_proven": False,
            "truncation_occurred": True,
            "ollama_full_tokenized_prompt": int(ev["prompt"]),
            "truncation_limit": int(ev["limit"]),
            "retained_evaluated_tokens": int(ev["new"]),
            "tokens_discarded": int(ev["prompt"]) - int(ev["new"]),
            "keep_tokens": int(ev["keep"]),
            "parsed": parsed,
        }
    n_hits = [h for h in parsed["n_tokens_hits"] if int(h["ctx"]) == int(num_ctx)]
    if pec is not None:
        n_hits = [h for h in n_hits if int(h["tokens"]) == pec] or n_hits
    zero_trunc = [h for h in parsed["truncated_eq_hits"] if int(h["tr"]) == 0]
    eval_hits = parsed["prompt_eval_hits"]
    if pec is not None:
        eval_hits = [h for h in eval_hits if int(h["tok"]) == pec] or eval_hits
    complete_tokens = None
    if n_hits:
        complete_tokens = int(n_hits[-1]["tokens"])
    elif eval_hits:
        complete_tokens = int(eval_hits[-1]["tok"])
    if complete_tokens is None:
        return {
            "passed": False,
            "classification": LOG_UNVERIFIED,
            "reason": "appended_segment_lacks_prompt_token_evidence",
            "segment_inspected": True,
            "no_truncation_proven": False,
            "truncation_occurred": False,
            "prompt_eval_count": pec,
            "above_half_context_not_automatic_truncation": True,
            "parsed": parsed,
        }
    if pec is not None and int(complete_tokens) != pec:
        return {
            "passed": False,
            "classification": LOG_AMBIGUOUS,
            "reason": "prompt_eval_count_disagrees_with_log_complete_tokens",
            "segment_inspected": True,
            "no_truncation_proven": False,
            "complete_log_tokens": complete_tokens,
            "prompt_eval_count": pec,
            "parsed": parsed,
        }
    tokens = int(complete_tokens)
    if predicted_complete is not None and tokens is not None and int(tokens) > int(predicted_complete):
        envelope = {
            "prediction_envelope_note": "complete_count_exceeds_preflight_prediction; not used to enlarge a ladder",
            "predicted_complete_prompt_tokens": int(predicted_complete),
            "observed_complete_prompt_tokens": int(tokens),
        }
    else:
        envelope = {}
    above_half = tokens is not None and int(tokens) > half
    if not zero_trunc and tokens is not None and int(tokens) > int(num_ctx):
        return {
            "passed": False,
            "classification": INVALID_TRUNCATED,
            "reason": "complete_tokens_exceed_num_ctx_without_truncated_eq",
            "segment_inspected": True,
            "no_truncation_proven": False,
            "parsed": parsed,
        }
    return {
        "passed": True,
        "classification": COMPLETE_EVALUATED,
        "reason": "appended_segment_no_truncating_input_prompt_and_complete_eval_matched",
        "segment_inspected": True,
        "no_truncation_proven": True,
        "truncation_occurred": False,
        "complete_log_tokens": tokens,
        "prompt_eval_count": pec,
        "half_context_retention_limit": half,
        "above_half_context": above_half,
        "above_half_context_not_automatic_truncation": True,
        "truncated_eq_zero": bool(zero_trunc),
        "runner_starts": parsed["runner_starts"],
        **envelope,
        "parsed": parsed,
    }
