"""Assemble the Gate 2 equal-input review package. Does not pick a winner."""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.i11a0_artifacts import (
    QUALITY_COLUMNS,
    append_run_workbook,
    write_quality_row,
    write_results_bundle,
    write_summary_rows,
)
from memorybox.ask.i11a.i11a0_prompt import SYSTEM_PROMPT, prompt_canonical_text, prompt_sha256
from memorybox.ask.i11a.i11a0_smoke import (
    CALIBRATED_A_EXECUTION_ID,
    GEMMA_FLIGHTSIM_EXECUTION_ID,
    PINNED_A_DIGEST,
    PINNED_B_DIGEST,
    PINNED_C_DIGEST,
)

SCORE_FIELDS = (
    "factual_accuracy",
    "attribution",
    "chronological_accuracy",
    "coherence",
    "unsupported_assertions",
    "readability",
    "usefulness",
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_calibrated_smoke_run(run_dir: Path | str, *, config_id: str) -> dict[str, Any]:
    folder = Path(run_dir)
    record = _read_json(folder / "run_record.json")
    accounting = _read_json(folder / "token_accounting.json")
    hardware = _read_json(folder / "hardware_telemetry.json")
    metadata = _read_json(folder / "model_metadata.json")
    supersession = _read_json(folder / "identity_supersession.json")
    request = record.get("request") or {}
    measurement = record.get("measurement") or {}
    execution_id = str(
        record.get("execution_id")
        or supersession.get("execution_id")
        or record.get("identity")
        or folder.name
    )
    classification = record.get("classification") or measurement.get("overall_classification")
    if classification != "successful_stable":
        raise ValueError(
            f"{config_id} is not a valid calibrated Gate 2 member: {classification}"
        )
    tag = str(request.get("model_tag") or metadata.get("tag") or "")
    digest = str(request.get("digest") or metadata.get("digest") or "")
    expected = {"A": PINNED_A_DIGEST, "B": PINNED_B_DIGEST, "C": PINNED_C_DIGEST}[config_id]
    if digest != expected:
        raise ValueError(f"{config_id} digest {digest} is not the pinned Gate 2 digest")
    hashes = {
        name: _sha256_file(folder / name)
        for name in (
            "run_record.json",
            "token_accounting.json",
            "narration.txt",
            "raw_api.jsonl",
            "hardware_telemetry.json",
            "telemetry.jsonl",
        )
        if (folder / name).is_file()
    }
    actual = int(measurement.get("actual_prompt_tokens") or accounting.get("actual_prompt_eval_count") or 0)
    reserve = int(measurement.get("output_reserve_tokens") or 2500)
    margin = int(measurement.get("required_safety_margin_tokens") or 1500)
    num_ctx = int(measurement.get("configured_num_ctx") or request.get("num_ctx") or 0)
    required = actual + reserve + margin
    return {
        "config_id": config_id,
        "run_dir": str(folder),
        "execution_id": execution_id,
        "test_case_id": record.get("test_case_id") or supersession.get("test_case_id"),
        "classification": classification,
        "tag": tag,
        "digest": digest,
        "architecture": metadata.get("architecture") or ("gemma4" if config_id == "C" else None),
        "quantization": metadata.get("quantization")
        or request.get("quantization")
        or ("Q4_K_M" if config_id == "C" else None),
        "parameter_size": metadata.get("parameter_size"),
        "family": metadata.get("family") or metadata.get("families"),
        "estimated_prompt_tokens": measurement.get("estimated_prompt_tokens"),
        "actual_prompt_tokens": actual,
        "estimation_error_tokens": measurement.get("estimation_error_tokens"),
        "configured_num_ctx": num_ctx,
        "output_reserve_tokens": reserve,
        "required_safety_margin_tokens": margin,
        "required_context_tokens": required,
        "safety_equation": f"{actual} + {reserve} + {margin} = {required} <= {num_ctx}",
        "safety_equation_pass": required <= num_ctx,
        "elapsed_seconds": measurement.get("elapsed_seconds"),
        "prompt_tokens_per_second": measurement.get("prompt_tokens_per_second"),
        "generation_tokens_per_second": measurement.get("generation_tokens_per_second"),
        "peak_vram_gb": hardware.get("vram_peak_gb") or measurement.get("peak_vram_gb"),
        "vram_baseline_gb": hardware.get("vram_baseline_gb"),
        "vram_final_gb": hardware.get("vram_final_gb"),
        "ram_baseline_gb": hardware.get("ram_baseline_gb"),
        "ram_peak_gb": hardware.get("ram_peak_gb"),
        "ram_final_gb": hardware.get("ram_final_gb"),
        "gpu_resident": hardware.get("gpu_resident", measurement.get("gpu_resident")),
        "cpu_offload": hardware.get("cpu_offload"),
        "narration": (folder / "narration.txt").read_text(encoding="utf-8")
        if (folder / "narration.txt").is_file()
        else "",
        "raw_api": (folder / "raw_api.jsonl").read_text(encoding="utf-8")
        if (folder / "raw_api.jsonl").is_file()
        else "",
        "telemetry": (folder / "telemetry.jsonl").read_text(encoding="utf-8")
        if (folder / "telemetry.jsonl").is_file()
        else "",
        "hardware": hardware,
        "packet_sha256": request.get("evidence_sha256"),
        "prompt_sha256": request.get("prompt_sha256"),
        "artifact_sha256": hashes,
        "load_unload": {
            "gpu_resident": hardware.get("gpu_resident"),
            "cpu_offload": hardware.get("cpu_offload"),
            "vram_released": (
                hardware.get("vram_final_gb") is not None
                and hardware.get("vram_baseline_gb") is not None
                and float(hardware["vram_final_gb"]) <= float(hardware["vram_baseline_gb"]) + 2.0
            ),
        },
    }


def _blind_labels(config_ids: list[str]) -> dict[str, str]:
    labels = [f"Candidate-{index}" for index in range(1, len(config_ids) + 1)]
    random.Random(42).shuffle(labels)
    return dict(zip(config_ids, labels, strict=True))


def _comparison_markdown(runs: list[dict[str, Any]], blinds: dict[str, str]) -> str:
    lines = [
        "# Gate 2 equal-input review package",
        "",
        "This package does **not** recommend a production winner.",
        "Do not start the context ladder, repeated trials, 250-token refinement, finalist testing, or I11A.1.",
        "",
        "Score the Quality Review sheet and `quality_score_sheet.md` using blinded Candidate labels before opening `sealed/identity_map.json`.",
        "",
        "## Calibrated members",
        "",
        "| Config | Tag | Digest | Architecture | Quantization | Execution ID |",
        "|---|---|---|---|---|---|",
    ]
    for run in runs:
        lines.append(
            f"| {run['config_id']} | `{run['tag']}` | `{run['digest']}` | {run.get('architecture')} | {run.get('quantization')} | `{run['execution_id']}` |"
        )
    lines.extend(
        [
            "",
            "## Tokens and safety",
            "",
            "| Config | Estimated | Actual | Error | Equation |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for run in runs:
        lines.append(
            f"| {run['config_id']} | {run['estimated_prompt_tokens']} | {run['actual_prompt_tokens']} | {run['estimation_error_tokens']} | `{run['safety_equation']}` |"
        )
    lines.extend(
        [
            "",
            "## Timing, VRAM, RAM",
            "",
            "| Config | Elapsed s | Prompt t/s | Gen t/s | VRAM peak GB | RAM peak GB | GPU resident | CPU offload | VRAM released |",
            "|---|---:|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for run in runs:
        unload = run.get("load_unload") or {}
        lines.append(
            "| {config_id} | {elapsed} | {prompt} | {gen} | {vram} | {ram} | {gpu} | {cpu} | {released} |".format(
                config_id=run["config_id"],
                elapsed=run.get("elapsed_seconds"),
                prompt=run.get("prompt_tokens_per_second"),
                gen=run.get("generation_tokens_per_second"),
                vram=run.get("peak_vram_gb"),
                ram=run.get("ram_peak_gb"),
                gpu=run.get("gpu_resident"),
                cpu=run.get("cpu_offload"),
                released=unload.get("vram_released"),
            )
        )
    lines.extend(["", "## Blinded narration labels", ""])
    for config_id, label in blinds.items():
        lines.append(f"- {label}: sealed mapping only (do not treat Config {config_id} as a ranking).")
    lines.extend(
        [
            "",
            "## Human score sheet",
            "",
            "Score 1-5 or N/A. Lower `unsupported_assertions` is better.",
            "",
            "| Blind ID | Factual accuracy | Attribution | Chronology | Coherence | Unsupported inference | Readability | Family usefulness | Notes |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for label in blinds.values():
        lines.append(f"| {label} |  |  |  |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "winner_recommendation: none",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def assemble_gate2_review_package(
    *,
    a_dir: Path | str,
    b_dir: Path | str,
    c_dir: Path | str,
    out_dir: Path | str,
) -> dict[str, Any]:
    runs = [
        load_calibrated_smoke_run(a_dir, config_id="A"),
        load_calibrated_smoke_run(b_dir, config_id="B"),
        load_calibrated_smoke_run(c_dir, config_id="C"),
    ]
    if not all(row["safety_equation_pass"] for row in runs):
        failed = [row["config_id"] for row in runs if not row["safety_equation_pass"]]
        raise ValueError(f"safety equation failed for {failed}")
    blinds = _blind_labels([row["config_id"] for row in runs])
    root = Path(out_dir)
    workbook = root.parent / f"{root.name}.xlsx"
    if workbook.exists():
        workbook.unlink()
    run_rows: list[dict[str, Any]] = []
    narrations: dict[str, str] = {}
    raw_responses: dict[str, str] = {}
    telemetry: dict[str, str] = {}
    identity_map: dict[str, Any] = {}
    for run in runs:
        blind = blinds[run["config_id"]]
        identity_map[blind] = {
            "config_id": run["config_id"],
            "tag": run["tag"],
            "digest": run["digest"],
            "execution_id": run["execution_id"],
        }
        row = {
            "run_id": run["execution_id"],
            "model": run["tag"],
            "digest": run["digest"],
            "warm_or_cold": "cold",
            "repetition": 1,
            "confirmation": False,
            "thinking_mode": "off",
            "requested_evidence_tokens": 1000,
            "evidence_sha256": run.get("packet_sha256"),
            "prompt_sha256": run.get("prompt_sha256"),
            "num_ctx": run.get("configured_num_ctx"),
            "reserved_output_tokens": run.get("output_reserve_tokens"),
            "classification": run["classification"],
            "elapsed_seconds": run.get("elapsed_seconds"),
            "prompt_tokens_per_second": run.get("prompt_tokens_per_second"),
            "generation_tokens_per_second": run.get("generation_tokens_per_second"),
            "prompt_eval_count": run.get("actual_prompt_tokens"),
            "peak_vram_gb": run.get("peak_vram_gb"),
            "gpu_resident": run.get("gpu_resident"),
            "narration_relpath": f"narrations/{blind}.txt",
            "record_relpath": f"{run['config_id']}/{run['execution_id']}/run_record.json",
        }
        append_run_workbook(workbook, row)
        run_rows.append(row)
        narrations[blind] = run["narration"]
        raw_responses[blind] = run["raw_api"]
        telemetry[blind] = run["telemetry"]
        write_quality_row(
            workbook,
            {
                "blind_id": blind,
                "comparison_view": "equal_input",
                "packet_sha256": run.get("packet_sha256"),
                "narration_relpath": f"narrations/{blind}.txt",
                **{field: None for field in SCORE_FIELDS},
            },
        )
    write_summary_rows(
        workbook,
        [
            ("gate", "winner_recommendation", "none"),
            ("gate", "context_ladder", "blocked"),
            ("gate", "i11a1", "blocked"),
            ("identity", "calibrated_a_execution_id", CALIBRATED_A_EXECUTION_ID),
            ("identity", "gemma_flightsim_execution_id", GEMMA_FLIGHTSIM_EXECUTION_ID),
        ],
    )
    markdown = _comparison_markdown(runs, blinds)
    (root.parent / f"{root.name}.preview.md").write_text(markdown, encoding="utf-8", newline="\n")
    bundle = write_results_bundle(
        bundle_dir=root,
        workbook_path=workbook,
        summary_markdown=markdown,
        run_rows=run_rows,
        narrations=narrations,
        raw_responses=raw_responses,
        telemetry=telemetry,
        console_logs={"note": "Gate 2 review package. No additional generation.\n"},
        validation={
            "safety": json.dumps(
                {row["config_id"]: row["safety_equation"] for row in runs},
                indent=2,
            )
            + "\n"
        },
        config_text=json.dumps(
            {
                "stage": "smoke",
                "command_kind": "gate2_review_package",
                "winner_recommendation": None,
                "full_context_ladder_blocked": True,
            },
            indent=2,
        )
        + "\n",
        prompt_text=prompt_canonical_text() + "\n\n" + SYSTEM_PROMPT,
        manifests={"quality_columns": json.dumps(list(QUALITY_COLUMNS), indent=2) + "\n"},
        identity_map=identity_map,
    )
    (root / "quality_score_sheet.md").write_text(
        "\n".join(
            [
                "# Blinded quality score sheet",
                "",
                "Do not open sealed/identity_map.json until scores are recorded.",
                "",
                markdown.split("## Human score sheet")[-1],
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    bundle.update(
        {
            "winner_recommendation": None,
            "full_context_ladder_blocked": True,
            "blind_ids": blinds,
            "runs": [
                {
                    "config_id": row["config_id"],
                    "execution_id": row["execution_id"],
                    "tag": row["tag"],
                    "digest": row["digest"],
                    "safety_equation": row["safety_equation"],
                }
                for row in runs
            ],
        }
    )
    return bundle
