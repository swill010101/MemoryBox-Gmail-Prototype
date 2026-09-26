"""Gate 2 smoke runner. One installed-model generate. No pull. No Stage 1."""
from __future__ import annotations

import json
import subprocess
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
    run_identity,
)
from memorybox.ask.i11a.i11a0_prompt import SYSTEM_PROMPT, render_user_message

PINNED_C_DIGEST = "08ae7ec1744bd7f451c4a530afb39d2673ad9d07a8369b8a33a3613b41212a68"


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


def _nvidia_used_gb() -> float | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    line = (completed.stdout or "").strip().splitlines()
    if not line:
        return None
    try:
        return float(line[0].strip()) / 1024.0
    except ValueError:
        return None


def _ollama_vram_gb(base_url: str, tag: str) -> float | None:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/ps", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None
    peak = None
    for model in payload.get("models") or []:
        name = str(model.get("name") or model.get("model") or "")
        if tag not in name:
            continue
        size = model.get("size_vram")
        if size is None:
            continue
        gb = float(size) / (1024 ** 3)
        peak = gb if peak is None else max(peak, gb)
    return peak


def _peak_vram_gb(base_url: str, tag: str, current: float | None) -> float | None:
    samples = [value for value in (current, _nvidia_used_gb(), _ollama_vram_gb(base_url, tag)) if value is not None]
    return max(samples) if samples else None


def _unload(base_url: str, tag: str) -> None:
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
        return


def _chat(request: RunRequest, *, base_url: str, timeout: int) -> tuple[Measurement, str]:
    user = render_user_message(
        packet_id=f"{request.model_tag}-{request.requested_evidence_tokens}-{request.warm_or_cold}-{request.repetition}",
        packet_role="smoke",
        time_start=request.time_start,
        time_end=request.time_end,
        partial_context=request.partial_context,
        partial_boundary_note=request.partial_boundary_note,
        evidence_ids=list(request.evidence_ids),
        evidence_text=request.evidence_text,
    )
    payload = {
        "model": request.model_tag,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "think": False,
        "keep_alive": "0",
        "options": {
            "num_ctx": request.num_ctx,
            "num_predict": request.reserved_output_tokens,
            "temperature": 0.1,
            "seed": request.seed,
        },
    }
    encoded = json.dumps(payload).encode("utf-8")
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
    peak = _peak_vram_gb(base_url, request.model_tag, None)
    samples = 0
    try:
        with urllib.request.urlopen(http, timeout=timeout) as response:
            for raw in response:
                samples += 1
                if samples == 1 or samples % 25 == 0:
                    peak = _peak_vram_gb(base_url, request.model_tag, peak)
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
                if event.get("done"):
                    peak = _peak_vram_gb(base_url, request.model_tag, peak)
                    break
    except urllib.error.HTTPError as exc:
        measurement = Measurement(
            elapsed_seconds=time.monotonic() - started,
            infrastructure_failure=True,
            peak_vram_gb=peak,
        )
        return measurement, f"HTTP {exc.code}", events
    except (urllib.error.URLError, TimeoutError) as exc:
        measurement = Measurement(
            elapsed_seconds=time.monotonic() - started,
            infrastructure_failure=True,
            timed_out=True,
            peak_vram_gb=peak,
        )
        return measurement, str(exc), events
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
    gpu_resident = True
    if peak is not None and peak >= 22.5:
        gpu_resident = False
    measurement = Measurement(
        prompt_tokens_per_second=prompt_tps,
        generation_tokens_per_second=gen_tps,
        elapsed_seconds=elapsed,
        peak_vram_gb=peak,
        gpu_resident=gpu_resident,
        cpu_spill=bool(peak is not None and peak < 1.0 and gen_n > 0),
        prompt_eval_count=prompt_n or None,
        truncated=bool(last.get("done_reason") == "length"),
    )
    return measurement, "".join(chunks), events


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


