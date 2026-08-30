"""FlightSim Phase 2 readiness before year-fair freeze / Gemma / Sol.

Writes PHASE2_PREFLIGHT.json so PR #77 sees Ollama + cloud Sol state even
when freeze or models later hang. Does not skip freeze.
"""
from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.trusted_full_evidence_v2 import (
    ESTABLISHED_GEMMA_MODEL,
    apply_flightsim_app_env,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OUT = _REPO_ROOT / "docs" / "test-output" / "trusted-full-evidence-v2"


def _ollama_status() -> dict[str, Any]:
    from memorybox.config import OLLAMA_AUTODETECT_URLS, settings
    from memorybox.providers.llm._ollama_http import ollama_has_model, ollama_reachable

    base = (os.environ.get("MEMORYBOX_OLLAMA_BASE_URL") or settings.ollama_base_url or "").strip()
    if not base:
        for url in OLLAMA_AUTODETECT_URLS:
            if ollama_reachable(url):
                base = url
                break
    reachable = bool(base) and ollama_reachable(base)
    has_gemma = bool(reachable and ollama_has_model(base, ESTABLISHED_GEMMA_MODEL))
    return {
        "base_url_set": bool(base),
        "reachable": reachable,
        "has_gemma4_26b": has_gemma,
        "model": ESTABLISHED_GEMMA_MODEL,
    }


def _cloud_status() -> dict[str, Any]:
    model = (os.environ.get("MEMORYBOX_CLOUD_LLM_MODEL") or "").strip()
    return {
        "base_url_set": bool((os.environ.get("MEMORYBOX_CLOUD_LLM_BASE_URL") or "").strip()),
        "api_key_set": bool((os.environ.get("MEMORYBOX_CLOUD_LLM_API_KEY") or "").strip()),
        "model": model or None,
        "max_tokens": (os.environ.get("MEMORYBOX_CLOUD_LLM_MAX_TOKENS") or "").strip() or "8192",
        "configured": bool(
            (os.environ.get("MEMORYBOX_CLOUD_LLM_BASE_URL") or "").strip()
            and (os.environ.get("MEMORYBOX_CLOUD_LLM_API_KEY") or "").strip()
            and model
        ),
    }


def run_phase2_preflight(*, out_dir: Path | str | None = None) -> dict[str, Any]:
    apply_flightsim_app_env()
    out = Path(out_dir) if out_dir else _DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    ollama = _ollama_status()
    cloud = _cloud_status()
    payload: dict[str, Any] = {
        "ok": bool(ollama.get("has_gemma4_26b") and cloud.get("configured")),
        "built_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "hostname": socket.gethostname(),
        "p1_runtime_host": (os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") or "").strip(),
        "allow_dev_defaults": (os.environ.get("MEMORYBOX_ALLOW_DEV_DEFAULTS") or "").strip(),
        "ollama": ollama,
        "cloud_sol": cloud,
        "note": (
            "Preflight only. Freeze still runs. "
            "Pull gemma4:26b and set MEMORYBOX_CLOUD_LLM_* if ok is false."
        ),
    }
    path = out / "PHASE2_PREFLIGHT.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    payload["path"] = str(path)
    return payload
