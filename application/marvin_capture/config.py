"""Configuration for Marvin Capture.

Loads config/marvin_capture.json (or MARVIN_CAPTURE_CONFIG path) with
sensible defaults under the MemoryBox runtime directories (gitignored).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG: dict[str, Any] = {
    "gmail": {
        "credentials_file": str(ROOT / "config" / "gmail_credentials.json"),
        "token_file": str(ROOT / "config" / "gmail_token.json"),
        "user_email": "",
        "processed_label": "MB/Processed",
        "scopes": [
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.send",
        ],
    },
    "polling_interval_seconds": 300,
    "sqlite_path": str(ROOT / "database" / "marvin_capture.db"),
    "attachment_storage": str(ROOT / "attachments" / "marvin_capture"),
    "raw_email_storage": str(ROOT / "attachments" / "marvin_capture" / "raw"),
    "whisper": {
        "endpoint": "http://127.0.0.1:9000/v1/audio/transcriptions",
        "api_key": "",
        "model": "whisper-1",
        "timeout_seconds": 300,
    },
    "schedule": {
        "daily_journal": {
            "enabled": True,
            "hour": 18,
            "minute": 0,
            "timezone": "local",
            "subject_template": "[MB-JRN] What happened today?",
            "body": (
                "What happened today?\n\n"
                "Reply naturally. Attach photos, documents, or voice memos if you want.\n"
                "No special formatting required."
            ),
        }
    },
    "review_ui": {
        "host": "127.0.0.1",
        "port": 8790,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def config_path() -> Path:
    env = os.environ.get("MARVIN_CAPTURE_CONFIG")
    if env:
        return Path(env)
    return ROOT / "config" / "marvin_capture.json"


def load_config() -> dict[str, Any]:
    path = config_path()
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        cfg = _deep_merge(DEFAULT_CONFIG, data)
    else:
        cfg = dict(DEFAULT_CONFIG)
    return _resolve_paths(cfg)


def _resolve_paths(cfg: dict[str, Any]) -> dict[str, Any]:
    """Make relative paths stable against repo root, not the caller's cwd."""

    def fix(value: str) -> str:
        p = Path(value)
        if p.is_absolute():
            return str(p)
        return str((ROOT / p).resolve())

    cfg = dict(cfg)
    for key in ("sqlite_path", "attachment_storage", "raw_email_storage"):
        if cfg.get(key):
            cfg[key] = fix(cfg[key])
    gmail = dict(cfg.get("gmail") or {})
    for key in ("credentials_file", "token_file"):
        if gmail.get(key):
            gmail[key] = fix(gmail[key])
    cfg["gmail"] = gmail
    return cfg


def ensure_runtime_dirs(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    Path(cfg["sqlite_path"]).parent.mkdir(parents=True, exist_ok=True)
    Path(cfg["attachment_storage"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["raw_email_storage"]).mkdir(parents=True, exist_ok=True)
    return cfg
