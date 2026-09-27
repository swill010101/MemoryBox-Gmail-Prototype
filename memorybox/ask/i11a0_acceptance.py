"""Offline acceptance for the I11A.0 harness. No Ollama generation."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_artifacts import (
    QUALITY_COLUMNS,
    _JsonWorkbook,
    _load_json_workbook,
    append_run_workbook,
    load_run_workbook,
    write_quality_row,
    write_results_bundle,
)
from memorybox.ask.i11a.i11a0_benchmark import (
    GATE2_SMOKE_AUTHORIZED,
    APPROVED_MODELS,
    DiagnosticTokenCounter,
    EvidencePiece,
    EvidenceTurn,
    I11A0Config,
    I11A0Error,
    MaterializedEvidence,
    Measurement,
    ModelSpec,
    QuantizationNotAuthorized,
    RunRequest,
    ScriptedLifecycle,
    ThinkingNotAuthorized,
    TokenCount,
    UncertainTokenCount,
    _regressed_against_baseline,
    build_preflight_package,
    classify_measurement,
    compare_i14_successor,
    ORIGINAL_GATE2_GEMMA_RUN_ID,
    apply_original_gemma_smoke_safety_correction,
    evaluate_recorded_prompt_safety,
    prompt_safety_assessment,
    write_identity_supersession,
    inventory_installed_models,
    inventory_peggy_chunks,
    pack_conversation_intact,
    plan_context,
    production_input_size,
    propose_quality_packets,
    recommend_operating_margin,
    refuse_inference_cli,
    refuse_model_pull,
    require_certain,
    run_authorized_stage,
)
from memorybox.ask.i11a.i11a0_prompt import (
    PROMPT_ACCEPTED,
    PRODUCTION_PROMPT_ACCEPTED,
    PROMPT_STATUS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    prompt_sha256,
)


def _production_narrator_source() -> str:
    """Read the production narrator module as text. Do not import Ask/Postgres."""
    return (Path(__file__).resolve().parent / "narrative.py").read_text(encoding="utf-8")


def _check(name: str, condition: bool, checks: list[str], problems: list[str], detail: Any = None) -> None:
    checks.append(name)
    if not condition:
        problems.append(f"{name}: {detail}")


class _CertainCounter:
    def __init__(self, tokens: int = 120) -> None:
        self.tokens = tokens

    def count(self, text: str, *, model: str) -> TokenCount:
        return TokenCount(tokens=self.tokens, method="test_tokenizer", certain=True, model=model)


class _LenCounter:
    def count(self, text: str, *, model: str) -> TokenCount:
        return TokenCount(
            tokens=max(1, len(text)),
            method="test_chars",
            certain=True,
            model=model,
        )


class _ModelAwareCounter:
    def __init__(self, by_model: dict[str, int]) -> None:
        self.by_model = by_model

    def count(self, text: str, *, model: str) -> TokenCount:
        return TokenCount(
            tokens=self.by_model[model],
            method="test_model_tokenizer",
            certain=True,
            model=model,
        )


class _EchoSource:
    def materialize(self, *, model: str, target_tokens: int, counter: Any) -> MaterializedEvidence:
        text = f"packet-{model}-{target_tokens}"
        return MaterializedEvidence(
            text=text,
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            estimated_evidence_tokens=target_tokens,
            evidence_ids=("email_1",),
            partial_context=False,
            partial_boundary_note="none",
            time_start="2010-01-01",
            time_end="2010-12-31",
            certain=True,
        )


def _spec(tag: str = "gemma4:26b", digest: str = "digest-c") -> ModelSpec:
    return ModelSpec(config_id="C", tag=tag, quantization="", digest=digest)


def _config(**overrides: Any) -> I11A0Config:
    models = overrides.pop("models", (_spec(),))
    raw = dict(
        stage="stage1_capacity",
        models=models,
        start_input_tokens=8000,
        increment_tokens=1000,
        refinement_increment_tokens=250,
        maximum_input_tokens=8000,
        prompt_instruction_tokens=100,
    )
    raw.update(overrides)
    return I11A0Config(**raw)


def _stable(size: int, *, tps: float = 100.0, elapsed: float | None = None, vram: float = 10.0) -> Measurement:
    return Measurement(
        prompt_tokens_per_second=tps,
        generation_tokens_per_second=tps,
        elapsed_seconds=elapsed if elapsed is not None else size / 800.0,
        evidence_tokens=size,
        peak_vram_gb=vram,
        gpu_resident=True,
        cpu_spill=False,
        prompt_eval_count=120,
        estimated_prompt_tokens=120,
    )


def _piece(index: int, chars: int, when: str) -> EvidencePiece:
    return EvidencePiece(
        piece_id=f"piece-{index}",
        turns=(EvidenceTurn(f"email_{index}", "x" * chars, when),),
        earliest=when,
        latest=when,
    )


def run_prove_i11a0_benchmark() -> dict[str, Any]:
    import sys

    checks: list[str] = []
    problems: list[str] = []
    prompt_hash = prompt_sha256()
    production_narrator = _production_narrator_source()
    _check(
        "offline_harness_does_not_import_postgres",
        "memorybox.db" not in sys.modules and "psycopg" not in sys.modules,
        checks,
        problems,
    )
    _check("prompt_is_draft", PROMPT_ACCEPTED is False, checks, problems)
    _check(
        "prompt_is_accepted_for_gate2_benchmark_only",
        PROMPT_STATUS == "accepted_for_gate2_benchmark_only"
        and PRODUCTION_PROMPT_ACCEPTED is False,
        checks,
        problems,
        PROMPT_STATUS,
    )
    _check("prompt_hash_stable", prompt_hash == prompt_sha256() and len(prompt_hash) == 64, checks, problems)
    _check(
        "prompt_requests_narrative",
        "documentary family narrative" in SYSTEM_PROMPT and "not an evidence ledger" in SYSTEM_PROMPT,
        checks,
        problems,
    )
    _check(
        "prompt_allows_marked_interpretation",
        "the exchange suggests" in SYSTEM_PROMPT
        and "Do not describe emotions, motives, atmosphere" not in SYSTEM_PROMPT
        and PROMPT_VERSION == "i11a0-narration-v0.2-draft",
        checks,
        problems,
    )
    _check(
        "prompt_is_not_production_narrator",
        "I11A0_BENCHMARK_NARRATION" not in production_narrator and PROMPT_VERSION not in production_narrator,
        checks,
        problems,
    )
    try:
        require_certain(DiagnosticTokenCounter().count("hello", model="gemma4:26b"))
        uncertain_blocked = False
    except UncertainTokenCount:
        uncertain_blocked = True
    _check("bytes_div_4_cannot_control_target", uncertain_blocked, checks, problems)

    try:
        plan_context(
            evidence_tokens=8000,
            prompt_tokens=500,
            reserved_output_tokens=2500,
            safety_margin_tokens=1500,
            num_ctx=12000,
        )
        budget_blocked = False
    except Exception:
        budget_blocked = True
    _check("context_inequality_is_enforced", budget_blocked, checks, problems)
    fitting = plan_context(
        evidence_tokens=8000,
        prompt_tokens=500,
        reserved_output_tokens=2500,
        safety_margin_tokens=1500,
    )
    _check(
        "num_ctx_defaults_to_required_sum",
        fitting.num_ctx == 8000 + 500 + 2500 + 1500,
        checks,
        problems,
        fitting.num_ctx,
    )

    clean_margin = recommend_operating_margin(absolute_estimation_errors=[100], boundary_flips=0)
    raised_margin = recommend_operating_margin(absolute_estimation_errors=[1600], boundary_flips=0)
    clamped_margin = recommend_operating_margin(absolute_estimation_errors=[5000], boundary_flips=2)
    _check(
        "margin_uses_floor_when_measurement_is_clean",
        clean_margin["margin_tokens"] == 1000 and clean_margin["locked_to_1000"] is False,
        checks,
        problems,
        clean_margin,
    )
    _check("margin_rises_inside_range", raised_margin["margin_tokens"] == 1750, checks, problems, raised_margin)
    _check("margin_clamps_at_2000", clamped_margin["margin_tokens"] == 2000, checks, problems, clamped_margin)
    _check(
        "production_size_subtracts_measured_margin",
        production_input_size(largest_stable_tokens=9750, margin_tokens=1750) == 8000,
        checks,
        problems,
    )

    baseline = {
        "prompt_tps": 100.0,
        "generation_tps": 100.0,
        "elapsed_per_token": 10.0 / 8000.0,
    }
    linear = _stable(16000, tps=100.0, elapsed=20.0)
    worse_elapsed = _stable(16000, tps=100.0, elapsed=30.0)
    dropped = _stable(9000, tps=84.0, elapsed=12.0)
    config = _config()
    _check(
        "linear_elapsed_growth_is_not_regression",
        _regressed_against_baseline(linear, config, baseline) is False,
        checks,
        problems,
    )
    _check(
        "elapsed_beyond_trend_is_regression",
        _regressed_against_baseline(worse_elapsed, config, baseline) is True,
        checks,
        problems,
    )
    _check(
        "throughput_drop_over_15_percent_is_regression",
        _regressed_against_baseline(dropped, config, baseline) is True,
        checks,
        problems,
    )
    spill = Measurement(
        prompt_tokens_per_second=100,
        generation_tokens_per_second=100,
        elapsed_seconds=10,
        evidence_tokens=8000,
        cpu_spill=True,
        gpu_resident=False,
        peak_vram_gb=20,
    )
    _check(
        "cpu_spill_is_not_a_successful_gpu_result",
        classify_measurement(spill, vram_ceiling_gb=22.5) == "degraded_cpu_spill",
        checks,
        problems,
    )

    same = "identical peggy evidence bytes"
    same_sha = hashlib.sha256(same.encode("utf-8")).hexdigest()
    aware = _ModelAwareCounter({"model-a": 100, "model-b": 140})
    _check(
        "equal_input_keeps_bytes_and_records_model_tokens",
        aware.count(same, model="model-a").tokens != aware.count(same, model="model-b").tokens
        and hashlib.sha256(same.encode("utf-8")).hexdigest() == same_sha,
        checks,
        problems,
    )

    packed = pack_conversation_intact(
        [_piece(1, 30, "2010-01-01"), _piece(2, 30, "2011-01-01")],
        target_tokens=50,
        counter=_LenCounter(),
        model="gemma4:26b",
    )
    _check(
        "packer_stops_on_conversation_boundary",
        packed.evidence_ids == ("email_1",) and "email_2" not in packed.text,
        checks,
        problems,
        packed.evidence_ids,
    )
    split = pack_conversation_intact(
        [
            EvidencePiece(
                piece_id="wide",
                turns=(
                    EvidenceTurn("email_9", "a" * 30, "2012-01-01"),
                    EvidenceTurn("email_10", "b" * 30, "2012-02-01"),
                ),
                earliest="2012-01-01",
                latest="2012-02-01",
            )
        ],
        target_tokens=40,
        counter=_LenCounter(),
        model="gemma4:26b",
    )
    _check(
        "oversized_thread_splits_only_between_messages",
        split.partial_context and split.evidence_ids == ("email_9",) and "email_10" in split.partial_boundary_note,
        checks,
        problems,
        split,
    )
    try:
        pack_conversation_intact(
            [_piece(3, 100, "2013-01-01")],
            target_tokens=40,
            counter=_LenCounter(),
            model="gemma4:26b",
        )
        unsplittable_blocked = False
    except I11A0Error:
        unsplittable_blocked = True
    _check("single_message_over_target_fails_closed", unsplittable_blocked, checks, problems)

    calls: list[RunRequest] = []

    def _runner(request: RunRequest) -> tuple[Measurement, str]:
        calls.append(request)
        size = request.requested_evidence_tokens
        tps = 100.0 if size < 10000 else 50.0
        vram = 22.5 if request.model_tag == "vram-model" and size >= 9000 else 10.0
        return _stable(size, tps=tps, vram=vram), f"narrative-{size}"

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        knee = run_authorized_stage(
            config=_config(maximum_input_tokens=15000),
            runner=_runner,
            lifecycle=ScriptedLifecycle({"gemma4:26b": {"digest": "digest-c", "quantization": ""}}),
            counter=_CertainCounter(),
            source=_EchoSource(),
            results_dir=root / "knee",
            prompt_tokens=100,
        )
        sizes = knee["models"][0]["sizes_ran"]
        _check(
            "three_confirmed_regressions_stop_the_ladder",
            knee["models"][0]["stop_reason"] == "three_confirmed_regressions"
            and sizes == [8000, 9000, 10000, 11000, 12000],
            checks,
            problems,
            knee["models"][0],
        )
        _check(
            "refinement_uses_250_token_steps",
            knee["models"][0]["largest_stable_tokens"] == 9750,
            checks,
            problems,
            knee["models"][0]["largest_stable_tokens"],
        )
        _check(
            "production_margin_is_not_hard_locked",
            knee["models"][0]["locked_margin_to_1000"] is False
            and knee["models"][0]["operating_margin"]["margin_tokens"] in {1000, 1250, 1500, 1750, 2000},
            checks,
            problems,
            knee["models"][0]["operating_margin"],
        )
        vram = run_authorized_stage(
            config=_config(
                maximum_input_tokens=15000,
                models=(ModelSpec("V", "vram-model", "", "digest-v"),),
            ),
            runner=_runner,
            lifecycle=ScriptedLifecycle({"vram-model": {"digest": "digest-v", "quantization": ""}}),
            counter=_CertainCounter(),
            source=_EchoSource(),
            results_dir=root / "vram",
            prompt_tokens=100,
        )
        _check(
            "vram_ceiling_stops_before_a_larger_size",
            vram["models"][0]["stop_reason"] == "vram_ceiling"
            and 10000 not in vram["models"][0]["sizes_ran"],
            checks,
            problems,
            vram["models"][0],
        )
        resume_config = _config()
        life = ScriptedLifecycle({"gemma4:26b": {"digest": "digest-c", "quantization": ""}})
        first = run_authorized_stage(
            config=resume_config,
            runner=_runner,
            lifecycle=life,
            counter=_CertainCounter(),
            source=_EchoSource(),
            results_dir=root / "resume",
            prompt_tokens=100,
        )
        calls_after_first = len(calls)
        second = run_authorized_stage(
            config=resume_config,
            runner=_runner,
            lifecycle=ScriptedLifecycle({"gemma4:26b": {"digest": "digest-c", "quantization": ""}}),
            counter=_CertainCounter(),
            source=_EchoSource(),
            results_dir=root / "resume",
            prompt_tokens=100,
        )
        _check(
            "resume_does_not_duplicate_completed_runs",
            first["run_count"] > 0 and second["skipped"] == first["run_count"] and len(calls) == calls_after_first,
            checks,
            problems,
            {"first": first["run_count"], "skipped": second["skipped"], "calls": len(calls) - calls_after_first},
        )
        failed = run_authorized_stage(
            config=_config(
                models=(
                    _spec(),
                    ModelSpec("B", "qwen3:14b-q8_0", "Q8_0", "digest-b"),
                )
            ),
            runner=_runner,
            lifecycle=ScriptedLifecycle(
                {
                    "gemma4:26b": {"digest": "digest-c", "quantization": ""},
                    "qwen3:14b-q8_0": {"digest": "digest-b", "quantization": "Q8_0"},
                },
                fail_on="load:qwen3:14b-q8_0",
            ),
            counter=_CertainCounter(),
            source=_EchoSource(),
            results_dir=root / "lifecycle",
            prompt_tokens=100,
        )
        _check(
            "lifecycle_failure_stops_and_keeps_earlier_results",
            failed["ok"] is False
            and failed["models"][0]["stop_reason"] == "maximum_input_tokens"
            and failed["models"][1]["stop_reason"] == "lifecycle_failure"
            and "unload:gemma4:26b" in failed["lifecycle_events"],
            checks,
            problems,
            failed,
        )
        smoke_calls = len(calls)
        smoke = run_authorized_stage(
            config=_config(stage="smoke", maximum_input_tokens=None),
            runner=_runner,
            lifecycle=ScriptedLifecycle({"gemma4:26b": {"digest": "digest-c", "quantization": ""}}),
            counter=_CertainCounter(),
            source=_EchoSource(),
            results_dir=root / "smoke",
            prompt_tokens=100,
        )
        _check(
            "smoke_stage_invokes_one_run",
            smoke["stop_reason"] == "smoke_complete" and len(calls) == smoke_calls + 1,
            checks,
            problems,
            smoke,
        )
        smoke_again = run_authorized_stage(
            config=_config(stage="smoke", maximum_input_tokens=None),
            runner=_runner,
            lifecycle=ScriptedLifecycle({"gemma4:26b": {"digest": "digest-c", "quantization": ""}}),
            counter=_CertainCounter(),
            source=_EchoSource(),
            results_dir=root / "smoke",
            prompt_tokens=100,
        )
        _check(
            "repeat_smoke_gets_unique_execution_id",
            smoke_again["execution_id"] != smoke["execution_id"]
            and smoke_again["test_case_id"] == smoke["test_case_id"]
            and smoke_again["run_id"] != smoke["run_id"]
            and len(calls) == smoke_calls + 2,
            checks,
            problems,
            {"first": smoke["run_id"], "second": smoke_again["run_id"], "case": smoke["test_case_id"]},
        )
        shared = {
            "identity": "0717c7de073416f1200ce2047b39c961161d9ffe674f8374657700273117a24e",
            "classification": "successful_stable",
            "request": {
                "model_tag": "gemma4:26b",
                "digest": "digest-c",
                "requested_evidence_tokens": 1000,
                "evidence_sha256": "abc",
                "repetition": 1,
                "warm_or_cold": "cold",
                "confirmation": False,
                "thinking_mode": "off",
                "seed": 42,
                "num_ctx": 6144,
                "reserved_output_tokens": 2500,
                "prompt_sha256": prompt_hash,
            },
        }
        desktop_dup = root / "desktop-dup" / shared["identity"]
        flight_dup = root / "flight-dup" / shared["identity"]
        desktop_dup.mkdir(parents=True)
        flight_dup.mkdir(parents=True)
        (desktop_dup / "run_record.json").write_text(json.dumps(shared) + "\n", encoding="utf-8")
        (flight_dup / "run_record.json").write_text(json.dumps(shared) + "\n", encoding="utf-8")
        desktop_ids = write_identity_supersession(
            desktop_dup,
            controller_hostname="Toms-Desktop",
            started_at_utc="2026-09-26T18:37:00Z",
            role="functional_token_safety_pass_hardware_telemetry_invalid",
        )
        flight_ids = write_identity_supersession(
            flight_dup,
            controller_hostname="FlightSim",
            started_at_utc="2026-09-26T19:01:54Z",
            role="flightsim_hardware_smoke",
        )
        _check(
            "duplicate_legacy_run_ids_receive_separate_execution_ids",
            desktop_ids["legacy_identity"] == flight_ids["legacy_identity"]
            and desktop_ids["test_case_id"] == flight_ids["test_case_id"]
            and desktop_ids["execution_id"] != flight_ids["execution_id"]
            and json.loads((desktop_dup / "run_record.json").read_text(encoding="utf-8"))["identity"]
            == shared["identity"],
            checks,
            problems,
            {"desktop": desktop_ids["execution_id"], "flight": flight_ids["execution_id"]},
        )
        _check(
            "conservative_overestimate_is_not_a_safety_failure",
            smoke["ok"] is True
            and (smoke.get("token_accounting") or {}).get("final_safety_result")
            in {"passed", "passed_conservative_overestimate"},
            checks,
            problems,
            smoke.get("token_accounting"),
        )
        original_values = prompt_safety_assessment(
            actual_prompt_tokens=2075,
            estimated_prompt_tokens=1893,
            configured_num_ctx=5893,
            output_reserve_tokens=2500,
            required_safety_margin_tokens=1500,
            pipeline_execution="passed",
            generation_completion="passed",
        )
        _check(
            "original_gemma_values_fail_safety_margin_by_182",
            original_values["required_context_tokens"] == 6075
            and original_values["remaining_context_after_prompt_and_output"] == 1318
            and original_values["remaining_safety_margin_tokens"] == 1318
            and original_values["safety_margin_shortfall_tokens"] == 182
            and original_values["context_overflow"] is False
            and original_values["pipeline_execution"] == "passed"
            and original_values["generation_completion"] == "passed"
            and original_values["final_safety_result"] == "failed"
            and original_values["overall_classification"]
            == "successful_pipeline_safety_margin_failed",
            checks,
            problems,
            original_values,
        )
        exact_pass = evaluate_recorded_prompt_safety(
            actual_prompt_eval_count=2075,
            estimated_total_prompt_tokens=1893,
            num_ctx=6075,
            reserved_output_tokens=2500,
            safety_margin_tokens=1500,
        )
        _check(
            "same_values_pass_exactly_at_num_ctx_6075",
            exact_pass["required_context_tokens"] == 6075
            and exact_pass["safety_margin_shortfall_tokens"] == 0
            and exact_pass["remaining_safety_margin_tokens"] == 1500
            and exact_pass["final_safety_result"] == "passed"
            and exact_pass["overall_classification"] == "successful_stable",
            checks,
            problems,
            exact_pass,
        )
        overestimate = prompt_safety_assessment(
            actual_prompt_tokens=2075,
            estimated_prompt_tokens=2300,
            configured_num_ctx=6075,
            output_reserve_tokens=2500,
            required_safety_margin_tokens=1500,
        )
        _check(
            "conservative_overestimate_does_not_fail_when_equation_passes",
            overestimate["estimation_error_tokens"] == -225
            and overestimate["final_safety_result"] == "passed"
            and overestimate["enlargement_stop"] is False
            and overestimate["overall_classification"] == "successful_stable",
            checks,
            problems,
            overestimate,
        )
        enlargement_stop = prompt_safety_assessment(
            actual_prompt_tokens=3601,
            estimated_prompt_tokens=2100,
            configured_num_ctx=7601,
            output_reserve_tokens=2500,
            required_safety_margin_tokens=1500,
        )
        _check(
            "positive_estimation_error_over_1500_stops_enlargement",
            enlargement_stop["estimation_error_tokens"] == 1501
            and enlargement_stop["enlargement_stop"] is True
            and enlargement_stop["final_safety_result"] == "passed"
            and enlargement_stop["overall_classification"]
            == "successful_pipeline_recalibrate",
            checks,
            problems,
            enlargement_stop,
        )
        completed_without_overflow = original_values
        _check(
            "completed_generation_without_overflow_can_fail_safety_margin",
            completed_without_overflow["context_overflow"] is False
            and completed_without_overflow["generation_completion"] == "passed"
            and completed_without_overflow["final_safety_result"] == "failed",
            checks,
            problems,
            completed_without_overflow,
        )
        original_dir = root / ORIGINAL_GATE2_GEMMA_RUN_ID
        original_dir.mkdir(parents=True, exist_ok=True)
        original_record = {
            "identity": ORIGINAL_GATE2_GEMMA_RUN_ID,
            "classification": "successful_stable",
            "skipped": False,
            "request": {"num_ctx": 5893},
            "measurement": {
                "prompt_eval_count": 2075,
                "estimated_prompt_tokens": 1893,
                "configured_num_ctx": 5893,
                "output_reserve_tokens": 2500,
                "safety_margin_tokens": 1500,
                "final_safety_result": "passed",
            },
        }
        (original_dir / "run_record.json").write_text(
            json.dumps(original_record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        original_hash = hashlib.sha256((original_dir / "run_record.json").read_bytes()).hexdigest()
        correction = apply_original_gemma_smoke_safety_correction(original_dir)
        rewritten_hash = hashlib.sha256((original_dir / "run_record.json").read_bytes()).hexdigest()
        preserved = json.loads((original_dir / "run_record.json").read_text(encoding="utf-8"))
        _check(
            "original_run_is_preserved_and_superseded",
            original_hash == rewritten_hash
            and preserved["classification"] == "successful_stable"
            and preserved["measurement"]["final_safety_result"] == "passed"
            and correction["corrected_overall_classification"]
            == "successful_pipeline_safety_margin_failed"
            and (original_dir / "safety_assessment_correction.json").exists(),
            checks,
            problems,
            correction,
        )
        try:
            run_authorized_stage(
                config=_config(thinking_mode="on", authorize_thinking_comparison=False),
                runner=_runner,
                lifecycle=ScriptedLifecycle({"gemma4:26b": {"digest": "digest-c"}}),
                counter=_CertainCounter(),
                source=_EchoSource(),
                results_dir=root / "think",
                prompt_tokens=100,
            )
            thinking_blocked = False
        except ThinkingNotAuthorized:
            thinking_blocked = True
        _check("thinking_on_is_blocked_in_the_initial_screen", thinking_blocked, checks, problems)
        try:
            run_authorized_stage(
                config=_config(alternate_quantization_tag="qwen3:14b-q4_0"),
                runner=_runner,
                lifecycle=ScriptedLifecycle({"gemma4:26b": {"digest": "digest-c"}}),
                counter=_CertainCounter(),
                source=_EchoSource(),
                results_dir=root / "quant",
                prompt_tokens=100,
            )
            quant_blocked = False
        except QuantizationNotAuthorized:
            quant_blocked = True
        _check("alternate_quantization_blocked_before_gate_4", quant_blocked, checks, problems)
        try:
            run_authorized_stage(
                config=_config(stage="quality_comparison", founder_gate3_accepted=True),
                runner=_runner,
                lifecycle=ScriptedLifecycle({"gemma4:26b": {"digest": "digest-c"}}),
                counter=_CertainCounter(),
                source=_EchoSource(),
                results_dir=root / "quality-stage",
                prompt_tokens=100,
            )
            quality_blocked = False
        except Exception:
            quality_blocked = True
        _check("quality_generation_is_not_started_by_this_build", quality_blocked, checks, problems)

        workbook = root / "book.xlsx"
        append_run_workbook(
            workbook,
            {
                "run_id": "r1",
                "model": "gemma4:26b",
                "classification": "successful_stable",
                "narration_relpath": "narrations/r1.txt",
                "record_relpath": "r1/run_record.json",
            },
        )
        append_run_workbook(workbook, {"run_id": "r2", "model": "gemma4:26b", "classification": "successful_stable"})
        book = load_run_workbook(workbook)
        _check(
            "workbook_has_four_sheets_and_appends",
            book.sheetnames == ["Runs", "Quality Review", "Configuration", "Summary"]
            and book["Runs"].max_row == 3,
            checks,
            problems,
            book.sheetnames,
        )
        blinded_error = False
        try:
            write_quality_row(workbook, {"blind_id": "B1", "model": "gemma4:26b"})
        except ValueError:
            blinded_error = True
        _check("quality_sheet_rejects_model_identity", blinded_error, checks, problems)
        write_quality_row(
            workbook,
            {"blind_id": "B1", "comparison_view": "equal_input", "packet_sha256": "abc"},
        )
        headers = [cell.value for cell in load_run_workbook(workbook)["Quality Review"][2]]
        _check(
            "quality_sheet_columns_have_no_model",
            "model" not in headers and headers[0] == QUALITY_COLUMNS[0],
            checks,
            problems,
            headers,
        )
        fallback = root / "fallback.json"
        json_book = _JsonWorkbook()
        json_book.active.title = "Runs"
        json_book.active.append(["run_id"])
        json_book.create_sheet("Quality Review")
        json_book.save(fallback)
        loaded_fallback = _load_json_workbook(fallback)
        _check(
            "workbook_stdlib_fallback_roundtrip",
            loaded_fallback.sheetnames == ["Runs", "Quality Review"]
            and loaded_fallback["Runs"].max_row == 1,
            checks,
            problems,
        )
        bundle = write_results_bundle(
            bundle_dir=root / "bundle",
            workbook_path=workbook,
            summary_markdown="# knee\n",
            run_rows=[{"run_id": "r1", "model": "gemma4:26b"}],
            narrations={"r1": "A short narrative."},
            raw_responses={"r1": "{}"},
            telemetry={"r1": "{}"},
            console_logs={"r1": "log"},
            validation={"r1": "{}"},
            config_text="{}\n",
            prompt_text=SYSTEM_PROMPT,
            manifests={"input": "{}"},
            identity_map={"B1": "gemma4:26b"},
        )
        required = [
            "benchmark_results.xlsx",
            "benchmark_summary.md",
            "runs.csv",
            "runs.jsonl",
            "narrations/r1.txt",
            "raw/r1.json",
            "telemetry/r1.jsonl",
            "console/r1.log",
            "validation/r1.json",
            "prompts/PROMPT_SHA256.txt",
            "sealed/identity_map.json",
            "HASHES.txt",
        ]
        _check(
            "bundle_contains_the_review_package",
            bundle["ok"] and all((root / "bundle" / name).is_file() for name in required),
            checks,
            problems,
            required,
        )

        for index in range(1, 8):
            folder = root / "chunks"
            folder.mkdir(exist_ok=True)
            paste = (
                "===== SYSTEM INSTRUCTIONS =====\nreview\n\n"
                "===== USER QUESTION AND EVIDENCE =====\nTell the story.\n\n"
                "===== TRUSTED EMAIL CONVERSATIONS =====\n\n"
                f"BEGIN CONVERSATION: synthetic-{index}\n"
                f"201{index}-06-01 — Peggy said: [email_{index}]\n"
                "Hello from the synthetic packet.\n"
                "END CONVERSATION\n"
            )
            (folder / f"CHUNK_{index:03d}_MODEL_PASTE.txt").write_text(paste, encoding="utf-8", newline="\n")
        (folder / "SOURCE_MAP.json").write_text(
            json.dumps(
                {
                    "citations": [
                        {"cite_as": f"email_{index}", "sent_at": f"201{index}-06-01"}
                        for index in range(1, 8)
                    ]
                }
            ),
            encoding="utf-8",
        )
        listed = inventory_peggy_chunks([folder])
        _check(
            "seven_synthetic_chunks_inventory_without_a_model",
            listed["chunk_count"] == 7
            and listed["seven_chunk_pool_found"]
            and listed["models_called"] is False
            and all(row["artifact_status"] == "not_compared" for row in listed["chunks"])
            and all(row["message_count"] == 1 for row in listed["chunks"]),
            checks,
            problems,
            listed["chunks"],
        )
        pieces: dict[str, list[EvidencePiece]] = {}
        for row, index in zip(listed["chunks"], range(1, 8)):
            pieces[row["path"]] = [_piece(index, 20, f"201{index}-06-01")]
        proposed = propose_quality_packets(
            listed["chunks"],
            pieces_by_chunk=pieces,
            counter=_LenCounter(),
            model_for_sizing="gemma4:26b",
            max_evidence_tokens=25,
        )
        packet_ids = [packet["packet_id"] for packet in proposed["packets"]]
        early = proposed["packets"][0]["time_start"]
        later = proposed["packets"][2]["time_start"]
        _check(
            "quality_packets_cover_early_middle_and_later",
            proposed["status"] == "proposed"
            and packet_ids == ["quality-early", "quality-middle", "quality-later"]
            and early < later,
            checks,
            problems,
            proposed,
        )
        huge = "H" * 722_000
        huge_chunks = [{"path": f"c{i}", "sha256": str(i)} for i in range(7)]
        huge_pieces = {
            f"c{i}": [
                EvidencePiece(
                    piece_id=f"huge-{i}",
                    turns=(EvidenceTurn(f"email_{i}", huge if i == 0 else "small", f"201{i}-01-01"),),
                    earliest=f"201{i}-01-01",
                    latest=f"201{i}-01-02",
                )
            ]
            for i in range(7)
        }
        huge_proposal = propose_quality_packets(
            huge_chunks,
            pieces_by_chunk=huge_pieces,
            counter=_LenCounter(),
            model_for_sizing="gemma4:26b",
            max_evidence_tokens=1000,
        )
        early_text_ids = huge_proposal["packets"][0]["evidence_ids"]
        _check(
            "oversized_chunk_is_not_sent_whole",
            "email_0" not in early_text_ids and huge_proposal["packets"][0]["bytes"] < 722_000,
            checks,
            problems,
            huge_proposal["packets"][0],
        )
        unchanged = compare_i14_successor(b"same", b"same")
        changed = compare_i14_successor(b"original line\n", b"successor line\n")
        _check(
            "i14_diff_preserves_both_hashes",
            unchanged["artifact_status"] == "unchanged"
            and changed["artifact_status"] == "needs_i14_successor"
            and changed["original_sha256"] != changed["successor_sha256"]
            and changed["diff_line_count"] > 0,
            checks,
            problems,
            changed,
        )

    with tempfile.TemporaryDirectory() as manifest_dir:
        folder = Path(manifest_dir)
        body = b"reviewed chunk bytes\n"
        (folder / "CHUNK_001_MODEL_PASTE.txt").write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        (folder / "CHUNK_MANIFEST.json").write_text(
            json.dumps(
                {
                    "chunks": [
                        {
                            "chunk_index": 1,
                            "paste_file": "CHUNK_001_MODEL_PASTE.txt",
                            "chunk_sha256": digest,
                            "conversation_count": 4,
                            "message_count": 9,
                            "date_range": {"start": "2009-01-01", "end": "2009-02-01"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (folder / "LOCAL_MANIFEST.json").write_text(
            json.dumps({"source_commit": "abc123", "frozen_input_sha256": "ff"}),
            encoding="utf-8",
        )
        listed = inventory_peggy_chunks([folder])
        row = listed["chunks"][0]
        _check(
            "manifest_paste_file_fields_are_read",
            row["conversation_count"] == 4
            and row["message_count"] == 9
            and row["date_start"] == "2009-01-01"
            and row["sha256"] == digest
            and row["artifact_status"] == "reviewed_manifest_match"
            and any(item["role"] == "manifest" for item in listed["companions"])
            and any(item["role"] == "generation_metadata" for item in listed["companions"]),
            checks,
            problems,
            row,
        )

    seen: list[str] = []

    def _fetcher(method: str, url: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        seen.append(url)
        if url.endswith("/api/generate") or url.endswith("/api/chat") or url.endswith("/api/pull"):
            raise AssertionError(url)
        if url.endswith("/api/version"):
            return {"version": "0.test"}
        if url.endswith("/api/tags"):
            return {
                "models": [
                    {"name": "gemma4:26b", "digest": "sha256:gemma", "size": 123},
                    {"name": "qwen3:30b", "digest": "sha256:alias", "size": 456},
                ]
            }
        if url.endswith("/api/show"):
            return {
                "details": {"quantization_level": "Q4_0"},
                "model_info": {"gemma4.context_length": 131072},
            }
        raise AssertionError(url)

    inventoried = inventory_installed_models(fetcher=_fetcher)
    by_id = {row["config_id"]: row for row in inventoried["approved"]}
    _check(
        "model_inventory_does_not_generate_or_pull",
        inventoried["pull_executed"] is False
        and inventoried["models_called"] is False
        and all("/api/generate" not in url and "/api/pull" not in url for url in seen)
        and by_id["C"]["status"] == "installed"
        and by_id["C"]["digest"] == "sha256:gemma"
        and by_id["C"]["context_length"] == 131072
        and by_id["A"]["status"] == "alias_present_not_accepted"
        and by_id["A"]["accepted_for_screen"] is False
        and by_id["B"]["status"] == "missing"
        and "ollama pull qwen3:14b-q8_0" in inventoried["manual_install_commands"]
        and "ollama pull gemma4:26b" not in inventoried["manual_install_commands"],
        checks,
        problems,
        inventoried,
    )
    try:
        refuse_model_pull()
        pull_blocked = False
    except Exception:
        pull_blocked = True
    _check("automatic_model_pull_is_forbidden", pull_blocked, checks, problems)
    try:
        refuse_inference_cli()
        inference_blocked = False
    except Exception as exc:
        inference_blocked = "confirm-benchmark" in str(exc)
    _check("cli_refuses_inference_without_smoke_confirm", inference_blocked, checks, problems)
    from memorybox.ask.i11a.i11a0_smoke import (
        PINNED_C_DIGEST,
        INITIAL_A_EXECUTION_ID,
        INITIAL_B_EXECUTION_ID,
        PINNED_A_DIGEST,
        PINNED_B_DIGEST,
        _select_installed_smoke_model,
        _select_installed_smoke_models,
        require_qwen_smoke_configuration,
        refuse_inherited_num_ctx,
        write_qwen_a_initial_calibration,
        write_qwen_b_initial_calibration,
    )
    from memorybox.ask.i11a.i11a0_host import (
        REMOTE_FUNCTIONAL_LABEL,
        REMOTE_FUNCTIONAL_RUN_ID,
        VRAM_CEILING_GB,
        HardwareSampler,
        HostAffinityError,
        collect_host_affinity_preflight,
        label_remote_functional_run,
        require_flightsim_host_affinity,
    )

    selected = _select_installed_smoke_model(
        (ModelSpec("C", "gemma4:26b", "Q4_K_M", PINNED_C_DIGEST),),
        {
            "approved": [
                {
                    "tag": "qwen3:30b-a3b-instruct-2507-q4_K_M",
                    "status": "missing",
                    "accepted_for_screen": False,
                },
                {
                    "tag": "gemma4:26b",
                    "status": "installed",
                    "accepted_for_screen": True,
                    "digest": PINNED_C_DIGEST,
                    "quantization": "Q4_K_M",
                },
            ]
        },
    )
    _check(
        "gate2_smoke_selects_installed_configuration_c",
        selected.tag == "gemma4:26b" and selected.digest == PINNED_C_DIGEST,
        checks,
        problems,
        selected,
    )
    a_row = {
        "status": "installed",
        "accepted_for_screen": True,
        "digest": "digest-a",
        "quantization": "Q4_K_M",
        "metadata": {"architecture": "qwen3", "parameter_size": "30.5B", "quantization": "Q4_K_M"},
    }
    b_row = {
        "status": "installed",
        "accepted_for_screen": True,
        "digest": "digest-b",
        "quantization": "Q8_0",
        "metadata": {"architecture": "qwen3", "parameter_size": "14.8B", "quantization": "Q8_0"},
    }
    verified_a = require_qwen_smoke_configuration(
        ModelSpec("A", "qwen3:30b-a3b-instruct-2507-q4_K_M", "Q4_K_M", "digest-a"),
        a_row,
    )
    verified_b = require_qwen_smoke_configuration(
        ModelSpec("B", "qwen3:14b-q8_0", "Q8_0", "digest-b"),
        b_row,
    )
    _check(
        "qwen_a_and_b_metadata_must_match_approved_tags",
        verified_a["verified"] is True and verified_b["verified"] is True,
        checks,
        problems,
        {"A": verified_a, "B": verified_b},
    )
    wrong_b = False
    try:
        require_qwen_smoke_configuration(
            ModelSpec("B", "qwen3:14b-q8_0", "Q8_0", "digest-b"),
            {
                "quantization": "Q4_K_M",
                "metadata": {"architecture": "qwen3", "parameter_size": "14.8B"},
            },
        )
    except I11A0Error:
        wrong_b = True
    _check("qwen_b_wrong_quantization_is_refused", wrong_b, checks, problems)
    ab_selected = _select_installed_smoke_models(
        (
            ModelSpec("A", "qwen3:30b-a3b-instruct-2507-q4_K_M", "Q4_K_M", "digest-a"),
            ModelSpec("B", "qwen3:14b-q8_0", "Q8_0", "digest-b"),
        ),
        {
            "approved": [
                {
                    "tag": "qwen3:30b-a3b-instruct-2507-q4_K_M",
                    **a_row,
                },
                {
                    "tag": "qwen3:14b-q8_0",
                    **b_row,
                },
            ]
        },
    )
    _check(
        "gate2_ab_selects_both_installed_qwen_tags",
        [row.tag for row in ab_selected]
        == ["qwen3:30b-a3b-instruct-2507-q4_K_M", "qwen3:14b-q8_0"],
        checks,
        problems,
        ab_selected,
    )
    missing_b = False
    try:
        _select_installed_smoke_models(
            (
                ModelSpec("A", "qwen3:30b-a3b-instruct-2507-q4_K_M", "Q4_K_M", "digest-a"),
                ModelSpec("B", "qwen3:14b-q8_0", "Q8_0", "digest-b"),
            ),
            {"approved": [{"tag": "qwen3:30b-a3b-instruct-2507-q4_K_M", **a_row}]},
        )
    except I11A0Error:
        missing_b = True
    _check("gate2_ab_stops_if_b_is_missing", missing_b, checks, problems)
    a_first = prompt_safety_assessment(
        actual_prompt_tokens=1980,
        estimated_prompt_tokens=1893,
        configured_num_ctx=5893,
        output_reserve_tokens=2500,
        required_safety_margin_tokens=1500,
        pipeline_execution="passed",
        generation_completion="passed",
    )
    _check(
        "qwen_a_initial_values_fail_safety_margin_by_87",
        a_first["estimation_error_tokens"] == 87
        and a_first["required_context_tokens"] == 5980
        and a_first["safety_margin_shortfall_tokens"] == 87
        and a_first["overall_classification"] == "successful_pipeline_safety_margin_failed",
        checks,
        problems,
        a_first,
    )
    a_cal = prompt_safety_assessment(
        actual_prompt_tokens=1980,
        estimated_prompt_tokens=1893,
        configured_num_ctx=6144,
        output_reserve_tokens=2500,
        required_safety_margin_tokens=1500,
    )
    _check(
        "qwen_a_calibrated_num_ctx_6144_passes_the_equation",
        a_cal["required_context_tokens"] == 5980
        and a_cal["final_safety_result"] == "passed"
        and a_cal["overall_classification"] == "successful_stable",
        checks,
        problems,
        a_cal,
    )
    b_pin_blocked = False
    try:
        refuse_inherited_num_ctx("B", 6144, ("A", "B"))
    except I11A0Error as exc:
        b_pin_blocked = "must not reuse Configuration A's calibrated num_ctx" in str(exc)
    _check("qwen_b_cannot_inherit_a_calibrated_num_ctx", b_pin_blocked, checks, problems)
    refuse_inherited_num_ctx("B", 6144, ("B",))
    _check("qwen_b_may_use_own_calibrated_num_ctx_6144", True, checks, problems)
    refuse_inherited_num_ctx("A", 6144)
    _check("qwen_a_may_use_calibrated_num_ctx_6144", True, checks, problems)
    b_first = prompt_safety_assessment(
        actual_prompt_tokens=1978,
        estimated_prompt_tokens=1893,
        configured_num_ctx=5893,
        output_reserve_tokens=2500,
        required_safety_margin_tokens=1500,
        pipeline_execution="passed",
        generation_completion="passed",
    )
    _check(
        "qwen_b_initial_values_fail_safety_margin_by_85",
        b_first["estimation_error_tokens"] == 85
        and b_first["required_context_tokens"] == 5978
        and b_first["safety_margin_shortfall_tokens"] == 85
        and b_first["overall_classification"] == "successful_pipeline_safety_margin_failed",
        checks,
        problems,
        b_first,
    )
    b_cal = prompt_safety_assessment(
        actual_prompt_tokens=1978,
        estimated_prompt_tokens=1893,
        configured_num_ctx=6144,
        output_reserve_tokens=2500,
        required_safety_margin_tokens=1500,
    )
    _check(
        "qwen_b_calibrated_num_ctx_6144_passes_the_equation",
        b_cal["required_context_tokens"] == 5978
        and b_cal["final_safety_result"] == "passed"
        and b_cal["overall_classification"] == "successful_stable",
        checks,
        problems,
        b_cal,
    )
    with tempfile.TemporaryDirectory() as a_dir:
        a_path = Path(a_dir) / INITIAL_A_EXECUTION_ID
        a_path.mkdir()
        (a_path / "run_record.json").write_text(
            json.dumps(
                {
                    "identity": INITIAL_A_EXECUTION_ID,
                    "execution_id": INITIAL_A_EXECUTION_ID,
                    "classification": "successful_pipeline_safety_margin_failed",
                    "measurement": {
                        "estimated_prompt_tokens": 1893,
                        "actual_prompt_tokens": 1980,
                        "estimation_error_tokens": 87,
                        "required_context_tokens": 5980,
                        "configured_num_ctx": 5893,
                        "safety_margin_shortfall_tokens": 87,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        before = hashlib.sha256((a_path / "run_record.json").read_bytes()).hexdigest()
        recorded = write_qwen_a_initial_calibration(a_path)
        after = hashlib.sha256((a_path / "run_record.json").read_bytes()).hexdigest()
        _check(
            "qwen_a_initial_run_is_preserved_with_plus_87_calibration",
            before == after
            and recorded["estimation_error_tokens"] == 87
            and recorded["classification"] == "successful_pipeline_safety_margin_failed"
            and recorded["calibrated_num_ctx"] == 6144
            and recorded["do_not_apply_to_configuration_b"] is True,
            checks,
            problems,
            recorded,
        )
    with tempfile.TemporaryDirectory() as b_dir:
        b_path = Path(b_dir) / INITIAL_B_EXECUTION_ID
        b_path.mkdir()
        (b_path / "run_record.json").write_text(
            json.dumps(
                {
                    "identity": INITIAL_B_EXECUTION_ID,
                    "execution_id": INITIAL_B_EXECUTION_ID,
                    "classification": "successful_pipeline_safety_margin_failed",
                    "measurement": {
                        "estimated_prompt_tokens": 1893,
                        "actual_prompt_tokens": 1978,
                        "estimation_error_tokens": 85,
                        "required_context_tokens": 5978,
                        "configured_num_ctx": 5893,
                        "safety_margin_shortfall_tokens": 85,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        before_b = hashlib.sha256((b_path / "run_record.json").read_bytes()).hexdigest()
        recorded_b = write_qwen_b_initial_calibration(b_path)
        after_b = hashlib.sha256((b_path / "run_record.json").read_bytes()).hexdigest()
        _check(
            "qwen_b_initial_run_is_preserved_with_plus_85_calibration",
            before_b == after_b
            and recorded_b["estimation_error_tokens"] == 85
            and recorded_b["classification"] == "successful_pipeline_safety_margin_failed"
            and recorded_b["calibrated_num_ctx"] == 6144
            and recorded_b["do_not_reuse_configuration_a_error"] is True,
            checks,
            problems,
            recorded_b,
        )
    from memorybox.ask.i11a.i11a0_gate2_review import assemble_gate2_review_package

    def _fake_calibrated(folder: Path, *, config_id: str, tag: str, digest: str, actual: int, execution_id: str) -> None:
        folder.mkdir(parents=True)
        (folder / "run_record.json").write_text(
            json.dumps(
                {
                    "classification": "successful_stable",
                    "execution_id": execution_id,
                    "measurement": {
                        "estimated_prompt_tokens": 1893,
                        "actual_prompt_tokens": actual,
                        "estimation_error_tokens": actual - 1893,
                        "configured_num_ctx": 6144,
                        "output_reserve_tokens": 2500,
                        "required_safety_margin_tokens": 1500,
                        "elapsed_seconds": 10,
                        "prompt_tokens_per_second": 100,
                        "generation_tokens_per_second": 50,
                        "peak_vram_gb": 20.0,
                        "gpu_resident": True,
                    },
                    "request": {
                        "model_tag": tag,
                        "digest": digest,
                        "num_ctx": 6144,
                        "evidence_sha256": "packet",
                        "prompt_sha256": "prompt",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (folder / "narration.txt").write_text(f"narration {config_id}\n", encoding="utf-8")
        (folder / "raw_api.jsonl").write_text("{}\n", encoding="utf-8")
        (folder / "telemetry.jsonl").write_text("{}\n", encoding="utf-8")
        (folder / "hardware_telemetry.json").write_text(
            json.dumps(
                {
                    "vram_baseline_gb": 2.0,
                    "vram_peak_gb": 20.0,
                    "vram_final_gb": 2.0,
                    "ram_baseline_gb": 20.0,
                    "ram_peak_gb": 21.0,
                    "ram_final_gb": 20.0,
                    "gpu_resident": True,
                    "cpu_offload": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (folder / "model_metadata.json").write_text(
            json.dumps(
                {
                    "architecture": "arch-" + config_id,
                    "quantization": "QTEST",
                    "tag": tag,
                    "digest": digest,
                }
            )
            + "\n",
            encoding="utf-8",
        )

    with tempfile.TemporaryDirectory() as pkg_dir:
        base = Path(pkg_dir)
        a_cal_dir = base / "A"
        b_cal_dir = base / "B"
        c_cal_dir = base / "C"
        _fake_calibrated(
            a_cal_dir,
            config_id="A",
            tag="qwen3:30b-a3b-instruct-2507-q4_K_M",
            digest=PINNED_A_DIGEST,
            actual=1980,
            execution_id="exec-a",
        )
        _fake_calibrated(
            b_cal_dir,
            config_id="B",
            tag="qwen3:14b-q8_0",
            digest=PINNED_B_DIGEST,
            actual=1978,
            execution_id="exec-b",
        )
        _fake_calibrated(
            c_cal_dir,
            config_id="C",
            tag="gemma4:26b",
            digest=PINNED_C_DIGEST,
            actual=2075,
            execution_id="exec-c",
        )
        packaged = assemble_gate2_review_package(
            a_dir=a_cal_dir,
            b_dir=b_cal_dir,
            c_dir=c_cal_dir,
            out_dir=base / "package",
        )
        summary = (base / "package" / "benchmark_summary.md").read_text(encoding="utf-8")
        identity = json.loads((base / "package" / "sealed" / "identity_map.json").read_text(encoding="utf-8"))
        _check(
            "gate2_review_package_is_blinded_and_does_not_name_a_winner",
            packaged.get("ok") is True
            and packaged.get("winner_recommendation") is None
            and "winner_recommendation: none" in summary
            and "Candidate-1" in summary
            and identity
            and (base / "package" / "runs.csv").is_file()
            and (base / "package" / "runs.jsonl").is_file()
            and (base / "package" / "quality_score_sheet.md").is_file(),
            checks,
            problems,
            packaged,
        )
    _check("gate2_smoke_is_authorized_flag", GATE2_SMOKE_AUTHORIZED is True, checks, problems)
    rtx_preflight = collect_host_affinity_preflight(
        ollama_base_url="http://127.0.0.1:11434",
        output_path="C:/memorybox/docs/test-output/i11a0-benchmark/smoke-flightsim",
        chunks_path="C:/memorybox/docs/test-output/trusted-email-review/REVIEW_20260831T120929Z",
        repo=Path("."),
        nvidia_reader=lambda: {
            "available": True,
            "name": "NVIDIA GeForce RTX 4090",
            "memory_total_gb": 23.988,
            "memory_used_gb": 0.4,
            "utilization_gpu_percent": 2.0,
        },
        ram_reader=lambda: {"available": True, "total_gb": 64.0, "used_gb": 20.0},
        git_reader=lambda _repo: {
            "branch": "cursor/p2-i11a0-offline-harness",
            "commit": "dfbe45b0712a8df3fab8d84fbc2c1b4747a3feba",
        },
        ollama_version_reader=lambda _url: "0.34.1",
        controller_hostname="FlightSim",
    )
    require_flightsim_host_affinity(rtx_preflight)
    _check(
        "flightsim_host_affinity_accepts_local_4090",
        rtx_preflight["checks"]["gpu_is_rtx_4090"] is True
        and rtx_preflight["checks"]["ollama_base_url_local"] is True
        and rtx_preflight["ollama_version"] == "0.34.1",
        checks,
        problems,
        rtx_preflight["checks"],
    )
    desktop_preflight = collect_host_affinity_preflight(
        ollama_base_url="http://127.0.0.1:11434",
        output_path=".",
        chunks_path=".",
        repo=Path("."),
        nvidia_reader=lambda: {
            "available": True,
            "name": "NVIDIA GeForce GTX 1650",
            "memory_total_gb": 4.0,
            "memory_used_gb": 1.5,
            "utilization_gpu_percent": 5.0,
        },
        ram_reader=lambda: {"available": True, "total_gb": 32.0, "used_gb": 10.0},
        git_reader=lambda _repo: {"branch": "cursor/p2-i11a0-offline-harness", "commit": "x"},
        ollama_version_reader=lambda _url: "0.34.1",
        controller_hostname="Toms-Desktop",
    )
    desktop_blocked = False
    try:
        require_flightsim_host_affinity(desktop_preflight)
    except HostAffinityError:
        desktop_blocked = True
    _check(
        "desktop_gpu_is_refused_before_inference",
        desktop_blocked and desktop_preflight["checks"]["gpu_is_rtx_4090"] is False,
        checks,
        problems,
        desktop_preflight["gpu_name"],
    )
    remote_url_blocked = False
    try:
        require_flightsim_host_affinity(
            collect_host_affinity_preflight(
                ollama_base_url="http://flightsim:11434",
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
                git_reader=lambda _repo: {"branch": "x", "commit": "y"},
                ollama_version_reader=lambda _url: "0.34.1",
            )
        )
    except HostAffinityError:
        remote_url_blocked = True
    _check(
        "remote_flightsim_ollama_alias_is_refused",
        remote_url_blocked,
        checks,
        problems,
    )
    ceiling = HardwareSampler()
    ceiling.samples = [
        {"vram_used_gb": 1.0, "system_ram_used_gb": 20.0, "gpu_utilization_percent": 0},
        {"vram_used_gb": 22.6, "system_ram_used_gb": 24.0, "gpu_utilization_percent": 90},
    ]
    ceiling_summary = ceiling.summary()
    _check(
        "flightsim_vram_ceiling_uses_local_peak",
        ceiling_summary["vram_peak_gb"] == 22.6
        and ceiling_summary["exceeds_vram_ceiling"] is True
        and VRAM_CEILING_GB == 22.5,
        checks,
        problems,
        ceiling_summary,
    )
    with tempfile.TemporaryDirectory() as remote_dir:
        remote_path = Path(remote_dir) / REMOTE_FUNCTIONAL_RUN_ID
        remote_path.mkdir()
        (remote_path / "run_record.json").write_text(
            json.dumps(
                {
                    "identity": REMOTE_FUNCTIONAL_RUN_ID,
                    "classification": "successful_stable",
                    "measurement": {"peak_vram_gb": 1.515625, "final_safety_result": "passed"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        labeled = label_remote_functional_run(remote_path)
        preserved = json.loads((remote_path / "run_record.json").read_text(encoding="utf-8"))
        _check(
            "remote_corrected_run_is_labeled_not_rewritten",
            labeled["label"] == REMOTE_FUNCTIONAL_LABEL
            and labeled["flightsim_hardware_smoke"] is False
            and preserved["classification"] == "successful_stable"
            and preserved["measurement"]["peak_vram_gb"] == 1.515625
            and (remote_path / "hardware_telemetry_classification.json").exists(),
            checks,
            problems,
            labeled,
        )
    _check(
        "approved_screen_is_the_three_named_tags",
        [row["tag"] for row in APPROVED_MODELS]
        == [
            "qwen3:30b-a3b-instruct-2507-q4_K_M",
            "qwen3:14b-q8_0",
            "gemma4:26b",
        ],
        checks,
        problems,
    )
    from memorybox.ask.i11a.i11a0_benchmark import TOKEN_ESTIMATOR_FORMULA

    preflight = build_preflight_package(chunk_roots=[Path(tempfile.gettempdir()) / "i11a0-missing-chunks"], fetcher=_fetcher)
    _check(
        "preflight_package_runs_without_inference",
        preflight["inference_authorized"] is False
        and preflight["prompt_sha256"] == prompt_hash
        and preflight["models_called"] is False
        and preflight["gate2_smoke_authorized"] is True
        and preflight["smoke_command_status"] == "gate2_smoke_authorized_confirm_required"
        and preflight["token_estimator_formula"] == TOKEN_ESTIMATOR_FORMULA
        and preflight["token_estimator_label"] == "estimated",
        checks,
        problems,
        preflight["smoke_command_status"],
    )
    from memorybox.ask.i11a.i11a0_gate3 import prove_gate3_offline

    gate3 = prove_gate3_offline()
    checks.extend(gate3.get("checks") or [])
    problems.extend(gate3.get("problems") or [])
    _check("gate3_offline_controller_did_not_call_a_model", gate3.get("models_called") is False, checks, problems)
    _check("gate3_offline_proofs_pass", gate3.get("ok") is True, checks, problems, gate3.get("problems"))
    from memorybox.ask.i11a.i11a0_prompt_accounting_proof import prove_prompt_accounting_control_offline

    control = prove_prompt_accounting_control_offline()
    checks.extend(control.get("checks") or [])
    problems.extend(control.get("problems") or [])
    _check("prompt_accounting_control_offline", control.get("ok") is True, checks, problems, control.get("problems"))
    _check("prompt_accounting_control_models_not_called", control.get("models_called") is False, checks, problems)
    return {
        "ok": not problems,
        "checks": len(checks),
        "problems": problems,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": prompt_hash,
        "models_called": False,
        "gate3_offline": {"ok": gate3.get("ok"), "check_count": len(gate3.get("checks") or [])},
        "prompt_accounting_control_offline": {
            "ok": control.get("ok"),
            "check_count": len(control.get("checks") or []),
            "models_called": control.get("models_called"),
        },
    }
