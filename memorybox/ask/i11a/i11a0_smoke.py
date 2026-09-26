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
    GATE2_SMOKE_AUTHORIZED,
    EvidencePiece,
    EvidenceTurn,
    GateNotAuthorized,
    I11A0Error,
    InferenceNotAuthorized,
    Measurement,
    ModelSpec,
    RunRequest,
    ScriptedLifecycle,
    TokenCount,
    UncertainTokenCount,
    inventory_installed_models,
    inventory_peggy_chunks,
    load_config,
    pack_conversation_intact,
    run_authorized_stage,
)
from memorybox.ask.i11a.i11a0_prompt import SYSTEM_PROMPT, render_user_message

PINNED_C_DIGEST = "08ae7ec1744bd7f451c4a530afb39d2673ad9d07a8369b8a33a3613b41212a68"


class OllamaTokenCounter:
    def __init__(self, *, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def count(self, text: str, *, model: str) -> TokenCount:
        payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/tokenize",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise UncertainTokenCount(f"tokenize failed HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise UncertainTokenCount(f"tokenize unavailable: {exc}") from exc
        tokens = body.get("tokens")
        if not isinstance(tokens, list):
            raise UncertainTokenCount("tokenize response had no token list")
        return TokenCount(tokens=len(tokens), method="ollama_tokenize", certain=True, model=model)


class PeggyPacketSource:
    def __init__(self, pieces: list[EvidencePiece]) -> None:
        self.pieces = pieces

    def materialize(self, *, model: str, target_tokens: int, counter: Any) -> Any:
        return pack_conversation_intact(
            self.pieces, target_tokens=target_tokens, counter=counter, model=model
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
    last: dict[str, Any] = {}
    started = time.monotonic()
    peak = _nvidia_used_gb()
    try:
        with urllib.request.urlopen(http, timeout=timeout) as response:
            for raw in response:
                sample = _nvidia_used_gb()
                if sample is not None:
                    peak = sample if peak is None else max(peak, sample)
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                event = json.loads(line)
                last = event
                message = event.get("message") or {}
                piece = message.get("content")
                if piece:
                    chunks.append(str(piece))
                if event.get("done"):
                    break
    except urllib.error.HTTPError as exc:
        measurement = Measurement(
            elapsed_seconds=time.monotonic() - started,
            infrastructure_failure=True,
            peak_vram_gb=peak,
        )
        return measurement, f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError) as exc:
        measurement = Measurement(
            elapsed_seconds=time.monotonic() - started,
            infrastructure_failure=True,
            timed_out=True,
            peak_vram_gb=peak,
        )
        return measurement, str(exc)
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
    return measurement, "".join(chunks)


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
    counter = OllamaTokenCounter(base_url=ollama_base_url)
    source = PeggyPacketSource(pieces)
    installed = {
        chosen.tag: {
            "digest": chosen.digest,
            "quantization": chosen.quantization,
            "resident_gb": 12.0,
        }
    }

    def runner(request: RunRequest) -> tuple[Measurement, str]:
        return _chat(request, base_url=ollama_base_url, timeout=config.timeout_seconds)

    try:
        payload = run_authorized_stage(
            config=config,
            runner=runner,
            lifecycle=ScriptedLifecycle(installed),
            counter=counter,
            source=source,
            results_dir=results_dir,
            prompt_tokens=config.prompt_instruction_tokens or 1,
        )
    finally:
        _unload(ollama_base_url, chosen.tag)
    payload.update(
        {
            "gate": "2",
            "model_tag": chosen.tag,
            "model_digest": chosen.digest,
            "models_called": True,
            "pull_executed": False,
            "thinking_mode": "off",
            "prompt_accepted": False,
            "chunks_root": str(chunks_root),
            "results_dir": str(results_dir),
        }
    )
    return payload
