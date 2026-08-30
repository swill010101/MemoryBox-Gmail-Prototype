#!/usr/bin/env python3
"""Emit cmd.exe SET lines from config/*.env (startmb files cmd cannot see).

Strips UTF-8 BOM, CR, and surrounding quotes so MEMORYBOX_CLOUD_LLM_* from
PowerShell-quoted app.env actually reach the trusted-identity gate.
Does not clobber variables already set in the environment.
Does not print values to stderr.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

KEYS = (
    "MEMORYBOX_DATABASE_URL",
    "MEMORYBOX_QDRANT_URL",
    "MEMORYBOX_OLLAMA_BASE_URL",
    "MEMORYBOX_CLOUD_LLM_BASE_URL",
    "MEMORYBOX_CLOUD_LLM_API_KEY",
    "MEMORYBOX_CLOUD_LLM_MODEL",
    "MEMORYBOX_CLOUD_LLM_MAX_TOKENS",
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_RELATIVE = (
    Path("config") / "memorybox_app.env",
    Path("config") / "video_worker.env",
    Path("config") / "memorybox_sources.env",
)


def env_files() -> list[Path]:
    """Repo-root files first, then cwd — cmd may start in either MemoryBox path."""
    seen: set[Path] = set()
    out: list[Path] = []
    for rel in _ENV_RELATIVE:
        for base in (_REPO_ROOT, Path.cwd()):
            path = (base / rel).resolve()
            if path in seen:
                continue
            seen.add(path)
            out.append(path)
    return out


def parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    for raw in text.splitlines():
        line = raw.strip().strip("\r")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("\r")
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {"'", '"'}:
            val = val[1:-1]
        if key:
            out[key] = val
    return out


def merged_unset_keys() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in env_files():
        merged.update(parse_env_file(path))
    emit: dict[str, str] = {}
    for key in KEYS:
        if (os.environ.get(key) or "").strip():
            continue
        val = merged.get(key) or ""
        if val:
            emit[key] = val
    return emit


def apply_unset_keys_to_environ() -> dict[str, str]:
    """Load FlightSim app.env into this process (cmd `for /f` set lines can miss)."""
    emit = merged_unset_keys()
    for key, val in emit.items():
        os.environ[key] = val
    return emit


def cmd_set_lines(values: dict[str, str]) -> list[str]:
    lines: list[str] = []
    for key, val in values.items():
        # set "KEY=value" keeps spaces and extra '=' in the value.
        safe = val.replace("%", "%%")
        lines.append(f'set "{key}={safe}"')
    return lines


def main(argv: list[str] | None = None) -> int:
    _ = argv
    for line in cmd_set_lines(merged_unset_keys()):
        sys.stdout.write(line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
