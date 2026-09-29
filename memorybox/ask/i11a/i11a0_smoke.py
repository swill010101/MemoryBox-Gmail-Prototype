"""Gate 2 smoke runner. One installed-model generate. No pull. No Stage 1."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.c1t_benchmark import parse_conversations
from memorybox.ask.i11a.i11a0_benchmark import (
    DiagnosticTokenCounter,
    GATE2_SMOKE_AUTHORIZED,
    TOKEN_ESTIMATOR_FORMULA,
    TOKEN_ESTIMATOR_ID,
    TOKEN_ESTIMATOR_LABEL,
    EvidencePiece,
    EvidenceTurn,
    GateNotAuthorized,
    I11A0Error,
    InferenceNotAuthorized,
    MaterializedEvidence,
    Measurement,
    ModelSpec,
    RunRequest,
    ScriptedLifecycle,
    _sha256_text,
    estimate_tokens,
    inventory_installed_models,
    inventory_peggy_chunks,
    load_config,
    run_authorized_stage,
)
from memorybox.ask.i11a.i11a0_host import (
    HardwareSampler,
    VRAM_CEILING_GB,
    collect_host_affinity_preflight,
    require_flightsim_host_affinity,
)
from memorybox.ask.i11a.i11a0_prompt import SYSTEM_PROMPT, prompt_acceptance_fields, render_user_message
from memorybox.ask.i11a.i11a0_prompt_accounting_audit import request_capture_payload

PINNED_C_DIGEST = "08ae7ec1744bd7f451c4a530afb39d2673ad9d07a8369b8a33a3613b41212a68"
REPO_ROOT = Path(__file__).resolve().parents[3]
VRAM_RELEASE_SLACK_GB = 2.0
GEMMA_PACKET_SHA256 = "1c24eb2fa792e553cef299653b6c20e186da9685ea4e7ac78763f3d36df7b690"
INITIAL_A_EXECUTION_ID = (
    "c1cd10594705ff1f1ac7f89bd8a4325c9a432017553b179abb5c2a2d7ff51b0f"
)
INITIAL_B_EXECUTION_ID = (
    "85644304f430bf48bb07b97e30cbb7336e6aa49fcc365228c064618970f3662b"
)
PINNED_A_DIGEST = "19e422b0231392335cfc49cfd172de7034bb1aeabb08aa307cce745c60b272fe"
PINNED_B_DIGEST = "304bf7349c71ad37a07eec8be67212b3f05b0f243f4a6f7c98e90dd2f3009f48"
CALIBRATED_A_EXECUTION_ID = (
    "a1b6b4b2ce743fdb6836381e8b443a501439d80fcd0bc25f72ba827ee5a8c124"
)
GEMMA_FLIGHTSIM_EXECUTION_ID = (
    "b62ec91636cdc3cf9e6a89167e1e78545f5e0ad99014a6a1afce5fa2690c39c6"
)


def require_qwen_smoke_configuration(spec: ModelSpec, row: dict[str, Any]) -> dict[str, Any]:
    """Refuse a Qwen smoke unless the installed metadata matches A or B."""
    metadata = dict(row.get("metadata") or {})
    quant = str(row.get("quantization") or metadata.get("quantization") or spec.quantization or "")
    parameter_size = str(metadata.get("parameter_size") or row.get("parameter_size") or "")
    architecture = str(metadata.get("architecture") or row.get("architecture") or "")
    tag = spec.tag
    if spec.config_id == "A":
        if tag != "qwen3:30b-a3b-instruct-2507-q4_K_M":
            raise I11A0Error(f"configuration A tag mismatch: {tag}")
        if quant != "Q4_K_M":
            raise I11A0Error(f"configuration A quantization mismatch: {quant}")
        lowered = f"{tag} {parameter_size} {architecture}".lower()
        if "a3b" not in lowered or "30" not in lowered:
            raise I11A0Error(
                "configuration A is not Qwen3-30B-A3B-Instruct-2507 Q4_K_M: "
                f"parameter_size={parameter_size} architecture={architecture}"
            )
    elif spec.config_id == "B":
        if tag != "qwen3:14b-q8_0":
            raise I11A0Error(f"configuration B tag mismatch: {tag}")
        if quant != "Q8_0":
            raise I11A0Error(f"configuration B quantization mismatch: {quant}")
        lowered = f"{tag} {parameter_size} {architecture}".lower()
        if "14" not in lowered:
            raise I11A0Error(
                "configuration B is not Qwen3 14B Q8_0: "
                f"parameter_size={parameter_size} architecture={architecture}"
            )
        if "a3b" in lowered or "moe" in lowered:
            raise I11A0Error("configuration B must be dense Qwen3 14B, not an MoE substitute")
    else:
        raise I11A0Error(f"Qwen smoke verification does not accept {spec.config_id}")
    metadata.update(
        {
            "config_id": spec.config_id,
            "tag": tag,
            "digest": spec.digest or row.get("digest"),
            "quantization": quant,
            "verified": True,
        }
    )
    return metadata


def refuse_inherited_num_ctx(
    config_id: str,
    configured_num_ctx: int | None,
    config_model_ids: tuple[str, ...] = (),
) -> None:
    if configured_num_ctx is None:
        return
    others = set(config_model_ids) - {config_id}
    if config_id == "B" and others:
        raise I11A0Error(
            "Configuration B must not reuse Configuration A's calibrated num_ctx; "
            "plan B from the estimator and this model's recorded prompt_eval_count"
        )


def write_model_specific_calibration(
    run_dir: Path,
    *,
    config_id: str,
    tag: str,
    calibrated_num_ctx: int = 6144,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record tokenizer calibration beside a first smoke. Do not rewrite run files."""
    run_dir = Path(run_dir)
    record = json.loads((run_dir / "run_record.json").read_text(encoding="utf-8"))
    measurement = record.get("measurement") or {}
    identity = str(record.get("execution_id") or record.get("identity") or run_dir.name)
    hashes = {
        name: hashlib.sha256((run_dir / name).read_bytes()).hexdigest()
        for name in ("run_record.json", "token_accounting.json", "narration.txt", "raw_api.jsonl")
        if (run_dir / name).exists()
    }
    payload = {
        "kind": "model_specific_calibration",
        "config_id": config_id,
        "tag": tag,
        "legacy_execution_id": identity,
        "classification": record.get("classification"),
        "pipeline_execution": "passed",
        "generation_completion": "passed",
        "hardware_telemetry_valid": True,
        "full_safety_margin": "failed",
        "estimated_prompt_tokens": measurement.get("estimated_prompt_tokens"),
        "actual_prompt_tokens": measurement.get("actual_prompt_tokens")
        or measurement.get("prompt_eval_count"),
        "estimation_error_tokens": measurement.get("estimation_error_tokens")
        or measurement.get("token_error"),
        "required_context_tokens": measurement.get("required_context_tokens"),
        "configured_num_ctx": measurement.get("configured_num_ctx"),
        "safety_margin_shortfall_tokens": measurement.get("safety_margin_shortfall_tokens"),
        "calibrated_num_ctx": calibrated_num_ctx,
        "original_files_unmodified": True,
        "original_artifact_sha256": hashes,
    }
    payload.update(extra or {})
    dest = run_dir / "model_specific_calibration.json"
    dest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return payload


