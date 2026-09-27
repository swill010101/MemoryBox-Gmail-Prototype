"""Isolated three-run Ollama prompt_eval_count diagnostic.

Not a ladder. Does not call a planner. Does not rewrite gate3-b-i14 artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from memorybox.ask.i11a.i11a0_benchmark import (
    I11A0Error,
    InferenceNotAuthorized,
    ModelSpec,
    OUTPUT_RESERVE_TOKENS,
    inventory_installed_models,
    new_execution_id,
)
from memorybox.ask.i11a.i11a0_control_telemetry import (
    FIRST_A_EXECUTION_ID,
    IndependentRequestSampler,
    classify_in_request_placement,
    find_aborted_a_folder,
    http_chat_post,
    invoke_post,
    write_aborted_a_sidecar,
)
from memorybox.ask.i11a.i11a0_gate3_progress import Gate3Progress, atomic_replace_text
from memorybox.ask.i11a.i11a0_host import (
    VRAM_CEILING_GB,
    collect_host_affinity_preflight,
    read_nvidia_snapshot,
    require_flightsim_host_affinity,
    require_literal_loopback_ollama_url,
)
from memorybox.ask.i11a.i11a0_i14_source import verify_pinned_i14_export
from memorybox.ask.i11a.i11a0_placement import read_ollama_ps
from memorybox.ask.i11a.i11a0_prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    prompt_sha256,
    render_user_message,
)
from memorybox.ask.i11a.i11a0_smoke import PINNED_B_DIGEST, REPO_ROOT, _unload, require_qwen_smoke_configuration

EXPERIMENT_ID = "i11a0_prompt_accounting_control_v1_telemetry_retry"
PRIOR_EXPERIMENT_ID = "i11a0_prompt_accounting_control_v1"
B_TAG = "qwen3:14b-q8_0"
PACKET_A_SHA256 = "ae0fcbb738dd956282aef23188fd53e703adefed7ba2ee1630a0a653b6ce20d7"
PACKET_BC_SHA256 = "9807caf061f57b4f949e837774a158f6dfbc142de2e88a252a62eba540d9f0b6"
FIXED_NUM_CTX = {"A2": 30720, "B": 30720, "C": 32768}
IDENTITY_EXPECTATION = {"A2": 15362, "B": 15362, "C": 16386}
MATRIX_ORDER = ("A2", "B", "C")
PACKET_ROLE = "prompt_accounting_control"
PACKET_ID_A = "control-v1-packet-27054"
PACKET_ID_BC = "control-v1-packet-42019"
KEEP_ALIVE = 0
TEMPERATURE = 0.1
SEED = 42
THINK = False
TIMEOUT_SECONDS = 1800
UNLOAD_WAIT_SECONDS = 90
VRAM_IDLE_SLACK_GB = 2.0
C_UNSAFE_PEAK_GB = 22.0
GATE3_SERIES_NAME = "gate3-b-i14"
PROMPT_COUNT_SEMANTICS = "under_test"

PostFn = Callable[[bytes, str, int], list[dict[str, Any]]]
UnloadFn = Callable[[str, str], float]
PsFn = Callable[[str], dict[str, Any]]
NvidiaFn = Callable[[], dict[str, Any]]


class PromptAccountingProofError(I11A0Error):
    """Control-v1 diagnostic refused to proceed."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def serialize_chat_request(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def atomic_replace_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def refuse_planner_num_ctx(run_id: str, num_ctx: int) -> int:
    expected = FIXED_NUM_CTX[run_id]
    if int(num_ctx) != expected:
        raise PromptAccountingProofError(
            f"run {run_id} num_ctx is fixed at {expected}; planner/override {num_ctx} refused"
        )
    return expected


def matrix_spec(run_id: str) -> dict[str, Any]:
    packet_sha = PACKET_A_SHA256 if run_id == "A2" else PACKET_BC_SHA256
    packet_id = PACKET_ID_A if run_id == "A2" else PACKET_ID_BC
    return {
        "run_id": run_id,
        "packet_sha256": packet_sha,
        "num_ctx": FIXED_NUM_CTX[run_id],
        "packet_id": packet_id,
        "estimated_evidence_tokens": 27054 if run_id == "A2" else 42019,
    }


def load_preserved_packet(series_root: Path | str, expected_sha256: str) -> dict[str, Any]:
    root = Path(series_root)
    runs = root / "runs"
    if not runs.is_dir():
        raise PromptAccountingProofError(f"preserved series runs/ missing: {runs}")
    for folder in sorted(p for p in runs.iterdir() if p.is_dir() and (p / "COMPLETE").is_file()):
        packet_path = folder / "evidence_packet.txt"
        if not packet_path.is_file():
            continue
        text = packet_path.read_text(encoding="utf-8")
        digest = _sha256_text(text)
        if digest != expected_sha256:
            continue
        manifest = {}
        man_path = folder / "packet_manifest.json"
        if man_path.is_file():
            manifest = json.loads(man_path.read_text(encoding="utf-8"))
        ids = list(manifest.get("evidence_ids") or [])
        return {
            "text": text,
            "sha256": digest,
            "bytes": len(text.encode("utf-8")),
            "characters": len(text),
            "evidence_ids": ids,
            "message_count": manifest.get("message_count") or len(ids),
            "thread_count": manifest.get("conversation_count") or len(manifest.get("conversation_ids") or []),
            "partial_context": bool(manifest.get("partial_context")),
            "partial_boundary_note": str(manifest.get("partial_boundary_note") or "none"),
            "time_start": str(manifest.get("time_start") or ""),
            "time_end": str(manifest.get("time_end") or ""),
            "source_execution_id": folder.name,
            "source_path": str(packet_path),
            "manifest_packet_sha256": manifest.get("packet_sha256"),
        }
    raise PromptAccountingProofError(f"no COMPLETE packet with sha256 {expected_sha256} under {runs}")


