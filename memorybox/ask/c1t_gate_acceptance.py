"""C1T I11A gate harness acceptance — mocked streams only; no Ollama."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from memorybox.ask.i11a.c1t_prompt_schemas import HISTORIAN_EVIDENCE_LEDGER_V1
from memorybox.ask.i11a.c1t_benchmark import (
    RunParameters,
    aggregate_gpu_peaks,
    accumulate_stream_events,
    determine_benchmark_outcome,
    interpret_legacy_run_record,
    preflight_benchmark,
    run_supervised_benchmark,
)


def _check(
    name: str,
    condition: bool,
    checks: list[str],
    problems: list[str],
    detail: Any = None,
) -> None:
    checks.append(name)
    if not condition:
        problems.append(f"{name}: {detail}")


def _fake_preflight(chunk_path: Path, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "chunk_path": str(chunk_path),
        "chunk": row,
        "chunk_sha256": row["sha256"],
        "estimated_input_tokens": row["estimated_input_tokens"],
        "inventory_sha256": "synthetic",
        "ollama_base_url": "http://127.0.0.1:9",
        "model_metadata": {"name": "synthetic:no-model"},
        "baseline_resources": {},
    }


def _install_stream_worker(
    *,
    raw: Path,
    response: Path,
    thinking: Path,
    events: list[dict[str, Any]],
) -> None:
    lines: list[str] = []
    thinking_text = ""
    response_text = ""
    for event in events:
        lines.append(json.dumps(event) + "\n")
        message = event.get("message") or {}
        thinking_text += str(message.get("thinking") or "")
        response_text += str(message.get("content") or "")
    raw.write_text("".join(lines), encoding="utf-8")
    thinking.write_text(thinking_text, encoding="utf-8")
    response.write_text(response_text, encoding="utf-8")


def _worker_from_events(events: list[dict[str, Any]], *, incremental: bool = False):
    def factory(_request: Path, raw: Path, response: Path, thinking: Path) -> list[str]:
        events_path = raw.parent / "_synthetic_events.json"
        script_path = raw.parent / "_synthetic_stream_worker.py"
        events_path.write_text(json.dumps(events), encoding="utf-8")
        sleep_line = "    time.sleep(0.2)" if incremental else ""
        script_path.write_text(
            "\n".join(
                [
                    "import json",
                    "import time",
                    "from pathlib import Path",
                    f"events = json.loads(Path({str(events_path)!r}).read_text(encoding='utf-8'))",
                    f"raw = Path({str(raw)!r})",
                    f"response = Path({str(response)!r})",
                    f"thinking = Path({str(thinking)!r})",
                    "lines = []",
                    "thinking_text = ''",
                    "response_text = ''",
                    "for event in events:",
                    sleep_line,
                    "    lines.append(json.dumps(event) + '\\n')",
                    "    msg = event.get('message') or {}",
                    "    thinking_text += str(msg.get('thinking') or '')",
                    "    response_text += str(msg.get('content') or '')",
                    "    raw.write_text(''.join(lines), encoding='utf-8')",
                    "    thinking.write_text(thinking_text, encoding='utf-8')",
                    "    response.write_text(response_text, encoding='utf-8')",
                ]
            ),
            encoding="utf-8",
        )
        return [sys.executable, str(script_path)]

    return factory


def _valid_historian_response(email_id: str = "email_1") -> str:
    return json.dumps(
        {
            "chunk_id": "chunk-001",
            "scope": {"start": "2024-01-01", "end": "2024-01-02", "partial_context": True},
            "events": [
                {
                    "local_event_id": "evt-1",
                    "date_or_range": "2024-01-01",
                    "description": "Synthetic event",
                    "people": ["Peggy"],
                    "event_type": "communication",
                    "local_significance": "medium",
                    "significance_reason": "test",
                    "evidence_ids": [email_id],
                    "evidence_basis": "direct",
                    "confidence": "high",
                    "uncertainties": [],
                    "connections_to_investigate": [],
                }
            ],
            "patterns": [],
            "conflicts": [],
            "potentially_meaningful_details": [],
            "segment_limits": [],
        }
    )


def run_prove_c1t_gate() -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        chunk_dir = root / "chunks"
        chunk_dir.mkdir()
        row = {
            "chunk_index": 1,
            "chunk_id": "synthetic-chunk-001",
            "file": "CHUNK_001_MODEL_PASTE.txt",
            "sha256": "abc",
            "estimated_input_tokens": 100,
            "email_ids": ["email_1"],
        }
        chunk_path = chunk_dir / row["file"]
        chunk_path.write_text(
            "===== TRUSTED EMAIL CONVERSATIONS =====\n[email_1] test\n",
            encoding="utf-8",
        )
        row["sha256"] = hashlib.sha256(chunk_path.read_bytes()).hexdigest()
        (chunk_dir / "CHUNK_MANIFEST.json").write_text(
            json.dumps(
                {
                    "chunks": [
                        {
                            "chunk_index": 1,
                            "file": row["file"],
                            "sha256": row["sha256"],
                            "estimated_input_tokens": row["estimated_input_tokens"],
                            "email_ids": row["email_ids"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        preflight = _fake_preflight(chunk_path, row)
        base_params = RunParameters(
            model="synthetic:no-model",
            num_ctx=4096,
            num_predict=128,
            think=False,
            prompt_schema_version=HISTORIAN_EVIDENCE_LEDGER_V1,
            hard_timeout_seconds=5,
            stall_warning_seconds=1,
            heartbeat_seconds=1,
            timeout_grace_seconds=1,
        )

        thinking_only_events = [
            {"message": {"thinking": "reasoning " * 20}, "done": False},
            {
                "message": {"thinking": "more"},
                "done": True,
                "done_reason": "length",
                "eval_count": 128,
                "prompt_eval_count": 10,
            },
        ]
        run_a = run_supervised_benchmark(
            preflight=preflight,
            results_root=root / "a",
            experiment_id="gate-thinking-only",
            repetition=1,
            parameters=base_params,
            confirm_model_run=True,
            worker_command_factory=_worker_from_events(thinking_only_events, incremental=True),
        )
        _check(
            "A_thinking_only_stream_fails_benchmark",
            run_a.get("ok") is False
            and run_a.get("benchmark_outcome") == "FAIL"
            and run_a["record"]["execution_status"] == "COMPLETE"
            and run_a["failure_reason"] == "output_budget_exhausted_before_final_response",
            checks,
            problems,
            run_a,
        )
        thinking_file = Path(run_a["run_dir"]) / "thinking.txt"
        response_file = Path(run_a["run_dir"]) / "response.txt"
        _check(
            "A_thinking_and_response_artifacts",
            thinking_file.read_text(encoding="utf-8").startswith("reasoning")
            and response_file.read_text(encoding="utf-8") == "",
            checks,
            problems,
        )
        console = (Path(run_a["run_dir"]) / "console.log").read_text(encoding="utf-8")
        _check(
            "A_heartbeat_saw_thinking_activity",
            "thinking_bytes=" in console and "first streamed thinking" in console,
            checks,
            problems,
        )

        valid = _valid_historian_response()
        run_b_events = [
            {"message": {"thinking": "plan"}},
            {"message": {"content": valid}},
            {"done": True, "done_reason": "stop", "eval_count": 4, "prompt_eval_count": 10},
        ]
        run_b = run_supervised_benchmark(
            preflight=preflight,
            results_root=root / "b",
            experiment_id="gate-thinking-then-content",
            repetition=1,
            parameters=RunParameters(**{**base_params.__dict__, "think": True}),
            confirm_model_run=True,
            worker_command_factory=_worker_from_events(run_b_events, incremental=True),
        )
        _check(
            "B_thinking_then_valid_content_passes",
            run_b.get("ok") is True
            and run_b.get("benchmark_outcome") == "PASS"
            and json.loads((Path(run_b["run_dir"]) / "response.txt").read_text(encoding="utf-8"))["chunk_id"]
            == "chunk-001"
            and (Path(run_b["run_dir"]) / "thinking.txt").read_text(encoding="utf-8") == "plan",
            checks,
            problems,
            run_b,
        )
        _check(
            "B_timing_fields_recorded",
            run_b["record"]["stream"]["time_to_first_thinking_seconds"] is not None
            and run_b["record"]["stream"]["time_to_first_content_seconds"] is not None,
            checks,
            problems,
        )

        run_c = run_supervised_benchmark(
            preflight=preflight,
            results_root=root / "c",
            experiment_id="gate-think-false",
            repetition=1,
            parameters=RunParameters(**{**base_params.__dict__, "think": False}),
            confirm_model_run=True,
            worker_command_factory=_worker_from_events(
                [{"message": {"content": valid}, "done": True, "done_reason": "stop"}]
            ),
        )
        request_c = json.loads((Path(run_c["run_dir"]) / "request.json").read_text(encoding="utf-8"))
        _check(
            "C_think_false_top_level_boolean",
            request_c.get("think") is False and "think" not in (request_c.get("options") or {}),
            checks,
            problems,
            request_c,
        )

        run_d = run_supervised_benchmark(
            preflight=preflight,
            results_root=root / "d",
            experiment_id="gate-think-true",
            repetition=1,
            parameters=RunParameters(**{**base_params.__dict__, "think": True}),
            confirm_model_run=True,
            worker_command_factory=_worker_from_events(
                [
                    {
                        "message": {"thinking": "x", "content": valid},
                        "done": True,
                        "done_reason": "stop",
                    }
                ]
            ),
        )
        request_d = json.loads((Path(run_d["run_dir"]) / "request.json").read_text(encoding="utf-8"))
        _check(
            "D_think_true_top_level_boolean",
            request_d.get("think") is True,
            checks,
            problems,
            request_d,
        )

        uncapped = RunParameters(
            **{
                **base_params.__dict__,
                "num_predict": -1,
                "hard_timeout_seconds": 1,
                "heartbeat_seconds": 1,
            }
        )
        run_e = run_supervised_benchmark(
            preflight=preflight,
            results_root=root / "e",
            experiment_id="gate-num-predict-uncapped",
            repetition=1,
            parameters=uncapped,
            confirm_model_run=True,
            worker_command_factory=lambda request, raw, response, thinking: [
                sys.executable,
                "-c",
                "import time; time.sleep(30)",
            ],
        )
        request_e = json.loads((Path(run_e["run_dir"]) / "request.json").read_text(encoding="utf-8"))
        _check(
            "E_num_predict_minus_one_preserved",
            request_e["options"]["num_predict"] == -1
            and run_e["record"]["model"]["num_predict"] == -1,
            checks,
            problems,
            request_e,
        )
        _check(
            "E_hard_timeout_still_active",
            run_e["record"]["execution_status"] == "TIMEOUT",
            checks,
            problems,
        )

        run_f = run_supervised_benchmark(
            preflight=preflight,
            results_root=root / "f",
            experiment_id="gate-empty-response",
            repetition=1,
            parameters=base_params,
            confirm_model_run=True,
            worker_command_factory=_worker_from_events(
                [{"done": True, "done_reason": "stop"}]
            ),
        )
        _check(
            "F_empty_response_fails_despite_complete_transport",
            run_f.get("ok") is False and run_f.get("failure_reason") == "empty_final_response",
            checks,
            problems,
        )

        missing_cite = _valid_historian_response()
        missing_payload = json.loads(missing_cite)
        missing_payload["events"][0]["evidence_ids"] = []
        run_g = run_supervised_benchmark(
            preflight=preflight,
            results_root=root / "g",
            experiment_id="gate-missing-citations",
            repetition=1,
            parameters=base_params,
            confirm_model_run=True,
            worker_command_factory=_worker_from_events(
                [
                    {
                        "message": {"content": json.dumps(missing_payload)},
                        "done": True,
                        "done_reason": "stop",
                    }
                ]
            ),
        )
        _check(
            "G_missing_citations_fail",
            run_g.get("ok") is False
            and run_g["record"]["quality"]["citation_pass"] is False
            and "required_citations_absent" in run_g["record"]["validation_failures"],
            checks,
            problems,
        )

        bad_cite = _valid_historian_response("email_999")
        run_h = run_supervised_benchmark(
            preflight=preflight,
            results_root=root / "h",
            experiment_id="gate-unsupported-citations",
            repetition=1,
            parameters=base_params,
            confirm_model_run=True,
            worker_command_factory=_worker_from_events(
                [
                    {
                        "message": {"content": bad_cite},
                        "done": True,
                        "done_reason": "stop",
                    }
                ]
            ),
        )
        _check(
            "H_unsupported_citations_fail",
            run_h.get("ok") is False
            and "unsupported_citations" in run_h["record"]["validation_failures"],
            checks,
            problems,
        )

        truncated = _valid_historian_response()
        run_i = run_supervised_benchmark(
            preflight=preflight,
            results_root=root / "i",
            experiment_id="gate-length-with-content",
            repetition=1,
            parameters=base_params,
            confirm_model_run=True,
            worker_command_factory=_worker_from_events(
                [
                    {
                        "message": {"content": truncated},
                        "done": True,
                        "done_reason": "length",
                    }
                ]
            ),
        )
        _check(
            "I_done_reason_length_with_content_still_fails",
            run_i.get("ok") is False
            and run_i.get("failure_reason") == "output_budget_exhausted",
            checks,
            problems,
        )

        gpu_samples = [
            {
                "nvidia": {
                    "gpus": [
                        {
                            "index": "0",
                            "memory.used": "1000",
                            "memory.free": "20000",
                            "utilization.gpu": "10",
                            "temperature.gpu": "40",
                            "power.draw": "50",
                        }
                    ]
                }
            },
            {
                "nvidia": {
                    "gpus": [
                        {
                            "index": "0",
                            "memory.used": "5000",
                            "memory.free": "15000",
                            "utilization.gpu": "80",
                            "temperature.gpu": "55",
                            "power.draw": "120",
                        }
                    ]
                }
            },
        ]
        peaks = aggregate_gpu_peaks(gpu_samples)
        _check(
            "J_gpu_peak_aggregation",
            peaks["gpus"][0]["memory_used_peak"] == 5000.0
            and peaks["gpus"][0]["memory_free_min"] == 15000.0
            and peaks["gpus"][0]["utilization_gpu_peak"] == 80.0,
            checks,
            problems,
            peaks,
        )

        legacy = interpret_legacy_run_record(
            {"run_record_version": 1, "run_id": "A-cold-r01-20260903T092932Z-588447b6"}
        )
        _check(
            "legacy_A_cold_r01_reclassified_without_touching_artifacts",
            legacy
            and legacy["benchmark_outcome"] == "FAIL"
            and legacy["failure_reason"] == "output_budget_exhausted_before_final_response",
            checks,
            problems,
            legacy,
        )

        accumulation = accumulate_stream_events(
            Path(run_a["run_dir"]) / "raw_api.jsonl"
        )
        outcome = determine_benchmark_outcome(
            execution_status="COMPLETE",
            response="",
            thinking=accumulation.thinking,
            final_event=accumulation.final_event,
            validation={"schema_pass": False, "missing_citations": False, "unsupported_citation_ids": []},
        )
        _check(
            "determine_benchmark_outcome_thinking_only",
            outcome == ("FAIL", "output_budget_exhausted_before_final_response", ["output_budget_exhausted_before_final_response", "schema_validation_failed"]),
            checks,
            problems,
            outcome,
        )

        (root / "inventory.json").write_text("{}", encoding="utf-8")
        with patch(
            "memorybox.ask.i11a.c1t_benchmark._ollama_inventory",
            return_value={
                "available": True,
                "models": [{"name": "gemma4:26b"}],
                "requested_model": {"name": "gemma4:26b"},
                "running_models": [],
            },
        ):
            uncapped_preflight = preflight_benchmark(
                chunk_dir=chunk_dir,
                chunk_index=1,
                expected_chunk_hash=row["sha256"],
                inventory_path=root / "inventory.json",
                parameters=RunParameters(
                    num_ctx=4096,
                    num_predict=-1,
                    think=False,
                    safety_margin_tokens=64,
                ),
                ollama_base_url="http://127.0.0.1:9",
            )
        _check(
            "E_preflight_accepts_num_predict_minus_one",
            uncapped_preflight.get("ok") is True,
            checks,
            problems,
            uncapped_preflight,
        )

    return {
        "ok": not problems,
        "prove": "c1t_gate",
        "checks": checks,
        "problems": problems,
        "model_calls": 0,
    }