def write_qwen_a_initial_calibration(run_dir: Path) -> dict[str, Any]:
    return write_model_specific_calibration(
        run_dir,
        config_id="A",
        tag="qwen3:30b-a3b-instruct-2507-q4_K_M",
        extra={"do_not_apply_to_configuration_b": True},
    )


def write_qwen_b_initial_calibration(run_dir: Path) -> dict[str, Any]:
    return write_model_specific_calibration(
        run_dir,
        config_id="B",
        tag="qwen3:14b-q8_0",
        extra={
            "do_not_reuse_configuration_a_error": True,
            "estimation_error_is_model_specific": True,
        },
    )


def _select_installed_smoke_models(config_models: tuple[ModelSpec, ...], inventory: dict[str, Any]) -> list[ModelSpec]:
    by_tag = {row["tag"]: row for row in inventory.get("approved") or []}
    selected: list[ModelSpec] = []
    missing: list[str] = []
    for spec in config_models:
        row = by_tag.get(spec.tag)
        if not (row and row.get("status") == "installed" and row.get("accepted_for_screen")):
            missing.append(spec.tag)
            continue
        digest = str(row.get("digest") or spec.digest or "")
        if spec.tag == "gemma4:26b" and digest != PINNED_C_DIGEST:
            raise I11A0Error(f"gemma4:26b digest is not the pinned Gate 1 digest: {digest}")
        if (
            spec.tag == "qwen3:30b-a3b-instruct-2507-q4_K_M"
            and len(digest) == 64
            and digest != PINNED_A_DIGEST
        ):
            raise I11A0Error(f"configuration A digest is not the recorded Gate 2 digest: {digest}")
        if (
            spec.tag == "qwen3:14b-q8_0"
            and len(digest) == 64
            and digest != PINNED_B_DIGEST
        ):
            raise I11A0Error(f"configuration B digest is not the recorded Gate 2 digest: {digest}")
        filled = ModelSpec(
            config_id=spec.config_id,
            tag=spec.tag,
            quantization=spec.quantization or str(row.get("quantization") or ""),
            digest=digest,
            alias=spec.alias,
        )
        if filled.config_id in {"A", "B"}:
            require_qwen_smoke_configuration(filled, row)
        selected.append(filled)
    if missing:
        raise I11A0Error(
            "Gate 2 smoke needs the configured models installed and accepted. Missing: "
            + ", ".join(missing)
        )
    if not selected:
        raise I11A0Error("Gate 2 smoke needs an installed approved model")
    return selected


