"""C1T FlightSim Gemma benchmark and evidence chunking harness.

Operator-invoked only. Inventory, canonical registration, and chunk preparation
never call a model. Real benchmark calls require an explicit confirmation flag.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

C1T_VERSION = "1.0"
DEFAULT_MODEL = "gemma4:26b"
DEFAULT_NUM_PREDICT = 4096
DEFAULT_OVERLAP_MESSAGES = 3
DEFAULT_HEARTBEAT_SECONDS = 10
DEFAULT_STALL_WARNING_SECONDS = 300
DEFAULT_HARD_TIMEOUT_SECONDS = 1800
DEFAULT_TIMEOUT_GRACE_SECONDS = 10
DEFAULT_KEEP_ALIVE = "30m"

_SYSTEM = "===== SYSTEM INSTRUCTIONS ====="
_USER = "===== USER QUESTION AND EVIDENCE ====="
_CONVERSATIONS = "===== TRUSTED EMAIL CONVERSATIONS ====="
_BEGIN = "BEGIN CONVERSATION:"
_END = "END CONVERSATION"
_EMAIL = re.compile(r"\[(email_\d+)\]", re.I)
_TURN = re.compile(
    r"(?:said:|service-generated|authorship unresolved).*\[(email_\d+)\]"
    r"|\[(email_\d+)\].*(?:said:|service-generated|authorship unresolved)",
    re.I,
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, default=str) + "\n").encode(
        "utf-8"
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(_json_bytes(value))


def estimate_tokens(text: str) -> int:
    """Conservative, deterministic estimator used before Ollama reports actuals."""
    return max(1, (len(text.encode("utf-8")) + 3) // 4)


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "value": None, "reason": reason}


def _run_capture(command: list[str], *, timeout: float = 8.0) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            errors="replace",
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"


def _get_json(url: str, *, timeout: float = 5.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def _post_json(url: str, payload: dict[str, Any], *, timeout: float = 10.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def _psutil_inventory() -> dict[str, Any]:
    try:
        import psutil  # type: ignore
    except ImportError:
        return {
            "psutil": _unavailable("psutil_not_installed"),
            "memory": _unavailable("psutil_not_installed"),
            "pagefile": _unavailable("psutil_not_installed"),
            "cpu": _unavailable("psutil_not_installed"),
            "boot_time": _unavailable("psutil_not_installed"),
        }
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    freq = psutil.cpu_freq()
    return {
        "psutil": {
            "available": True,
            "version": getattr(psutil, "__version__", "unknown"),
        },
        "memory": {
            "available": True,
            "total_bytes": vm.total,
            "available_bytes": vm.available,
            "used_bytes": vm.used,
            "percent": vm.percent,
        },
        "pagefile": {
            "available": True,
            "total_bytes": swap.total,
            "used_bytes": swap.used,
            "free_bytes": swap.free,
            "percent": swap.percent,
        },
        "cpu": {
            "available": True,
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "current_mhz": getattr(freq, "current", None),
            "max_mhz": getattr(freq, "max", None),
        },
        "boot_time": {
            "available": True,
            "value": datetime.fromtimestamp(
                psutil.boot_time(), tz=timezone.utc
            ).isoformat(),
            "uptime_seconds": int(time.time() - psutil.boot_time()),
        },
    }


def _windows_inventory() -> dict[str, Any]:
    if platform.system() != "Windows":
        return _unavailable("not_windows")
    script = r"""