def _select_installed_smoke_model(config_models: tuple[ModelSpec, ...], inventory: dict[str, Any]) -> ModelSpec:
    by_tag = {row["tag"]: row for row in inventory.get("approved") or []}
    for spec in config_models:
        row = by_tag.get(spec.tag)
        if row and row.get("status") == "installed" and row.get("accepted_for_screen"):
            digest = str(row.get("digest") or spec.digest)
            if spec.tag == "gemma4:26b" and digest != PINNED_C_DIGEST:
                raise I11A0Error(f"gemma4:26b digest is not the pinned Gate 1 digest: {digest}")
            return ModelSpec(
                config_id=spec.config_id,
                tag=spec.tag,
                quantization=spec.quantization or str(row.get("quantization") or ""),
                digest=digest,
                alias=spec.alias,
            )
    raise I11A0Error(
        "Gate 2 smoke needs an installed approved model. Configuration C is present on FlightSim; "
        "A and B were missing and were not pulled."
    )


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
    inventory = inventory_installed_models(base_url=ollama_base_url)
    if inventory.get("pull_executed"):
        raise I11A0Error("inventory reported a pull")
    chosen = _select_installed_smoke_model(config.models, inventory)
    config = replace(config, models=(chosen,))
    pieces = _pieces_from_review(Path(chunks_root))
    source = PeggyPacketSource(pieces)
    installed = {
        chosen.tag: {
            "digest": chosen.digest,
            "quantization": chosen.quantization,
            "resident_gb": 12.0,
        }
    }
    recorded: dict[str, Any] = {"events": [], "unload_recorded": False}

    def runner(request: RunRequest) -> tuple[Measurement, str]:
        measurement, narration, events = _chat(
            request, base_url=ollama_base_url, timeout=config.timeout_seconds
        )
        recorded["events"] = events
        recorded["request"] = request
        return measurement, narration

    try:
        payload = run_authorized_stage(
            config=config,
            runner=runner,
            lifecycle=ScriptedLifecycle(installed),
            counter=DiagnosticTokenCounter(),
            source=source,
            results_dir=results_dir,
            prompt_tokens=config.prompt_instruction_tokens or 1,
        )
    finally:
        _unload(ollama_base_url, chosen.tag)
        recorded["unload_recorded"] = True
    run_id = str(payload.get("run_id") or "")
    folder = Path(results_dir) / run_id if run_id else Path(results_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "raw_api.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in recorded.get("events") or []),
        encoding="utf-8",
        newline="\n",
    )
    (folder / "telemetry.jsonl").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "endpoint": "/api/chat",
                "inference": True,
                "purpose": "authorized_gate2_smoke_generation",
                "model": chosen.tag,
                "digest": chosen.digest,
                "elapsed_seconds": (payload.get("token_accounting") or {}).get("elapsed_seconds"),
            }
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    approved = {row["config_id"]: row for row in inventory.get("approved") or []}
    missing = [
        row["config_id"]
        for row in inventory.get("approved") or []
        if row.get("status") != "installed"
    ]
    gemma_only = chosen.config_id == "C" and missing
    payload.update(
        {
            "gate": "2",
            "command_kind": "preliminary_gemma_pipeline_check" if gemma_only else "gate2_smoke",
            "gate2_complete": False if gemma_only else True,
            "preliminary_gemma_pipeline_check": bool(gemma_only),
            "full_context_ladder_blocked": True,
            "model_tag": chosen.tag,
            "model_digest": chosen.digest,
            "models_called": True,
            "pull_executed": False,
            "thinking_mode": "off",
            "prompt_accepted": False,
            "token_estimator_formula": TOKEN_ESTIMATOR_FORMULA,
            "token_estimator_id": TOKEN_ESTIMATOR_ID,
            "token_estimator_label": TOKEN_ESTIMATOR_LABEL,
            "actual_count_source": "recorded_smoke_generation_prompt_eval_count",
            "hidden_token_eval_generations": 0,
            "chunks_root": str(chunks_root),
            "results_dir": str(results_dir),
            "installed_configurations": approved,
            "missing_configurations": missing,
            "models_in_this_command": [chosen.tag],
            "lifecycle_unload_recorded": recorded["unload_recorded"],
        }
    )
    return payload