def _select_installed_smoke_model(config_models: tuple[ModelSpec, ...], inventory: dict[str, Any]) -> ModelSpec:
    return _select_installed_smoke_models(config_models, inventory)[0]


class PeggyPacketSource:
    """Build one candidate packet with the cheap estimator only. No Ollama eval."""

    def __init__(self, pieces: list[EvidencePiece]) -> None:
        self.pieces = pieces

    def materialize(self, *, model: str, target_tokens: int, counter: Any) -> MaterializedEvidence:
        chosen: list[EvidencePiece] = []
        for piece in self.pieces:
            trial = chosen + [piece]
            trial_text = "\n\n".join(item.render() for item in trial)
            if chosen and estimate_tokens(trial_text) > target_tokens:
                break
            if estimate_tokens(piece.render()) > target_tokens:
                continue
            chosen.append(piece)
        if not chosen:
            raise I11A0Error("no conversation fits the smoke target")
        text = "\n\n".join(item.render() for item in chosen)
        ids = tuple(evidence_id for item in chosen for evidence_id in item.evidence_ids)
        estimated = estimate_tokens(text)
        return MaterializedEvidence(
            text=text,
            sha256=_sha256_text(text),
            estimated_evidence_tokens=estimated,
            evidence_ids=ids,
            partial_context=False,
            partial_boundary_note="none",
            time_start=min(item.earliest for item in chosen),
            time_end=max(item.latest for item in chosen),
            certain=False,
        )


def _unload(base_url: str, tag: str) -> float:
    started = time.monotonic()
    payload = json.dumps({"model": tag, "keep_alive": 0}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=30).read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        pass
    return time.monotonic() - started


