"""P2-I11A.0 offline sweep controller.

Inventory, token budgets, stop rules, resume, and model-lifecycle planning.
Ollama generation is refused until a later Gate 2 authorization.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from memorybox.ask.i11a.c1t_benchmark import estimate_tokens, parse_conversations
from memorybox.ask.i11a.i11a0_prompt import (
    PROMPT_ACCEPTED,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    prompt_sha256,
    render_user_message,
)

I11A0_VERSION = "0.1-offline"
INFERENCE_AUTHORIZED = False
GATE2_SMOKE_AUTHORIZED = True
TOKEN_ESTIMATOR_ID = "utf8_bytes_plus_3_div_4"
TOKEN_ESTIMATOR_FORMULA = "max(1, (len(text.encode('utf-8')) + 3) // 4)"
TOKEN_ESTIMATOR_LABEL = "estimated"
VRAM_CEILING_GB = 22.5
OUTPUT_RESERVE_TOKENS = 2500
SAFETY_MARGIN_TOKENS = 1500
START_EVIDENCE_TOKENS = 8000
PRIMARY_INCREMENT_TOKENS = 1000
REFINEMENT_INCREMENT_TOKENS = 250
PRODUCTION_MARGIN_MIN = 1000
PRODUCTION_MARGIN_MAX = 2000
REGRESSION_FRACTION = 0.15
ELAPSED_REGRESSION_FRACTION = 0.25
CONFIRMED_REGRESSION_STOP = 3

APPROVED_MODELS: tuple[dict[str, str], ...] = (
    {
        "config_id": "A",
        "tag": "qwen3:30b-a3b-instruct-2507-q4_K_M",
        "alias": "qwen3:30b",
        "quantization": "Q4_K_M",
        "install": "ollama pull qwen3:30b-a3b-instruct-2507-q4_K_M",
    },
    {
        "config_id": "B",
        "tag": "qwen3:14b-q8_0",
        "alias": "",
        "quantization": "Q8_0",
        "install": "ollama pull qwen3:14b-q8_0",
    },
    {
        "config_id": "C",
        "tag": "gemma4:26b",
        "alias": "",
        "quantization": "",
        "install": "ollama pull gemma4:26b",
    },
)

Fetcher = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]


class I11A0Error(RuntimeError):
    """Fail-closed benchmark error. No model call is implied."""


class ThinkingNotAuthorized(I11A0Error):
    pass


class QuantizationNotAuthorized(I11A0Error):
    pass


class GateNotAuthorized(I11A0Error):
    pass


class UncertainTokenCount(I11A0Error):
    pass


class ContextBudgetError(I11A0Error):
    pass


class ModelPullForbidden(I11A0Error):
    pass


class InferenceNotAuthorized(I11A0Error):
    pass


@dataclass(frozen=True)
class TokenCount:
    tokens: int
    method: str
    certain: bool
    model: str


class TokenCounter(Protocol):
    def count(self, text: str, *, model: str) -> TokenCount: ...


@dataclass(frozen=True)
class ModelSpec:
    config_id: str
    tag: str
    quantization: str
    digest: str
    alias: str = ""


@dataclass
class I11A0Config:
    stage: str
    models: tuple[ModelSpec, ...]
    start_input_tokens: int = START_EVIDENCE_TOKENS
    increment_tokens: int = PRIMARY_INCREMENT_TOKENS
    refinement_increment_tokens: int = REFINEMENT_INCREMENT_TOKENS
    maximum_input_tokens: int | None = None
    reserved_output_tokens: int = OUTPUT_RESERVE_TOKENS
    safety_margin_tokens: int = SAFETY_MARGIN_TOKENS
    temperature: float = 0.1
    seed: int = 42
    thinking_mode: str = "off"
    authorize_thinking_comparison: bool = False
    warm_runs_per_size: int = 2
    cold_runs_per_model: int = 1
    timeout_seconds: int = 1800
    maximum_vram_gb: float = VRAM_CEILING_GB
    regression_prompt_fraction: float = REGRESSION_FRACTION
    regression_generation_fraction: float = REGRESSION_FRACTION
    regression_elapsed_fraction: float = ELAPSED_REGRESSION_FRACTION
    regression_run_count: int = CONFIRMED_REGRESSION_STOP
    smoke_evidence_tokens: int = 1000
    prompt_version: str = PROMPT_VERSION
    manage_model_lifecycle: bool = True
    founder_gate3_accepted: bool = False
    founder_gate4_accepted: bool = False
    authorize_alternate_quantization: bool = False
    alternate_quantization_tag: str | None = None
    finalist_tags: tuple[str, ...] = ()
    prompt_instruction_tokens: int = 0

    def validate(self) -> None:
        if self.stage not in {
            "smoke",
            "stage1_capacity",
            "quality_comparison",
            "stage2_finalist",
        }:
            raise I11A0Error(f"unknown stage {self.stage}")
        if self.thinking_mode not in {"off", "on"}:
            raise ThinkingNotAuthorized(
                "thinking_mode must be recorded as off or on; it must not be omitted"
            )
        if self.thinking_mode == "on":
            if not (
                self.authorize_thinking_comparison
                and self.stage == "stage2_finalist"
                and self.founder_gate4_accepted
            ):
                raise ThinkingNotAuthorized(
                    "thinking-on is limited to an authorized Stage 2 finalist comparison"
                )
        if self.alternate_quantization_tag:
            if not (
                self.stage == "stage2_finalist"
                and self.founder_gate4_accepted
                and self.authorize_alternate_quantization
                and self.finalist_tags
            ):
                raise QuantizationNotAuthorized(
                    "alternate quantization waits for Gate 4 finalist selection"
                )
        if self.stage == "quality_comparison" and not self.founder_gate3_accepted:
            raise GateNotAuthorized("quality comparison waits for Gate 3")
        if self.stage == "stage2_finalist" and not self.founder_gate4_accepted:
            raise GateNotAuthorized("finalist refinement waits for Gate 4")
        if self.reserved_output_tokens <= 0 or self.safety_margin_tokens <= 0:
            raise I11A0Error("output reserve and safety margin must be positive")
        if self.warm_runs_per_size < 2 and self.stage == "stage1_capacity":
            raise I11A0Error("stage 1 requires two warm runs per size")
        if not self.models:
            raise I11A0Error("at least one model is required")
        for spec in self.models:
            if not spec.digest:
                raise I11A0Error(f"digest is required for {spec.tag}")


def load_config(path: Path | str) -> I11A0Config:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    models = tuple(
        ModelSpec(
            config_id=str(row["config_id"]),
            tag=str(row["tag"]),
            quantization=str(row.get("quantization") or ""),
            digest=str(row.get("digest") or ""),
            alias=str(row.get("alias") or ""),
        )
        for row in raw.get("models") or []
    )
    return I11A0Config(
        stage=str(raw["stage"]),
        models=models,
        start_input_tokens=int(raw.get("start_input_tokens", START_EVIDENCE_TOKENS)),
        increment_tokens=int(raw.get("increment_tokens", PRIMARY_INCREMENT_TOKENS)),
        refinement_increment_tokens=int(
            raw.get("refinement_increment_tokens", REFINEMENT_INCREMENT_TOKENS)
        ),
        maximum_input_tokens=(
            int(raw["maximum_input_tokens"])
            if raw.get("maximum_input_tokens") is not None
            else None
        ),
        reserved_output_tokens=int(
            raw.get("reserved_output_tokens", OUTPUT_RESERVE_TOKENS)
        ),
        safety_margin_tokens=int(raw.get("safety_margin_tokens", SAFETY_MARGIN_TOKENS)),
        temperature=float(raw.get("temperature", 0.1)),
        seed=int(raw.get("seed", 42)),
        thinking_mode=str(raw.get("thinking_mode", "off")),
        authorize_thinking_comparison=bool(
            raw.get("authorize_thinking_comparison", False)
        ),
        warm_runs_per_size=int(raw.get("warm_runs_per_size", 2)),
        cold_runs_per_model=int(raw.get("cold_runs_per_model", 1)),
        timeout_seconds=int(raw.get("timeout_seconds", 1800)),
        maximum_vram_gb=float(raw.get("maximum_vram_gb", VRAM_CEILING_GB)),
        regression_prompt_fraction=float(raw.get("regression_prompt_fraction", 0.15)),
        regression_generation_fraction=float(
            raw.get("regression_generation_fraction", 0.15)
        ),
        regression_elapsed_fraction=float(raw.get("regression_elapsed_fraction", 0.25)),
        regression_run_count=int(raw.get("regression_run_count", 3)),
        smoke_evidence_tokens=int(raw.get("smoke_evidence_tokens", 1000)),
        prompt_version=str(raw.get("prompt_version", PROMPT_VERSION)),
        manage_model_lifecycle=bool(raw.get("manage_model_lifecycle", True)),
        founder_gate3_accepted=bool(raw.get("founder_gate3_accepted", False)),
        founder_gate4_accepted=bool(raw.get("founder_gate4_accepted", False)),
        authorize_alternate_quantization=bool(
            raw.get("authorize_alternate_quantization", False)
        ),
        alternate_quantization_tag=raw.get("alternate_quantization_tag"),
        finalist_tags=tuple(raw.get("finalist_tags") or ()),
        prompt_instruction_tokens=int(raw.get("prompt_instruction_tokens", 0)),
    )


def default_config_document() -> dict[str, Any]:
    return {
        "stage": "smoke",
        "inference_authorized": False,
        "thinking_mode": "off",
        "authorize_thinking_comparison": False,
        "temperature": 0.1,
        "seed": 42,
        "start_input_tokens": START_EVIDENCE_TOKENS,
        "increment_tokens": PRIMARY_INCREMENT_TOKENS,
        "refinement_increment_tokens": REFINEMENT_INCREMENT_TOKENS,
        "reserved_output_tokens": OUTPUT_RESERVE_TOKENS,
        "safety_margin_tokens": SAFETY_MARGIN_TOKENS,
        "safety_margin_note": (
            "1500 tokens, separate from the 2500 output reserve. "
            "It absorbs chat-template overhead and early tokenizer error. "
            "evidence + prompt/instructions + output reserve + safety margin <= num_ctx. "
            "The production operating margin is chosen later inside 1000-2000 from measurements."
        ),
        "maximum_vram_gb": VRAM_CEILING_GB,
        "warm_runs_per_size": 2,
        "cold_runs_per_model": 1,
        "timeout_seconds": 1800,
        "regression_prompt_fraction": REGRESSION_FRACTION,
        "regression_generation_fraction": REGRESSION_FRACTION,
        "regression_elapsed_fraction": ELAPSED_REGRESSION_FRACTION,
        "regression_run_count": CONFIRMED_REGRESSION_STOP,
        "smoke_evidence_tokens": 1000,
        "token_estimator_id": TOKEN_ESTIMATOR_ID,
        "token_estimator_formula": TOKEN_ESTIMATOR_FORMULA,
        "token_estimator_label": TOKEN_ESTIMATOR_LABEL,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha256(),
        "prompt_accepted": PROMPT_ACCEPTED,
        "models": [
            {
                "config_id": row["config_id"],
                "tag": row["tag"],
                "alias": row["alias"],
                "quantization": row["quantization"],
                "digest": "",
            }
            for row in APPROVED_MODELS
        ],
        "founder_gate3_accepted": False,
        "founder_gate4_accepted": False,
        "authorize_alternate_quantization": False,
        "alternate_quantization_tag": None,
    }


class DiagnosticTokenCounter:
    """bytes/4 estimate. Never authoritative for an evidence-token target."""

    method = "bytes_div_4"

    def count(self, text: str, *, model: str) -> TokenCount:
        return TokenCount(
            tokens=estimate_tokens(text),
            method=self.method,
            certain=False,
            model=model,
        )


def require_certain(count: TokenCount) -> TokenCount:
    if not count.certain:
        raise UncertainTokenCount(
            f"{count.method} cannot control an evidence target for {count.model}"
        )
    return count


@dataclass(frozen=True)
class ContextPlan:
    evidence_tokens: int
    prompt_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int
    num_ctx: int

    @property
    def required(self) -> int:
        return (
            self.evidence_tokens
            + self.prompt_tokens
            + self.reserved_output_tokens
            + self.safety_margin_tokens
        )


def plan_context(
    *,
    evidence_tokens: int,
    prompt_tokens: int,
    reserved_output_tokens: int,
    safety_margin_tokens: int,
    num_ctx: int | None = None,
) -> ContextPlan:
    required = (
        evidence_tokens + prompt_tokens + reserved_output_tokens + safety_margin_tokens
    )
    chosen = required if num_ctx is None else num_ctx
    if required > chosen:
        raise ContextBudgetError(
            "evidence + prompt/instructions + output reserve + safety margin "
            f"({required}) exceeds num_ctx ({chosen})"
        )
    return ContextPlan(
        evidence_tokens=evidence_tokens,
        prompt_tokens=prompt_tokens,
        reserved_output_tokens=reserved_output_tokens,
        safety_margin_tokens=safety_margin_tokens,
        num_ctx=chosen,
    )


@dataclass
class CalibrationBook:
    errors_by_model: dict[str, list[int]] = field(default_factory=dict)

    def add(self, model: str, actual_minus_estimated: int) -> None:
        self.errors_by_model.setdefault(model, []).append(int(actual_minus_estimated))

    def median_error(self, model: str) -> int | None:
        values = self.errors_by_model.get(model) or []
        if not values:
            return None
        return int(round(_median([float(v) for v in values])))

    def calibrated_target(self, model: str, requested: int) -> int:
        bias = self.median_error(model)
        if bias is None:
            return requested
        return max(1, requested - bias)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _ceil_250(value: int) -> int:
    if value <= 0:
        return 0
    return int(math.ceil(value / 250.0) * 250)


def recommend_operating_margin(
    *,
    absolute_estimation_errors: list[int],
    boundary_flips: int = 0,
) -> dict[str, Any]:
    """Pick a margin inside 1000-2000. A clean measurement stays at the floor."""
    if not absolute_estimation_errors and boundary_flips <= 0:
        return {
            "margin_tokens": None,
            "reason": "no_measurements",
            "locked_to_1000": False,
        }
    peak = max(absolute_estimation_errors) if absolute_estimation_errors else 0
    raw = peak + (250 * max(0, boundary_flips))
    rounded = _ceil_250(raw)
    margin = min(PRODUCTION_MARGIN_MAX, max(PRODUCTION_MARGIN_MIN, rounded))
    return {
        "margin_tokens": margin,
        "unclamped_tokens": rounded,
        "peak_absolute_error": peak,
        "boundary_flips": boundary_flips,
        "range": [PRODUCTION_MARGIN_MIN, PRODUCTION_MARGIN_MAX],
        "locked_to_1000": False,
        "reason": (
            "floor of the 1000-2000 range"
            if margin == PRODUCTION_MARGIN_MIN and rounded <= PRODUCTION_MARGIN_MIN
            else "raised inside 1000-2000 from estimation error or boundary flips"
        ),
    }


def production_input_size(*, largest_stable_tokens: int, margin_tokens: int) -> int:
    return largest_stable_tokens - margin_tokens


@dataclass
class Measurement:
    prompt_tokens_per_second: float | None = None
    generation_tokens_per_second: float | None = None
    elapsed_seconds: float | None = None
    evidence_tokens: int = 0
    peak_vram_gb: float | None = None
    gpu_resident: bool | None = None
    cpu_spill: bool = False
    prompt_eval_count: int | None = None
    estimated_prompt_tokens: int | None = None
    truncated: bool = False
    malformed: bool = False
    timed_out: bool = False
    infrastructure_failure: bool = False
    out_of_memory: bool = False
    cancelled: bool = False
    evidence_bytes: int | None = None
    evidence_characters: int | None = None
    estimated_evidence_tokens: int | None = None
    estimated_prompt_template_tokens: int | None = None
    estimated_total_prompt_tokens: int | None = None
    token_estimator_id: str | None = None
    token_estimator_formula: str | None = None
    token_count_kind: str | None = None
    token_error: int | None = None
    token_error_percent: float | None = None
    configured_num_ctx: int | None = None
    output_reserve_tokens: int | None = None
    safety_margin_tokens: int | None = None
    final_safety_result: str | None = None


def classify_measurement(measurement: Measurement, *, vram_ceiling_gb: float) -> str:
    if measurement.cancelled:
        return "operator_cancelled"
    if measurement.infrastructure_failure:
        return "infrastructure_failure"
    if measurement.out_of_memory:
        return "out_of_memory"
    if measurement.peak_vram_gb is not None and measurement.peak_vram_gb >= vram_ceiling_gb:
        return "vram_ceiling"
    if measurement.cpu_spill or measurement.gpu_resident is False:
        return "degraded_cpu_spill"
    if measurement.timed_out:
        return "timed_out"
    if measurement.truncated or measurement.malformed:
        return "invalid_output"
    return "successful_stable"


def _regressed_against_baseline(
    measurement: Measurement,
    config: I11A0Config,
    baseline: dict[str, float] | None,
) -> bool:
    kind = classify_measurement(measurement, vram_ceiling_gb=config.maximum_vram_gb)
    if kind in {
        "degraded_cpu_spill",
        "timed_out",
        "invalid_output",
        "out_of_memory",
        "vram_ceiling",
        "infrastructure_failure",
    }:
        return True
    if kind != "successful_stable" or not baseline:
        return False
    prompt_base = baseline.get("prompt_tps")
    gen_base = baseline.get("generation_tps")
    rate = baseline.get("elapsed_per_token")
    prompt_drop = (
        measurement.prompt_tokens_per_second is not None
        and prompt_base is not None
        and measurement.prompt_tokens_per_second
        < prompt_base * (1.0 - config.regression_prompt_fraction)
    )
    gen_drop = (
        measurement.generation_tokens_per_second is not None
        and gen_base is not None
        and measurement.generation_tokens_per_second
        < gen_base * (1.0 - config.regression_generation_fraction)
    )
    elapsed_worse = False
    if (
        rate is not None
        and measurement.elapsed_seconds is not None
        and measurement.evidence_tokens > 0
    ):
        expected = rate * measurement.evidence_tokens
        elapsed_worse = measurement.elapsed_seconds > expected * (
            1.0 + config.regression_elapsed_fraction
        )
    return bool(prompt_drop or gen_drop or elapsed_worse)


def baseline_from_stable(runs: list[Measurement]) -> dict[str, float] | None:
    usable = [
        row
        for row in runs
        if row.prompt_tokens_per_second is not None
        and row.generation_tokens_per_second is not None
        and row.elapsed_seconds is not None
        and row.evidence_tokens > 0
    ]
    if not usable:
        return None
    return {
        "prompt_tps": _median([float(row.prompt_tokens_per_second or 0) for row in usable]),
        "generation_tps": _median(
            [float(row.generation_tokens_per_second or 0) for row in usable]
        ),
        "elapsed_per_token": _median(
            [float(row.elapsed_seconds or 0) / row.evidence_tokens for row in usable]
        ),
    }


@dataclass(frozen=True)
class EvidenceTurn:
    evidence_id: str
    text: str
    sent_at: str = ""


@dataclass(frozen=True)
class EvidencePiece:
    piece_id: str
    turns: tuple[EvidenceTurn, ...]
    earliest: str
    latest: str

    def render(self) -> str:
        return "\n".join(turn.text for turn in self.turns)

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(turn.evidence_id for turn in self.turns)


@dataclass
class MaterializedEvidence:
    text: str
    sha256: str
    estimated_evidence_tokens: int
    evidence_ids: tuple[str, ...]
    partial_context: bool
    partial_boundary_note: str
    time_start: str
    time_end: str
    certain: bool


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pack_conversation_intact(
    pieces: list[EvidencePiece],
    *,
    target_tokens: int,
    counter: TokenCounter,
    model: str,
) -> MaterializedEvidence:
    """Pack whole conversations. Split only between complete turns when one conversation exceeds the target."""
    require_certain(counter.count(" ", model=model))
    chosen: list[EvidencePiece] = []
    partial = False
    boundary = "none"
    for piece in pieces:
        trial = chosen + [piece]
        trial_text = "\n\n".join(item.render() for item in trial)
        cost = require_certain(counter.count(trial_text, model=model)).tokens
        if chosen and cost > target_tokens:
            break
        piece_cost = require_certain(counter.count(piece.render(), model=model)).tokens
        if piece_cost > target_tokens:
            partial, boundary, chosen = _split_oversized_piece(
                piece, target_tokens=target_tokens, counter=counter, model=model
            )
            break
        chosen.append(piece)
    if not chosen:
        raise I11A0Error("no conversation fits the token target")
    text = "\n\n".join(item.render() for item in chosen)
    ids = tuple(evidence_id for item in chosen for evidence_id in item.evidence_ids)
    tokens = require_certain(counter.count(text, model=model)).tokens
    return MaterializedEvidence(
        text=text,
        sha256=_sha256_text(text),
        estimated_evidence_tokens=tokens,
        evidence_ids=ids,
        partial_context=partial,
        partial_boundary_note=boundary,
        time_start=min(item.earliest for item in chosen),
        time_end=max(item.latest for item in chosen),
        certain=True,
    )


def _split_oversized_piece(
    piece: EvidencePiece,
    *,
    target_tokens: int,
    counter: TokenCounter,
    model: str,
) -> tuple[bool, str, list[EvidencePiece]]:
    group: list[EvidenceTurn] = []
    for turn in piece.turns:
        trial = group + [turn]
        text = "\n".join(item.text for item in trial)
        if group and require_certain(counter.count(text, model=model)).tokens > target_tokens:
            break
        one = require_certain(counter.count(turn.text, model=model)).tokens
        if one > target_tokens:
            raise I11A0Error(
                f"evidence {turn.evidence_id} exceeds the token target and cannot be split"
            )
        group.append(turn)
    if not group:
        raise I11A0Error("oversized conversation produced no complete turn")
    kept_ids = {turn.evidence_id for turn in group}
    omitted = [turn.evidence_id for turn in piece.turns if turn.evidence_id not in kept_ids]
    partial_piece = EvidencePiece(
        piece_id=piece.piece_id + "-partial",
        turns=tuple(group),
        earliest=piece.earliest,
        latest=piece.latest,
    )
    note = "partial thread; omitted complete messages: " + ", ".join(omitted)
    return True, note, [partial_piece]


def refuse_model_pull() -> None:
    raise ModelPullForbidden(
        "I11A.0 must not pull, update, or replace a model. Install manually, then re-inventory."
    )


class ScriptedLifecycle:
    """Test double for unload, VRAM release, load, and digest checks."""

    def __init__(
        self,
        installed: dict[str, dict[str, Any]],
        *,
        fail_on: str | None = None,
    ) -> None:
        self.installed = installed
        self.fail_on = fail_on
        self.events: list[str] = []
        self.loaded: str | None = None
        self.vram_gb = 0.4

    def verify_installed(self, spec: ModelSpec) -> dict[str, Any]:
        row = self.installed.get(spec.tag)
        if not row:
            raise I11A0Error(f"model not installed: {spec.tag}")
        if row.get("digest") != spec.digest:
            raise I11A0Error(
                f"digest mismatch for {spec.tag}: expected {spec.digest} got {row.get('digest')}"
            )
        if spec.quantization and row.get("quantization") not in {spec.quantization, ""}:
            raise I11A0Error(f"quantization mismatch for {spec.tag}")
        self.events.append(f"verify:{spec.tag}")
        return row

    def unload(self, tag: str) -> None:
        self.events.append(f"unload:{tag}")
        self.loaded = None
        self.vram_gb = 0.4

    def wait_vram_baseline(self) -> float:
        self.events.append("vram_baseline")
        if self.fail_on == "vram":
            raise I11A0Error("VRAM did not return to baseline")
        return self.vram_gb

    def load(self, spec: ModelSpec) -> dict[str, Any]:
        if self.fail_on == "load" or self.fail_on == f"load:{spec.tag}":
            raise I11A0Error(f"load failed for {spec.tag}")
        row = self.verify_installed(spec)
        self.loaded = spec.tag
        self.vram_gb = float(row.get("resident_gb") or 12.0)
        self.events.append(f"load:{spec.tag}")
        return row


def _default_fetcher(method: str, url: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise I11A0Error(f"ollama_unavailable:{exc}") from exc
    parsed = json.loads(body or "{}")
    if not isinstance(parsed, dict):
        raise I11A0Error("ollama_inventory_not_object")
    return parsed


def _context_length(show: dict[str, Any]) -> int | None:
    info = show.get("model_info") if isinstance(show.get("model_info"), dict) else {}
    for key, value in info.items():
        if str(key).endswith("context_length"):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    parameters = str(show.get("parameters") or "")
    for line in parameters.splitlines():
        if "num_ctx" in line:
            digits = "".join(ch for ch in line if ch.isdigit())
            if digits:
                return int(digits)
    return None


def inventory_installed_models(
    *,
    base_url: str = "http://127.0.0.1:11434",
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    """Read Ollama tags and show metadata. Does not generate, embed, or pull."""
    fetch = fetcher or _default_fetcher
    base = base_url.rstrip("/")
    try:
        version = fetch("GET", f"{base}/api/version", None)
        tags = fetch("GET", f"{base}/api/tags", None)
    except I11A0Error as exc:
        return {
            "ok": False,
            "available": False,
            "reason": str(exc),
            "models_called": False,
            "pull_executed": False,
            "approved": [_missing_model(row) for row in APPROVED_MODELS],
            "manual_install_commands": [row["install"] for row in APPROVED_MODELS],
            "stop_for_authorization": True,
        }
    listed = list(tags.get("models") or [])
    by_name = {str(row.get("name") or row.get("model") or ""): row for row in listed}
    approved_rows = []
    missing_commands = []
    for spec in APPROVED_MODELS:
        tag = spec["tag"]
        installed = by_name.get(tag) or by_name.get(f"{tag}:latest")
        alias_name = spec.get("alias") or ""
        alias_row = by_name.get(alias_name) if alias_name else None
        if not installed:
            status = "alias_present_not_accepted" if alias_row else "missing"
            missing_commands.append(spec["install"])
            approved_rows.append(
                {
                    "config_id": spec["config_id"],
                    "tag": tag,
                    "status": status,
                    "digest": (alias_row or {}).get("digest"),
                    "quantization": None,
                    "size_bytes": (alias_row or {}).get("size"),
                    "context_length": None,
                    "accepted_for_screen": False,
                    "models_called": False,
                }
            )
            continue
        show: dict[str, Any] = {}
        try:
            show = fetch("POST", f"{base}/api/show", {"name": tag})
        except I11A0Error as exc:
            show = {"available": False, "reason": str(exc)}
        details = show.get("details") if isinstance(show.get("details"), dict) else {}
        quantization = str(details.get("quantization_level") or "")
        digest = str(installed.get("digest") or show.get("digest") or "")
        accepted = True
        if spec["quantization"] and quantization and quantization != spec["quantization"]:
            accepted = False
        approved_rows.append(
            {
                "config_id": spec["config_id"],
                "tag": tag,
                "status": "installed" if accepted else "quantization_mismatch",
                "digest": digest or None,
                "quantization": quantization or None,
                "size_bytes": installed.get("size"),
                "context_length": _context_length(show),
                "accepted_for_screen": accepted,
                "models_called": False,
            }
        )
    return {
        "ok": True,
        "available": True,
        "ollama_version": version.get("version"),
        "models_called": False,
        "pull_executed": False,
        "approved": approved_rows,
        "manual_install_commands": missing_commands,
        "stop_for_authorization": bool(missing_commands),
        "installed_names": sorted(by_name),
    }


def _missing_model(spec: dict[str, str]) -> dict[str, Any]:
    return {
        "config_id": spec["config_id"],
        "tag": spec["tag"],
        "status": "not_inventoried",
        "accepted_for_screen": False,
        "models_called": False,
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


_COMPANION_ROLES = {
    "chunk_manifest.json": "manifest",
    "model_paste.txt": "model_paste",
    "source_map.json": "source_map",
    "preparation_report.txt": "preparation_report",
    "chunk_preparation_report.txt": "chunk_preparation_report",
    "chunk_manifest_resync_report.txt": "hash_ledger",
    "freeze_resync_report.txt": "freeze_report",
    "local_manifest.json": "generation_metadata",
    "generation_manifest.json": "generation_metadata",
}


def inventory_peggy_chunks(roots: list[Path | str]) -> dict[str, Any]:
    """Inventory a review directory recursively. Does not call a model or copy evidence."""
    chunk_files: list[Path] = []
    companions: list[Path] = []
    searched = []
    for root in roots:
        path = Path(root)
        searched.append(str(path))
        found_chunks, found_companions = _review_files(path)
        chunk_files.extend(found_chunks)
        companions.extend(found_companions)
    chunk_files = sorted(set(chunk_files))
    companions = sorted(set(companions))
    records = [_chunk_record(path) for path in chunk_files]
    companion_records = [_companion_record(path, roots) for path in companions]
    return {
        "ok": True,
        "models_called": False,
        "pull_executed": False,
        "searched_roots": searched,
        "chunk_count": len(records),
        "exactly_seven": len(records) == 7,
        "seven_chunk_pool_found": len(records) == 7,
        "canonical_set_resolved": len(records) == 7,
        "chunks": records,
        "companions": companion_records,
        "i14_comparison_files": [
            row["path"] for row in companion_records if "i14" in row["filename"].lower()
        ],
    }


def _review_files(root: Path) -> tuple[list[Path], list[Path]]:
    import os

    chunks: list[Path] = []
    companions: list[Path] = []
    if not root.exists():
        return chunks, companions
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in {".git", "archive"}]
        for name in filenames:
            path = Path(dirpath) / name
            if name.startswith("CHUNK_") and name.endswith("_MODEL_PASTE.txt"):
                chunks.append(path)
            else:
                companions.append(path)
    return chunks, companions


def _chunk_files(root: Path) -> list[Path]:
    chunks, _companions = _review_files(root)
    return chunks


def _manifest_row(manifest: dict[str, Any] | None, filename: str) -> dict[str, Any] | None:
    if not manifest:
        return None
    for candidate in manifest.get("chunks") or []:
        names = {candidate.get("file"), candidate.get("paste_file")}
        if filename in names:
            return candidate
    return None


def _review_identity(directory: Path) -> dict[str, Any]:
    review_id = directory.name if directory.name.upper().startswith("REVIEW_") else None
    local = _read_json(directory / "LOCAL_MANIFEST.json") or {}
    generation = _read_json(directory / "GENERATION_MANIFEST.json") or {}
    interval = local.get("interval") if isinstance(local.get("interval"), dict) else {}
    return {
        "review_id": review_id,
        "generation_id": generation.get("generation_id"),
        "source_commit": local.get("source_commit") or generation.get("source_commit"),
        "frozen_input_sha256": local.get("frozen_input_sha256") or generation.get("model_paste_sha256"),
        "interval_start": interval.get("start"),
        "interval_end": interval.get("end"),
    }


def _resync_by_index(directory: Path) -> dict[int, dict[str, Any]]:
    path = directory / "CHUNK_MANIFEST_RESYNC_REPORT.txt"
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    start = text.find("[")
    if start < 0:
        return {}
    try:
        rows = json.loads(text[start:])
    except json.JSONDecodeError:
        return {}
    found: dict[int, dict[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("chunk_index") is not None:
                found[int(row["chunk_index"])] = row
    return found


def _chunk_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    actual_sha = hashlib.sha256(data).hexdigest()
    manifest = _read_json(path.parent / "CHUNK_MANIFEST.json")
    generation = _read_json(path.parent / "GENERATION_MANIFEST.json") or _read_json(
        path.parent.parent / "GENERATION_MANIFEST.json"
    )
    row = _manifest_row(manifest, path.name)
    identity = _review_identity(path.parent)
    if generation and generation.get("generation_id"):
        identity["generation_id"] = generation.get("generation_id")
    time_range = {}
    if row:
        time_range = row.get("date_range") or row.get("time_range") or {}
    conversations = row.get("conversation_count") if row else None
    messages = row.get("message_count") if row else None
    if conversations is None and row:
        conversations = len(row.get("conversation_ids") or [])
    if messages is None and row:
        messages = len(row.get("email_ids") or row.get("cite_as") or [])
    parsed_ids = 0
    if conversations in (None, 0) or messages in (None, 0):
        text = data.decode("utf-8", errors="replace")
        source_map = _read_json(path.parent / "SOURCE_MAP.json") or {}
        if "===== TRUSTED EMAIL CONVERSATIONS =====" in text:
            try:
                _prefix, parsed = parse_conversations(text, source_map)
            except ValueError:
                parsed = []
            conversations = len(parsed)
            messages = sum(len(item.turns) for item in parsed)
            parsed_ids = messages
            dates = [item.earliest for item in parsed if item.earliest and item.earliest != "9999"]
            dates += [item.latest for item in parsed if item.latest]
            if dates and not time_range:
                time_range = {"start": min(dates), "end": max(dates)}
    manifest_sha = None
    if row:
        manifest_sha = row.get("chunk_sha256") or row.get("sha256")
    sequence = None
    if row and row.get("chunk_index") is not None:
        sequence = int(row["chunk_index"])
    else:
        match = re.search(r"CHUNK_(\d+)_", path.name, re.I)
        if match:
            sequence = int(match.group(1))
    resync = _resync_by_index(path.parent).get(sequence or -1, {})
    reviewed_sha = resync.get("reviewed_sha256")
    i14_files = [
        item.name
        for item in path.parent.iterdir()
        if item.is_file() and "i14" in item.name.lower()
    ] if path.parent.exists() else []
    if manifest_sha and actual_sha == str(manifest_sha).lower():
        status = "reviewed_manifest_match"
    elif reviewed_sha and actual_sha == str(reviewed_sha).lower():
        status = "reviewed_hash_match"
    elif not manifest_sha and not reviewed_sha:
        status = "not_compared"
    else:
        status = "hash_disagrees_with_review_record"
    return {
        "sequence": sequence,
        "filename": path.name,
        "relative_path": path.name,
        "path": str(path),
        "flightsim_path": str(Path(r"C:\memorybox\docs\test-output\trusted-email-review") / path.parent.name / path.name)
        if path.parent.name.upper().startswith("REVIEW_")
        else None,
        "review_id": identity.get("review_id"),
        "generation_id": identity.get("generation_id"),
        "source_commit": identity.get("source_commit"),
        "frozen_input_sha256": identity.get("frozen_input_sha256"),
        "sha256": actual_sha,
        "manifest_sha256": manifest_sha,
        "predecessor_sha256": resync.get("previous_sha256"),
        "reviewed_sha256": reviewed_sha,
        "bytes": len(data),
        "diagnostic_tokens_bytes_div_4": max(1, (len(data) + 3) // 4),
        "token_count_authoritative": False,
        "date_start": time_range.get("start"),
        "date_end": time_range.get("end"),
        "conversation_count": conversations or 0,
        "message_count": messages or 0,
        "evidence_id_count": messages or parsed_ids or 0,
        "review_status": status,
        "i14_relationship": "no_i14_comparison_in_review_directory" if not i14_files else "i14_file_present",
        "i14_files": i14_files,
        "artifact_status": status,
        "models_called": False,
    }


def _companion_record(path: Path, roots: list[Path | str]) -> dict[str, Any]:
    data = path.read_bytes()
    relative = path.name
    for root in roots:
        try:
            relative = str(path.relative_to(Path(root)))
            break
        except ValueError:
            continue
    role = _COMPANION_ROLES.get(path.name.lower(), "companion")
    if "i14" in path.name.lower():
        role = "i14_comparison"
    return {
        "filename": path.name,
        "relative_path": relative,
        "path": str(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "role": role,
        "models_called": False,
    }


def compare_i14_successor(original: bytes, successor: bytes) -> dict[str, Any]:
    """Deterministic difference report. Does not replace the original."""
    original_lines = original.decode("utf-8", errors="replace").splitlines()
    successor_lines = successor.decode("utf-8", errors="replace").splitlines()
    import difflib

    diff = list(
        difflib.unified_diff(
            original_lines,
            successor_lines,
            fromfile="original",
            tofile="i14-successor",
            lineterm="",
        )
    )
    return {
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "successor_sha256": hashlib.sha256(successor).hexdigest(),
        "unchanged": original == successor,
        "artifact_status": "unchanged" if original == successor else "needs_i14_successor",
        "original_lines": len(original_lines),
        "successor_lines": len(successor_lines),
        "diff_line_count": len(diff),
        "diff_sha256": hashlib.sha256("\n".join(diff).encode("utf-8")).hexdigest(),
    }


def propose_quality_packets(
    chunks: list[dict[str, Any]],
    *,
    pieces_by_chunk: dict[str, list[EvidencePiece]],
    counter: TokenCounter | None,
    model_for_sizing: str,
    max_evidence_tokens: int = 6000,
) -> dict[str, Any]:
    """Build early, middle, and later gold packets. Do not emit an oversized whole chunk."""
    if len(chunks) < 7:
        return {
            "ok": False,
            "status": "blocked_missing_chunks",
            "chunks_found": len(chunks),
            "packets": [],
            "models_called": False,
            "note": "The seven reviewed Peggy chunks are not on this machine.",
        }
    pool: list[tuple[str, EvidencePiece]] = []
    for chunk in chunks:
        for piece in pieces_by_chunk.get(chunk["path"], []):
            pool.append((chunk["path"], piece))
    pool.sort(key=lambda item: (item[1].earliest, item[1].piece_id))
    if not pool:
        return {
            "ok": False,
            "status": "blocked_unparsed_conversations",
            "chunks_found": len(chunks),
            "packets": [],
            "models_called": False,
        }
    tertiles = _tertiles(pool)
    labels = ("quality-early", "quality-middle", "quality-later")
    packets = []
    certain = False
    if counter is not None:
        try:
            require_certain(counter.count("x", model=model_for_sizing))
            certain = True
        except UncertainTokenCount:
            certain = False
    for label, group in zip(labels, tertiles):
        packets.append(
            _packet_from_group(
                label,
                group,
                counter=counter,
                model=model_for_sizing,
                max_evidence_tokens=max_evidence_tokens,
                certain=certain,
            )
        )
    return {
        "ok": all(packet["ready_for_founder_review"] for packet in packets),
        "status": "proposed",
        "token_count_authoritative": certain,
        "packets": packets,
        "models_called": False,
        "founder_contract_status": "structure_only_pending_founder_facts",
    }


def _tertiles(pool: list[tuple[str, EvidencePiece]]) -> list[list[tuple[str, EvidencePiece]]]:
    count = len(pool)
    cuts = [0, count // 3, (2 * count) // 3, count]
    return [pool[cuts[index] : cuts[index + 1]] for index in range(3)]


def _packet_from_group(
    packet_id: str,
    group: list[tuple[str, EvidencePiece]],
    *,
    counter: TokenCounter | None,
    model: str,
    max_evidence_tokens: int,
    certain: bool,
) -> dict[str, Any]:
    chosen: list[tuple[str, EvidencePiece]] = []
    excluded: list[str] = []
    for source, piece in group:
        trial = chosen + [(source, piece)]
        cost = _group_cost(trial, counter=counter, model=model, certain=certain)
        if cost > max_evidence_tokens:
            excluded.append(piece.piece_id)
            break
        chosen.append((source, piece))
    text = "\n\n".join(piece.render() for _source, piece in chosen)
    ids = [evidence_id for _source, piece in chosen for evidence_id in piece.evidence_ids]
    sources = sorted({source for source, _piece in chosen})
    dates = [piece.earliest for _source, piece in chosen if piece.earliest]
    date_end = [piece.latest for _source, piece in chosen if piece.latest]
    whole_chunk_hashes = set()
    return {
        "packet_id": packet_id,
        "sha256": _sha256_text(text) if text else None,
        "bytes": len(text.encode("utf-8")),
        "source_chunks": sources,
        "time_start": min(dates) if dates else None,
        "time_end": max(date_end) if date_end else None,
        "conversation_count": len(chosen),
        "message_count": len(ids),
        "evidence_ids": ids,
        "excluded_oversize_piece_ids": excluded,
        "partial_context": False,
        "diagnostic_tokens_bytes_div_4": estimate_tokens(text) if text else 0,
        "token_count_authoritative": certain,
        "whole_chunk_rejected": not whole_chunk_hashes,
        "ready_for_founder_review": bool(text),
        "founder_contract": {
            "expected_facts": [],
            "exclusions": [],
            "chronology": [
                f"Dates present in this packet run from {min(dates) if dates else 'unknown'} to {max(date_end) if date_end else 'unknown'}."
            ],
            "uncertainties": [
                "Founder has not yet marked claims this packet cannot settle."
            ],
            "prohibited_conclusions": [
                "No emotion, motive, or significance that the packet text does not state.",
                "Quoted or forwarded text is not the outer author's own statement.",
                "A planned or discussed event is not an event that occurred.",
            ],
        },
        "models_called": False,
    }


def _group_cost(
    group: list[tuple[str, EvidencePiece]],
    *,
    counter: TokenCounter | None,
    model: str,
    certain: bool,
) -> int:
    text = "\n\n".join(piece.render() for _source, piece in group)
    if certain and counter is not None:
        return require_certain(counter.count(text, model=model)).tokens
    # Conservative diagnostic: treat bytes/4 as possibly 50% low, so the packet stays under the cap.
    return int(math.ceil(estimate_tokens(text) * 1.5))


@dataclass
class RunRequest:
    model_tag: str
    digest: str
    requested_evidence_tokens: int
    evidence_sha256: str
    evidence_text: str
    repetition: int
    warm_or_cold: str
    confirmation: bool
    thinking_mode: str
    seed: int
    num_ctx: int
    reserved_output_tokens: int
    prompt_sha256: str
    time_start: str = ""
    time_end: str = ""
    partial_context: bool = False
    partial_boundary_note: str = "none"
    evidence_ids: tuple[str, ...] = ()


@dataclass
class RunObservation:
    request: RunRequest
    measurement: Measurement
    classification: str
    narration_text: str = ""
    skipped: bool = False


class Runner(Protocol):
    def __call__(self, request: RunRequest) -> tuple[Measurement, str]: ...


def run_identity(request: RunRequest) -> str:
    """Identity of a scheduled ladder step. Evidence bytes stay in the saved record."""
    payload = {
        "model": request.model_tag,
        "digest": request.digest,
        "prompt_sha256": request.prompt_sha256,
        "requested_evidence_tokens": request.requested_evidence_tokens,
        "repetition": request.repetition,
        "warm_or_cold": request.warm_or_cold,
        "thinking_mode": request.thinking_mode,
        "confirmation": request.confirmation,
        "seed": request.seed,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def load_completed_identities(results_dir: Path) -> set[str]:
    found: set[str] = set()
    if not results_dir.exists():
        return found
    for path in results_dir.glob("*/run_record.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        identity = str(record.get("identity") or path.parent.name)
        found.add(identity)
    return found


def _persist_run(results_dir: Path, observation: RunObservation) -> None:
    identity = run_identity(observation.request)
    folder = results_dir / identity
    folder.mkdir(parents=True, exist_ok=True)
    record = {
        "identity": identity,
        "classification": observation.classification,
        "skipped": observation.skipped,
        "request": {key: value for key, value in asdict(observation.request).items() if key != "evidence_text"},
        "measurement": asdict(observation.measurement),
        "narration_sha256": _sha256_text(observation.narration_text),
    }
    (folder / "run_record.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    accounting = {
        "evidence_bytes": observation.measurement.evidence_bytes,
        "evidence_characters": observation.measurement.evidence_characters,
        "estimated_evidence_tokens": observation.measurement.estimated_evidence_tokens,
        "estimated_prompt_template_tokens": observation.measurement.estimated_prompt_template_tokens,
        "estimated_total_prompt_tokens": observation.measurement.estimated_total_prompt_tokens,
        "estimator_id": observation.measurement.token_estimator_id or TOKEN_ESTIMATOR_ID,
        "estimator_formula": observation.measurement.token_estimator_formula or TOKEN_ESTIMATOR_FORMULA,
        "estimator_result_kind": TOKEN_ESTIMATOR_LABEL,
        "actual_prompt_eval_count": observation.measurement.prompt_eval_count,
        "actual_count_source": "recorded_generation_prompt_eval_count",
        "actual_includes_chat_template_and_instructions": True,
        "token_error": observation.measurement.token_error,
        "token_error_percent": observation.measurement.token_error_percent,
        "configured_num_ctx": observation.measurement.configured_num_ctx,
        "output_reserve_tokens": observation.measurement.output_reserve_tokens,
        "safety_margin_tokens": observation.measurement.safety_margin_tokens,
        "final_safety_result": observation.measurement.final_safety_result,
        "calibration_recorded": observation.measurement.token_error is not None,
    }
    (folder / "token_accounting.json").write_text(
        json.dumps(accounting, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (folder / "narration.txt").write_text(observation.narration_text, encoding="utf-8", newline="\n")


class EvidenceSource(Protocol):
    def materialize(
        self, *, model: str, target_tokens: int, counter: TokenCounter
    ) -> MaterializedEvidence: ...


def run_authorized_stage(
    *,
    config: I11A0Config,
    runner: Runner,
    lifecycle: ScriptedLifecycle,
    counter: TokenCounter,
    source: EvidenceSource,
    results_dir: Path | str,
    prompt_tokens: int,
) -> dict[str, Any]:
    """Execute one authorized stage with a supplied runner. This does not open Ollama."""
    config.validate()
    if config.prompt_version != PROMPT_VERSION:
        raise I11A0Error("prompt version does not match the draft benchmark prompt")
    root = Path(results_dir)
    root.mkdir(parents=True, exist_ok=True)
    completed = load_completed_identities(root)
    calibration = CalibrationBook()
    if config.stage == "smoke":
        return _run_smoke(
            config=config,
            runner=runner,
            lifecycle=lifecycle,
            counter=counter,
            source=source,
            results_dir=root,
            completed=completed,
            calibration=calibration,
            prompt_tokens=prompt_tokens,
        )
    if config.stage == "stage1_capacity":
        return _run_capacity(
            config=config,
            runner=runner,
            lifecycle=lifecycle,
            counter=counter,
            source=source,
            results_dir=root,
            completed=completed,
            calibration=calibration,
            prompt_tokens=prompt_tokens,
        )
    raise GateNotAuthorized(f"{config.stage} is not launched by the offline stage-1 controller")


def _execute(
    *,
    config: I11A0Config,
    spec: ModelSpec,
    runner: Runner,
    counter: TokenCounter,
    source: EvidenceSource,
    results_dir: Path,
    completed: set[str],
    calibration: CalibrationBook,
    prompt_tokens: int,
    requested_tokens: int,
    repetition: int,
    warm_or_cold: str,
    confirmation: bool,
    pack_target: int,
) -> RunObservation:
    smoke = config.stage == "smoke"
    evidence = source.materialize(model=spec.tag, target_tokens=pack_target, counter=counter)
    if not smoke and not evidence.certain:
        raise UncertainTokenCount("capacity evidence is not model-token certain")
    user = render_user_message(
        packet_id=f"{spec.config_id}-{requested_tokens}-{warm_or_cold}-{repetition}",
        packet_role="capacity" if config.stage == "stage1_capacity" else "smoke",
        time_start=evidence.time_start,
        time_end=evidence.time_end,
        partial_context=evidence.partial_context,
        partial_boundary_note=evidence.partial_boundary_note,
        evidence_ids=list(evidence.evidence_ids),
        evidence_text=evidence.text,
    )
    request_key = RunRequest(
        model_tag=spec.tag,
        digest=spec.digest,
        requested_evidence_tokens=requested_tokens,
        evidence_sha256="",
        evidence_text="",
        repetition=repetition,
        warm_or_cold=warm_or_cold,
        confirmation=confirmation,
        thinking_mode=config.thinking_mode,
        seed=config.seed,
        num_ctx=0,
        reserved_output_tokens=config.reserved_output_tokens,
        prompt_sha256=prompt_sha256(),
    )
    identity = run_identity(request_key)
    if identity in completed:
        return RunObservation(
            request=request_key,
            measurement=Measurement(evidence_tokens=requested_tokens),
            classification="resumed_skip",
            skipped=True,
        )
    full_prompt = SYSTEM_PROMPT + "\n" + user
    if smoke:
        estimated_evidence = estimate_tokens(evidence.text)
        estimated_total = estimate_tokens(full_prompt)
        estimated_template = max(0, estimated_total - estimated_evidence)
    else:
        if not evidence.certain:
            raise UncertainTokenCount("capacity evidence is not model-token certain")
        estimated_evidence = evidence.estimated_evidence_tokens
        estimated_total = require_certain(counter.count(full_prompt, model=spec.tag)).tokens
        estimated_template = max(prompt_tokens, estimated_total - estimated_evidence)
    plan = plan_context(
        evidence_tokens=estimated_evidence if smoke else evidence.estimated_evidence_tokens,
        prompt_tokens=estimated_template,
        reserved_output_tokens=config.reserved_output_tokens,
        safety_margin_tokens=config.safety_margin_tokens,
    )
    estimated_budget_ok = (
        estimated_total + config.reserved_output_tokens + config.safety_margin_tokens
        <= plan.num_ctx
    )
    if smoke and not estimated_budget_ok:
        raise ContextBudgetError(
            "estimated total prompt tokens + output reserve + safety margin exceed num_ctx"
        )
    request = RunRequest(
        model_tag=spec.tag,
        digest=spec.digest,
        requested_evidence_tokens=requested_tokens,
        evidence_sha256=evidence.sha256,
        evidence_text=evidence.text,
        repetition=repetition,
        warm_or_cold=warm_or_cold,
        confirmation=confirmation,
        thinking_mode=config.thinking_mode,
        seed=config.seed,
        num_ctx=plan.num_ctx,
        reserved_output_tokens=config.reserved_output_tokens,
        prompt_sha256=prompt_sha256(),
        time_start=evidence.time_start,
        time_end=evidence.time_end,
        partial_context=evidence.partial_context,
        partial_boundary_note=evidence.partial_boundary_note,
        evidence_ids=evidence.evidence_ids,
    )
    measurement, narration = runner(request)
    measurement.evidence_tokens = measurement.evidence_tokens or estimated_evidence
    measurement.evidence_bytes = len(evidence.text.encode("utf-8"))
    measurement.evidence_characters = len(evidence.text)
    measurement.estimated_evidence_tokens = estimated_evidence
    measurement.estimated_prompt_template_tokens = estimated_template
    measurement.estimated_total_prompt_tokens = estimated_total
    measurement.estimated_prompt_tokens = estimated_total
    measurement.token_estimator_id = TOKEN_ESTIMATOR_ID
    measurement.token_estimator_formula = TOKEN_ESTIMATOR_FORMULA
    measurement.token_count_kind = TOKEN_ESTIMATOR_LABEL
    measurement.configured_num_ctx = plan.num_ctx
    measurement.output_reserve_tokens = config.reserved_output_tokens
    measurement.safety_margin_tokens = config.safety_margin_tokens
    actual = measurement.prompt_eval_count
    if actual is not None:
        error = actual - estimated_total
        calibration.add(spec.tag, error)
        measurement.token_error = error
        measurement.token_error_percent = (
            round((error / estimated_total) * 100.0, 4) if estimated_total else None
        )
        actual_budget_ok = (
            actual + config.reserved_output_tokens + config.safety_margin_tokens
            <= plan.num_ctx
        )
        error_ok = abs(error) <= config.safety_margin_tokens
        if not actual_budget_ok or not error_ok:
            measurement.final_safety_result = "failed"
            observation = RunObservation(
                request,
                measurement,
                "context_rejected" if not actual_budget_ok else "estimation_exceeded",
                narration,
            )
            _persist_run(results_dir, observation)
            completed.add(identity)
            return observation
        measurement.final_safety_result = "passed"
    elif smoke:
        measurement.final_safety_result = "failed_missing_prompt_eval_count"
        observation = RunObservation(request, measurement, "context_rejected", narration)
        _persist_run(results_dir, observation)
        completed.add(identity)
        return observation
    classification = classify_measurement(
        measurement, vram_ceiling_gb=config.maximum_vram_gb
    )
    if measurement.final_safety_result is None:
        measurement.final_safety_result = "passed"
    observation = RunObservation(request, measurement, classification, narration)
    _persist_run(results_dir, observation)
    completed.add(identity)
    return observation


def _run_smoke(
    *,
    config: I11A0Config,
    runner: Runner,
    lifecycle: ScriptedLifecycle,
    counter: TokenCounter,
    source: EvidenceSource,
    results_dir: Path,
    completed: set[str],
    calibration: CalibrationBook,
    prompt_tokens: int,
) -> dict[str, Any]:
    spec = config.models[0]
    lifecycle.verify_installed(spec)
    lifecycle.load(spec)
    observation = _execute(
        config=config,
        spec=spec,
        runner=runner,
        counter=counter,
        source=source,
        results_dir=results_dir,
        completed=completed,
        calibration=calibration,
        prompt_tokens=prompt_tokens,
        requested_tokens=config.smoke_evidence_tokens,
        repetition=1,
        warm_or_cold="cold",
        confirmation=False,
        pack_target=calibration.calibrated_target(spec.tag, config.smoke_evidence_tokens),
    )
    return {
        "ok": observation.classification in {"successful_stable", "resumed_skip"},
        "stage": "smoke",
        "stop_reason": "smoke_complete"
        if observation.classification in {"successful_stable", "resumed_skip"}
        else observation.classification,
        "runs": 1 if not observation.skipped else 0,
        "run_id": run_identity(observation.request),
        "runner_invocations_recorded_by_caller": True,
        "classifications": [observation.classification],
        "lifecycle_events": list(lifecycle.events),
        "models_called_by_controller": False,
        "token_accounting": {
            "evidence_bytes": observation.measurement.evidence_bytes,
            "evidence_characters": observation.measurement.evidence_characters,
            "estimated_evidence_tokens": observation.measurement.estimated_evidence_tokens,
            "estimated_prompt_template_tokens": observation.measurement.estimated_prompt_template_tokens,
            "estimated_total_prompt_tokens": observation.measurement.estimated_total_prompt_tokens,
            "estimator_formula": TOKEN_ESTIMATOR_FORMULA,
            "estimator_result_kind": TOKEN_ESTIMATOR_LABEL,
            "actual_prompt_eval_count": observation.measurement.prompt_eval_count,
            "token_error": observation.measurement.token_error,
            "token_error_percent": observation.measurement.token_error_percent,
            "configured_num_ctx": observation.measurement.configured_num_ctx,
            "output_reserve_tokens": observation.measurement.output_reserve_tokens,
            "safety_margin_tokens": observation.measurement.safety_margin_tokens,
            "final_safety_result": observation.measurement.final_safety_result,
        },
    }


def _run_capacity(
    *,
    config: I11A0Config,
    runner: Runner,
    lifecycle: ScriptedLifecycle,
    counter: TokenCounter,
    source: EvidenceSource,
    results_dir: Path,
    completed: set[str],
    calibration: CalibrationBook,
    prompt_tokens: int,
) -> dict[str, Any]:
    observations: list[RunObservation] = []
    per_model: list[dict[str, Any]] = []
    previous: str | None = None
    stopped_job = False
    job_error = None
    for spec in config.models:
        if stopped_job:
            break
        try:
            if previous and config.manage_model_lifecycle:
                lifecycle.unload(previous)
                lifecycle.wait_vram_baseline()
            lifecycle.verify_installed(spec)
            lifecycle.load(spec)
        except I11A0Error as exc:
            job_error = str(exc)
            stopped_job = True
            per_model.append({"tag": spec.tag, "stop_reason": "lifecycle_failure", "error": job_error})
            break
        previous = spec.tag
        stable_warm: list[Measurement] = []
        confirmed_streak = 0
        largest_stable = None
        first_regression = None
        boundary_flips = 0
        last_state = None
        size = config.start_input_tokens
        stop_reason = "stage_complete"
        sizes_ran: list[int] = []
        cold_done = False
        while True:
            if config.maximum_input_tokens is not None and size > config.maximum_input_tokens:
                stop_reason = "maximum_input_tokens"
                break
            pack_target = calibration.calibrated_target(spec.tag, size)
            if not cold_done and config.cold_runs_per_model:
                cold = _execute(
                    config=config,
                    spec=spec,
                    runner=runner,
                    counter=counter,
                    source=source,
                    results_dir=results_dir,
                    completed=completed,
                    calibration=calibration,
                    prompt_tokens=prompt_tokens,
                    requested_tokens=size,
                    repetition=1,
                    warm_or_cold="cold",
                    confirmation=False,
                    pack_target=pack_target,
                )
                observations.append(cold)
                if cold.classification == "context_rejected":
                    stop_reason = "context_budget"
                    break
                if cold.classification in {"vram_ceiling", "infrastructure_failure", "out_of_memory", "operator_cancelled"}:
                    stop_reason = cold.classification
                    break
                cold_done = True
            baseline = baseline_from_stable(stable_warm)
            warm_rows: list[RunObservation] = []
            hard_stop = None
            suspicious = False
            for repetition in range(1, config.warm_runs_per_size + 1):
                warm = _execute(
                    config=config,
                    spec=spec,
                    runner=runner,
                    counter=counter,
                    source=source,
                    results_dir=results_dir,
                    completed=completed,
                    calibration=calibration,
                    prompt_tokens=prompt_tokens,
                    requested_tokens=size,
                    repetition=repetition,
                    warm_or_cold="warm",
                    confirmation=False,
                    pack_target=pack_target,
                )
                observations.append(warm)
                warm_rows.append(warm)
                if warm.classification == "context_rejected":
                    hard_stop = "context_budget"
                    break
                if warm.classification in {
                    "vram_ceiling",
                    "infrastructure_failure",
                    "out_of_memory",
                    "operator_cancelled",
                }:
                    hard_stop = warm.classification
                    break
                if _regressed_against_baseline(warm.measurement, config, baseline):
                    suspicious = True
            if hard_stop:
                stop_reason = hard_stop
                break
            confirmed = False
            if suspicious:
                confirmation = _execute(
                    config=config,
                    spec=spec,
                    runner=runner,
                    counter=counter,
                    source=source,
                    results_dir=results_dir,
                    completed=completed,
                    calibration=calibration,
                    prompt_tokens=prompt_tokens,
                    requested_tokens=size,
                    repetition=config.warm_runs_per_size + 1,
                    warm_or_cold="warm",
                    confirmation=True,
                    pack_target=pack_target,
                )
                observations.append(confirmation)
                if confirmation.classification in {
                    "vram_ceiling",
                    "infrastructure_failure",
                    "out_of_memory",
                    "operator_cancelled",
                    "context_rejected",
                }:
                    stop_reason = confirmation.classification
                    break
                confirmed = _regressed_against_baseline(
                    confirmation.measurement, config, baseline
                )
            sizes_ran.append(size)
            if confirmed:
                confirmed_streak += 1
                first_regression = first_regression or size
                if last_state == "stable":
                    boundary_flips += 1
                last_state = "regressing"
                if confirmed_streak >= config.regression_run_count:
                    stop_reason = "three_confirmed_regressions"
                    break
            else:
                if last_state == "regressing":
                    boundary_flips += 1
                last_state = "stable"
                confirmed_streak = 0
                largest_stable = size
                for row in warm_rows:
                    if row.classification == "successful_stable" and not row.skipped:
                        stable_warm.append(row.measurement)
            size += config.increment_tokens
        refined_stable = largest_stable
        if (
            largest_stable is not None
            and first_regression is not None
            and stop_reason == "three_confirmed_regressions"
        ):
            refined_stable, flips = _refine(
                config=config,
                spec=spec,
                runner=runner,
                counter=counter,
                source=source,
                results_dir=results_dir,
                completed=completed,
                calibration=calibration,
                prompt_tokens=prompt_tokens,
                low=largest_stable,
                high=first_regression,
                stable_warm=stable_warm,
                observations=observations,
            )
            boundary_flips += flips
        errors = [abs(value) for value in calibration.errors_by_model.get(spec.tag, [])]
        margin = recommend_operating_margin(
            absolute_estimation_errors=errors,
            boundary_flips=boundary_flips,
        )
        production = None
        if refined_stable is not None and margin.get("margin_tokens") is not None:
            production = production_input_size(
                largest_stable_tokens=refined_stable,
                margin_tokens=int(margin["margin_tokens"]),
            )
        per_model.append(
            {
                "tag": spec.tag,
                "stop_reason": stop_reason,
                "sizes_ran": sizes_ran,
                "largest_stable_tokens": refined_stable,
                "first_confirmed_regression_tokens": first_regression,
                "operating_margin": margin,
                "recommended_production_input_tokens": production,
                "locked_margin_to_1000": False,
            }
        )
    return {
        "ok": job_error is None,
        "stage": "stage1_capacity",
        "error": job_error,
        "models": per_model,
        "run_count": len(observations),
        "skipped": sum(1 for row in observations if row.skipped),
        "lifecycle_events": list(lifecycle.events),
        "models_called_by_controller": False,
        "alternate_quantization_tested": False,
    }


def _refine(
    *,
    config: I11A0Config,
    spec: ModelSpec,
    runner: Runner,
    counter: TokenCounter,
    source: EvidenceSource,
    results_dir: Path,
    completed: set[str],
    calibration: CalibrationBook,
    prompt_tokens: int,
    low: int,
    high: int,
    stable_warm: list[Measurement],
    observations: list[RunObservation],
) -> tuple[int, int]:
    largest = low
    flips = 0
    previous = "stable"
    size = low + config.refinement_increment_tokens
    while size < high:
        pack_target = calibration.calibrated_target(spec.tag, size)
        baseline = baseline_from_stable(stable_warm)
        suspicious = False
        warm_rows: list[RunObservation] = []
        for repetition in range(1, config.warm_runs_per_size + 1):
            warm = _execute(
                config=config,
                spec=spec,
                runner=runner,
                counter=counter,
                source=source,
                results_dir=results_dir,
                completed=completed,
                calibration=calibration,
                prompt_tokens=prompt_tokens,
                requested_tokens=size,
                repetition=repetition,
                warm_or_cold="warm",
                confirmation=False,
                pack_target=pack_target,
            )
            observations.append(warm)
            warm_rows.append(warm)
            if _regressed_against_baseline(warm.measurement, config, baseline):
                suspicious = True
        confirmed = False
        if suspicious:
            confirmation = _execute(
                config=config,
                spec=spec,
                runner=runner,
                counter=counter,
                source=source,
                results_dir=results_dir,
                completed=completed,
                calibration=calibration,
                prompt_tokens=prompt_tokens,
                requested_tokens=size,
                repetition=config.warm_runs_per_size + 1,
                warm_or_cold="warm",
                confirmation=True,
                pack_target=pack_target,
            )
            observations.append(confirmation)
            confirmed = _regressed_against_baseline(confirmation.measurement, config, baseline)
        if confirmed:
            if previous == "stable":
                flips += 1
            previous = "regressing"
            break
        if previous == "regressing":
            flips += 1
        previous = "stable"
        largest = size
        for row in warm_rows:
            if row.classification == "successful_stable" and not row.skipped:
                stable_warm.append(row.measurement)
        size += config.refinement_increment_tokens
    return largest, flips


def refuse_inference_cli() -> dict[str, Any]:
    raise InferenceNotAuthorized(
        "Capacity sweep and model pulls are not authorized. Gate 2 smoke requires "
        "--stage smoke --confirm-benchmark on an installed model."
    )


def build_preflight_package(
    *,
    chunk_roots: list[Path | str],
    ollama_base_url: str = "http://127.0.0.1:11434",
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    models = inventory_installed_models(base_url=ollama_base_url, fetcher=fetcher)
    chunks = inventory_peggy_chunks(chunk_roots)
    packets = propose_quality_packets(
        chunks["chunks"],
        pieces_by_chunk={},
        counter=DiagnosticTokenCounter(),
        model_for_sizing="unresolved",
    )
    return {
        "ok": True,
        "inference_authorized": INFERENCE_AUTHORIZED,
        "gate2_smoke_authorized": GATE2_SMOKE_AUTHORIZED,
        "prompt_accepted": PROMPT_ACCEPTED,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_sha256(),
        "models_called": False,
        "pull_executed": False,
        "models": models,
        "chunks": chunks,
        "quality_packets": packets,
        "safety_margin_tokens": SAFETY_MARGIN_TOKENS,
        "token_estimator_id": TOKEN_ESTIMATOR_ID,
        "token_estimator_formula": TOKEN_ESTIMATOR_FORMULA,
        "token_estimator_label": TOKEN_ESTIMATOR_LABEL,
        "context_rule": (
            "evidence + prompt/instructions + output reserve + safety margin <= num_ctx"
        ),
        "proposed_smoke_command": (
            "python -m memorybox i11a0-benchmark --config docs/ops/i11a0_benchmark.example.json "
            "--stage smoke --confirm-benchmark"
        ),
        "smoke_command_status": "gate2_smoke_authorized_confirm_required",
    }
