"""Independent in-request telemetry for the prompt-accounting control diagnostic.

Never calls Ollama unless the caller injects live nvidia/ps/ram readers.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO

from memorybox.ask.i11a.i11a0_gate3_progress import Gate3Progress
from memorybox.ask.i11a.i11a0_host import VRAM_CEILING_GB, read_nvidia_snapshot, read_system_ram, read_working_set_bytes
from memorybox.ask.i11a.i11a0_placement import (
    VRAM_RESIDENCY_DELTA_GB,
    interpret_ollama_placement,
    read_ollama_ps,
)
from memorybox.ask.i11a.i11a0_smoke import PINNED_B_DIGEST

B_TAG = "qwen3:14b-q8_0"
FIRST_A_EXECUTION_ID = "f2294a49635d5dddc79c2517bbca99869b83e737f96ee9493487e5ebf5f908cb"
ABORTED_A_SIDECAR_NAME = "classification_sidecar.json"
PROTECTED_FIRST_A_NAMES = (
    "COMPLETE",
    "request_capture.json",
    "request_identity.json",
    "packet.txt",
    "packet_identity.json",
    "preflight.json",
    "raw_api.jsonl",
    "narration.txt",
    "run_record.json",
    "hardware_telemetry.json",
)

IN_REQUEST_PHASES = {"request_active", "first_token", "streaming"}

NvidiaFn = Callable[[], dict[str, Any]]
PsFn = Callable[[str], dict[str, Any]]
RamFn = Callable[[], dict[str, Any]]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def aborted_a_sidecar_payload() -> dict[str, Any]:
    return {
        "experiment_role": "aborted_control_attempt",
        "request_accounting_valid": True,
        "prompt_count_observation_valid": True,
        "hardware_telemetry_valid": False,
        "placement_status": "unknown",
        "gpu_resident": None,
        "gpu_residency_lost": "not_proven",
        "reason": "no in-request placement or VRAM samples",
        "eligible_for_a_b_c_conclusion": False,
        "execution_id": FIRST_A_EXECUTION_ID,
        "do_not_count_as_valid_a_slot": True,
        "original_files_rewritten": False,
    }


def write_aborted_a_sidecar(folder: Path | str) -> dict[str, Any]:
    """Add sidecar only. Never rewrite protected original files."""
    root = Path(folder)
    before = {
        name: (root / name).read_bytes() if (root / name).is_file() else None
        for name in PROTECTED_FIRST_A_NAMES
    }
    sidecar = root / ABORTED_A_SIDECAR_NAME
    payload = aborted_a_sidecar_payload()
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    after = {
        name: (root / name).read_bytes() if (root / name).is_file() else None
        for name in PROTECTED_FIRST_A_NAMES
    }
    if before != after:
        raise RuntimeError("aborted-A sidecar writer mutated protected originals")
    payload["protected_files_unchanged"] = True
    return payload


def find_aborted_a_folder(prior_root: Path | str) -> Path | None:
    root = Path(prior_root)
    if not root.exists():
        return None
    runs = root / "runs"
    search_roots = [runs] if runs.is_dir() else [root]
    for base in search_roots:
        for folder in sorted(p for p in base.rglob("*") if p.is_dir()):
            record = folder / "run_record.json"
            if not record.is_file():
                continue
            try:
                row = json.loads(record.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if str(row.get("execution_id") or folder.name) == FIRST_A_EXECUTION_ID:
                return folder
            if folder.name == FIRST_A_EXECUTION_ID:
                return folder
    direct = root / "runs" / "A"
    if direct.is_dir() and (direct / "run_record.json").is_file():
        row = json.loads((direct / "run_record.json").read_text(encoding="utf-8"))
        if str(row.get("execution_id") or "") == FIRST_A_EXECUTION_ID:
            return direct
    return None


def _match_ps_model(ps_payload: dict[str, Any], tag: str, digest: str) -> dict[str, Any] | None:
    for row in ps_payload.get("models") or []:
        name = str(row.get("name") or row.get("model") or "")
        row_digest = str(row.get("digest") or "")
        if name == tag or name.startswith(tag) or (digest and row_digest == digest):
            return row
        if row_digest and digest and row_digest != digest and (name == tag or tag in name):
            return {**row, "digest_mismatch": True}
    return None


def classify_in_request_placement(
    samples: list[dict[str, Any]],
    *,
    tag: str = B_TAG,
    digest: str = PINNED_B_DIGEST,
    baseline_vram_gb: float | None = None,
) -> dict[str, Any]:
    """Tri-state placement from in-request samples only. Unknown is not residency lost."""
    in_request = [row for row in samples if str(row.get("request_phase") or "") in IN_REQUEST_PHASES]
    empty = {
        "placement_status": "unknown",
        "gpu_resident": None,
        "cpu_offload": None,
        "gpu_residency_lost": False,
        "gpu_residency_lost_proven": False,
        "gpu_presence_observed": False,
        "safety_label": "placement_unproven",
        "reason": "no in-request placement or VRAM samples",
        "evidence": [],
        "in_request_sample_count": 0,
    }
    if not in_request:
        return empty

    evidence: list[str] = []
    saw_gpu_resident = False
    saw_cpu_offload = False
    saw_digest_mismatch = False
    lost_after_resident = False
    ps_listed = False
    vram_values: list[float] = []
    for row in in_request:
        used = row.get("gpu_vram_used_gb")
        if isinstance(used, (int, float)):
            vram_values.append(float(used))
        if row.get("digest_mismatch"):
            saw_digest_mismatch = True
            evidence.append("in-request digest mismatch")
        status = row.get("placement_status")
        if status == "gpu_resident":
            saw_gpu_resident = True
            ps_listed = True
            evidence.append("in-request /api/ps size_vram matched model size")
        elif status == "cpu_offload":
            saw_cpu_offload = True
            if saw_gpu_resident:
                lost_after_resident = True
            evidence.append("in-request /api/ps processor or size_vram showed CPU/partial offload")
        if row.get("ps_model_listed"):
            ps_listed = True
    peak = max(vram_values) if vram_values else None
    rise = None
    if peak is not None and baseline_vram_gb is not None:
        rise = float(peak) - float(baseline_vram_gb)
    presence = bool(rise is not None and rise >= VRAM_RESIDENCY_DELTA_GB)

    if saw_digest_mismatch:
        return {
            "placement_status": "unknown",
            "gpu_resident": None,
            "cpu_offload": None,
            "gpu_residency_lost": False,
            "gpu_residency_lost_proven": False,
            "gpu_presence_observed": presence,
            "safety_label": "model_digest_mismatch",
            "reason": "in-request /api/ps digest did not match the pinned model",
            "evidence": evidence,
            "in_request_sample_count": len(in_request),
        }
    if lost_after_resident:
        return {
            "placement_status": "cpu_offload",
            "gpu_resident": False,
            "cpu_offload": True,
            "gpu_residency_lost": True,
            "gpu_residency_lost_proven": True,
            "gpu_presence_observed": True,
            "safety_label": "gpu_residency_lost",
            "reason": "model was GPU-resident in-request and later lost residency during the request",
            "evidence": evidence,
            "in_request_sample_count": len(in_request),
        }
    if saw_cpu_offload:
        return {
            "placement_status": "cpu_offload",
            "gpu_resident": False,
            "cpu_offload": True,
            "gpu_residency_lost": False,
            "gpu_residency_lost_proven": False,
            "gpu_presence_observed": presence,
            "safety_label": "cpu_offload",
            "reason": "affirmative in-request /api/ps CPU or partial-VRAM placement",
            "evidence": evidence,
            "in_request_sample_count": len(in_request),
        }
    if saw_gpu_resident:
        return {
            "placement_status": "gpu_resident",
            "gpu_resident": True,
            "cpu_offload": False,
            "gpu_residency_lost": False,
            "gpu_residency_lost_proven": False,
            "gpu_presence_observed": True,
            "safety_label": None,
            "reason": "in-request /api/ps listed the pinned model with size_vram matching size",
            "evidence": evidence,
            "in_request_sample_count": len(in_request),
        }
    reason = "in-request samples exist but /api/ps did not affirm GPU residency"
    if presence:
        evidence.append(f"nvidia-smi VRAM rose {rise:.3f} GB during the request")
        reason = (
            "nvidia-smi showed a model-sized VRAM rise during the request, "
            "but /api/ps lacked affirmative residency fields"
        )
    return {
        "placement_status": "unknown",
        "gpu_resident": None,
        "cpu_offload": None,
        "gpu_residency_lost": False,
        "gpu_residency_lost_proven": False,
        "gpu_presence_observed": presence,
        "safety_label": "placement_unproven",
        "reason": reason,
        "evidence": evidence,
        "in_request_sample_count": len(in_request),
        "ps_listed": ps_listed,
    }


class IndependentRequestSampler:
    """Thread that samples nvidia-smi and /api/ps while HTTP streaming is blocked."""

    def __init__(
        self,
        *,
        telemetry_path: Path,
        base_url: str,
        experiment_id: str,
        run_id: str,
        execution_id: str,
        tag: str = B_TAG,
        digest: str = PINNED_B_DIGEST,
        nvidia_fn: NvidiaFn | None = None,
        ps_fn: PsFn | None = None,
        ram_fn: RamFn | None = None,
        interval_seconds: float = 1.5,
        ram_every_n: int = 2,
        heartbeat_seconds: float = 15.0,
        progress: Gate3Progress | None = None,
        started_monotonic: float | None = None,
    ) -> None:
        self.telemetry_path = Path(telemetry_path)
        self.base_url = base_url
        self.experiment_id = experiment_id
        self.run_id = run_id
        self.execution_id = execution_id
        self.tag = tag
        self.digest = digest
        self.nvidia_fn = nvidia_fn or read_nvidia_snapshot
        self.ps_fn = ps_fn or read_ollama_ps
        self.ram_fn = ram_fn or read_system_ram
        self.interval_seconds = interval_seconds
        self.ram_every_n = max(1, ram_every_n)
        self.heartbeat_seconds = heartbeat_seconds
        self.progress = progress
        self.started_monotonic = started_monotonic or time.monotonic()
        self.cancel = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.phase = "idle"
        self.samples: list[dict[str, Any]] = []
        self.cancel_reason: str | None = None
        self._ticks = 0
        self._last_heartbeat = 0.0
        self._lock = threading.Lock()
        self._handle: TextIO | None = None
        self.saw_gpu_resident = False
        self.ps_detected = False

    def start(self, phase: str = "request_active") -> None:
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.telemetry_path.open("a", encoding="utf-8", newline="\n")
        self.phase = phase
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="control-telemetry", daemon=True)
        self._thread.start()

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        if self._handle is not None:
            self._handle.flush()
            self._handle.close()
            self._handle = None

    def in_request_samples(self) -> list[dict[str, Any]]:
        with self._lock:
            return [row for row in self.samples if str(row.get("request_phase") or "") in IN_REQUEST_PHASES]

    def vram_for_phases(self, phases: set[str]) -> list[float]:
        values: list[float] = []
        with self._lock:
            for row in self.samples:
                if str(row.get("request_phase") or "") not in phases:
                    continue
                used = row.get("gpu_vram_used_gb")
                if isinstance(used, (int, float)):
                    values.append(float(used))
        return values

    def _signal(self, reason: str) -> None:
        if not self.cancel.is_set():
            self.cancel_reason = reason
            self.cancel.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._capture()
            self._stop.wait(self.interval_seconds)

    def _capture(self) -> dict[str, Any]:
        errors: list[str] = []
        nvidia: dict[str, Any] = {}
        ps_payload: dict[str, Any] = {}
        ram: dict[str, Any] = {}
        try:
            nvidia = dict(self.nvidia_fn() or {})
        except Exception as exc:
            errors.append(f"nvidia:{type(exc).__name__}:{exc}")
            nvidia = {"available": False, "reason": str(exc)}
        try:
            ps_payload = dict(self.ps_fn(self.base_url) or {})
        except Exception as exc:
            errors.append(f"ps:{type(exc).__name__}:{exc}")
            ps_payload = {"available": False, "reason": str(exc), "models": []}
        self._ticks += 1
        if self._ticks % self.ram_every_n == 0:
            try:
                ram = dict(self.ram_fn() or {})
            except Exception as exc:
                errors.append(f"ram:{type(exc).__name__}:{exc}")
                ram = {"available": False, "reason": str(exc)}
        match = _match_ps_model(ps_payload, self.tag, self.digest)
        interpreted = interpret_ollama_placement(
            ps_payload,
            tag=self.tag,
            digest=self.digest,
            queried_while_loaded=self.phase in IN_REQUEST_PHASES,
        )
        digest_mismatch = bool(match and match.get("digest_mismatch"))
        sample = {
            "utc": utc_stamp(),
            "monotonic_elapsed_s": round(time.monotonic() - self.started_monotonic, 3),
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "execution_id": self.execution_id,
            "request_phase": self.phase,
            "gpu_name": nvidia.get("name"),
            "gpu_vram_used_gb": nvidia.get("memory_used_gb"),
            "gpu_vram_total_gb": nvidia.get("memory_total_gb"),
            "gpu_utilization_percent": nvidia.get("utilization_gpu_percent"),
            "system_ram_used_gb": ram.get("used_gb"),
            "system_ram_available_gb": ram.get("available_gb"),
            "ps_available": bool(ps_payload.get("available", True)),
            "ps_model_listed": match is not None and not digest_mismatch,
            "model_tag": None if match is None else (match.get("name") or match.get("model")),
            "model_digest": None if match is None else match.get("digest"),
            "ollama_size": None if match is None else match.get("size"),
            "ollama_size_vram": None if match is None else match.get("size_vram"),
            "processor": None if match is None else (match.get("processor") or (match.get("details") or {}).get("processor")),
            "placement_status": interpreted.get("status") if self.phase in IN_REQUEST_PHASES else None,
            "digest_mismatch": digest_mismatch,
            "sampling_error": ";".join(errors) if errors else None,
            "controller_working_set_bytes": read_working_set_bytes(__import__("os").getpid()),
        }
        with self._lock:
            self.samples.append(sample)
        if self._handle is not None:
            self._handle.write(json.dumps(sample, default=str) + "\n")
            self._handle.flush()
        used = sample.get("gpu_vram_used_gb")
        if isinstance(used, (int, float)) and float(used) >= VRAM_CEILING_GB and self.phase in IN_REQUEST_PHASES:
            self._signal("vram_ceiling")
        if self.phase in IN_REQUEST_PHASES:
            if interpreted.get("status") == "gpu_resident":
                self.saw_gpu_resident = True
                if not self.ps_detected:
                    self.ps_detected = True
                    if self.progress is not None:
                        self.progress.emit(
                            f"/api/ps model detected ({self.tag})",
                            phase="generation",
                            current_vram_gb=used,
                        )
            if interpreted.get("status") == "cpu_offload":
                if self.saw_gpu_resident:
                    self._signal("gpu_residency_lost")
                else:
                    self._signal("cpu_offload")
            if digest_mismatch:
                self._signal("model_digest_mismatch")
        now = time.monotonic()
        if self.progress is not None and now - self._last_heartbeat >= self.heartbeat_seconds:
            self._last_heartbeat = now
            peaks = self.vram_for_phases(IN_REQUEST_PHASES)
            peak = max(peaks) if peaks else None
            self.progress.emit(
                (
                    f"telemetry heartbeat vram_gb={used} peak_vram_gb={peak} "
                    f"phase={self.phase} ps_listed={sample.get('ps_model_listed')}"
                ),
                heartbeat=True,
                phase=self.phase,
                current_vram_gb=used,
                peak_vram_gb=peak,
            )
        return sample


def http_chat_post(
    body: bytes,
    base_url: str,
    timeout: int,
    cancel: threading.Event | None = None,
    on_first_token: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    http = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events: list[dict[str, Any]] = []
    announced = False
    with urllib.request.urlopen(http, timeout=timeout) as response:
        for raw in response:
            if cancel is not None and cancel.is_set():
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            events.append(json.loads(line))
            message = events[-1].get("message") or {}
            if not announced and message.get("content"):
                announced = True
                if on_first_token is not None:
                    on_first_token()
            if events[-1].get("done"):
                break
    return events


def invoke_post(
    post_fn: Callable[..., list[dict[str, Any]]],
    body: bytes,
    base_url: str,
    timeout: int,
    cancel: threading.Event | None,
    on_first_token: Callable[[], None] | None,
) -> list[dict[str, Any]]:
    try:
        return post_fn(body, base_url, timeout, cancel=cancel, on_first_token=on_first_token)
    except TypeError:
        return post_fn(body, base_url, timeout)