def _chat(
    request: RunRequest,
    *,
    base_url: str,
    timeout: int,
    sampler: HardwareSampler,
    packet_role: str = "smoke",
    on_stream_phase: Any = None,
    on_first_token: Any = None,
    keep_alive: Any = 0,
    system_text: str | None = None,
    user_text: str | None = None,
) -> tuple[Measurement, str, list[dict[str, Any]], dict[str, Any]]:
    system_text = SYSTEM_PROMPT if system_text is None else system_text
    if user_text is None:
        packet_id = request.model_visible_packet_id or (
            f"{request.model_tag}-{request.requested_evidence_tokens}-"
            f"{request.warm_or_cold}-{request.repetition}"
        )
        user_text = render_user_message(
            packet_id=packet_id,
            packet_role=packet_role,
            time_start=request.time_start,
            time_end=request.time_end,
            partial_context=request.partial_context,
            partial_boundary_note=request.partial_boundary_note,
            evidence_ids=list(request.evidence_ids),
            evidence_text=request.evidence_text,
        )
    user = user_text
    payload = {
        "model": request.model_tag,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "think": False,
        "keep_alive": keep_alive,
        "truncate": False,
        "shift": False,
        "options": {
            "num_ctx": request.num_ctx,
            "num_predict": request.reserved_output_tokens,
            "temperature": 0.1,
            "seed": request.seed,
        },
    }
    capture = request_capture_payload(
        system_text=system_text,
        user_text=user,
        evidence_text=request.evidence_text or "",
        options=payload["options"],
        model_tag=request.model_tag,
        digest=request.digest,
        execution_id=str(getattr(request, "execution_id", "") or ""),
        test_case_id=str(getattr(request, "test_case_id", "") or ""),
        keep_alive=keep_alive,
    )
    capture["request_json"] = payload
    capture["truncate_top_level"] = payload.get("truncate") is False
    capture["shift_top_level"] = payload.get("shift") is False
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    capture["request_body_sha256"] = hashlib.sha256(encoded).hexdigest()
    capture["request_body_bytes"] = len(encoded)
    capture["request_body_contains_full_evidence"] = (request.evidence_text or "") in user
    http = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    chunks: list[str] = []
    events: list[dict[str, Any]] = []
    last: dict[str, Any] = {}
    started = time.monotonic()
    sampler.capture("generate_start")
    samples = 0
    announced_generation = False
    try:
        with urllib.request.urlopen(http, timeout=timeout) as response:
            for raw in response:
                samples += 1
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                event = json.loads(line)
                events.append(event)
                last = event
                message = event.get("message") or {}
                piece = message.get("content")
                if piece:
                    chunks.append(str(piece))
                    if not announced_generation:
                        announced_generation = True
                        if on_stream_phase is not None:
                            on_stream_phase("generation")
                        if on_first_token is not None:
                            on_first_token()
                if event.get("done"):
                    sampler.capture("generate_done")
                    break
    except urllib.error.HTTPError as exc:
        measurement = Measurement(
            elapsed_seconds=time.monotonic() - started,
            infrastructure_failure=True,
            peak_vram_gb=sampler.summary().get("vram_peak_gb"),
        )
        return measurement, f"HTTP {exc.code}", events, capture
    except (urllib.error.URLError, TimeoutError) as exc:
        measurement = Measurement(
            elapsed_seconds=time.monotonic() - started,
            infrastructure_failure=True,
            timed_out=True,
            peak_vram_gb=sampler.summary().get("vram_peak_gb"),
        )
        return measurement, str(exc), events, capture
    elapsed = time.monotonic() - started
    prompt_n = int(last.get("prompt_eval_count") or 0)
    gen_n = int(last.get("eval_count") or 0)
    prompt_ns = last.get("prompt_eval_duration")
    gen_ns = last.get("eval_duration")
    prompt_tps = None
    gen_tps = None
    if prompt_n and isinstance(prompt_ns, (int, float)) and prompt_ns > 0:
        prompt_tps = prompt_n / (float(prompt_ns) / 1e9)
    if gen_n and isinstance(gen_ns, (int, float)) and gen_ns > 0:
        gen_tps = gen_n / (float(gen_ns) / 1e9)
    hardware = sampler.summary()
    peak = hardware.get("vram_peak_gb")
    measurement = Measurement(
        prompt_tokens_per_second=prompt_tps,
        generation_tokens_per_second=gen_tps,
        elapsed_seconds=elapsed,
        peak_vram_gb=peak,
        gpu_resident=bool(hardware.get("gpu_resident")),
        cpu_spill=bool(hardware.get("cpu_offload")),
        prompt_eval_count=prompt_n or None,
        truncated=bool(last.get("done_reason") == "length"),
    )
    return measurement, "".join(chunks), events, capture