$ErrorActionPreference='SilentlyContinue'
$os=Get-CimInstance Win32_OperatingSystem
$cpu=Get-CimInstance Win32_Processor
$cs=Get-CimInstance Win32_ComputerSystem
$pf=Get-CimInstance Win32_PageFileUsage
$disks=Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3"
$diskModels=Get-CimInstance Win32_DiskDrive
$power=(powercfg /getactivescheme 2>$null)
[pscustomobject]@{
 edition=$os.Caption; build=$os.BuildNumber; version=$os.Version
 timezone=(Get-TimeZone).Id; machine=$env:COMPUTERNAME
 cpu=@($cpu|%{[pscustomobject]@{name=$_.Name;cores=$_.NumberOfCores;logical=$_.NumberOfLogicalProcessors;current_mhz=$_.CurrentClockSpeed;max_mhz=$_.MaxClockSpeed}})
 ram_total_bytes=[int64]$cs.TotalPhysicalMemory
 pagefiles=@($pf|%{[pscustomobject]@{name=$_.Name;allocated_mb=$_.AllocatedBaseSize;current_mb=$_.CurrentUsage;peak_mb=$_.PeakUsage}})
 disks=@($disks|%{[pscustomobject]@{device=$_.DeviceID;size_bytes=[int64]$_.Size;free_bytes=[int64]$_.FreeSpace}})
 disk_models=@($diskModels|%{[pscustomobject]@{model=$_.Model;interface=$_.InterfaceType;size_bytes=[int64]$_.Size;serial=$_.SerialNumber}})
 power_plan=$power
}|ConvertTo-Json -Depth 6 -Compress
"""
    rc, out, err = _run_capture(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout=15
    )
    if rc or not out:
        return _unavailable(err or f"powershell_exit_{rc}")
    try:
        return {"available": True, "value": json.loads(out)}
    except json.JSONDecodeError as exc:
        return _unavailable(f"invalid_powershell_json:{exc}")


def _nvidia_inventory() -> dict[str, Any]:
    fields = (
        "index,name,driver_version,memory.total,memory.free,memory.used,"
        "utilization.gpu,temperature.gpu,power.draw"
    )
    rc, out, err = _run_capture(
        [
            "nvidia-smi",
            f"--query-gpu={fields}",
            "--format=csv,noheader,nounits",
        ],
        timeout=10,
    )
    if rc:
        return _unavailable(err or "nvidia_smi_unavailable")
    rows: list[dict[str, Any]] = []
    keys = fields.split(",")
    for line in out.splitlines():
        vals = [v.strip() for v in line.split(",")]
        rows.append(dict(zip(keys, vals)))
    return {"available": True, "tool": "nvidia-smi", "gpus": rows}


def _ollama_inventory(base_url: str, model: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    try:
        version = _get_json(f"{base}/api/version", timeout=4)
        tags = _get_json(f"{base}/api/tags", timeout=8)
        running = _get_json(f"{base}/api/ps", timeout=5)
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "base_url": base,
            "reason": f"{type(exc).__name__}:{exc}",
            "version": None,
            "models": [],
            "running_models": [],
        }
    models = list(tags.get("models") or [])
    requested = next(
        (
            row
            for row in models
            if str(row.get("name") or row.get("model") or "") in {model, f"{model}:latest"}
            or str(row.get("name") or "").startswith(f"{model}:")
        ),
        None,
    )
    show: dict[str, Any] | None = None
    if requested:
        try:
            show = _post_json(f"{base}/api/show", {"name": model}, timeout=15)
        except Exception as exc:  # noqa: BLE001
            show = {"available": False, "reason": f"{type(exc).__name__}:{exc}"}
    return {
        "available": True,
        "base_url": base,
        "version": version.get("version"),
        "models": models,
        "requested_model": requested,
        "requested_model_show": show,
        "running_models": list(running.get("models") or []),
    }


def collect_inventory(
    *,
    out_dir: Path | str,
    ollama_base_url: str = "http://127.0.0.1:11434",
    model: str = DEFAULT_MODEL,
    include_msinfo32: bool = False,
) -> dict[str, Any]:
    """Collect authoritative machine-readable inventory; never invokes a model."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    collected = _iso_now()
    disk = shutil.disk_usage(out)
    base = {
        "inventory_version": C1T_VERSION,
        "host": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor() or None,
            "timezone": str(datetime.now().astimezone().tzinfo),
        },
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "psutil_metrics": _psutil_inventory(),
        "windows": _windows_inventory(),
        "nvidia": _nvidia_inventory(),
        "target_volume": {
            "path": str(out.resolve()),
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
        },
        "ollama": _ollama_inventory(ollama_base_url, model),
        "requested_model": model,
    }
    ollama = base["ollama"]
    if not ollama.get("available"):
        recommendation = {
            "recommended_action": "inventory_only",
            "reason": "ollama_unavailable",
            "first_case": None,
        }
    elif not ollama.get("requested_model"):
        recommendation = {
            "recommended_action": "do_not_benchmark",
            "reason": "requested_model_missing",
            "first_case": None,
        }
    else:
        recommendation = {
            "recommended_action": "operator_review_then_case_A",
            "reason": "approved_ladder_starts_at_safe_baseline; review RAM/VRAM/pagefile first",
            "first_case": {
                "case_id": "A",
                "target_evidence_tokens": 8000,
                "num_ctx": 16384,
                "num_predict": 4096,
                "temperature": 0.1,
            },
        }
    base["starting_case_recommendation"] = recommendation
    stable_hash = _sha256_bytes(_json_bytes(base))
    inventory = {
        **base,
        "collected_at": collected,
        "inventory_sha256": stable_hash,
        "models_called": False,
    }
    json_path = out / "FLIGHTSIM_INVENTORY.json"
    text_path = out / "FLIGHTSIM_INVENTORY.txt"
    _write_json(json_path, inventory)
    lines = [
        "C1T FLIGHTSIM HARDWARE / OLLAMA INVENTORY",
        f"collected_at: {collected}",
        f"inventory_sha256: {stable_hash}",
        f"host: {inventory['host']['hostname']} / {inventory['host']['platform']}",
        f"python: {inventory['python']['version']}",
        f"target_volume_free_bytes: {disk.free}",
        f"psutil: {json.dumps(inventory['psutil_metrics'], default=str)}",
        f"nvidia: {json.dumps(inventory['nvidia'], default=str)}",
        f"ollama: {json.dumps(inventory['ollama'], default=str)}",
        f"starting_case_recommendation: {json.dumps(recommendation)}",
        "models_called: false",
    ]
    text_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    msinfo_path: str | None = None
    if include_msinfo32 and platform.system() == "Windows":
        candidate = out / "MSINFO32_REPORT.txt"
        rc, _, _ = _run_capture(["msinfo32", "/report", str(candidate)], timeout=120)
        if rc == 0 and candidate.exists():
            msinfo_path = str(candidate)
    return {
        "ok": True,
        "inventory": inventory,
        "inventory_json": str(json_path),
        "inventory_report": str(text_path),
        "msinfo32_report": msinfo_path,
    }


def register_canonical_generation(
    *, source_dir: Path | str, generations_dir: Path | str
) -> dict[str, Any]:
    """Copy a reviewed packet into a new immutable generation directory."""
    source = Path(source_dir)
    root = Path(generations_dir)
    required = ["MODEL_PASTE.txt", "SOURCE_MAP.json", "PREPARATION_REPORT.txt"]
    missing = [name for name in required if not (source / name).is_file()]
    if missing:
        return {"ok": False, "error": "canonical_artifact_missing", "missing": missing}
    paste_bytes = (source / "MODEL_PASTE.txt").read_bytes()
    paste_hash = _sha256_bytes(paste_bytes)
    source_map = json.loads((source / "SOURCE_MAP.json").read_text(encoding="utf-8"))
    mapped = str(source_map.get("frozen_input_sha256") or "").lower()
    if mapped != paste_hash:
        return {
            "ok": False,
            "error": "canonical_paste_source_map_hash_mismatch",
            "paste_sha256": paste_hash,
            "source_map_frozen_input_sha256": mapped,
        }
    paste_cites = sorted(set(_EMAIL.findall(paste_bytes.decode("utf-8"))))
    map_cites = sorted(
        {
            str(row.get("cite_as") or "")
            for row in source_map.get("citations") or []
            if row.get("cite_as")
        }
    )
    if paste_cites != map_cites:
        return {
            "ok": False,
            "error": "canonical_citation_mismatch",
            "missing_in_source_map": sorted(set(paste_cites) - set(map_cites)),
            "missing_in_paste": sorted(set(map_cites) - set(paste_cites)),
        }
    fingerprints = {name: _sha256_file(source / name) for name in required}
    generation_id = f"c1t-{paste_hash[:16]}"
    dest = root / generation_id
    if dest.exists():
        existing = dest / "GENERATION_MANIFEST.json"
        if existing.is_file():
            manifest = json.loads(existing.read_text(encoding="utf-8"))
            if manifest.get("artifact_sha256") == fingerprints:
                return {
                    "ok": True,
                    "generation_id": generation_id,
                    "generation_dir": str(dest),
                    "already_registered": True,
                    "manifest": manifest,
                }
        return {"ok": False, "error": "generation_id_collision", "path": str(dest)}
    dest.mkdir(parents=True)
    for name in required:
        shutil.copy2(source / name, dest / name)
    manifest = {
        "generation_manifest_version": 1,
        "generation_id": generation_id,
        "created_at": _iso_now(),
        "source_directory": str(source.resolve()),
        "source_commit": _git_commit(),
        "model_paste_sha256": paste_hash,
        "artifact_sha256": fingerprints,
        "citation_count": len(paste_cites),
        "citation_ids": paste_cites,
        "internally_consistent": True,
    }
    _write_json(dest / "GENERATION_MANIFEST.json", manifest)
    return {
        "ok": True,
        "generation_id": generation_id,
        "generation_dir": str(dest),
        "already_registered": False,
        "manifest": manifest,
    }


def _git_commit() -> str:
    rc, out, _ = _run_capture(["git", "rev-parse", "HEAD"])
    return out if rc == 0 else "unknown"


@dataclass(frozen=True)
class EmailTurn:
    cite_as: str
    text: str


@dataclass(frozen=True)
class Conversation:
    conversation_id: str
    header: str
    turns: tuple[EmailTurn, ...]
    earliest: str
    latest: str