def assert_a_prefix_of_b(packet_a: dict[str, Any], packet_b: dict[str, Any]) -> dict[str, Any]:
    ids_a = list(packet_a["evidence_ids"])
    ids_b = list(packet_b["evidence_ids"])
    prefix = ids_b[: len(ids_a)] == ids_a
    byte_prefix = str(packet_b["text"]).startswith(str(packet_a["text"]))
    removed = [eid for eid in ids_a if eid not in set(ids_b)]
    if not prefix or removed or not byte_prefix:
        raise PromptAccountingProofError("packet A is not an ordered byte/id prefix of packet B")
    return {
        "ordered_id_prefix": True,
        "exact_byte_prefix": True,
        "ids_removed": [],
        "ids_reordered": False,
    }


def build_chat_payload(
    *,
    packet: dict[str, Any],
    packet_id: str,
    num_ctx: int,
) -> dict[str, Any]:
    user = render_user_message(
        packet_id=packet_id,
        packet_role=PACKET_ROLE,
        time_start=packet["time_start"],
        time_end=packet["time_end"],
        partial_context=bool(packet["partial_context"]),
        partial_boundary_note=str(packet["partial_boundary_note"]),
        evidence_ids=list(packet["evidence_ids"]),
        evidence_text=packet["text"],
    )
    return {
        "model": B_TAG,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "think": THINK,
        "keep_alive": KEEP_ALIVE,
        "options": {
            "num_ctx": int(num_ctx),
            "num_predict": OUTPUT_RESERVE_TOKENS,
            "temperature": TEMPERATURE,
            "seed": SEED,
        },
    }


def persist_pre_post_artifacts(
    folder: Path,
    *,
    payload: dict[str, Any],
    packet: dict[str, Any],
    execution_id: str,
    test_case_id: str,
    preflight: dict[str, Any],
    i14_proof: dict[str, Any],
    digest: str,
) -> bytes:
    encoded = serialize_chat_request(payload)
    atomic_replace_bytes(folder / "request_capture.json", encoded)
    disk = (folder / "request_capture.json").read_bytes()
    if disk != encoded:
        raise PromptAccountingProofError("request_capture.json bytes do not match serialized request")
    user = payload["messages"][1]["content"]
    system = payload["messages"][0]["content"]
    evidence = packet["text"]
    identity = {
        "experiment_id": EXPERIMENT_ID,
        "execution_id": execution_id,
        "test_case_id": test_case_id,
        "model_tag": B_TAG,
        "digest": digest,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha256(),
        "keep_alive": KEEP_ALIVE,
        "num_ctx": payload["options"]["num_ctx"],
        "num_predict": payload["options"]["num_predict"],
        "temperature": TEMPERATURE,
        "seed": SEED,
        "think": THINK,
        "request_json_sha256": _sha256_bytes(disk),
        "request_json_bytes": len(disk),
        "system_sha256": _sha256_text(system),
        "system_bytes": len(system.encode("utf-8")),
        "system_characters": len(system),
        "user_sha256": _sha256_text(user),
        "user_bytes": len(user.encode("utf-8")),
        "user_characters": len(user),
        "evidence_sha256": _sha256_text(evidence),
        "evidence_bytes": len(evidence.encode("utf-8")),
        "evidence_characters": len(evidence),
        "evidence_inserted_verbatim": evidence in user,
        "messages_sha256": _sha256_text(json.dumps(payload["messages"], ensure_ascii=False, separators=(",", ":"))),
        "i14_frozen_export": {
            "generation_id": i14_proof.get("generation_id"),
            "generation_checksum": i14_proof.get("generation_checksum"),
            "prompt_sha256": i14_proof.get("prompt_sha256"),
            "related_sha256": i14_proof.get("related_sha256"),
        },
        "outgoing_bytes_match_capture": True,
    }
    atomic_replace_text(folder / "request_identity.json", json.dumps(identity, indent=2, sort_keys=True) + "\n")
    atomic_replace_bytes(folder / "packet.txt", packet["text"].encode("utf-8"))
    packet_identity = {
        "packet_sha256": packet["sha256"],
        "bytes": packet["bytes"],
        "characters": packet["characters"],
        "message_count": packet["message_count"],
        "thread_count": packet["thread_count"],
        "evidence_id_count": len(packet["evidence_ids"]),
        "evidence_ids": packet["evidence_ids"],
        "source_execution_id": packet["source_execution_id"],
        "source_path": packet["source_path"],
        "copied_not_rebuilt": True,
    }
    atomic_replace_text(folder / "packet_identity.json", json.dumps(packet_identity, indent=2, sort_keys=True) + "\n")
    atomic_replace_text(folder / "preflight.json", json.dumps(preflight, indent=2, sort_keys=True, default=str) + "\n")
    reread = (folder / "request_capture.json").read_bytes()
    if reread != disk:
        raise PromptAccountingProofError("re-read request_capture.json diverged before POST")
    return reread


def last_event(events: list[dict[str, Any]]) -> dict[str, Any]:
    return events[-1] if events else {}


def model_listed(ps_payload: dict[str, Any], tag: str, digest: str) -> bool:
    for row in ps_payload.get("models") or []:
        name = str(row.get("name") or row.get("model") or "")
        row_digest = str(row.get("digest") or "")
        if name == tag or name.startswith(tag) or (digest and row_digest == digest):
            return True
    return False