def _pieces_from_review(root: Path) -> list[EvidencePiece]:
    source_map_path = root / "SOURCE_MAP.json"
    if not source_map_path.is_file():
        raise I11A0Error(f"SOURCE_MAP.json missing under {root}")
    source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
    inventory = inventory_peggy_chunks([root])
    if not inventory.get("exactly_seven"):
        raise I11A0Error("Gate 2 smoke requires the seven reviewed Peggy chunks")
    pieces: list[EvidencePiece] = []
    for row in inventory["chunks"]:
        text = Path(row["path"]).read_text(encoding="utf-8", errors="replace")
        _prefix, conversations = parse_conversations(text, source_map)
        for conversation in conversations:
            turns = tuple(
                EvidenceTurn(turn.cite_as, turn.text, conversation.earliest)
                for turn in conversation.turns
            )
            pieces.append(
                EvidencePiece(
                    piece_id=conversation.conversation_id,
                    turns=turns,
                    earliest=conversation.earliest,
                    latest=conversation.latest,
                )
            )
    pieces.sort(key=lambda item: (item.earliest, item.piece_id))
    return pieces


def _write_smoke_artifacts(
    *,
    folder: Path,
    preflight: dict[str, Any],
    recorded: dict[str, Any],
    hardware: dict[str, Any],
    payload: dict[str, Any],
    chosen: ModelSpec,
    metadata: dict[str, Any] | None,
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    last = recorded.get("last_event") or {}
    run_id = str(payload.get("run_id") or folder.name)
    (folder / "host_affinity_preflight.json").write_text(
        json.dumps(preflight, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (folder / "model_metadata.json").write_text(
        json.dumps(metadata or {}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (folder / "raw_api.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in recorded.get("events") or []),
        encoding="utf-8",
        newline="\n",
    )
    (folder / "hardware_telemetry.json").write_text(
        json.dumps(hardware, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (folder / "telemetry.jsonl").write_text(
        "".join(json.dumps(sample) + "\n" for sample in hardware.get("samples") or [])
        + json.dumps(
            {
                "run_id": run_id,
                "execution_id": payload.get("execution_id") or run_id,
                "test_case_id": payload.get("test_case_id"),
                "endpoint": "/api/chat",
                "inference": True,
                "purpose": "authorized_gate2_flightsim_hardware_smoke",
                "model": chosen.tag,
                "digest": chosen.digest,
                "host_affinity": "flightsim_rtx_4090_local",
                "elapsed_seconds": (payload.get("token_accounting") or {}).get("elapsed_seconds"),
                "load_duration_ns": last.get("load_duration"),
                "prompt_eval_duration_ns": last.get("prompt_eval_duration"),
                "eval_duration_ns": last.get("eval_duration"),
                "total_duration_ns": last.get("total_duration"),
                "unload_seconds": recorded.get("unload_seconds"),
                "vram_peak_gb": hardware.get("vram_peak_gb"),
                "vram_after_unload_gb": hardware.get("vram_final_gb"),
                "cpu_offload": hardware.get("cpu_offload"),
                "exceeds_vram_ceiling": hardware.get("exceeds_vram_ceiling"),
            }
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _smoke_failed(payload: dict[str, Any], hardware: dict[str, Any]) -> str | None:
    if hardware.get("exceeds_vram_ceiling"):
        return "vram_ceiling"
    if hardware.get("cpu_offload"):
        return "cpu_offload"
    if payload.get("classification") not in {None, "successful_stable", "resumed_skip"} and payload.get(
        "stop_reason"
    ) not in {"smoke_complete"}:
        return str(payload.get("stop_reason") or payload.get("classification") or "smoke_failed")
    accounting = payload.get("token_accounting") or {}
    if accounting.get("final_safety_result") not in {None, "passed"}:
        return "safety_margin_failed"
    if payload.get("ok") is False:
        return str(payload.get("stop_reason") or "smoke_failed")
    return None


def _vram_released(baseline: float | None, final: float | None) -> bool:
    if baseline is None or final is None:
        return False
    return float(final) <= float(baseline) + VRAM_RELEASE_SLACK_GB


def _smoke_one_model(
    *,
    config,
    chosen: ModelSpec,
    inventory_row: dict[str, Any],
    source: PeggyPacketSource,
    results: Path,
    ollama_base_url: str,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    ids = tuple(spec.config_id for spec in config.models)
    refuse_inherited_num_ctx(chosen.config_id, config.configured_num_ctx, ids)
    metadata = dict(inventory_row.get("metadata") or {})
    if chosen.config_id in {"A", "B"}:
        metadata = require_qwen_smoke_configuration(chosen, inventory_row)
    model_results = results / chosen.config_id
    model_results.mkdir(parents=True, exist_ok=True)
    installed = {
        chosen.tag: {
            "digest": chosen.digest,
            "quantization": chosen.quantization,
            "resident_gb": 12.0,
        }
    }
    sampler = HardwareSampler()
    sampler.capture("baseline")
    recorded: dict[str, Any] = {
        "events": [],
        "unload_recorded": False,
        "unload_seconds": None,
        "hardware": None,
    }

    def runner(request: RunRequest) -> tuple[Measurement, str]:
        measurement, narration, events, _capture = _chat(
            request,
            base_url=ollama_base_url,
            timeout=config.timeout_seconds,
            sampler=sampler,
        )
        recorded["events"] = events
        recorded["request"] = request
        recorded["last_event"] = events[-1] if events else {}
        return measurement, narration

    inherited_b = chosen.config_id == "B" and set(ids) - {"B"}
    one_config = replace(
        config,
        models=(chosen,),
        configured_num_ctx=None if inherited_b else config.configured_num_ctx,
    )
    try:
        payload = run_authorized_stage(
            config=one_config,
            runner=runner,
            lifecycle=ScriptedLifecycle(installed),
            counter=DiagnosticTokenCounter(),
            source=source,
            results_dir=model_results,
            prompt_tokens=config.prompt_instruction_tokens or 1,
        )
    finally:
        sampler.capture("before_unload")
        recorded["unload_seconds"] = _unload(ollama_base_url, chosen.tag)
        recorded["unload_recorded"] = True
        time.sleep(1.0)
        sampler.capture("after_unload")
    hardware = sampler.summary()
    recorded["hardware"] = hardware
    run_id = str(payload.get("run_id") or "")
    folder = model_results / run_id if run_id else model_results
    _write_smoke_artifacts(
        folder=folder,
        preflight=preflight,
        recorded=recorded,
        hardware=hardware,
        payload=payload,
        chosen=chosen,
        metadata=metadata,
    )
    last = recorded.get("last_event") or {}
    payload.update(
        {
            "config_id": chosen.config_id,
            "model_tag": chosen.tag,
            "model_digest": chosen.digest,
            "model_metadata": metadata,
            "results_dir": str(model_results),
            "artifact_dir": str(folder),
            "lifecycle_unload_recorded": recorded["unload_recorded"],
            "unload_seconds": recorded["unload_seconds"],
            "load_duration_ns": last.get("load_duration"),
            "prompt_eval_duration_ns": last.get("prompt_eval_duration"),
            "eval_duration_ns": last.get("eval_duration"),
            "total_duration_ns": last.get("total_duration"),
            "hardware_telemetry": {
                "vram_baseline_gb": hardware.get("vram_baseline_gb"),
                "vram_peak_gb": hardware.get("vram_peak_gb"),
                "vram_final_gb": hardware.get("vram_final_gb"),
                "ram_baseline_gb": hardware.get("ram_baseline_gb"),
                "ram_peak_gb": hardware.get("ram_peak_gb"),
                "ram_final_gb": hardware.get("ram_final_gb"),
                "cpu_offload": hardware.get("cpu_offload"),
                "gpu_resident": hardware.get("gpu_resident"),
                "exceeds_vram_ceiling": hardware.get("exceeds_vram_ceiling"),
                "vram_released": _vram_released(
                    hardware.get("vram_baseline_gb"), hardware.get("vram_final_gb")
                ),
                "ceiling_gb": VRAM_CEILING_GB,
            },
        }
    )
    payload["stop_before_next_model"] = _smoke_failed(payload, hardware)
    if payload["stop_before_next_model"] is None and not payload["hardware_telemetry"]["vram_released"]:
        payload["stop_before_next_model"] = "unload_vram_not_released"
    return payload


def run_gate2_smoke(
    *,
    config_path: Path | str,
    chunks_root: Path | str,
    results_dir: Path | str,
    ollama_base_url: str,
    confirm_benchmark: bool,
    stage: str | None,
) -> dict[str, Any]:
    if not GATE2_SMOKE_AUTHORIZED:
        raise InferenceNotAuthorized("Gate 2 smoke is not authorized")
    if not confirm_benchmark:
        raise InferenceNotAuthorized("Gate 2 smoke requires --confirm-benchmark")
    config = load_config(config_path)
    if stage:
        config = replace(config, stage=stage)
    if config.stage != "smoke":
        raise GateNotAuthorized(f"{config.stage} is not authorized; Gate 2 is smoke only")
    if config.thinking_mode != "off":
        raise GateNotAuthorized("Gate 2 smoke is thinking-off only")
    results = Path(results_dir)
    results.mkdir(parents=True, exist_ok=True)
    preflight = collect_host_affinity_preflight(
        ollama_base_url=ollama_base_url,
        output_path=results,
        chunks_path=chunks_root,
        repo=REPO_ROOT,
    )
    (results / "host_affinity_preflight.json").write_text(
        json.dumps(preflight, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    require_flightsim_host_affinity(preflight)
    inventory = inventory_installed_models(base_url=ollama_base_url)
    if inventory.get("pull_executed"):
        raise I11A0Error("inventory reported a pull")
    selected = _select_installed_smoke_models(config.models, inventory)
    by_tag = {row["tag"]: row for row in inventory.get("approved") or []}
    pieces = _pieces_from_review(Path(chunks_root))
    source = PeggyPacketSource(pieces)
    runs: list[dict[str, Any]] = []
    stopped = None
    for chosen in selected:
        payload = _smoke_one_model(
            config=config,
            chosen=chosen,
            inventory_row=by_tag.get(chosen.tag) or {},
            source=source,
            results=results,
            ollama_base_url=ollama_base_url,
            preflight=preflight,
        )
        runs.append(payload)
        stopped = payload.get("stop_before_next_model")
        if stopped:
            break
    approved = {row["config_id"]: row for row in inventory.get("approved") or []}
    missing = [
        row["config_id"]
        for row in inventory.get("approved") or []
        if row.get("status") != "installed"
    ]
    ids = [spec.config_id for spec in selected]
    ab_complete = {"A", "B"}.issubset({row.get("config_id") for row in runs if row.get("ok")})
    gemma_only = ids == ["C"]
    prompt_fields = prompt_acceptance_fields()
    first = runs[0] if runs else {}
    return {
        "ok": bool(runs) and all(row.get("ok") for row in runs) and not stopped,
        "gate": "2",
        "command_kind": "gate2_ab_smoke" if "A" in ids or "B" in ids else (
            "preliminary_gemma_pipeline_check" if gemma_only else "gate2_smoke"
        ),
        "gate2_complete": bool(ab_complete),
        "preliminary_gemma_pipeline_check": bool(gemma_only),
        "full_context_ladder_blocked": True,
        "models_called": True,
        "pull_executed": False,
        "thinking_mode": "off",
        "prompt_status": prompt_fields["prompt_status"],
        "production_prompt_accepted": prompt_fields["production_prompt_accepted"],
        "prompt_accepted": prompt_fields["production_prompt_accepted"],
        "token_estimator_formula": TOKEN_ESTIMATOR_FORMULA,
        "token_estimator_id": TOKEN_ESTIMATOR_ID,
        "token_estimator_label": TOKEN_ESTIMATOR_LABEL,
        "actual_count_source": "recorded_smoke_generation_prompt_eval_count",
        "hidden_token_eval_generations": 0,
        "chunks_root": str(chunks_root),
        "results_dir": str(results),
        "installed_configurations": approved,
        "missing_configurations": missing,
        "models_in_this_command": [row.get("model_tag") for row in runs],
        "host_affinity": preflight,
        "ollama_version": inventory.get("ollama_version"),
        "runs": runs,
        "run_id": first.get("run_id"),
        "execution_id": first.get("execution_id"),
        "test_case_id": first.get("test_case_id"),
        "stop_reason": stopped,
        "flightsim_hardware_smoke": True,
    }