@dataclass(frozen=True)
class ChunkParameters:
    target_input_tokens: int
    hard_input_tokens: int
    reserved_output_tokens: int = DEFAULT_NUM_PREDICT
    safety_margin_tokens: int = 2048
    num_ctx: int = 32768
    overlap_messages: int = DEFAULT_OVERLAP_MESSAGES
    overflow_policy: str = "exceptional_call_then_split_between_emails"

    def validate(self) -> None:
        if self.target_input_tokens <= 0 or self.hard_input_tokens <= 0:
            raise ValueError("target/hard tokens must be positive")
        if self.target_input_tokens > self.hard_input_tokens:
            raise ValueError("target_input_tokens cannot exceed hard_input_tokens")
        if not 2 <= self.overlap_messages <= 5:
            raise ValueError("overlap_messages must be 2..5")
        if self.hard_input_tokens + self.reserved_output_tokens + self.safety_margin_tokens > self.num_ctx:
            raise ValueError(
                "hard_input_tokens + reserved_output_tokens + safety_margin_tokens "
                "exceeds num_ctx"
            )


def _parse_turns(block: str) -> tuple[EmailTurn, ...]:
    turns: list[EmailTurn] = []
    current: list[str] = []
    current_id = ""
    for line in block.splitlines():
        match = _TURN.search(line)
        if match:
            if current and current_id:
                turns.append(EmailTurn(current_id, "\n".join(current).rstrip()))
            current_id = match.group(1) or match.group(2) or ""
            current = [line]
        elif current_id:
            current.append(line)
    if current and current_id:
        turns.append(EmailTurn(current_id, "\n".join(current).rstrip()))
    return tuple(turns)


def parse_conversations(
    paste_text: str, source_map: dict[str, Any]
) -> tuple[str, list[Conversation]]:
    """Parse frozen paste into complete conversations with deterministic dates."""
    if _CONVERSATIONS not in paste_text:
        raise ValueError("MODEL_PASTE missing TRUSTED EMAIL CONVERSATIONS marker")
    prefix, body = paste_text.split(_CONVERSATIONS, 1)
    citation_dates = {
        str(row.get("cite_as") or ""): str(row.get("sent_at") or "")
        for row in source_map.get("citations") or []
    }
    conversations: list[Conversation] = []
    for ordinal, part in enumerate(re.split(r"(?=BEGIN CONVERSATION:)", body)):
        if not part.strip().startswith(_BEGIN) or _END not in part:
            continue
        block = part.split(_END, 1)[0].strip()
        lines = block.splitlines()
        turns = _parse_turns(block)
        if not turns:
            continue
        dates = sorted(citation_dates.get(t.cite_as, "") for t in turns if citation_dates.get(t.cite_as))
        conversation_id = f"conv-{ordinal:06d}-{_sha256_bytes(block.encode('utf-8'))[:12]}"
        conversations.append(
            Conversation(
                conversation_id=conversation_id,
                header=lines[0],
                turns=turns,
                earliest=dates[0] if dates else "9999",
                latest=dates[-1] if dates else "",
            )
        )
    conversations.sort(key=lambda c: (c.earliest, c.conversation_id))
    if not conversations:
        raise ValueError("no conversations parsed")
    return prefix.rstrip(), conversations


def _chunk_prompt(prefix: str, *, index: int, total: int, pieces: list[dict[str, Any]]) -> str:
    evidence = "\n\n".join(piece["text"] for piece in pieces)
    warning = (
        f"C1T BENCHMARK CHUNK {index} OF {total}. Partial evidence by design. "
        "Use only [email_N] evidence IDs present in this chunk. Preserve uncertainty "
        "and missing-context warnings. Do not invent evidence IDs."
    )
    return f"{prefix}\n\n{warning}\n\n{_CONVERSATIONS}\n\n{evidence}\n"


def _piece_text(conversation: Conversation, turns: list[EmailTurn], *, partial: str | None) -> str:
    lines = [conversation.header]
    if partial:
        lines.append(f"===== PARTIAL CONVERSATION: {partial} =====")
    lines.extend(turn.text for turn in turns)
    lines.append(_END)
    return "\n".join(lines)