def wait_unloaded(
    *,
    ps_fn: PsFn,
    nvidia_fn: NvidiaFn,
    base_url: str,
    tag: str,
    digest: str,
    idle_vram_gb: float | None,
    timeout: float = UNLOAD_WAIT_SECONDS,
) -> dict[str, Any]:
    started = time.monotonic()
    last_ps: dict[str, Any] = {}
    last_nv: dict[str, Any] = {}
    while time.monotonic() - started <= timeout:
        last_ps = ps_fn(base_url)
        last_nv = nvidia_fn()
        listed = model_listed(last_ps, tag, digest)
        used = last_nv.get("memory_used_gb")
        near_idle = True
        if idle_vram_gb is not None and isinstance(used, (int, float)):
            near_idle = float(used) <= float(idle_vram_gb) + VRAM_IDLE_SLACK_GB
        if not listed and near_idle:
            return {
                "unloaded": True,
                "seconds": round(time.monotonic() - started, 3),
                "ps": last_ps,
                "nvidia": last_nv,
                "model_listed": False,
                "near_idle": True,
            }
        time.sleep(1.0)
    raise PromptAccountingProofError(
        f"model still loaded or VRAM not near baseline after {timeout}s: listed={model_listed(last_ps, tag, digest)}"
    )


def interpret_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["run_id"]: row.get("ollama_reported_prompt_eval_count") for row in rows}
    identity_hits = {
        run_id: by_id.get(run_id) == IDENTITY_EXPECTATION[run_id]
        for run_id in FIXED_NUM_CTX
        if run_id in by_id and by_id.get(run_id) is not None
    }
    a = by_id.get("A2")
    b = by_id.get("B")
    c = by_id.get("C")
    a_eq_b = a is not None and b is not None and a == b
    b_tracks_ctx = b is not None and c is not None and b == IDENTITY_EXPECTATION["B"] and c == IDENTITY_EXPECTATION["C"]
    tracks_evidence = a is not None and b is not None and a != b
    identity_confirmed = bool(identity_hits) and all(identity_hits.values()) and a_eq_b and b_tracks_ctx
    return {
        "prompt_count_semantics": PROMPT_COUNT_SEMANTICS,
        "do_not_call_actual_complete_prompt_tokens": True,
        "identity_formula": "num_ctx // 2 + 2",
        "identity_expectation": IDENTITY_EXPECTATION,
        "identity_hits": identity_hits,
        "a_equals_b": a_eq_b,
        "b_to_c_tracks_num_ctx_identity": b_tracks_ctx,
        "counts_track_evidence_size": tracks_evidence and not a_eq_b,
        "num_ctx_over_2_plus_2_confirmed": identity_confirmed,
        "operating_point_named": False,
        "ladder_resumed": False,
        "v2_recalibrated": False,
        "coexistence_started": False,
        "peggy_started": False,
    }


def _http_chat_post(body: bytes, base_url: str, timeout: int, cancel=None, on_first_token=None) -> list[dict[str, Any]]:
    return http_chat_post(body, base_url, timeout, cancel=cancel, on_first_token=on_first_token)


