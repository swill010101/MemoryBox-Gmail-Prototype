"""v0.3 confirmation runtime: tri-state safety, split timeouts, durable failure records.

Does not call Ollama unless the caller supplies a live urlopen. Original COMPLETE
run artifacts are never rewritten by sidecar writers.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from io import TextIOBase
from pathlib import Path
from typing import Any, Callable

from memorybox.ask.i11a.i11a0_benchmark import I11A0Error, Measurement
from memorybox.ask.i11a.i11a0_gate3_progress import Gate3Progress

HEARTBEAT_PHASES = (
    "starting_runner",
    "loading_model",
    "waiting_for_api_stream",
    "prompt_evaluation",
    "generation",
    "validation",
    "unload",
)
RUNNER_NOT_READY_PHASES = frozenset(
    {"starting_runner", "loading_model", "waiting_for_api_stream"}
)
CLASSIFICATION_INFRA_PRE_PROMPT = "infrastructure_failure_pre_prompt_model_runner_not_ready"
SIDECAR_NAME = "classification_sidecar.json"
PROTECTED_ORIGINAL_NAMES = (
    "COMPLETE",
    "run_record.json",
    "safety_checks.json",
    "log_correlation.json",
    "token_accounting.json",
    "request_capture.json",
    "raw_api.jsonl",
    "narration.txt",
    "telemetry.jsonl",
    "citation_validation.json",
    "chronology_coverage.json",
    "claim_audit.json",
    "user_wrapper.txt",
    "evidence_packet.txt",
)
TIMED_OUT_EXECUTION_ID = "7e7284836cc3891973ef070ee454c11e5d6744d6141a3ec0dca89598717645ab"
PLANNED_REQUEST_BODY_SHA256 = "7241aa52c9beae0a37fdd1dcaa52181c7402413e7dedfb4de98c919aaeb974db"

UrlOpen = Callable[..., Any]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_inventory(root: Path, *, exclude_names: frozenset[str] | None = None) -> dict[str, str]:
    skip = exclude_names or frozenset()
    rows: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.name in skip:
            continue
        rows[path.relative_to(root).as_posix()] = _sha256_file(path)
    return rows


def tri_state_setting(*, requested_false: bool, prompt_evaluated: bool, truncation_occurred: bool | None) -> str:
    """effective / ineffective / unverified for truncate=false or shift=false."""
    if not requested_false:
        return "ineffective"
    if not prompt_evaluated:
        return "unverified"
    if truncation_occurred is True:
        return "ineffective"
    if truncation_occurred is False:
        return "effective"
    return "unverified"


def evaluate_confirmation_safety(
    *,
    request_json: dict[str, Any],
    prompt_eval_count: int | None,
    timed_out: bool,
    infrastructure_failure: bool,
    http_status: int | None,
    stream_bytes_received: int,
    truncation_occurred: bool | None,
    gpu_resident: bool | None,
    vram_peak_gb: float | None,
    vram_released: bool | None,
    log_truncation: bool | None,
) -> dict[str, Any]:
    requested_truncate_false = request_json.get("truncate") is False
    requested_shift_false = request_json.get("shift") is False
    prompt_evaluated = prompt_eval_count not in (None, 0)
    truncate_state = tri_state_setting(
        requested_false=requested_truncate_false,
        prompt_evaluated=prompt_evaluated,
        truncation_occurred=truncation_occurred,
    )
    shift_state = tri_state_setting(
        requested_false=requested_shift_false,
        prompt_evaluated=prompt_evaluated,
        truncation_occurred=truncation_occurred,
    )
    if not prompt_evaluated:
        truncation_state = "unverified"
        gpu_state = "unverified"
        placement_state = "unverified"
    else:
        if truncation_occurred is True or log_truncation is True:
            truncation_state = "ineffective"
        elif truncation_occurred is False and log_truncation is not True:
            truncation_state = "effective"
        else:
            truncation_state = "unverified"
        if gpu_resident is True:
            gpu_state = "effective"
        elif gpu_resident is False:
            gpu_state = "ineffective"
        else:
            gpu_state = "unverified"
        placement_state = gpu_state
    problems: list[str] = []
    if requested_truncate_false is False:
        problems.append("truncate_requested_not_false")
    if requested_shift_false is False:
        problems.append("shift_requested_not_false")
    if prompt_evaluated and truncate_state == "ineffective":
        problems.append("truncate_ineffective")
    if prompt_evaluated and shift_state == "ineffective":
        problems.append("shift_ineffective")
    if prompt_eval_count in (None, 0) and (timed_out or infrastructure_failure):
        problems.append("full_prompt_not_evaluated")
    elif prompt_evaluated:
        pec = int(prompt_eval_count or 0)
        if pec + 2500 + 1500 > int((request_json.get("options") or {}).get("num_ctx") or 0):
            problems.append("reserve_equation_failed")
    if log_truncation is True:
        problems.append("log_truncation")
    if prompt_evaluated and gpu_resident is False:
        problems.append("not_gpu_resident")
    if vram_peak_gb is not None and float(vram_peak_gb) >= 22.5:
        problems.append("vram_ceiling")
    if vram_released is False:
        problems.append("vram_not_released")
    classification = "safety_or_identity_failed" if problems and prompt_evaluated else None
    if not prompt_evaluated and (timed_out or infrastructure_failure or http_status not in (None, 200)):
        classification = CLASSIFICATION_INFRA_PRE_PROMPT
    claims_not_supported = {
        "truncate_enabled": False,
        "shift_enabled": False,
        "truncation_occurred": False,
        "gpu_residency_lost": False,
        "qwen_narration_quality_failed": False,
        "capacity_27k_invalid": False,
    }
    return {
        "ok": classification is None,
        "problems": problems,
        "classification": classification,
        "truncate": truncate_state,
        "shift": shift_state,
        "truncation_occurred": truncation_state,
        "gpu_residency": gpu_state,
        "placement": placement_state,
        "prompt_evaluated": prompt_evaluated,
        "stream_bytes_received": int(stream_bytes_received),
        "http_status": http_status,
        "claims_not_supported": claims_not_supported,
    }


def timed_out_execution_sidecar() -> dict[str, Any]:
    return {
        "execution_id": TIMED_OUT_EXECUTION_ID,
        "original_files_rewritten": False,
        "classification": CLASSIFICATION_INFRA_PRE_PROMPT,
        "prompt_eval_count": None,
        "gpu_peak_vram_gb_sampled": 1.4658203125,
        "placement": "unverified",
        "generated_narration": False,
        "llama_server_cmd_num_ctx": 39424,
        "n_tokens_observed": False,
        "prompt_eval_observed": False,
        "truncation_observed": False,
        "truncate": "unverified",
        "shift": "unverified",
        "truncation_occurred": "unverified",
        "gpu_residency": "unverified",
        "original_safety_problems_incorrect": [
            "truncate_not_false",
            "shift_not_false",
        ],
        "original_safety_problems_note": (
            "truncate_top_level True meant 'requested truncate is False'; "
            "the live checker treated that as a failed setting. Prompt never ran."
        ),
        "not_evidence_of": [
            "truncate_enabled",
            "shift_enabled",
            "truncation_occurred",
            "gpu_residency_lost",
            "qwen_narration_quality_failure",
            "invalid_27k_capacity_result",
        ],
        "ollama_load_failed": (
            "timed out waiting for llama-server to start (2026-09-29T07:26:50-05:00)"
        ),
        "gin_chat_status": 500,
        "gin_chat_duration": "57m33s",
        "client_urlopen_timeout_seconds": 1800,
        "request_body_sha256": PLANNED_REQUEST_BODY_SHA256,
        "recovery_authorized_required": True,
    }


def write_classification_sidecar(run_dir: Path | str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(run_dir)
    before = {
        name: (root / name).read_bytes() if (root / name).is_file() else None
        for name in PROTECTED_ORIGINAL_NAMES
    }
    body = payload if payload is not None else timed_out_execution_sidecar()
    dest = root / SIDECAR_NAME
    dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8", newline="\n")
    after = {
        name: (root / name).read_bytes() if (root / name).is_file() else None
        for name in PROTECTED_ORIGINAL_NAMES
    }
    if before != after:
        raise I11A0Error("sidecar write mutated a protected original artifact")
    return {"ok": True, "path": str(dest), "originals_unchanged": True, "payload": body}


def find_unresolved_attempts(out: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    runs = Path(out) / "runs"
    if not runs.is_dir():
        return found
    for run_dir in sorted(p for p in runs.iterdir() if p.is_dir()):
        markers = [name for name in ("IN_FLIGHT", "TIMEOUT", "FAILURE", "UNRESOLVED") if (run_dir / name).is_file()]
        rec: dict[str, Any] = {}
        record_path = run_dir / "run_record.json"
        if record_path.is_file():
            try:
                rec = json.loads(record_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                rec = {"unreadable": True}
        measurement = rec.get("measurement") or {}
        complete = (run_dir / "COMPLETE").is_file()
        pec = measurement.get("prompt_eval_count")
        unresolved_complete = complete and (
            rec.get("classification") == CLASSIFICATION_INFRA_PRE_PROMPT
            or measurement.get("timed_out") is True
            or measurement.get("infrastructure_failure") is True
            or pec in (None, 0)
        )
        if markers or unresolved_complete:
            found.append(
                {
                    "execution_id": run_dir.name,
                    "path": str(run_dir),
                    "markers": markers,
                    "complete": complete,
                    "classification": rec.get("classification"),
                    "timed_out": measurement.get("timed_out"),
                    "prompt_eval_count": measurement.get("prompt_eval_count"),
                }
            )
    return found


def refuse_if_unresolved(out: Path, *, recovery_authorized: bool) -> None:
    unresolved = find_unresolved_attempts(out)
    if not unresolved:
        return
    if recovery_authorized:
        return
    ids = ", ".join(row["execution_id"] for row in unresolved)
    raise I11A0Error(
        "unresolved prior confirmation attempt exists "
        f"({ids}); refuse generate until founder sets recovery_authorized"
    )


def persist_request_capture(run_dir: Path, capture: dict[str, Any]) -> Path:
    path = run_dir / "request_capture.json"
    tmp = run_dir / "request_capture.json.writing"
    tmp.write_text(json.dumps(capture, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return path


def persist_failure_record(run_dir: Path, *, kind: str, payload: dict[str, Any]) -> Path:
    name = "TIMEOUT" if kind == "timeout" else "FAILURE"
    path = run_dir / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    (run_dir / "failure_record.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return path


def apply_socket_timeout(response: Any, timeout: float) -> None:
    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
    if sock is not None and hasattr(sock, "settimeout"):
        sock.settimeout(timeout)


def infer_stream_phase(event: dict[str, Any], current: str) -> str:
    if event.get("prompt_eval_count") and current in RUNNER_NOT_READY_PHASES:
        return "prompt_evaluation"
    message = event.get("message") or {}
    if message.get("content"):
        return "generation"
    if event.get("prompt_eval_count") or event.get("eval_count"):
        return "prompt_evaluation"
    return current


def chat_with_split_timeouts(
    *,
    encoded: bytes,
    base_url: str,
    runner_ready_timeout: int,
    generation_timeout: int,
    progress: Gate3Progress | None,
    phase_setter: Callable[[str], None] | None = None,
    on_first_token: Callable[[], None] | None = None,
    urlopen: UrlOpen | None = None,
    cancel: Any = None,
) -> dict[str, Any]:
    """POST /api/chat. First-byte wait uses runner_ready_timeout; body uses generation_timeout."""
    opener = urlopen or urllib.request.urlopen
    http = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events: list[dict[str, Any]] = []
    chunks: list[str] = []
    stream_bytes = 0
    http_status: int | None = None
    headers_received = False
    announced = False
    started = __import__("time").monotonic()
    if progress is not None:
        progress.emit("waiting for API stream / model runner", phase="waiting_for_api_stream")
    if phase_setter is not None:
        phase_setter("waiting_for_api_stream")
    try:
        response_cm = opener(http, timeout=int(runner_ready_timeout))
        response = response_cm.__enter__() if hasattr(response_cm, "__enter__") else response_cm
        try:
            headers_received = True
            http_status = int(getattr(response, "status", None) or getattr(response, "code", None) or 200)
            apply_socket_timeout(response, float(generation_timeout))
            if progress is not None:
                progress.emit("HTTP headers received", phase="prompt_evaluation", http_status=http_status)
            if phase_setter is not None:
                phase_setter("prompt_evaluation")
            for raw in response:
                if cancel is not None and getattr(cancel, "is_set", lambda: False)():
                    break
                stream_bytes += len(raw) if isinstance(raw, (bytes, bytearray)) else len(str(raw))
                line = raw.decode("utf-8", errors="replace").strip() if isinstance(raw, (bytes, bytearray)) else str(raw).strip()
                if not line:
                    continue
                event = json.loads(line)
                events.append(event)
                next_phase = infer_stream_phase(event, "prompt_evaluation")
                if phase_setter is not None:
                    phase_setter(next_phase)
                if progress is not None and next_phase == "generation" and not announced:
                    progress.emit("generation started", phase="generation")
                message = event.get("message") or {}
                piece = message.get("content")
                if piece:
                    chunks.append(str(piece))
                    if not announced:
                        announced = True
                        if on_first_token is not None:
                            on_first_token()
                if event.get("done"):
                    break
        finally:
            if hasattr(response_cm, "__exit__"):
                response_cm.__exit__(None, None, None)
            elif hasattr(response, "close"):
                response.close()
    except TimeoutError as exc:
        elapsed = __import__("time").monotonic() - started
        return {
            "measurement": Measurement(
                elapsed_seconds=elapsed,
                infrastructure_failure=True,
                timed_out=True,
            ),
            "narration": str(exc),
            "events": events,
            "http_status": http_status,
            "headers_received": headers_received,
            "stream_bytes_received": stream_bytes,
            "runner_ready_timeout": True,
            "failure_kind": "timeout",
        }
    except urllib.error.HTTPError as exc:
        elapsed = __import__("time").monotonic() - started
        body = b""
        try:
            body = exc.read() or b""
        except Exception:
            body = b""
        return {
            "measurement": Measurement(
                elapsed_seconds=elapsed,
                infrastructure_failure=True,
            ),
            "narration": f"HTTP {exc.code}",
            "events": events,
            "http_status": int(exc.code),
            "headers_received": True,
            "stream_bytes_received": stream_bytes + len(body),
            "runner_ready_timeout": False,
            "failure_kind": "http_error",
        }
    except (urllib.error.URLError, OSError) as exc:
        elapsed = __import__("time").monotonic() - started
        return {
            "measurement": Measurement(
                elapsed_seconds=elapsed,
                infrastructure_failure=True,
                timed_out="timed out" in str(exc).lower(),
            ),
            "narration": str(exc),
            "events": events,
            "http_status": http_status,
            "headers_received": headers_received,
            "stream_bytes_received": stream_bytes,
            "runner_ready_timeout": not headers_received,
            "failure_kind": "timeout" if "timed out" in str(exc).lower() else "transport",
        }
    last = events[-1] if events else {}
    pec = last.get("prompt_eval_count")
    elapsed = __import__("time").monotonic() - started
    measurement = Measurement(
        elapsed_seconds=elapsed,
        prompt_eval_count=None if pec in (None, 0) else int(pec),
        truncated=bool(last.get("done_reason") == "length"),
    )
    return {
        "measurement": measurement,
        "narration": "".join(chunks),
        "events": events,
        "http_status": http_status,
        "headers_received": headers_received,
        "stream_bytes_received": stream_bytes,
        "runner_ready_timeout": False,
        "failure_kind": None,
    }


def start_confirmation_progress(run_dir: Path, *, timeout_seconds: int, execution_id: str, stream: TextIOBase | None = None) -> Gate3Progress:
    progress = Gate3Progress(
        run_dir,
        timeout_seconds=timeout_seconds,
        controller_id=execution_id,
        stream=stream,
        heartbeat_seconds=35.0,
    )
    progress.json_path = run_dir / "confirmation_progress.json"
    progress.log_path = run_dir / "confirmation_progress.log"
    progress.start_heartbeat()
    return progress


def prove_confirmation_runtime_offline(tmp: Path) -> dict[str, Any]:
    checks: list[str] = []
    problems: list[str] = []

    def ok(name: str, condition: bool, detail: Any = None) -> None:
        checks.append(name)
        if not condition:
            problems.append(f"{name}: {detail}")

    safety = evaluate_confirmation_safety(
        request_json={"truncate": False, "shift": False, "options": {"num_ctx": 39424}},
        prompt_eval_count=None,
        timed_out=True,
        infrastructure_failure=True,
        http_status=None,
        stream_bytes_received=0,
        truncation_occurred=None,
        gpu_resident=None,
        vram_peak_gb=1.47,
        vram_released=None,
        log_truncation=None,
    )
    ok("pre_prompt_classification", safety["classification"] == CLASSIFICATION_INFRA_PRE_PROMPT, safety)
    ok("truncate_unverified", safety["truncate"] == "unverified", safety)
    ok("shift_unverified", safety["shift"] == "unverified", safety)
    ok("no_truncate_not_false", "truncate_not_false" not in safety["problems"], safety["problems"])
    ok("no_shift_not_false", "shift_not_false" not in safety["problems"], safety["problems"])
    ok("placement_unverified", safety["placement"] == "unverified", safety)
    ok("not_claiming_truncation", safety["claims_not_supported"]["truncation_occurred"] is False, safety)

    ran = evaluate_confirmation_safety(
        request_json={"truncate": False, "shift": False, "options": {"num_ctx": 39424}},
        prompt_eval_count=34806,
        timed_out=False,
        infrastructure_failure=False,
        http_status=200,
        stream_bytes_received=12,
        truncation_occurred=False,
        gpu_resident=True,
        vram_peak_gb=21.0,
        vram_released=True,
        log_truncation=False,
    )
    ok("truncate_effective_after_prompt", ran["truncate"] == "effective", ran)
    ok("not_pre_prompt_when_eval", ran["classification"] != CLASSIFICATION_INFRA_PRE_PROMPT, ran)

    run_dir = tmp / "runs" / TIMED_OUT_EXECUTION_ID
    run_dir.mkdir(parents=True, exist_ok=True)
    original = {
        "ok": False,
        "classification": "safety_or_identity_failed",
        "measurement": {"timed_out": True, "prompt_eval_count": None, "infrastructure_failure": True},
    }
    (run_dir / "run_record.json").write_text(json.dumps(original) + "\n", encoding="utf-8")
    (run_dir / "COMPLETE").write_text("complete\n", encoding="utf-8")
    (run_dir / "safety_checks.json").write_text(
        json.dumps({"problems": ["truncate_not_false", "shift_not_false"]}) + "\n", encoding="utf-8"
    )
    before = (run_dir / "run_record.json").read_bytes()
    written = write_classification_sidecar(run_dir)
    ok("sidecar_written", written["ok"] is True, written)
    ok("sidecar_does_not_rewrite", (run_dir / "run_record.json").read_bytes() == before, None)
    ok("sidecar_class", json.loads((run_dir / SIDECAR_NAME).read_text(encoding="utf-8"))["classification"] == CLASSIFICATION_INFRA_PRE_PROMPT, None)

    out = tmp
    unresolved = find_unresolved_attempts(out)
    ok("unresolved_detects_timeout_complete", any(row["execution_id"] == TIMED_OUT_EXECUTION_ID for row in unresolved), unresolved)
    refused = False
    try:
        refuse_if_unresolved(out, recovery_authorized=False)
    except I11A0Error:
        refused = True
    ok("refuse_without_recovery", refused, None)
    refuse_if_unresolved(out, recovery_authorized=True)
    ok("recovery_authorized_allows", True, None)

    capture_dir = tmp / "capture-run"
    capture_dir.mkdir(parents=True, exist_ok=True)
    posted = {"called": False}

    def fake_urlopen(_http: Any, timeout: int = 0) -> Any:
        posted["called"] = True
        posted["timeout"] = timeout
        raise TimeoutError("timed out")

    cap = {"request_json": {"truncate": False, "shift": False}, "request_body_sha256": "abc"}
    persist_request_capture(capture_dir, cap)
    ok("capture_before_post_file", (capture_dir / "request_capture.json").is_file() and not posted["called"], None)
    result = chat_with_split_timeouts(
        encoded=b"{}",
        base_url="http://127.0.0.1:9",
        runner_ready_timeout=12,
        generation_timeout=1800,
        progress=None,
        urlopen=fake_urlopen,
    )
    ok("urlopen_used_runner_ready_timeout", posted.get("timeout") == 12, posted)
    ok("timeout_is_runner_not_generation", result.get("runner_ready_timeout") is True, result)
    ok("measurement_timed_out", result["measurement"].timed_out is True, asdict(result["measurement"]))
    persist_failure_record(
        capture_dir,
        kind="timeout",
        payload={"classification": CLASSIFICATION_INFRA_PRE_PROMPT, "execution_id": "x"},
    )
    ok("timeout_marker", (capture_dir / "TIMEOUT").is_file(), None)
    ok("no_complete_on_timeout_path", not (capture_dir / "COMPLETE").is_file(), None)

    class _Resp:
        status = 200

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def __iter__(self):
            yield b'{"message":{"content":"hi"},"done":true,"prompt_eval_count":10}\n'

    def ok_urlopen(_http: Any, timeout: int = 0) -> _Resp:
        return _Resp()

    good = chat_with_split_timeouts(
        encoded=b"{}",
        base_url="http://127.0.0.1:9",
        runner_ready_timeout=12,
        generation_timeout=99,
        progress=None,
        urlopen=ok_urlopen,
    )
    ok("headers_received", good["headers_received"] is True, good)
    ok("narration_from_stream", good["narration"] == "hi", good)
    ok("prompt_eval_recorded", good["measurement"].prompt_eval_count == 10, good)

    log_dir = tmp / "progress-run"
    log_dir.mkdir(parents=True, exist_ok=True)
    from io import StringIO

    buf = StringIO()
    progress = start_confirmation_progress(log_dir, timeout_seconds=1800, execution_id="demo", stream=buf)
    for phase in HEARTBEAT_PHASES:
        progress.emit(f"phase {phase}", phase=phase)
    progress.stop_heartbeat()
    text = (log_dir / "confirmation_progress.log").read_text(encoding="utf-8")
    ok("progress_log_flushed", bool(text.strip()), text[:80])
    ok("heartbeat_seconds_35", progress.heartbeat_seconds == 35.0, progress.heartbeat_seconds)
    missing = [phase for phase in HEARTBEAT_PHASES if phase not in text]
    ok("all_heartbeat_phases_logged", not missing, missing)

    return {
        "ok": not problems,
        "checks": checks,
        "problems": problems,
        "models_called": False,
    }
