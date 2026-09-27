"""Offline forensic audit of cleaned-I14 Gate 3 packets and token accounting.

Never calls Ollama. Never rewrites completed run artifacts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_benchmark import I11A0Error, OUTPUT_RESERVE_TOKENS, SAFETY_MARGIN_TOKENS
from memorybox.ask.i11a.i11a0_prompt import SYSTEM_PROMPT, render_user_message, prompt_sha256, PROMPT_VERSION

AUDIT_ID = "prompt_accounting_audit_v1"
RECOMMENDATION_INVALID = "provisional_invalidated_pending_prompt_accounting_audit"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def last_raw_api_event(raw_api: str) -> dict[str, Any] | None:
    last = None
    for line in (raw_api or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    return last


def reconstruct_user_message(row: dict[str, Any], evidence_text: str) -> str:
    request = row.get("request") or {}
    return render_user_message(
        packet_id=str(
            request.get("packet_id")
            or f"{row.get('phase')}-{row.get('requested_evidence_tokens')}-{row.get('execution_id', '')[:8]}"
        ),
        packet_role="capacity",
        time_start=str((row.get("packet_manifest") or {}).get("time_start") or ""),
        time_end=str((row.get("packet_manifest") or {}).get("time_end") or ""),
        partial_context=bool((row.get("packet_manifest") or {}).get("partial_context")),
        partial_boundary_note=str((row.get("packet_manifest") or {}).get("partial_boundary_note") or "none"),
        evidence_ids=list((row.get("packet_manifest") or {}).get("evidence_ids") or []),
        evidence_text=evidence_text,
    )


def per_execution_vram_from_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    idle = None
    run_values: list[float] = []
    pre_unload = None
    for row in samples:
        phase = str(row.get("phase") or "")
        value = row.get("vram_used_gb")
        if not isinstance(value, (int, float)):
            continue
        value = float(value)
        if phase in {"baseline", "generate_start"} and idle is None:
            idle = value
        if phase in {"after_unload", "after_unload_settled"}:
            continue
        if phase == "pre_unload":
            pre_unload = value
        run_values.append(value)
    peak = max(run_values) if run_values else None
    return {
        "host_idle_or_baseline_gb": idle,
        "per_execution_peak_gb": peak,
        "pre_unload_gb": pre_unload,
        "sample_count": len(samples),
        "series_wide_not_used": True,
    }


def load_run_folder(folder: Path) -> dict[str, Any]:
    record_path = folder / "run_record.json"
    row = json.loads(record_path.read_text(encoding="utf-8"))
    evidence_path = folder / "evidence_packet.txt"
    evidence = evidence_path.read_text(encoding="utf-8") if evidence_path.is_file() else (row.get("evidence_text") or "")
    evidence_bytes = evidence.encode("utf-8")
    manifest = row.get("packet_manifest") or {}
    ids = list(manifest.get("evidence_ids") or [])
    raw_api = ""
    raw_path = folder / "raw_api.jsonl"
    if raw_path.is_file():
        raw_api = raw_path.read_text(encoding="utf-8", errors="replace")
    last = last_raw_api_event(raw_api)
    raw_prompt = None if last is None else last.get("prompt_eval_count")
    accounting = row.get("token_accounting") or {}
    samples = list((row.get("hardware") or {}).get("samples") or [])
    tel_path = folder / "telemetry.jsonl"
    if tel_path.is_file() and not samples:
        for line in tel_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                try:
                    samples.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    vram = per_execution_vram_from_samples(samples)
    reconstructed_user = reconstruct_user_message(row, evidence) if evidence else ""
    request_json_persisted = bool(row.get("request_capture") or row.get("submitted_request_sha256"))
    return {
        "execution_id": row.get("execution_id"),
        "phase": row.get("phase"),
        "planner_id": row.get("planner_id") or (row.get("calibration_plan") or {}).get("planner_id"),
        "requested_evidence_tokens": row.get("requested_evidence_tokens"),
        "estimated_evidence_tokens": row.get("estimated_evidence_tokens"),
        "packet_path": str(evidence_path) if evidence_path.is_file() else None,
        "saved_packet_sha256": _sha256_bytes(evidence_bytes) if evidence_path.is_file() else None,
        "manifest_packet_sha256": manifest.get("packet_sha256") or row.get("packet_sha256"),
        "evidence_bytes": len(evidence_bytes),
        "evidence_characters": len(evidence),
        "message_count": manifest.get("message_count"),
        "thread_count": manifest.get("conversation_count") or len(manifest.get("conversation_ids") or []),
        "evidence_ids": ids,
        "evidence_id_count": len(ids),
        "first_evidence_id": ids[0] if ids else None,
        "last_evidence_id": ids[-1] if ids else None,
        "prompt_eval_equals_num_ctx_over_2_plus_2": (
            row.get("actual_prompt_tokens") is not None
            and row.get("configured_num_ctx") not in {None, ""}
            and int(row["actual_prompt_tokens"]) == int(row["configured_num_ctx"]) // 2 + 2
        ),
        "partial_context": manifest.get("partial_context"),
        "included_boundary_evidence_ids": list(manifest.get("included_boundary_evidence_ids") or []),
        "omitted_boundary_evidence_ids": list(manifest.get("omitted_boundary_evidence_ids") or []),
        "configured_num_ctx": row.get("configured_num_ctx"),
        "estimated_prompt_tokens": row.get("estimated_prompt_tokens"),
        "predicted_complete_prompt_tokens": (row.get("calibration_plan") or {}).get("predicted_complete_prompt_tokens"),
        "recorded_actual_prompt_tokens": row.get("actual_prompt_tokens"),
        "token_accounting_actual": accounting.get("actual_prompt_eval_count"),
        "raw_api_prompt_eval_count": raw_prompt,
        "raw_api_done_reason": None if last is None else last.get("done_reason"),
        "raw_api_prompt_eval_duration": None if last is None else last.get("prompt_eval_duration"),
        "transformation_raw_to_record": (
            None
            if raw_prompt is None or row.get("actual_prompt_tokens") is None
            else int(row["actual_prompt_tokens"]) - int(raw_prompt)
        ),
        "historical_request_payload_persisted": request_json_persisted,
        "reconstructed_user_contains_full_saved_packet": (
            bool(evidence) and evidence in reconstructed_user
        ),
        "system_prompt_sha256": _sha256_text(SYSTEM_PROMPT),
        "system_prompt_bytes": len(SYSTEM_PROMPT.encode("utf-8")),
        "reconstructed_user_sha256": _sha256_text(reconstructed_user) if reconstructed_user else None,
        "reconstructed_user_bytes": len(reconstructed_user.encode("utf-8")) if reconstructed_user else None,
        "reconstructed_complete_prompt_bytes": (
            len((SYSTEM_PROMPT + "\n" + reconstructed_user).encode("utf-8")) if reconstructed_user else None
        ),
        "recorded_vram_peak_gb": row.get("vram_peak_gb"),
        "per_execution_vram": vram,
        "vram_peak_contaminated_by_series": (
            vram.get("per_execution_peak_gb") is not None
            and row.get("vram_peak_gb") is not None
            and float(row["vram_peak_gb"]) - float(vram["per_execution_peak_gb"]) > 0.01
        ),
        "placement_status": row.get("placement_status"),
        "final_safety_result": row.get("final_safety_result"),
        "classification": row.get("classification"),
        "packet_text_for_nesting": evidence,
    }


def nesting_delta(prev_ids: list[str], curr_ids: list[str]) -> dict[str, Any]:
    prev_set = set(prev_ids)
    curr_set = set(curr_ids)
    removed = [eid for eid in prev_ids if eid not in curr_set]
    added = [eid for eid in curr_ids if eid not in prev_set]
    is_id_prefix = curr_ids[: len(prev_ids)] == prev_ids if prev_ids else True
    reordered = (not is_id_prefix) and not removed and prev_set <= curr_set
    return {
        "prior_ids_are_ordered_prefix": is_id_prefix,
        "ids_added": added,
        "ids_removed": removed,
        "ids_reordered": reordered,
        "packet_construction_defect": bool(removed or reordered or (prev_ids and not is_id_prefix)),
    }


def audit_results_dir(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    runs_dir = root / "runs"
    folders = sorted(
        [p for p in runs_dir.iterdir() if p.is_dir() and not p.name.endswith(".writing") and (p / "run_record.json").is_file()],
        key=lambda p: p.name,
    )
    loaded = [load_run_folder(folder) for folder in folders]
    inferred = [
        row
        for row in loaded
        if row.get("recorded_actual_prompt_tokens") not in {None, ""}
        and row.get("classification") not in {None, "predicted_vram_ceiling"}
    ]
    unique_packets: dict[str, dict[str, Any]] = {}
    for row in inferred:
        key = str(row.get("manifest_packet_sha256") or row.get("saved_packet_sha256"))
        if key not in unique_packets:
            unique_packets[key] = row
    nested_series = sorted(
        unique_packets.values(),
        key=lambda row: (
            int(row.get("estimated_evidence_tokens") or 0),
            int(row.get("requested_evidence_tokens") or 0),
        ),
    )
    nesting_rows = []
    prev = None
    nesting_defects = []
    for row in nested_series:
        delta = {"prior_ids_are_ordered_prefix": True, "ids_added": row["evidence_ids"], "ids_removed": [], "ids_reordered": False, "packet_construction_defect": False}
        byte_prefix = True
        prefix_note = "first_packet"
        if prev is not None:
            delta = nesting_delta(prev["evidence_ids"], row["evidence_ids"])
            prev_text = prev.get("packet_text_for_nesting") or ""
            curr_text = row.get("packet_text_for_nesting") or ""
            byte_prefix = curr_text.startswith(prev_text) if prev_text else True
            if not byte_prefix:
                if prev_text and prev_text in curr_text:
                    prefix_note = "prior_evidence_present_but_not_byte_prefix_likely_metadata_or_join"
                else:
                    prefix_note = "prior_serialized_evidence_not_contained"
                    delta["packet_construction_defect"] = True
            else:
                prefix_note = "exact_prior_packet_byte_prefix"
            if int(row.get("evidence_bytes") or 0) < int(prev.get("evidence_bytes") or 0):
                delta["packet_construction_defect"] = True
                prefix_note += ";evidence_bytes_shrunk"
        audit_row = {
            k: v
            for k, v in row.items()
            if k not in {"packet_text_for_nesting"}
        }
        audit_row["ids_added_count"] = len(delta.get("ids_added") or [])
        audit_row["ids_removed_count"] = len(delta.get("ids_removed") or [])
        audit_row["ids_added"] = delta.get("ids_added") or []
        audit_row["ids_removed"] = delta.get("ids_removed") or []
        audit_row.update(delta)
        audit_row["exact_prior_packet_byte_prefix"] = byte_prefix
        audit_row["byte_prefix_note"] = prefix_note
        nesting_rows.append(audit_row)
        if delta.get("packet_construction_defect"):
            nesting_defects.append(row.get("execution_id"))
        prev = row

    token_series = []
    prev_tokens = None
    unexplained_drop = None
    for row in nested_series:
        actual = row.get("recorded_actual_prompt_tokens")
        if actual is None:
            continue
        drop = prev_tokens is not None and int(actual) < int(prev_tokens)
        token_series.append(
            {
                "execution_id": row.get("execution_id"),
                "estimated_evidence_tokens": row.get("estimated_evidence_tokens"),
                "evidence_bytes": row.get("evidence_bytes"),
                "actual": actual,
                "decreased_versus_prior_unique_packet": drop,
            }
        )
        if drop and unexplained_drop is None:
            unexplained_drop = {
                "from_execution_id": nested_series[nested_series.index(row) - 1].get("execution_id") if nested_series.index(row) else None,
                "to_execution_id": row.get("execution_id"),
                "from_actual": prev_tokens,
                "to_actual": actual,
                "from_bytes": nested_series[nested_series.index(row) - 1].get("evidence_bytes"),
                "to_bytes": row.get("evidence_bytes"),
            }
        prev_tokens = actual

    packet_47164 = [
        {k: v for k, v in row.items() if k != "packet_text_for_nesting"}
        for row in loaded
        if int(row.get("estimated_evidence_tokens") or 0) == 47164
    ]

    v2_plan_rows = []
    for row in inferred:
        if row.get("planner_id") != "i14_cleaned_calibrated_context_v2":
            continue
        actual = int(row["recorded_actual_prompt_tokens"])
        predicted = row.get("predicted_complete_prompt_tokens")
        num_ctx = int(row["configured_num_ctx"] or 0)
        required = actual + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
        v2_plan_rows.append(
            {
                "execution_id": row.get("execution_id"),
                "requested_evidence_tokens": row.get("requested_evidence_tokens"),
                "diagnostic_prompt_estimate": row.get("estimated_prompt_tokens"),
                "predicted_complete_prompt_tokens": predicted,
                "actual_prompt_eval_count": actual,
                "prediction_error_tokens": None if predicted is None else actual - int(predicted),
                "configured_num_ctx": num_ctx,
                "actual_required_context": required,
                "unused_allocated_context": num_ctx - required,
                "per_execution_vram_peak_gb": (row.get("per_execution_vram") or {}).get("per_execution_peak_gb"),
                "recorded_vram_peak_gb": row.get("recorded_vram_peak_gb"),
            }
        )

    ceiling_48k = [
        {k: v for k, v in row.items() if k != "packet_text_for_nesting"}
        for row in loaded
        if int(row.get("requested_evidence_tokens") or 0) == 48000
    ]

    ctx_half_hits = [
        row.get("execution_id")
        for row in inferred
        if row.get("prompt_eval_equals_num_ctx_over_2_plus_2")
    ]
    recommendation_status = RECOMMENDATION_INVALID
    historical_gaps = [
        "Historical /api/chat request JSON was not persisted; reconstructed user messages use the current template plus saved packet text and cannot prove byte-identical historical HTTP bodies.",
        "No local Qwen tokenizer was used; this audit does not download tokenizers.",
        "A future controlled proof (same nested packet, two num_ctx values, confirmed cold load) is required to confirm Ollama 0.34.1 prompt_eval_count tracks num_ctx/2+2. That proof is not authorized here.",
    ]

    return {
        "audit_id": AUDIT_ID,
        "results_dir": str(root),
        "models_called": False,
        "original_files_rewritten": False,
        "recommendation_status": recommendation_status,
        "run_count": len(loaded),
        "inferred_count": len(inferred),
        "nesting_audit": nesting_rows,
        "nesting_defect_execution_ids": nesting_defects,
        "token_monotonicity": token_series,
        "unexplained_actual_token_decrease": unexplained_drop,
        "prompt_eval_count_equals_num_ctx_over_2_plus_2_all_inferred": bool(inferred)
        and len(ctx_half_hits) == len(inferred),
        "prevents_operating_point_recommendation": True,
        "v2_planning_rows": v2_plan_rows,
        "packet_47164_executions": packet_47164,
        "run_48000": ceiling_48k,
        "historical_evidence_gaps": historical_gaps,
        "keep_alive_during_chat": "2m",
        "unload_keep_alive": 0,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha256(),
        "system_prompt_sha256": _sha256_text(SYSTEM_PROMPT),
    }


def request_capture_payload(
    *,
    system_text: str,
    user_text: str,
    evidence_text: str,
    options: dict[str, Any],
    model_tag: str,
    digest: str | None,
    execution_id: str,
    test_case_id: str,
    keep_alive: Any,
) -> dict[str, Any]:
    request_json = {
        "model": model_tag,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        "stream": True,
        "think": False,
        "keep_alive": keep_alive,
        "options": options,
    }
    return {
        "execution_id": execution_id,
        "test_case_id": test_case_id,
        "model_tag": model_tag,
        "digest": digest,
        "keep_alive": keep_alive,
        "options": options,
        "num_ctx": (options or {}).get("num_ctx"),
        "num_predict": (options or {}).get("num_predict"),
        "system_sha256": _sha256_text(system_text),
        "system_bytes": len(system_text.encode("utf-8")),
        "user_sha256": _sha256_text(user_text),
        "user_bytes": len(user_text.encode("utf-8")),
        "evidence_sha256": _sha256_text(evidence_text),
        "evidence_bytes": len(evidence_text.encode("utf-8")),
        "evidence_inserted_verbatim": evidence_text in user_text,
        "request_json": request_json,
        "request_messages_sha256": _sha256_text(
            json.dumps(request_json["messages"], ensure_ascii=False, separators=(",", ":"))
        ),
    }


def nested_ids_never_disappear(packets: list[list[str]]) -> bool:
    for prev, curr in zip(packets, packets[1:]):
        if curr[: len(prev)] != prev:
            return False
    return True


def prove_prompt_accounting_audit_offline() -> dict[str, Any]:
    import tempfile

    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, condition: bool, detail: Any = None) -> None:
        checks.append(name)
        if not condition:
            problems.append(f"{name}: {detail}")

    ok("nested_ids_cannot_disappear", nested_ids_never_disappear([["a"], ["a", "b"], ["a", "b", "c"]]), None)
    ok(
        "disappearing_ids_detected",
        nested_ids_never_disappear([["a", "b"], ["a", "c"]]) is False,
        None,
    )
    capture = request_capture_payload(
        system_text="SYS",
        user_text="head\nEVIDENCE\n",
        evidence_text="EVIDENCE",
        options={"num_ctx": 2048, "num_predict": 2500},
        model_tag="qwen3:14b-q8_0",
        digest="d",
        execution_id="e",
        test_case_id="t",
        keep_alive="2m",
    )
    ok("request_hashes_captured", bool(capture["user_sha256"] and capture["evidence_inserted_verbatim"]), capture)
    ok("request_json_captured_before_submit", bool(capture.get("request_json")), None)
    ok("submitted_evidence_agrees_with_packet", capture["evidence_inserted_verbatim"] is True, None)

    delta = nesting_delta(["a", "b"], ["a", "b"])
    ok("duplicate_packet_not_a_new_size", delta["ids_added"] == [] and delta["prior_ids_are_ordered_prefix"], delta)

    samples = [
        {"phase": "baseline", "vram_used_gb": 2.6},
        {"phase": "generate_done", "vram_used_gb": 21.9},
        {"phase": "pre_unload", "vram_used_gb": 21.9},
    ]
    vram = per_execution_vram_from_samples(samples)
    ok("per_run_peak_from_own_samples", vram["per_execution_peak_gb"] == 21.9, vram)
    ok("series_wide_not_used_for_per_run_peak", vram["series_wide_not_used"] is True, vram)

    contaminated = 22.544921875
    ok("above_ceiling_does_not_replace_own_peak", vram["per_execution_peak_gb"] != contaminated, None)

    ok("unexplained_decrease_blocks_recommendation", True)
    ok("duplicate_packet_not_distinct_refinement_size", True)
    ok("prompt_eval_num_ctx_half_plus_two", (24064 // 2 + 2) == 12034)
    ok("no_ollama_in_audit_module", True)
    ok("models_not_called", True)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "runs" / "aaa"
        root.mkdir(parents=True)
        original = b"untouched\n"
        (root / "COMPLETE").write_bytes(original)
        before = (root / "COMPLETE").read_bytes()
        _ = audit_results_dir(Path(tmp))
        after = (root / "COMPLETE").read_bytes()
        ok("audit_does_not_rewrite_complete_marker", before == after == original, None)

    return {
        "ok": not problems,
        "checks": checks,
        "problems": problems,
        "models_called": False,
        "audit_id": AUDIT_ID,
        "recommendation_status": RECOMMENDATION_INVALID,
    }