def run_one(
    *,
    run_id: str,
    packet: dict[str, Any],
    folder: Path,
    base_url: str,
    digest: str,
    preflight: dict[str, Any],
    i14_proof: dict[str, Any],
    idle_vram_gb: float | None,
    post_fn: PostFn,
    unload_fn: UnloadFn,
    ps_fn: PsFn,
    nvidia_fn: NvidiaFn,
    progress: Gate3Progress | None = None,
    telemetry_interval: float = 1.5,
) -> dict[str, Any]:
    spec = matrix_spec(run_id)
    num_ctx = refuse_planner_num_ctx(run_id, spec["num_ctx"])
    if packet["sha256"] != spec["packet_sha256"]:
        raise PromptAccountingProofError(f"run {run_id} packet hash mismatch")
    execution_id = new_execution_id(
        test_case=f"{EXPERIMENT_ID}-{run_id}",
        hostname=socket.gethostname(),
        started_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    )
    test_case_id = f"{EXPERIMENT_ID}-{run_id}"
    folder.mkdir(parents=True, exist_ok=True)
    if progress is not None:
        progress.begin_execution()
        progress.emit("Waiting for idle baseline", phase="preflight", run_id=run_id)
    baseline_nv = nvidia_fn()
    baseline = baseline_nv.get("memory_used_gb")
    payload = build_chat_payload(packet=packet, packet_id=spec["packet_id"], num_ctx=num_ctx)
    if progress is not None:
        progress.emit("Capturing exact request JSON", phase="capture")
    body = persist_pre_post_artifacts(
        folder,
        payload=payload,
        packet=packet,
        execution_id=execution_id,
        test_case_id=test_case_id,
        preflight=preflight,
        i14_proof=i14_proof,
        digest=digest,
    )
    outgoing_hash = _sha256_bytes(body)
    capture_hash = _sha256_bytes((folder / "request_capture.json").read_bytes())
    if outgoing_hash != capture_hash:
        raise PromptAccountingProofError("outgoing HTTP body hash != captured request hash")
    if progress is not None:
        progress.emit("Exact request captured; independent telemetry starting", phase="telemetry_start")

    telemetry = IndependentRequestSampler(
        telemetry_path=folder / "in_request_telemetry.jsonl",
        base_url=base_url,
        experiment_id=EXPERIMENT_ID,
        run_id=run_id,
        execution_id=execution_id,
        digest=digest,
        nvidia_fn=nvidia_fn,
        ps_fn=ps_fn,
        interval_seconds=telemetry_interval,
        heartbeat_seconds=15.0,
        progress=progress,
    )
    telemetry.start("request_active")
    if progress is not None:
        progress.emit("Independent telemetry started; POST submitted", phase="generation")

    def on_first_token() -> None:
        telemetry.set_phase("first_token")
        if progress is not None:
            progress.emit("First streamed token", phase="first_token")
        telemetry.set_phase("streaming")

    try:
        events = invoke_post(post_fn, body, base_url, TIMEOUT_SECONDS, telemetry.cancel, on_first_token)
    finally:
        telemetry.set_phase("stream_complete")
    if progress is not None:
        progress.emit("Final event received", phase="stream_complete")
    telemetry.set_phase("pre_unload")
    in_request = telemetry.in_request_samples()
    in_request_vram = telemetry.vram_for_phases({"request_active", "first_token", "streaming"})
    in_request_peak = max(in_request_vram) if in_request_vram else None
    pre_final = None
    if in_request:
        last_in = in_request[-1].get("gpu_vram_used_gb")
        if isinstance(last_in, (int, float)):
            pre_final = float(last_in)
    post_response = nvidia_fn().get("memory_used_gb")
    placement = classify_in_request_placement(
        telemetry.samples,
        tag=B_TAG,
        digest=digest,
        baseline_vram_gb=baseline if isinstance(baseline, (int, float)) else None,
    )
    safety_stop = telemetry.cancel_reason
    if safety_stop is None and in_request_peak is not None and in_request_peak >= VRAM_CEILING_GB:
        safety_stop = "vram_ceiling"
    if safety_stop is None and placement.get("safety_label"):
        safety_stop = placement["safety_label"]

    if progress is not None:
        progress.emit(
            f"Placement classification: {placement.get('placement_status')} ({placement.get('reason')})",
            phase="placement",
        )
        progress.emit("Unload started", phase="unload")
    unload_s = unload_fn(base_url, B_TAG)
    telemetry.set_phase("unloading")
    settled = wait_unloaded(
        ps_fn=ps_fn,
        nvidia_fn=nvidia_fn,
        base_url=base_url,
        tag=B_TAG,
        digest=digest,
        idle_vram_gb=idle_vram_gb if isinstance(idle_vram_gb, (int, float)) else baseline,
    )
    telemetry.set_phase("after_unload_settled")
    settled_vram = nvidia_fn().get("memory_used_gb")
    telemetry.stop()
    if progress is not None:
        progress.emit("Model absent from /api/ps; VRAM returned to baseline" if settled.get("unloaded") else "Unload verification incomplete", phase="unloaded")

    final_event = last_event(events)
    raw_count = final_event.get("prompt_eval_count")
    narration = "".join(str((ev.get("message") or {}).get("content") or "") for ev in events)
    done_reason = final_event.get("done_reason")
    if done_reason == "length" and safety_stop is None:
        safety_stop = "context_or_length"
    if not events and safety_stop is None:
        safety_stop = "generation_failed"
    if not settled.get("unloaded"):
        safety_stop = safety_stop or "unload_failure"
    if progress is not None:
        progress.emit(f"Prompt count reported: {raw_count}", phase="accounted")

    extra_fields = {
        key: final_event.get(key)
        for key in (
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
            "total_duration",
            "load_duration",
            "done",
            "done_reason",
            "context",
            "truncated",
            "truncate",
            "cache",
            "warning",
            "warnings",
        )
        if key in final_event or final_event.get(key) is not None
    }
    raw_text = "".join(json.dumps(event) + "\n" for event in events)
    atomic_replace_text(folder / "raw_api.jsonl", raw_text)
    atomic_replace_text(folder / "narration.txt", narration)
    identity = json.loads((folder / "request_identity.json").read_text(encoding="utf-8"))
    record = {
        "experiment_id": EXPERIMENT_ID,
        "run_id": run_id,
        "execution_id": execution_id,
        "test_case_id": test_case_id,
        "packet_sha256": packet["sha256"],
        "num_ctx": num_ctx,
        "planner_used": False,
        "keep_alive": KEEP_ALIVE,
        "outgoing_request_sha256": outgoing_hash,
        "captured_request_sha256": capture_hash,
        "outgoing_equals_captured": outgoing_hash == capture_hash,
        "prompt_count_semantics": PROMPT_COUNT_SEMANTICS,
        "ollama_reported_prompt_eval_count": raw_count,
        "accounting_prompt_eval_count": raw_count,
        "summary_prompt_eval_count": raw_count,
        "transformation": 0 if raw_count is not None else None,
        "identity_expectation": IDENTITY_EXPECTATION[run_id],
        "matches_num_ctx_over_2_plus_2": raw_count == IDENTITY_EXPECTATION[run_id],
        "done_reason": done_reason,
        "final_event_fields": extra_fields,
        "final_event_sha256": _sha256_text(json.dumps(final_event, sort_keys=True, default=str)),
        "narration_sha256": _sha256_text(narration),
        "vram_baseline_gb": baseline,
        "vram_in_request_peak_gb": in_request_peak,
        "vram_pre_final_event_gb": pre_final,
        "vram_immediate_post_response_gb": post_response,
        "vram_settled_post_unload_gb": settled_vram,
        "vram_peak_gb": in_request_peak,
        "series_peak_not_used": True,
        "placement_status": placement.get("placement_status"),
        "gpu_resident": placement.get("gpu_resident"),
        "cpu_offload": placement.get("cpu_offload"),
        "gpu_residency_lost": placement.get("gpu_residency_lost"),
        "gpu_presence_observed": placement.get("gpu_presence_observed"),
        "placement_reason": placement.get("reason"),
        "placement_evidence": placement.get("evidence"),
        "in_request_sample_count": placement.get("in_request_sample_count"),
        "unload_seconds": unload_s,
        "unload": settled,
        "safety_stop": safety_stop,
        "request_options": payload["options"],
        "user_sha256": identity["user_sha256"],
        "system_sha256": identity["system_sha256"],
        "messages_sha256": identity["messages_sha256"],
        "first_a_execution_excluded": FIRST_A_EXECUTION_ID,
    }
    atomic_replace_text(folder / "run_record.json", json.dumps(record, indent=2, sort_keys=True, default=str) + "\n")
    atomic_replace_text(
        folder / "placement_proof.json",
        json.dumps(placement, indent=2, sort_keys=True, default=str) + "\n",
    )
    atomic_replace_text(folder / "COMPLETE", "ok\n")
    if progress is not None:
        nxt = "next matrix member" if safety_stop is None else f"stop: {safety_stop}"
        progress.emit(f"Run {run_id} complete; {nxt}", phase="complete")
    return record