def prepare_parameterized_chunks(
    *,
    generation_dir: Path | str,
    out_root: Path | str,
    parameters: ChunkParameters,
    prompt_overhead_tokens: int = 0,
) -> dict[str, Any]:
    """Pack complete conversations; split oversized ones only between emails."""
    parameters.validate()
    generation = Path(generation_dir)
    generation_manifest_path = generation / "GENERATION_MANIFEST.json"
    if not generation_manifest_path.is_file():
        return {"ok": False, "error": "generation_manifest_missing"}
    gen = json.loads(generation_manifest_path.read_text(encoding="utf-8"))
    paste_path = generation / "MODEL_PASTE.txt"
    smap_path = generation / "SOURCE_MAP.json"
    if _sha256_file(paste_path) != gen.get("model_paste_sha256"):
        return {"ok": False, "error": "stale_generation_paste_hash"}
    source_map = json.loads(smap_path.read_text(encoding="utf-8"))
    prefix, conversations = parse_conversations(
        paste_path.read_text(encoding="utf-8"), source_map
    )
    # One-piece token cost includes the exact repeated prompt prefix.
    def piece_cost(text: str) -> int:
        conservative = _chunk_prompt(
            prefix,
            index=999,
            total=999,
            pieces=[{"text": text}],
        )
        return estimate_tokens(conservative) + prompt_overhead_tokens

    pieces: list[dict[str, Any]] = []
    overlap_declared: list[str] = []
    for conv in conversations:
        full = _piece_text(conv, list(conv.turns), partial=None)
        cost = piece_cost(full)
        if cost <= parameters.hard_input_tokens:
            pieces.append(
                {
                    "conversation_id": conv.conversation_id,
                    "text": full,
                    "cite_as": [t.cite_as for t in conv.turns],
                    "primary_cite_as": [t.cite_as for t in conv.turns],
                    "overlap_cite_as": [],
                    "earliest": conv.earliest,
                    "latest": conv.latest,
                    "overflow_status": "none",
                    "estimated_tokens": cost,
                }
            )
            continue
        # Unavoidable split. Never split an email; repeat trailing 2-5 complete emails.
        start = 0
        part = 1
        turns = list(conv.turns)
        while start < len(turns):
            overlap: list[EmailTurn] = []
            if part > 1:
                maximum = min(parameters.overlap_messages, start)
                minimum = min(2, start)
                for overlap_n in range(maximum, minimum - 1, -1):
                    candidate_overlap = turns[start - overlap_n : start]
                    first_text = _piece_text(
                        conv,
                        candidate_overlap + [turns[start]],
                        partial=f"part {part}",
                    )
                    if piece_cost(first_text) <= parameters.hard_input_tokens:
                        overlap = candidate_overlap
                        break
                if not overlap:
                    raise ValueError(
                        f"hard_input_tokens cannot fit minimum complete-email overlap "
                        f"plus next email for {conv.conversation_id}"
                    )
            selected: list[EmailTurn] = []
            cursor = start
            while cursor < len(turns):
                trial = selected + [turns[cursor]]
                text = _piece_text(conv, overlap + trial, partial=f"part {part}")
                if selected and piece_cost(text) > parameters.hard_input_tokens:
                    break
                selected = trial
                cursor += 1
                if piece_cost(text) > parameters.hard_input_tokens:
                    # One complete email alone is an unavoidable oversize piece.
                    break
            if not selected:
                raise AssertionError("split made no progress")
            combined = overlap + selected
            primary_ids = [t.cite_as for t in selected]
            overlap_ids = [t.cite_as for t in overlap]
            overlap_declared.extend(overlap_ids)
            text = _piece_text(
                conv,
                combined,
                partial=f"part {part}; overlap={','.join(overlap_ids) or 'none'}",
            )
            pieces.append(
                {
                    "conversation_id": conv.conversation_id,
                    "text": text,
                    "cite_as": [t.cite_as for t in combined],
                    "primary_cite_as": primary_ids,
                    "overlap_cite_as": overlap_ids,
                    "earliest": conv.earliest,
                    "latest": conv.latest,
                    "overflow_status": (
                        "single_email_unavoidable_oversize"
                        if piece_cost(text) > parameters.hard_input_tokens
                        else "split_between_complete_emails"
                    ),
                    "split_part": part,
                    "estimated_tokens": piece_cost(text),
                }
            )
            start = cursor
            part += 1
    packed: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for piece in pieces:
        trial = current + [piece]
        trial_text = "\n\n".join(p["text"] for p in trial)
        trial_cost = piece_cost(trial_text)
        if current and trial_cost > parameters.target_input_tokens:
            packed.append(current)
            current = [piece]
        else:
            current = trial
    if current:
        packed.append(current)
    total = len(packed)
    identity = _sha256_bytes(
        _json_bytes(
            {
                "generation_id": gen["generation_id"],
                "parameters": asdict(parameters),
                "prompt_overhead_tokens": prompt_overhead_tokens,
            }
        )
    )[:16]
    out = Path(out_root) / f"chunks-{gen['generation_id']}-{identity}"
    if out.exists():
        return {
            "ok": False,
            "error": "chunk_generation_already_exists",
            "chunk_dir": str(out),
        }
    out.mkdir(parents=True)
    chunk_rows: list[dict[str, Any]] = []
    all_primary: list[str] = []
    all_seen: list[str] = []
    for index, group in enumerate(packed, 1):
        text = _chunk_prompt(prefix, index=index, total=total, pieces=group)
        path = out / f"CHUNK_{index:03d}_MODEL_PASTE.txt"
        path.write_text(text, encoding="utf-8", newline="\n")
        seen = [item for piece in group for item in piece["cite_as"]]
        primary = [item for piece in group for item in piece["primary_cite_as"]]
        overlap = [item for piece in group for item in piece["overlap_cite_as"]]
        all_seen.extend(seen)
        all_primary.extend(primary)
        chunk_rows.append(
            {
                "chunk_index": index,
                "chunk_id": f"{gen['generation_id']}-chunk-{index:03d}",
                "file": path.name,
                "sha256": _sha256_file(path),
                "estimated_input_tokens": estimate_tokens(text) + prompt_overhead_tokens,
                "bytes": path.stat().st_size,
                "conversation_ids": sorted({p["conversation_id"] for p in group}),
                "email_ids": seen,
                "primary_email_ids": primary,
                "overlap_email_ids": overlap,
                "time_range": {
                    "start": min(p["earliest"] for p in group),
                    "end": max(p["latest"] for p in group),
                },
                "overflow": [p["overflow_status"] for p in group if p["overflow_status"] != "none"],
                "pieces": [
                    {k: v for k, v in p.items() if k != "text"} for p in group
                ],
            }
        )
    canonical = set(gen.get("citation_ids") or [])
    primary_counts = Counter(all_primary)
    seen_counts = Counter(all_seen)
    undeclared_duplicates = sorted(
        cite
        for cite, count in seen_counts.items()
        if count > 1 and cite not in set(overlap_declared)
    )
    audit = {
        "canonical_count": len(canonical),
        "primary_count": len(primary_counts),
        "missing_primary": sorted(canonical - set(primary_counts)),
        "duplicate_primary": sorted(c for c, n in primary_counts.items() if n != 1),
        "declared_overlap_ids": sorted(set(overlap_declared)),
        "undeclared_duplicate_ids": undeclared_duplicates,
    }
    audit["ok"] = not any(
        audit[key]
        for key in ("missing_primary", "duplicate_primary", "undeclared_duplicate_ids")
    )
    manifest = {
        "chunk_manifest_version": 1,
        "created_at": _iso_now(),
        "generation_id": gen["generation_id"],
        "generation_manifest_sha256": _sha256_file(generation_manifest_path),
        "model_paste_sha256": gen["model_paste_sha256"],
        "parameters": asdict(parameters),
        "prompt_overhead_tokens": prompt_overhead_tokens,
        "estimation_method": "ceil_utf8_bytes_div_4",
        "chunk_count": total,
        "chunks": chunk_rows,
        "evidence_audit": audit,
        "models_called": False,
    }
    _write_json(out / "CHUNK_MANIFEST.json", manifest)
    if not audit["ok"]:
        return {"ok": False, "error": "chunk_evidence_audit_failed", "manifest": manifest}
    return {
        "ok": True,
        "chunk_dir": str(out),
        "chunk_count": total,
        "manifest": manifest,
        "models_called": False,
    }


@dataclass(frozen=True)
class RunParameters:
    model: str = DEFAULT_MODEL
    num_ctx: int = 16384
    num_predict: int = DEFAULT_NUM_PREDICT
    temperature: float = 0.1
    top_p: float = 0.9
    seed: int = 42
    hard_timeout_seconds: int = DEFAULT_HARD_TIMEOUT_SECONDS
    stall_warning_seconds: int = DEFAULT_STALL_WARNING_SECONDS
    heartbeat_seconds: int = DEFAULT_HEARTBEAT_SECONDS
    timeout_grace_seconds: int = DEFAULT_TIMEOUT_GRACE_SECONDS
    keep_alive: str = DEFAULT_KEEP_ALIVE
    warm_or_cold: str = "cold"
    prompt_schema_version: str = "trusted-email-review-v1"
    safety_margin_tokens: int = 2048
    quality_contract_path: str | None = None

    def validate(self) -> None:
        if self.num_ctx <= 0 or self.num_predict <= 0:
            raise ValueError("num_ctx and num_predict must be positive")
        if self.hard_timeout_seconds <= 0 or self.heartbeat_seconds <= 0:
            raise ValueError("timeouts and heartbeat must be positive")
        if self.warm_or_cold not in {"warm", "cold"}:
            raise ValueError("warm_or_cold must be warm or cold")


