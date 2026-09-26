"""FlightSim host-affinity and local hardware telemetry for Gate 2 smoke."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from memorybox.ask.i11a.i11a0_benchmark import I11A0Error

REQUIRED_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
REQUIRED_GPU_NAME = "NVIDIA GeForce RTX 4090"
VRAM_TOTAL_MIN_GB = 22.0
VRAM_TOTAL_MAX_GB = 26.0
VRAM_CEILING_GB = 22.5
REMOTE_FUNCTIONAL_RUN_ID = (
    "0717c7de073416f1200ce2047b39c961161d9ffe674f8374657700273117a24e"
)
REMOTE_FUNCTIONAL_LABEL = "functional_token_safety_pass_hardware_telemetry_invalid"
FORBIDDEN_OLLAMA_HOSTS = ("flightsim",)


class HostAffinityError(I11A0Error):
    """Controller is not on the FlightSim RTX 4090 host."""


NvidiaReader = Callable[[], dict[str, Any]]
RamReader = Callable[[], dict[str, Any]]
GitReader = Callable[[Path], dict[str, Any]]
OllamaVersionReader = Callable[[str], str | None]


def _float_or_none(value: Any) -> float | None:
    try:
        text = str(value).strip()
        if not text or text.upper() == "[N/A]":
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def read_nvidia_snapshot() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "reason": type(exc).__name__}
    if completed.returncode != 0:
        return {
            "available": False,
            "reason": (completed.stderr or completed.stdout or "nvidia_smi_failed").strip(),
        }
    line = (completed.stdout or "").strip().splitlines()
    if not line:
        return {"available": False, "reason": "nvidia_smi_empty"}
    parts = [item.strip() for item in line[0].split(",")]
    while len(parts) < 4:
        parts.append("")
    total_mb = _float_or_none(parts[1])
    used_mb = _float_or_none(parts[2])
    util = _float_or_none(parts[3])
    total_gb = None if total_mb is None else total_mb / 1024.0
    used_gb = None if used_mb is None else used_mb / 1024.0
    return {
        "available": True,
        "name": parts[0],
        "memory_total_mb": total_mb,
        "memory_used_mb": used_mb,
        "memory_total_gb": total_gb,
        "memory_used_gb": used_gb,
        "utilization_gpu_percent": util,
        "raw": line[0],
    }


def read_system_ram() -> dict[str, Any]:
    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {"available": False, "reason": "GlobalMemoryStatusEx_failed"}
    total = int(status.ullTotalPhys)
    avail = int(status.ullAvailPhys)
    used = total - avail
    return {
        "available": True,
        "total_bytes": total,
        "available_bytes": avail,
        "used_bytes": used,
        "total_gb": total / (1024 ** 3),
        "used_gb": used / (1024 ** 3),
        "available_gb": avail / (1024 ** 3),
        "memory_load_percent": int(status.dwMemoryLoad),
    }


def read_working_set_bytes(pid: int) -> int | None:
    try:
        import ctypes.wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        PROCESS_VM_READ = 0x0010
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid
        )
        if not handle:
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
        if not handle:
            return None

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.wintypes.DWORD),
                ("PageFaultCount", ctypes.wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        )
        ctypes.windll.kernel32.CloseHandle(handle)
        if not ok:
            return None
        return int(counters.WorkingSetSize)
    except Exception:
        return None


def read_ollama_process_memory() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "reason": type(exc).__name__, "processes": []}
    if completed.returncode != 0:
        return {"available": False, "reason": "tasklist_failed", "processes": []}
    processes: list[dict[str, Any]] = []
    for raw in (completed.stdout or "").splitlines():
        if "ollama" not in raw.lower():
            continue
        parts = [item.strip().strip('"') for item in raw.split('","')]
        if len(parts) < 2:
            continue
        name = parts[0]
        try:
            pid = int(parts[1])
        except ValueError:
            continue
        working_set = read_working_set_bytes(pid)
        processes.append(
            {
                "name": name,
                "pid": pid,
                "working_set_bytes": working_set,
                "working_set_gb": None if working_set is None else working_set / (1024 ** 3),
            }
        )
    return {
        "available": bool(processes),
        "processes": processes,
        "working_set_bytes_total": sum(
            int(row["working_set_bytes"] or 0) for row in processes
        ),
    }


def read_git_identity(repo: Path) -> dict[str, Any]:
    def _git(*args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        return (completed.stdout or "").strip()

    return {
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or None,
        "commit": _git("rev-parse", "HEAD") or None,
        "commit_short": _git("rev-parse", "--short", "HEAD") or None,
        "status_short": _git("status", "-sb") or None,
    }


def read_ollama_version(base_url: str) -> str | None:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/version", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None
    version = payload.get("version")
    return str(version) if version else None


def normalize_ollama_base_url(url: str) -> str:
    return str(url or "").strip().rstrip("/")


def collect_host_affinity_preflight(
    *,
    ollama_base_url: str,
    output_path: Path | str,
    chunks_path: Path | str,
    repo: Path,
    nvidia_reader: NvidiaReader = read_nvidia_snapshot,
    ram_reader: RamReader = read_system_ram,
    git_reader: GitReader = read_git_identity,
    ollama_version_reader: OllamaVersionReader = read_ollama_version,
    controller_hostname: str | None = None,
) -> dict[str, Any]:
    gpu = nvidia_reader()
    ram = ram_reader()
    git = git_reader(repo)
    os_hostname = socket.gethostname()
    controller = controller_hostname or os_hostname
    normalized = normalize_ollama_base_url(ollama_base_url)
    version = ollama_version_reader(normalized) if normalized else None
    gpu_name = str(gpu.get("name") or "")
    total_gb = gpu.get("memory_total_gb")
    url_ok = normalized == REQUIRED_OLLAMA_BASE_URL
    forbidden_host = any(host in normalized.lower() for host in FORBIDDEN_OLLAMA_HOSTS)
    gpu_ok = REQUIRED_GPU_NAME.lower() in gpu_name.lower()
    vram_ok = isinstance(total_gb, (int, float)) and VRAM_TOTAL_MIN_GB <= float(total_gb) <= VRAM_TOTAL_MAX_GB
    return {
        "kind": "flightsim_host_affinity_preflight",
        "controller_hostname": controller,
        "operating_system_hostname": os_hostname,
        "ollama_base_url": normalized,
        "ollama_version": version,
        "gpu_name": gpu_name or None,
        "gpu_total_vram_gb": total_gb,
        "gpu_used_vram_gb": gpu.get("memory_used_gb"),
        "gpu_utilization_percent": gpu.get("utilization_gpu_percent"),
        "system_ram_total_gb": ram.get("total_gb"),
        "system_ram_used_gb": ram.get("used_gb"),
        "git": git,
        "output_path": str(output_path),
        "peggy_chunk_path": str(chunks_path),
        "nvidia": gpu,
        "system_ram": ram,
        "controller_pid": os.getpid(),
        "controller_working_set_bytes": read_working_set_bytes(os.getpid()),
        "checks": {
            "ollama_base_url_local": url_ok,
            "ollama_url_not_remote_flightsim_alias": not forbidden_host,
            "gpu_is_rtx_4090": gpu_ok,
            "vram_total_approximately_24gb": bool(vram_ok),
        },
        "required": {
            "ollama_base_url": REQUIRED_OLLAMA_BASE_URL,
            "gpu_name": REQUIRED_GPU_NAME,
            "vram_total_gb_range": [VRAM_TOTAL_MIN_GB, VRAM_TOTAL_MAX_GB],
        },
    }


def require_flightsim_host_affinity(preflight: dict[str, Any]) -> None:
    checks = preflight.get("checks") or {}
    if not checks.get("ollama_base_url_local") or not checks.get("ollama_url_not_remote_flightsim_alias"):
        raise HostAffinityError(
            "FlightSim hardware smoke requires Ollama at http://127.0.0.1:11434 "
            "on the controller host; remote aliases such as http://flightsim:11434 are refused"
        )
    if not checks.get("gpu_is_rtx_4090"):
        raise HostAffinityError(
            "FlightSim hardware smoke requires a local NVIDIA GeForce RTX 4090; "
            f"controller GPU was {preflight.get('gpu_name') or 'unavailable'}"
        )
    if not checks.get("vram_total_approximately_24gb"):
        raise HostAffinityError(
            "FlightSim hardware smoke requires approximately 24 GB local VRAM; "
            f"controller total was {preflight.get('gpu_total_vram_gb')}"
        )


def label_remote_functional_run(run_dir: Path) -> dict[str, Any]:
    """Classify the desktop-controlled rerun without rewriting its metrics."""
    run_dir = Path(run_dir)
    record_path = run_dir / "run_record.json"
    if not record_path.exists():
        raise I11A0Error(f"remote functional run_record.json is missing in {run_dir}")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    identity = str(record.get("identity") or run_dir.name)
    hashes = {
        name: hashlib.sha256((run_dir / name).read_bytes()).hexdigest()
        for name in ("run_record.json", "token_accounting.json", "narration.txt", "raw_api.jsonl")
        if (run_dir / name).exists()
    }
    payload = {
        "kind": "hardware_telemetry_classification",
        "identity": identity,
        "label": REMOTE_FUNCTIONAL_LABEL,
        "original_files_unmodified": True,
        "accepted_as": "functional_and_token_accounting_proof",
        "flightsim_hardware_smoke": False,
        "reason": (
            "Controller and telemetry ran on Desktop while Ollama ran on FlightSim. "
            "Token accounting may be used; RTX 4090 VRAM/RAM measurements may not."
        ),
        "original_artifact_sha256": hashes,
        "original_classification": record.get("classification"),
    }
    dest = run_dir / "hardware_telemetry_classification.json"
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return payload


class HardwareSampler:
    """Local nvidia-smi and RAM samples. Does not use a remote Ollama alias."""

    def __init__(self) -> None:
        self.samples: list[dict[str, Any]] = []

    def capture(self, phase: str) -> dict[str, Any]:
        gpu = read_nvidia_snapshot()
        ram = read_system_ram()
        ollama = read_ollama_process_memory()
        sample = {
            "phase": phase,
            "monotonic": time.monotonic(),
            "gpu_name": gpu.get("name"),
            "vram_used_gb": gpu.get("memory_used_gb"),
            "vram_total_gb": gpu.get("memory_total_gb"),
            "gpu_utilization_percent": gpu.get("utilization_gpu_percent"),
            "system_ram_used_gb": ram.get("used_gb"),
            "system_ram_total_gb": ram.get("total_gb"),
            "controller_working_set_bytes": read_working_set_bytes(os.getpid()),
            "ollama_process_memory": ollama,
        }
        self.samples.append(sample)
        return sample

    def vram_used_values(self) -> list[float]:
        return [
            float(row["vram_used_gb"])
            for row in self.samples
            if isinstance(row.get("vram_used_gb"), (int, float))
        ]

    def ram_used_values(self) -> list[float]:
        return [
            float(row["system_ram_used_gb"])
            for row in self.samples
            if isinstance(row.get("system_ram_used_gb"), (int, float))
        ]

    def summary(self) -> dict[str, Any]:
        vram = self.vram_used_values()
        ram = self.ram_used_values()
        utils = [
            float(row["gpu_utilization_percent"])
            for row in self.samples
            if isinstance(row.get("gpu_utilization_percent"), (int, float))
        ]
        peak_vram = max(vram) if vram else None
        baseline_vram = vram[0] if vram else None
        return {
            "sample_count": len(self.samples),
            "vram_baseline_gb": baseline_vram,
            "vram_peak_gb": peak_vram,
            "vram_final_gb": vram[-1] if vram else None,
            "ram_baseline_gb": ram[0] if ram else None,
            "ram_peak_gb": max(ram) if ram else None,
            "ram_final_gb": ram[-1] if ram else None,
            "gpu_utilization_peak_percent": max(utils) if utils else None,
            "exceeds_vram_ceiling": bool(peak_vram is not None and peak_vram >= VRAM_CEILING_GB),
            "gpu_resident": bool(
                peak_vram is not None
                and baseline_vram is not None
                and (peak_vram - baseline_vram) >= 4.0
            ),
            "cpu_offload": bool(
                peak_vram is not None
                and baseline_vram is not None
                and (peak_vram - baseline_vram) < 4.0
            ),
            "ceiling_gb": VRAM_CEILING_GB,
            "samples": self.samples,
        }