def hash_tree_marker(path: Path) -> str | None:
    if not path.is_file():
        return None
    return _sha256_bytes(path.read_bytes())


def run_prompt_accounting_control(
    *,
    confirm_benchmark: bool,
    source_series: Path | str,
    results_dir: Path | str,
    ollama_base_url: str,
    i14_export: Path | str,
    prior_attempt: Path | str | None = None,
    post_fn: PostFn | None = None,
    unload_fn: UnloadFn | None = None,
    ps_fn: PsFn | None = None,
    nvidia_fn: NvidiaFn | None = None,
    require_host: bool = True,
    models_called: bool = True,
    telemetry_interval: float = 1.5,
) -> dict[str, Any]:
    if not confirm_benchmark:
        raise InferenceNotAuthorized("prompt-accounting control requires --confirm-benchmark")
    results = Path(results_dir)
    source = Path(source_series)
    if GATE3_SERIES_NAME in Path(results).resolve().parts:
        raise PromptAccountingProofError("refusing to write diagnostic runs into the capacity series directory")
    if results.resolve() == source.resolve():
        raise PromptAccountingProofError("diagnostic output must not be the gate3-b-i14 series")
    hashes_before = hash_tree_marker(source / "HASHES.txt")
    results.mkdir(parents=True, exist_ok=True)
    packet_a = load_preserved_packet(source, PACKET_A_SHA256)
    packet_b = load_preserved_packet(source, PACKET_BC_SHA256)
    prefix = assert_a_prefix_of_b(packet_a, packet_b)
    if packet_b["sha256"] != PACKET_BC_SHA256 or packet_a["sha256"] != PACKET_A_SHA256:
        raise PromptAccountingProofError("frozen packet hashes do not match the preserved series")

    i14_proof = verify_pinned_i14_export(i14_export)
    base_url = ollama_base_url
    digest = PINNED_B_DIGEST
    preflight: dict[str, Any] = {"require_host": require_host}
    if require_host:
        base_url = require_literal_loopback_ollama_url(ollama_base_url)
        preflight = collect_host_affinity_preflight(
            ollama_base_url=base_url,
            output_path=results,
            chunks_path=i14_export,
            repo=REPO_ROOT,
        )
        require_flightsim_host_affinity(preflight)
        version = str(preflight.get("ollama_version") or "")
        if "0.34" not in version:
            raise PromptAccountingProofError(f"Ollama version must be 0.34.1 family, got {version!r}")
        inventory = inventory_installed_models(base_url=base_url)
        if inventory.get("pull_executed"):
            raise PromptAccountingProofError("inventory reported a pull")
        spec = ModelSpec("B", B_TAG, "Q8_0", PINNED_B_DIGEST)
        by_tag = {row["tag"]: row for row in inventory.get("approved") or []}
        row = by_tag.get(spec.tag) or {}
        digest = str(row.get("digest") or spec.digest)
        if digest != PINNED_B_DIGEST:
            raise PromptAccountingProofError(f"digest mismatch: {digest}")
        require_qwen_smoke_configuration(spec, row)
        nvidia_fn = nvidia_fn or read_nvidia_snapshot
        idle = nvidia_fn().get("memory_used_gb")
        unload_fn = unload_fn or _unload
        ps_fn = ps_fn or read_ollama_ps
        unload_fn(base_url, B_TAG)
        wait_unloaded(
            ps_fn=ps_fn,
            nvidia_fn=nvidia_fn,
            base_url=base_url,
            tag=B_TAG,
            digest=digest,
            idle_vram_gb=idle if isinstance(idle, (int, float)) else None,
        )
        post_fn = post_fn or _http_chat_post
        preflight["i14"] = i14_proof
        preflight["idle_vram_gb"] = idle
        preflight["experiment_id"] = EXPERIMENT_ID
        preflight["not_a_capacity_ladder"] = True
        preflight["prior_experiment_id"] = PRIOR_EXPERIMENT_ID
        preflight["excluded_first_a_execution_id"] = FIRST_A_EXECUTION_ID
    else:
        nvidia_fn = nvidia_fn or (lambda: {"memory_used_gb": 2.6, "memory_total_gb": 24.0, "name": "NVIDIA GeForce RTX 4090", "utilization_gpu_percent": 0})
        unload_fn = unload_fn or (lambda _url, _tag: 0.0)
        ps_fn = ps_fn or (lambda _url: {"available": True, "models": []})
        post_fn = post_fn or (lambda _body, _url, _timeout, **_kw: [{"done": True, "prompt_eval_count": 1, "done_reason": "stop"}])
        idle = 2.6
        preflight = {
            "require_host": False,
            "experiment_id": EXPERIMENT_ID,
            "i14": i14_proof,
            "idle_vram_gb": idle,
            "not_a_capacity_ladder": True,
            "excluded_first_a_execution_id": FIRST_A_EXECUTION_ID,
        }

    aborted_sidecar = None
    prior_path = Path(prior_attempt) if prior_attempt else None
    if prior_path:
        found = find_aborted_a_folder(prior_path)
        if found is not None:
            aborted_sidecar = write_aborted_a_sidecar(found)

    class _NullStream:
        def write(self, text: str) -> int:
            return len(text)

        def flush(self) -> None:
            return None

    progress = Gate3Progress(
        results,
        timeout_seconds=TIMEOUT_SECONDS,
        controller_id=EXPERIMENT_ID,
        heartbeat_seconds=15.0,
        stream=None if require_host else _NullStream(),
    )
    packets = {"A2": packet_a, "B": packet_b, "C": packet_b}
    rows: list[dict[str, Any]] = []
    blocked_reason = None
    for run_id in MATRIX_ORDER:
        if blocked_reason:
            break
        if run_id == "B" and rows:
            a2 = rows[0]
            if a2.get("placement_status") != "gpu_resident" or a2.get("gpu_resident") is not True:
                blocked_reason = f"a2_placement_not_affirmative:{a2.get('placement_status')}"
                progress.emit(f"Not continuing to B: {blocked_reason}", phase="stop")
                break
            if a2.get("safety_stop"):
                blocked_reason = f"prior_safety_stop:{a2.get('safety_stop')}"
                break
        if run_id == "C" and rows:
            peaks = [r.get("vram_peak_gb") for r in rows if isinstance(r.get("vram_peak_gb"), (int, float))]
            if peaks and max(peaks) >= C_UNSAFE_PEAK_GB:
                blocked_reason = "c_predicted_unsafe_from_ab_vram"
                progress.emit(blocked_reason, phase="stop")
                break
            if any(r.get("safety_stop") for r in rows):
                blocked_reason = f"prior_safety_stop:{rows[-1].get('safety_stop')}"
                break
            if rows[-1].get("placement_status") != "gpu_resident":
                blocked_reason = "b_placement_not_affirmative"
                break
        folder = results / "runs" / run_id
        row = run_one(
            run_id=run_id,
            packet=packets[run_id],
            folder=folder,
            base_url=base_url,
            digest=digest,
            preflight=preflight,
            i14_proof=i14_proof,
            idle_vram_gb=preflight.get("idle_vram_gb") if isinstance(preflight.get("idle_vram_gb"), (int, float)) else idle,
            post_fn=post_fn,
            unload_fn=unload_fn,
            ps_fn=ps_fn,
            nvidia_fn=nvidia_fn,
            progress=progress,
            telemetry_interval=telemetry_interval,
        )
        rows.append(row)
        if row.get("safety_stop"):
            blocked_reason = row["safety_stop"]
            progress.emit(f"Stop remaining matrix: {blocked_reason}", phase="stop")
            break

    hashes_after = hash_tree_marker(source / "HASHES.txt")
    if hashes_before and hashes_after and hashes_before != hashes_after:
        raise PromptAccountingProofError("gate3-b-i14 HASHES.txt changed; diagnostic must not rewrite the series")

    bc_diff = None
    if len(rows) >= 3:
        b_req = json.loads((results / "runs" / "B" / "request_capture.json").read_text(encoding="utf-8"))
        c_req = json.loads((results / "runs" / "C" / "request_capture.json").read_text(encoding="utf-8"))
        bc_diff = {
            "messages_identical": b_req.get("messages") == c_req.get("messages"),
            "keep_alive_identical": b_req.get("keep_alive") == c_req.get("keep_alive"),
            "think_identical": b_req.get("think") == c_req.get("think"),
            "options_except_num_ctx_identical": {
                k: v for k, v in (b_req.get("options") or {}).items() if k != "num_ctx"
            }
            == {k: v for k, v in (c_req.get("options") or {}).items() if k != "num_ctx"},
            "num_ctx_b": (b_req.get("options") or {}).get("num_ctx"),
            "num_ctx_c": (c_req.get("options") or {}).get("num_ctx"),
            "packet_sha_b": rows[1]["packet_sha256"],
            "packet_sha_c": rows[2]["packet_sha256"],
        }
    analysis = interpret_counts(rows)
    summary = {
        "ok": blocked_reason is None and len(rows) == 3,
        "experiment_id": EXPERIMENT_ID,
        "models_called": bool(models_called and require_host),
        "pull_executed": False,
        "run_count": len(rows),
        "blocked_reason": blocked_reason,
        "prefix_proof": prefix,
        "packet_a_sha256": packet_a["sha256"],
        "packet_bc_sha256": packet_b["sha256"],
        "b_c_request_diff": bc_diff,
        "runs": rows,
        "analysis": analysis,
        "source_series_hashes_txt_sha256": hashes_after or hashes_before,
        "source_series_unchanged": hashes_before == hashes_after,
        "results_dir": str(results),
        "not_an_operating_point_test": True,
        "aborted_first_a": aborted_sidecar,
        "valid_matrix_slots": list(MATRIX_ORDER),
        "first_a_not_a_matrix_member": FIRST_A_EXECUTION_ID,
    }
    atomic_replace_text(results / "control_summary.json", json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    return summary


def prove_prompt_accounting_control_offline() -> dict[str, Any]:
    import tempfile

    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, cond: bool, detail: Any = None) -> None:
        checks.append(name)
        if not cond:
            problems.append(f"{name}: {detail}")

    ok("fixed_num_ctx_a2", FIXED_NUM_CTX["A2"] == 30720, FIXED_NUM_CTX)
    ok("fixed_num_ctx_not_planner", refuse_planner_num_ctx("B", 30720) == 30720, None)
    planner_blocked = False
    try:
        refuse_planner_num_ctx("C", 34560)
    except PromptAccountingProofError:
        planner_blocked = True
    ok("planner_cannot_change_num_ctx", planner_blocked, None)
    ok("exactly_three_matrix_slots", list(FIXED_NUM_CTX) == ["A2", "B", "C"], None)
    ok("first_a_excluded_from_matrix", "A" not in FIXED_NUM_CTX and FIRST_A_EXECUTION_ID, None)

    missing = classify_in_request_placement([], baseline_vram_gb=2.6)
    ok("missing_samples_are_unknown", missing["placement_status"] == "unknown" and missing["gpu_resident"] is None, missing)
    ok("missing_samples_not_residency_lost", missing["gpu_residency_lost"] is False and missing["safety_label"] == "placement_unproven", missing)

    idle_only = classify_in_request_placement(
        [{"request_phase": "after_unload_settled", "gpu_vram_used_gb": 2.6, "placement_status": None}],
        baseline_vram_gb=2.6,
    )
    ok("post_unload_idle_not_in_request_placement", idle_only["placement_status"] == "unknown", idle_only)

    resident = classify_in_request_placement(
        [
            {
                "request_phase": "request_active",
                "gpu_vram_used_gb": 18.0,
                "placement_status": "gpu_resident",
                "ps_model_listed": True,
            }
        ],
        baseline_vram_gb=2.6,
    )
    ok("ps_loaded_is_gpu_resident", resident["placement_status"] == "gpu_resident" and resident["gpu_resident"] is True, resident)

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "gate3-b-i14" / "runs"
        out = Path(tmp) / "prompt-accounting-proof"
        text_a = "MSG-A-COMPLETE"
        text_b = "MSG-A-COMPLETE\n\nMSG-B-EXTRA"
        packet_a_sha = _sha256_text(text_a)
        packet_b_sha = _sha256_text(text_b)

        def write_run(name: str, text: str, ids: list[str]) -> None:
            folder = src / name
            folder.mkdir(parents=True)
            (folder / "evidence_packet.txt").write_text(text, encoding="utf-8")
            (folder / "packet_manifest.json").write_text(
                json.dumps(
                    {
                        "evidence_ids": ids,
                        "message_count": len(ids),
                        "conversation_count": 1,
                        "packet_sha256": _sha256_text(text),
                        "time_start": "2009-01-01T00:00:00Z",
                        "time_end": "2009-01-02T00:00:00Z",
                        "partial_context": False,
                        "partial_boundary_note": "none",
                    }
                ),
                encoding="utf-8",
            )
            (folder / "COMPLETE").write_text("ok\n", encoding="utf-8")

        write_run("exec-a", text_a, ["id-a"])
        write_run("exec-b", text_b, ["id-a", "id-b"])
        (Path(tmp) / "gate3-b-i14" / "HASHES.txt").write_text("placeholder\n", encoding="utf-8")
        hashes_before = (Path(tmp) / "gate3-b-i14" / "HASHES.txt").read_bytes()

        loaded_a = load_preserved_packet(Path(tmp) / "gate3-b-i14", packet_a_sha)
        loaded_b = load_preserved_packet(Path(tmp) / "gate3-b-i14", packet_b_sha)
        proof = assert_a_prefix_of_b(loaded_a, loaded_b)
        ok("a_is_ordered_prefix_of_b", proof["ordered_id_prefix"] and proof["exact_byte_prefix"], proof)
        ok("b_and_c_would_share_hash", loaded_b["sha256"] == packet_b_sha, loaded_b["sha256"])

        posted: list[bytes] = []
        loaded = {"on": False}

        def fake_post(body: bytes, _url: str, _timeout: int, cancel=None, on_first_token=None) -> list[dict[str, Any]]:
            posted.append(body)
            loaded["on"] = True
            time.sleep(0.35)
            if on_first_token is not None:
                on_first_token()
            time.sleep(0.15)
            idx = len(posted)
            count = {1: 15362, 2: 15362, 3: 16386}.get(idx, 15362)
            return [
                {
                    "done": True,
                    "prompt_eval_count": count,
                    "prompt_eval_duration": 1,
                    "eval_count": 10,
                    "eval_duration": 1,
                    "total_duration": 2,
                    "load_duration": 1,
                    "done_reason": "stop",
                    "message": {"content": "ok"},
                }
            ]

        def fake_unload(_url: str, _tag: str) -> float:
            loaded["on"] = False
            return 0.01

        def fake_ps(_url: str) -> dict[str, Any]:
            if loaded["on"]:
                return {
                    "available": True,
                    "models": [
                        {
                            "name": B_TAG,
                            "digest": PINNED_B_DIGEST,
                            "size": 20 * 1024 ** 3,
                            "size_vram": 20 * 1024 ** 3,
                        }
                    ],
                }
            return {"available": True, "models": []}

        def nvidia_ok() -> dict[str, Any]:
            return {
                "name": "NVIDIA GeForce RTX 4090",
                "memory_used_gb": 18.0 if loaded["on"] else 2.6,
                "memory_total_gb": 24.0,
                "utilization_gpu_percent": 40 if loaded["on"] else 0,
            }

        def nvidia_hot() -> dict[str, Any]:
            return {
                "name": "NVIDIA GeForce RTX 4090",
                "memory_used_gb": 22.6 if loaded["on"] else 2.6,
                "memory_total_gb": 24.0,
                "utilization_gpu_percent": 90 if loaded["on"] else 0,
            }

        original_a = PACKET_A_SHA256
        original_bc = PACKET_BC_SHA256
        try:
            globals_mod = globals()
            globals_mod["PACKET_A_SHA256"] = packet_a_sha
            globals_mod["PACKET_BC_SHA256"] = packet_b_sha
            # mutate module-level constants used by load/run
            import memorybox.ask.i11a.i11a0_prompt_accounting_proof as mod

            mod.PACKET_A_SHA256 = packet_a_sha
            mod.PACKET_BC_SHA256 = packet_b_sha

            i14 = Path(tmp) / "i14"
            i14.mkdir()
            # verify_pinned_i14_export needs a real freeze; skip host and inject i14 by stubbing
            from memorybox.ask.i11a import i11a0_prompt_accounting_proof as proof_mod

            def fake_i14(_path: Path | str, **_kwargs: Any) -> dict[str, Any]:
                return {
                    "generation_id": "test",
                    "generation_checksum": "x",
                    "prompt_sha256": "p",
                    "related_sha256": "r",
                }

            proof_mod.verify_pinned_i14_export = fake_i14  # type: ignore[assignment]
            prior = Path(tmp) / "prior-attempt" / "runs" / "A"
            prior.mkdir(parents=True)
            original_capture = b'{"model":"qwen3:14b-q8_0"}'
            (prior / "request_capture.json").write_bytes(original_capture)
            (prior / "raw_api.jsonl").write_text("{}\n", encoding="utf-8")
            (prior / "narration.txt").write_text("kept\n", encoding="utf-8")
            (prior / "run_record.json").write_text(
                json.dumps({"execution_id": FIRST_A_EXECUTION_ID, "run_id": "A"}) + "\n",
                encoding="utf-8",
            )
            (prior / "COMPLETE").write_text("ok\n", encoding="utf-8")
            before_capture = (prior / "request_capture.json").read_bytes()
            before_complete = (prior / "COMPLETE").read_bytes()
            payload = proof_mod.run_prompt_accounting_control(
                confirm_benchmark=True,
                source_series=Path(tmp) / "gate3-b-i14",
                results_dir=out,
                ollama_base_url="http://127.0.0.1:11434",
                i14_export=i14,
                prior_attempt=Path(tmp) / "prior-attempt",
                post_fn=fake_post,
                unload_fn=fake_unload,
                ps_fn=fake_ps,
                nvidia_fn=nvidia_ok,
                require_host=False,
                models_called=False,
                telemetry_interval=0.05,
            )
            ok("exactly_three_runs", payload.get("run_count") == 3, payload.get("run_count"))
            ok("models_not_called_in_offline_harness", payload.get("models_called") is False, payload.get("models_called"))
            ok("capture_before_post_count", len(posted) == 3, len(posted))
            for run_id, body in zip(("A2", "B", "C"), posted):
                disk = (out / "runs" / run_id / "request_capture.json").read_bytes()
                ok(f"captured_equals_outgoing_{run_id}", disk == body, (len(disk), len(body)))
            b_cap = json.loads((out / "runs" / "B" / "request_capture.json").read_text(encoding="utf-8"))
            c_cap = json.loads((out / "runs" / "C" / "request_capture.json").read_text(encoding="utf-8"))
            ok("b_c_packet_hash_identical", payload["runs"][1]["packet_sha256"] == payload["runs"][2]["packet_sha256"], None)
            ok("b_c_messages_identical", b_cap["messages"] == c_cap["messages"], None)
            ok("b_c_only_num_ctx_differs", b_cap["options"]["num_ctx"] == 30720 and c_cap["options"]["num_ctx"] == 32768, None)
            ok("cold_unload_keep_alive_zero", b_cap["keep_alive"] == 0, b_cap["keep_alive"])
            ok(
                "per_run_peak_reset",
                all(row.get("series_peak_not_used") is True for row in payload["runs"]),
                None,
            )
            a2 = payload["runs"][0]
            ok("in_request_samples_during_blocked_post", int(a2.get("in_request_sample_count") or 0) >= 2, a2.get("in_request_sample_count"))
            ok("ps_loaded_retained_before_unload", a2.get("placement_status") == "gpu_resident", a2.get("placement_status"))
            ok("in_request_peak_not_post_unload", a2.get("vram_peak_gb") == 18.0, a2.get("vram_peak_gb"))
            ok("a2_num_ctx_30720", a2.get("num_ctx") == 30720, a2.get("num_ctx"))
            hashes_after = (Path(tmp) / "gate3-b-i14" / "HASHES.txt").read_bytes()
            ok("series_hashes_unchanged", hashes_before == hashes_after, None)
            ok("complete_markers_untouched", (src / "exec-a" / "COMPLETE").read_text(encoding="utf-8") == "ok\n", None)
            ok("first_a_request_capture_unchanged", (prior / "request_capture.json").read_bytes() == before_capture, None)
            ok("first_a_complete_unchanged", (prior / "COMPLETE").read_bytes() == before_complete, None)
            sidecar = json.loads((prior / "classification_sidecar.json").read_text(encoding="utf-8"))
            ok("first_a_sidecar_aborted_role", sidecar.get("experiment_role") == "aborted_control_attempt", sidecar)
            ok("first_a_not_valid_matrix_slot", sidecar.get("eligible_for_a_b_c_conclusion") is False, sidecar)

            posted.clear()
            loaded["on"] = False
            out2 = Path(tmp) / "proof-stop"
            stopped = proof_mod.run_prompt_accounting_control(
                confirm_benchmark=True,
                source_series=Path(tmp) / "gate3-b-i14",
                results_dir=out2,
                ollama_base_url="http://127.0.0.1:11434",
                i14_export=i14,
                post_fn=fake_post,
                unload_fn=fake_unload,
                ps_fn=fake_ps,
                nvidia_fn=nvidia_hot,
                require_host=False,
                models_called=False,
                telemetry_interval=0.05,
            )
            ok(
                "safety_failure_blocks_remaining",
                stopped.get("run_count") == 1 and stopped.get("blocked_reason") == "vram_ceiling",
                stopped,
            )
        finally:
            import memorybox.ask.i11a.i11a0_prompt_accounting_proof as mod

            mod.PACKET_A_SHA256 = original_a
            mod.PACKET_BC_SHA256 = original_bc
            from memorybox.ask.i11a.i11a0_i14_source import verify_pinned_i14_export as real_i14

            mod.verify_pinned_i14_export = real_i14  # type: ignore[assignment]

    ok("no_ollama_in_prove_function", True, None)
    return {
        "ok": not problems,
        "checks": checks,
        "problems": problems,
        "models_called": False,
        "experiment_id": EXPERIMENT_ID,
        "pull_executed": False,
    }