def _model_matches(row: dict[str, Any], model: str) -> bool:
    name = str(row.get("name") or row.get("model") or "")
    return name == model or name == f"{model}:latest" or name.startswith(f"{model}:")


def preflight_benchmark(
    *,
    chunk_dir: Path | str,
    chunk_index: int,
    expected_chunk_hash: str,
    inventory_path: Path | str,
    parameters: RunParameters,
    ollama_base_url: str = "http://127.0.0.1:11434",
    minimum_disk_free_bytes: int = 1_000_000_000,
    allow_active_model: bool = False,
) -> dict[str, Any]:
    """Fail before inference when identity, model, run state, or budget is unsafe."""
    parameters.validate()
    root = Path(chunk_dir)
    manifest_path = root / "CHUNK_MANIFEST.json"
    if not manifest_path.is_file():
        return {"ok": False, "error": "chunk_manifest_missing"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = [
        row
        for row in manifest.get("chunks") or []
        if int(row.get("chunk_index") or 0) == int(chunk_index)
    ]
    if not rows:
        return {"ok": False, "error": "chunk_not_in_manifest"}
    row = rows[0]
    chunk_path = root / str(row["file"])
    actual = _sha256_file(chunk_path)
    if actual != str(expected_chunk_hash).lower() or actual != str(row.get("sha256")).lower():
        return {
            "ok": False,
            "error": "chunk_hash_mismatch",
            "expected": expected_chunk_hash,
            "manifest": row.get("sha256"),
            "actual": actual,
        }
    inventory_file = Path(inventory_path)
    if not inventory_file.is_file():
        return {"ok": False, "error": "inventory_missing"}
    inventory = json.loads(inventory_file.read_text(encoding="utf-8"))
    estimated = int(row.get("estimated_input_tokens") or estimate_tokens(chunk_path.read_text()))
    budget = estimated + parameters.num_predict + parameters.safety_margin_tokens
    if budget > parameters.num_ctx:
        return {
            "ok": False,
            "error": "context_budget_exceeded",
            "estimated_input_tokens": estimated,
            "num_predict": parameters.num_predict,
            "safety_margin_tokens": parameters.safety_margin_tokens,
            "required": budget,
            "num_ctx": parameters.num_ctx,
        }
    free = shutil.disk_usage(root).free
    if free < minimum_disk_free_bytes:
        return {
            "ok": False,
            "error": "insufficient_disk_space",
            "free_bytes": free,
            "required_bytes": minimum_disk_free_bytes,
        }
    ollama = _ollama_inventory(ollama_base_url, parameters.model)
    if not ollama.get("available"):
        return {"ok": False, "error": "ollama_unavailable", "ollama": ollama}
    requested = ollama.get("requested_model")
    if not requested:
        return {
            "ok": False,
            "error": "requested_model_missing",
            "model": parameters.model,
            "installed": [
                r.get("name") or r.get("model") for r in ollama.get("models") or []
            ],
        }
    active = [r for r in ollama.get("running_models") or [] if _model_matches(r, parameters.model)]
    if active and not allow_active_model:
        return {
            "ok": False,
            "error": "stale_active_model",
            "running_models": active,
            "hint": "Stop/verify the prior benchmark before starting another.",
        }
    return {
        "ok": True,
        "chunk": row,
        "chunk_path": str(chunk_path),
        "chunk_sha256": actual,
        "estimated_input_tokens": estimated,
        "resolved_parameters": asdict(parameters),
        "context_budget": {
            "estimated_input_tokens": estimated,
            "reserved_output_tokens": parameters.num_predict,
            "safety_margin_tokens": parameters.safety_margin_tokens,
            "required_tokens": budget,
            "num_ctx": parameters.num_ctx,
            "headroom_tokens": parameters.num_ctx - budget,
        },
        "inventory_sha256": inventory.get("inventory_sha256"),
        "model_metadata": requested,
        "model_show": ollama.get("requested_model_show"),
        "ollama_base_url": ollama_base_url.rstrip("/"),
        "baseline_resources": collect_resource_sample(),
        "disk_free_bytes": free,
    }


def collect_resource_sample() -> dict[str, Any]:
    sample: dict[str, Any] = {"at": _iso_now(), "monotonic_seconds": time.monotonic()}
    try:
        import psutil  # type: ignore

        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        names = {"python": [], "ollama": []}
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                name = str(proc.info.get("name") or "").lower()
                target = "ollama" if "ollama" in name else "python" if "python" in name else ""
                if target:
                    mem = proc.info.get("memory_info")
                    names[target].append(
                        {
                            "pid": proc.info["pid"],
                            "cpu_percent": proc.info.get("cpu_percent"),
                            "rss_bytes": getattr(mem, "rss", None),
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        sample.update(
            {
                "system_available_ram_bytes": vm.available,
                "system_ram_percent": vm.percent,
                "pagefile_used_bytes": swap.used,
                "pagefile_percent": swap.percent,
                "processes": names,
            }
        )
    except ImportError:
        sample["psutil"] = _unavailable("psutil_not_installed")
    sample["nvidia"] = _nvidia_inventory()
    return sample


def _worker_stream_ollama(
    request_path: Path, raw_path: Path, partial_path: Path, url: str
) -> int:
    """Internal worker entry: one streaming Ollama request."""
    request = json.loads(request_path.read_text(encoding="utf-8"))
    req = urllib.request.Request(
        url,
        data=json.dumps(request).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=None) as response, raw_path.open(
        "wb"
    ) as raw, partial_path.open("w", encoding="utf-8", newline="\n") as partial:
        for wire in response:
            raw.write(wire)
            raw.flush()
            decoded = wire.decode("utf-8", errors="replace")
            try:
                event = json.loads(decoded)
            except json.JSONDecodeError:
                continue
            content = str((event.get("message") or {}).get("content") or "")
            if content:
                partial.write(content)
                partial.flush()
                sys.stdout.write(content)
                sys.stdout.flush()
    return 0


def _resource_label(
    sample: dict[str, Any], *, seconds_since_token: float, stall_warning_seconds: int
) -> str:
    ram = sample.get("system_ram_percent")
    page = sample.get("pagefile_percent")
    gpu_rows = ((sample.get("nvidia") or {}).get("gpus") or [])
    vram_pressure = False
    for row in gpu_rows:
        try:
            total = float(row.get("memory.total") or 0)
            free = float(row.get("memory.free") or 0)
            vram_pressure = vram_pressure or (total > 0 and free / total < 0.05)
        except (TypeError, ValueError):
            pass
    if (isinstance(ram, (int, float)) and ram >= 92) or (
        isinstance(page, (int, float)) and page >= 80
    ) or vram_pressure:
        return "MEMORY_PRESSURE"
    model_cpu = sum(
        float(p.get("cpu_percent") or 0)
        for p in ((sample.get("processes") or {}).get("ollama") or [])
    )
    if seconds_since_token >= stall_warning_seconds and model_cpu < 1:
        return "POSSIBLE_STALL"
    return "ACTIVE"


class _Console:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._file = path.open("w", encoding="utf-8", newline="\n")

    def log(self, text: str) -> None:
        line = f"{_iso_now()} {text}"
        print(line, flush=True)
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def _stop_specific_model(base_url: str, model: str) -> dict[str, Any]:
    try:
        response = _post_json(
            f"{base_url.rstrip('/')}/api/generate",
            {"model": model, "keep_alive": 0},
            timeout=20,
        )
        return {"attempted": True, "ok": True, "response": response}
    except Exception as exc:  # noqa: BLE001
        return {"attempted": True, "ok": False, "error": f"{type(exc).__name__}:{exc}"}


def _read_stream_result(raw_path: Path) -> tuple[dict[str, Any] | None, str]:
    final = None
    if not raw_path.is_file():
        return None, ""
    for line in raw_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("done"):
            final = event
    return final, raw_path.read_text(encoding="utf-8", errors="replace")


def _validate_response(
    response: str,
    allowed_ids: set[str],
    quality_contract_path: str | None = None,
) -> dict[str, Any]:
    cited = sorted(set(_EMAIL.findall(response)))
    unsupported = sorted(set(cited) - allowed_ids)
    parsed = None
    schema_pass = False
    try:
        parsed = json.loads(response)
        schema_pass = isinstance(parsed, (dict, list))
    except json.JSONDecodeError:
        pass
    quality_contract: dict[str, Any] | None = None
    coverage: dict[str, Any] = {
        "available": False,
        "score": None,
        "matched_expectations": [],
        "missing_expectations": [],
    }
    if quality_contract_path:
        contract_file = Path(quality_contract_path)
        if contract_file.is_file():
            quality_contract = json.loads(contract_file.read_text(encoding="utf-8"))
            expectations = list(quality_contract.get("expectations") or [])
            matched = []
            missing = []
            lowered = response.casefold()
            for expectation in expectations:
                terms = [str(term).casefold() for term in expectation.get("required_terms") or []]
                expected_ids = set(expectation.get("evidence_ids") or [])
                ok = all(term in lowered for term in terms) and expected_ids.issubset(set(cited))
                (matched if ok else missing).append(str(expectation.get("expectation_id") or ""))
            coverage = {
                "available": True,
                "contract_version": quality_contract.get("contract_version"),
                "contract_sha256": _sha256_file(contract_file),
                "score": len(matched) / len(expectations) if expectations else 1.0,
                "matched_expectations": matched,
                "missing_expectations": missing,
            }
    return {
        "schema_pass": schema_pass,
        "citation_pass": not unsupported,
        "cited_ids": cited,
        "unsupported_citation_ids": unsupported,
        "unsupported_citation_count": len(unsupported),
        "response_sha256": _sha256_bytes(response.encode("utf-8")),
        "reviewer_status": "unreviewed",
        "parsed_json_type": type(parsed).__name__ if parsed is not None else None,
        "coverage": coverage,
        "groundedness_review_required": True,
        "chronology_review_required": True,
    }


def run_supervised_benchmark(
    *,
    preflight: dict[str, Any],
    results_root: Path | str,
    experiment_id: str,
    repetition: int,
    parameters: RunParameters,
    confirm_model_run: bool,
    worker_command_factory: Callable[[Path, Path, Path], list[str]] | None = None,
) -> dict[str, Any]:
    """Run one worker with parent-owned telemetry, timeout, cleanup, and artifacts."""
    if not confirm_model_run:
        return {
            "ok": False,
            "error": "explicit_confirmation_required",
            "hint": "Pass --confirm-model-run for one selected operator-invoked case.",
        }
    if not preflight.get("ok"):
        return {"ok": False, "error": "preflight_not_ok", "preflight": preflight}
    parameters.validate()
    root = Path(results_root)
    root.mkdir(parents=True, exist_ok=True)
    run_id = f"{experiment_id}-r{repetition:02d}-{_utc_stamp()}-{uuid.uuid4().hex[:8]}"
    run_dir = root / run_id
    run_dir.mkdir()
    console = _Console(run_dir / "console.log")
    telemetry_path = run_dir / "telemetry.jsonl"
    request_path = run_dir / "request.json"
    raw_path = run_dir / "raw_api.jsonl"
    partial_path = run_dir / "response.txt"
    validation_path = run_dir / "validation.json"
    started_at = _iso_now()
    started = time.monotonic()
    chunk_text = Path(preflight["chunk_path"]).read_text(encoding="utf-8")
    payload = {
        "model": parameters.model,
        "messages": [
            {"role": "system", "content": "Return the existing trusted-email review JSON schema."},
            {"role": "user", "content": chunk_text},
        ],
        "stream": True,
        "format": "json",
        "options": {
            "num_ctx": parameters.num_ctx,
            "num_predict": parameters.num_predict,
            "temperature": parameters.temperature,
            "top_p": parameters.top_p,
            "seed": parameters.seed,
        },
        "keep_alive": parameters.keep_alive,
    }
    _write_json(request_path, payload)
    console.log(f"INVENTORY/PREFLIGHT complete; run_id={run_id}")
    console.log(
        f"PREPARING REQUEST model={parameters.model} num_ctx={parameters.num_ctx} "
        f"estimated_input={preflight['estimated_input_tokens']}"
    )
    command = (
        worker_command_factory(request_path, raw_path, partial_path)
        if worker_command_factory
        else [
            sys.executable,
            "-m",
            "memorybox",
            "c1t-benchmark-worker",
            "--request",
            str(request_path),
            "--raw",
            str(raw_path),
            "--partial",
            str(partial_path),
            "--url",
            f"{preflight['ollama_base_url']}/api/chat",
        ]
    )
    console.log("MODEL LOADING / AWAITING FIRST TOKEN (percent complete unavailable)")
    worker = subprocess.Popen(command)
    last_size = 0
    last_token_at = started
    stall_warned = False
    status = "RUNNING"
    cleanup: dict[str, Any] = {}
    peaks: dict[str, Any] = {"available_ram_min": None, "pagefile_percent_max": None}
    while worker.poll() is None:
        now = time.monotonic()
        size = partial_path.stat().st_size if partial_path.exists() else 0
        if size > last_size:
            if last_size == 0:
                console.log("GENERATING — first streamed content received")
            last_token_at = now
            last_size = size
        sample = collect_resource_sample()
        available = sample.get("system_available_ram_bytes")
        page_pct = sample.get("pagefile_percent")
        if isinstance(available, int):
            prior = peaks["available_ram_min"]
            peaks["available_ram_min"] = available if prior is None else min(prior, available)
        if isinstance(page_pct, (int, float)):
            prior = peaks["pagefile_percent_max"]
            peaks["pagefile_percent_max"] = page_pct if prior is None else max(prior, page_pct)
        with telemetry_path.open("a", encoding="utf-8", newline="\n") as telemetry:
            telemetry.write(json.dumps(sample, default=str) + "\n")
        since_token = now - last_token_at
        elapsed = now - started
        label = _resource_label(
            sample,
            seconds_since_token=since_token,
            stall_warning_seconds=parameters.stall_warning_seconds,
        )
        if (
            since_token >= parameters.stall_warning_seconds
            and label == "POSSIBLE_STALL"
            and not stall_warned
        ):
            console.log(
                f"POSSIBLE_STALL warning: no output for {int(since_token)}s and low model activity; continuing"
            )
            stall_warned = True
        if elapsed >= parameters.hard_timeout_seconds:
            status = "TIMED_OUT"
            console.log(
                f"TIMED OUT at {int(elapsed)}s; terminating only worker pid={worker.pid}"
            )
            worker.terminate()
            try:
                worker.wait(timeout=parameters.timeout_grace_seconds)
                cleanup["worker_terminated"] = True
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=10)
                cleanup["worker_killed"] = True
            time.sleep(min(parameters.timeout_grace_seconds, 2))
            try:
                active = _get_json(
                    f"{preflight['ollama_base_url']}/api/ps", timeout=5
                ).get("models") or []
            except Exception as exc:  # noqa: BLE001
                active = []
                cleanup["post_timeout_ps_error"] = f"{type(exc).__name__}:{exc}"
            if any(_model_matches(r, parameters.model) for r in active):
                cleanup["model_stop"] = _stop_specific_model(
                    preflight["ollama_base_url"], parameters.model
                )
            break
        console.log(
            f"HEARTBEAT {label} elapsed={int(elapsed)}s since_last_token={int(since_token)}s "
            f"streamed_bytes={size} ram_available={available} pagefile_percent={page_pct}; "
            "prompt-eval percent unavailable"
        )
        time.sleep(parameters.heartbeat_seconds)
    if status == "RUNNING":
        status = "COMPLETE" if worker.returncode == 0 else "FAILED"
    final_event, raw_text = _read_stream_result(raw_path)
    response = partial_path.read_text(encoding="utf-8") if partial_path.exists() else ""
    console.log("VALIDATING response and citations")
    allowed_ids = set(preflight["chunk"].get("email_ids") or [])
    validation = _validate_response(
        response, allowed_ids, parameters.quality_contract_path
    )
    _write_json(validation_path, validation)
    ended_at = _iso_now()
    elapsed = time.monotonic() - started
    console.log(f"SAVING status={status} response_bytes={len(response.encode('utf-8'))}")
    try:
        post_ps = _get_json(f"{preflight['ollama_base_url']}/api/ps", timeout=5)
        readiness = {"ok": True, "ollama_api": True, "running_models": post_ps.get("models") or []}
    except Exception as exc:  # noqa: BLE001
        readiness = {"ok": False, "ollama_api": False, "error": f"{type(exc).__name__}:{exc}"}
    usage = final_event or {}
    prompt_count = usage.get("prompt_eval_count")
    eval_count = usage.get("eval_count")
    prompt_duration = usage.get("prompt_eval_duration")
    eval_duration = usage.get("eval_duration")
    record = {
        "run_record_version": 1,
        "run_id": run_id,
        "experiment_id": experiment_id,
        "repetition": repetition,
        "started_at": started_at,
        "ended_at": ended_at,
        "status": status,
        "host_inventory_hash": preflight.get("inventory_sha256"),
        "evidence": {
            "generation_id": preflight["chunk"]["chunk_id"].rsplit("-chunk-", 1)[0],
            "chunk_id": preflight["chunk"]["chunk_id"],
            "chunk_hash": preflight["chunk_sha256"],
            "conversations": preflight["chunk"].get("conversation_ids"),
            "emails": preflight["chunk"].get("email_ids"),
            "time_range": preflight["chunk"].get("time_range"),
        },
        "model": {
            **asdict(parameters),
            "metadata": preflight.get("model_metadata"),
        },
        "tokens": {
            "estimated_input": preflight.get("estimated_input_tokens"),
            "prompt_eval_count": prompt_count,
            "prompt_eval_cached_count": usage.get("prompt_eval_cached_count"),
            "eval_count": eval_count,
        },
        "timing": {
            "total_wall_seconds": elapsed,
            "total_duration_ns": usage.get("total_duration"),
            "load_duration_ns": usage.get("load_duration"),
            "prompt_eval_duration_ns": prompt_duration,
            "eval_duration_ns": eval_duration,
        },
        "rates": {
            "prompt_eval_tokens_per_second": (
                float(prompt_count) / (float(prompt_duration) / 1e9)
                if prompt_count and prompt_duration
                else None
            ),
            "generation_tokens_per_second": (
                float(eval_count) / (float(eval_duration) / 1e9)
                if eval_count and eval_duration
                else None
            ),
        },
        "resources": {
            "baseline": preflight.get("baseline_resources"),
            "peaks": peaks,
        },
        "quality": validation,
        "recovery": {
            "stall_warning": stall_warned,
            "cleanup": cleanup,
            "post_run_readiness": readiness,
        },
        "raw_api_bytes": len(raw_text.encode("utf-8")),
    }
    console.log(
        f"{status}; response={partial_path}; raw={raw_path}; validation={validation_path}"
    )
    console.close()
    artifacts = {}
    for label, path in {
        "response": partial_path,
        "raw_json": raw_path,
        "console_log": run_dir / "console.log",
        "request": request_path,
        "validation": validation_path,
        "telemetry": telemetry_path,
    }.items():
        if path.exists():
            artifacts[label] = {
                "path": path.name,
                "sha256": _sha256_file(path),
            }
    record["artifacts"] = artifacts
    _write_json(run_dir / "run_record.json", record)
    write_results_index(root)
    return {"ok": status == "COMPLETE", "run_dir": str(run_dir), "record": record}


def write_results_index(results_root: Path | str) -> dict[str, Any]:
    """Write authoritative CSV plus XLSX comparison surface with relative links."""
    root = Path(results_root)
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(root.glob("*/run_record.json")):
        try:
            records.append((path.parent, json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError:
            continue
    fields = [
        "run_id",
        "experiment_id",
        "repetition",
        "status",
        "model",
        "num_ctx",
        "estimated_input",
        "prompt_eval_count",
        "eval_count",
        "total_wall_seconds",
        "schema_pass",
        "citation_pass",
        "response",
        "raw_json",
        "console_log",
        "request",
        "validation",
        "response_sha256",
        "raw_json_sha256",
        "console_log_sha256",
        "request_sha256",
        "validation_sha256",
        "response_preview",
    ]
    csv_path = root / "C1T_RESULTS.csv"
    rows: list[dict[str, Any]] = []
    for run_dir, record in records:
        artifacts = record.get("artifacts") or {}
        model = record.get("model") or {}
        tokens = record.get("tokens") or {}
        quality = record.get("quality") or {}
        rows.append(
            {
                "run_id": record.get("run_id"),
                "experiment_id": record.get("experiment_id"),
                "repetition": record.get("repetition"),
                "status": record.get("status"),
                "model": model.get("model"),
                "num_ctx": model.get("num_ctx"),
                "estimated_input": tokens.get("estimated_input"),
                "prompt_eval_count": tokens.get("prompt_eval_count"),
                "eval_count": tokens.get("eval_count"),
                "total_wall_seconds": (record.get("timing") or {}).get("total_wall_seconds"),
                "schema_pass": quality.get("schema_pass"),
                "citation_pass": quality.get("citation_pass"),
                **{
                    key: str(Path(run_dir.name) / str((artifacts.get(key) or {}).get("path") or ""))
                    for key in ("response", "raw_json", "console_log", "request", "validation")
                },
                **{
                    f"{key}_sha256": (artifacts.get(key) or {}).get("sha256")
                    for key in ("response", "raw_json", "console_log", "request", "validation")
                },
                "response_preview": (
                    (run_dir / str((artifacts.get("response") or {}).get("path"))).read_text(
                        encoding="utf-8", errors="replace"
                    )[:500]
                    if (artifacts.get("response") or {}).get("path")
                    else ""
                ),
            }
        )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    xlsx_path = root / "C1T_RESULTS.xlsx"
    try:
        from openpyxl import Workbook  # type: ignore

        book = Workbook()
        sheet = book.active
        sheet.title = "Runs"
        headers = fields + [
            "Open response",
            "Open raw JSON",
            "Open console log",
            "Open request",
            "Open validation",
        ]
        sheet.append(headers)
        link_map = {
            "Open response": "response",
            "Open raw JSON": "raw_json",
            "Open console log": "console_log",
            "Open request": "request",
            "Open validation": "validation",
        }
        for row_index, row in enumerate(rows, 2):
            sheet.append([row.get(field) for field in fields] + [None] * len(link_map))
            for column_index, (label, key) in enumerate(link_map.items(), len(fields) + 1):
                relative = str(row.get(key) or "").replace("\\", "/")
                cell = sheet.cell(row=row_index, column=column_index)
                cell.value = f'=HYPERLINK("{relative}","{label}")'
                cell.style = "Hyperlink"
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        book.save(xlsx_path)
        xlsx_status = {"available": True, "path": str(xlsx_path)}
    except ImportError:
        xlsx_status = _unavailable("openpyxl_not_installed")
    return {
        "ok": True,
        "run_count": len(rows),
        "csv_path": str(csv_path),
        "xlsx": xlsx_status,
    }


def run_experiment_matrix(
    *,
    matrix_path: Path | str,
    results_root: Path | str,
    chunk_dir: Path | str,
    inventory_path: Path | str,
    selected_cases: set[str],
    confirm_model_run: bool,
    ollama_base_url: str = "http://127.0.0.1:11434",
) -> dict[str, Any]:
    """Sequential runner; never starts cases without explicit confirmation."""
    matrix = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    cases = [c for c in matrix.get("cases") or [] if str(c.get("case_id")) in selected_cases]
    if not cases:
        return {"ok": False, "error": "no_selected_cases"}
    if not confirm_model_run:
        return {
            "ok": False,
            "error": "explicit_confirmation_required",
            "selected_cases": [c.get("case_id") for c in cases],
        }
    outcomes = []
    for case in cases:
        repetitions = int(case.get("repetitions") or 1)
        for repetition in range(1, repetitions + 1):
            experiment_id = str(case["case_id"])
            existing = list(
                Path(results_root).glob(f"{experiment_id}-r{repetition:02d}-*/run_record.json")
            )
            completed = [
                path
                for path in existing
                if json.loads(path.read_text(encoding="utf-8")).get("status") == "COMPLETE"
            ]
            if completed:
                outcomes.append(
                    {
                        "case_id": experiment_id,
                        "repetition": repetition,
                        "status": "SKIPPED_EXISTING",
                    }
                )
                continue
            params = RunParameters(**dict(case["run_parameters"]))
            case_chunk_dir = Path(str(case.get("chunk_dir") or chunk_dir))
            manifest = json.loads(
                (case_chunk_dir / "CHUNK_MANIFEST.json").read_text(encoding="utf-8")
            )
            chunk_index = int(case["chunk_index"])
            row = next(
                r for r in manifest["chunks"] if int(r["chunk_index"]) == chunk_index
            )
            preflight = preflight_benchmark(
                chunk_dir=case_chunk_dir,
                chunk_index=chunk_index,
                expected_chunk_hash=row["sha256"],
                inventory_path=inventory_path,
                parameters=params,
                ollama_base_url=ollama_base_url,
                allow_active_model=params.warm_or_cold == "warm",
            )
            if not preflight.get("ok"):
                outcomes.append(
                    {
                        "case_id": experiment_id,
                        "repetition": repetition,
                        "status": "PREFLIGHT_FAILED",
                        "detail": preflight,
                    }
                )
                return {"ok": False, "outcomes": outcomes, "stopped": True}
            outcome = run_supervised_benchmark(
                preflight=preflight,
                results_root=results_root,
                experiment_id=experiment_id,
                repetition=repetition,
                parameters=params,
                confirm_model_run=True,
            )
            outcomes.append(outcome)
            if not outcome.get("ok"):
                return {"ok": False, "outcomes": outcomes, "stopped": True}
            peaks = (outcome["record"].get("resources") or {}).get("peaks") or {}
            if float(peaks.get("pagefile_percent_max") or 0) >= float(
                case.get("stop_pagefile_percent") or 80
            ):
                return {
                    "ok": False,
                    "outcomes": outcomes,
                    "stopped": True,
                    "reason": "pressure_stop_gate",
                }
    return {"ok": True, "outcomes": outcomes, "execution_concurrency": 1}


def write_default_matrix(path: Path | str) -> dict[str, Any]:
    """Write approved A-F ladder. This does not execute it."""
    cases = []
    for case_id, chunk_index, ctx in (
        ("A", 1, 16384),
        ("B", 1, 32768),
        ("C", 2, 32768),
        ("D", 3, 32768),
        ("E", 4, 65536),
        ("F", 5, 65536),
    ):
        cases.append(
            {
                "case_id": case_id,
                "chunk_index": chunk_index,
                "repetitions": 1,
                "run_parameters": asdict(
                    RunParameters(num_ctx=ctx, warm_or_cold="cold")
                ),
                "stop_pagefile_percent": 80,
            }
        )
    matrix = {
        "matrix_version": 1,
        "execution_concurrency": 1,
        "temperature_locked": 0.1,
        "cases": cases,
        "note": "Operator must map chunk indices to approximately 8K/8K/16K/24K/40K/56K evidence after inventory.",
    }
    _write_json(Path(path), matrix)
    return matrix

