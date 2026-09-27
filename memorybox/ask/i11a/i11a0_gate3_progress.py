"""Terminal-and-file progress for Gate 3. No extra dependencies. No Ollama calls."""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO


HEARTBEAT_SECONDS = 45


def atomic_replace_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def local_now() -> datetime:
    return datetime.now().astimezone()


def format_target(tokens: int | None) -> str:
    if not tokens:
        return "n/a"
    if tokens >= 1000 and tokens % 1000 == 0:
        return f"{tokens // 1000}K"
    if tokens >= 1000:
        return f"{tokens / 1000:.1f}K"
    return str(tokens)


class Gate3Progress:
    def __init__(
        self,
        results_dir: Path | str,
        *,
        timeout_seconds: int,
        controller_id: str,
        stream: TextIO | None = None,
        snapshot: Callable[[], dict[str, Any]] | None = None,
        heartbeat_seconds: float = HEARTBEAT_SECONDS,
        sleeper: Callable[[float], None] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds
        self.controller_id = controller_id
        self.stream = stream
        self.snapshot = snapshot or (lambda: {})
        self.heartbeat_seconds = heartbeat_seconds
        self.sleeper = sleeper or time.sleep
        self.monotonic = monotonic or time.monotonic
        self.json_path = self.results_dir / "gate3_progress.json"
        self.log_path = self.results_dir / "gate3_progress.log"
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._phase_started = self.monotonic()
        self._peak_vram: float | None = None
        self.vram_history: list[float] = []
        self.flushes = 0
        self.lines: list[str] = []
        self.state: dict[str, Any] = {
            "controller_execution_id": controller_id,
            "status": "starting",
            "stage": "preflight",
            "phase": "starting",
            "current_target_evidence_tokens": None,
            "current_estimated_evidence_tokens": None,
            "current_actual_evidence_tokens": None,
            "current_repetition": None,
            "completed_run_count": 0,
            "last_completed_execution_id": None,
            "current_phase_start_time": utc_now().isoformat(),
            "last_heartbeat_time": None,
            "phase_elapsed_seconds": 0.0,
            "timeout_seconds": timeout_seconds,
            "timeout_remaining_seconds": timeout_seconds,
            "current_vram_gb": None,
            "peak_vram_gb": None,
            "current_system_ram_gb": None,
            "gpu_utilization_percent": None,
            "most_recent_classification": None,
            "most_recent_artifact_directory": None,
            "stop_reason": None,
            "warning": None,
            "error": None,
            "expected_next_action": "preflight",
            "heartbeat": False,
            "message": "",
        }

    def _write_line(self, line: str) -> None:
        self.lines.append(line)
        if self.stream is not None:
            self.stream.write(line + "\n")
            self.stream.flush()
            self.flushes += 1
        else:
            import sys

            sys.stdout.write(line + "\n")
            sys.stdout.flush()
            self.flushes += 1
        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def emit(
        self,
        message: str,
        *,
        status: str | None = None,
        stage: str | None = None,
        phase: str | None = None,
        heartbeat: bool = False,
        expected_next_action: str | None = None,
        **fields: Any,
    ) -> dict[str, Any]:
        with self._lock:
            if phase and phase != self.state.get("phase"):
                self._phase_started = self.monotonic()
                self.state["current_phase_start_time"] = utc_now().isoformat()
            if status:
                self.state["status"] = status
            if stage:
                self.state["stage"] = stage
            if phase:
                self.state["phase"] = phase
            if expected_next_action is not None:
                self.state["expected_next_action"] = expected_next_action
            for key, value in fields.items():
                self.state[key] = value
            sample = {}
            try:
                sample = dict(self.snapshot() or {})
            except Exception:
                sample = {}
            vram = sample.get("vram_gb")
            if vram is not None:
                self.state["current_vram_gb"] = vram
                self.vram_history.append(float(vram))
                peak = self._peak_vram
                self._peak_vram = vram if peak is None else max(float(peak), float(vram))
                self.state["peak_vram_gb"] = self._peak_vram
            if sample.get("ram_gb") is not None:
                self.state["current_system_ram_gb"] = sample.get("ram_gb")
            if sample.get("gpu_util") is not None:
                self.state["gpu_utilization_percent"] = sample.get("gpu_util")
            elapsed = self.monotonic() - self._phase_started
            remaining = max(0.0, float(self.timeout_seconds) - elapsed)
            self.state["phase_elapsed_seconds"] = round(elapsed, 3)
            self.state["timeout_remaining_seconds"] = round(remaining, 3)
            self.state["heartbeat"] = heartbeat
            self.state["message"] = message
            stamp_utc = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
            stamp_local = local_now().strftime("%Y-%m-%dT%H:%M:%S%z")
            if heartbeat:
                self.state["last_heartbeat_time"] = utc_now().isoformat()
                line = (
                    f"{stamp_utc} | {stamp_local} | HEARTBEAT | phase={self.state.get('phase')} "
                    f"target={format_target(self.state.get('current_target_evidence_tokens'))} "
                    f"rep={self.state.get('current_repetition')} "
                    f"elapsed_s={self.state['phase_elapsed_seconds']} "
                    f"timeout_remaining_s={self.state['timeout_remaining_seconds']} "
                    f"vram_gb={self.state.get('current_vram_gb')} "
                    f"peak_vram_gb={self.state.get('peak_vram_gb')} "
                    f"gpu_util={self.state.get('gpu_utilization_percent')} "
                    f"ram_gb={self.state.get('current_system_ram_gb')}"
                )
            else:
                line = f"{stamp_utc} | {stamp_local} | {message}"
            payload = dict(self.state)
            atomic_replace_text(self.json_path, json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
            leftover = self.json_path.with_name(self.json_path.name + ".tmp")
            if leftover.exists():
                leftover.unlink()
            self._write_line(line)
            return payload

    def start_heartbeat(self) -> None:
        self.stop_heartbeat()
        self._stop.clear()
        self._phase_started = self.monotonic()

        def loop() -> None:
            while not self._stop.wait(self.heartbeat_seconds):
                self.emit("heartbeat", heartbeat=True, phase=self.state.get("phase"))

        self._thread = threading.Thread(target=loop, name="gate3-heartbeat", daemon=True)
        self._thread.start()

    def stop_heartbeat(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None

    def fail(self, error: str, *, stop_reason: str = "failed") -> None:
        self.stop_heartbeat()
        self.emit(
            f"Gate 3 failed: {error}",
            status="failed",
            phase="failed",
            error=error,
            stop_reason=stop_reason,
            expected_next_action="founder_review",
        )
