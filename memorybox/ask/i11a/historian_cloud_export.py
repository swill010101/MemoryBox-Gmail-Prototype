"""Export frozen ASK_RELATIVE request bytes for clean cloud/GPT benchmarks.

Uses ask_relative_request_from_prepared() — the same construction path as
historian-fixture-run. Does not include answers, narrator input, or archive.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from memorybox.ask.i11a.historian_fixture import load_fixture
from memorybox.ask.i11a.historian_prepared import ask_relative_request_from_prepared

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OUT_DIR = _REPO_ROOT / "docs" / "test-output" / "cloud-benchmark"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _estimate_tokens(system: str, user: str) -> int:
    return max(1, (len(system.encode("utf-8")) + len(user.encode("utf-8"))) // 4)


def export_cloud_request(
    fixture_path: Path | str,
    *,
    out_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Write CLOUDREQ_* files from a frozen HISTFIX fixture. No model calls."""
    path = Path(fixture_path)
    fixture = load_fixture(path)
    prepared = fixture.get("prepared") or {}
    case_id = str(fixture.get("case_id") or "unknown")
    ask = str(fixture.get("ask") or prepared.get("ask") or "")
    fixture_sha = str(fixture.get("input_sha256") or "")
    source_commit = str(fixture.get("source_commit") or "")

    req = ask_relative_request_from_prepared(prepared)
    system = str(req["system"])
    user_message = str(req["user_message"])
    system_bytes = int(req["system_bytes"])
    user_bytes = int(req["user_bytes"])
    request_bytes = int(req["request_bytes"])

    out = Path(out_dir) if out_dir else _DEFAULT_OUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    system_name = f"CLOUDREQ_{case_id}_system.txt"
    user_name = f"CLOUDREQ_{case_id}_user.txt"
    paste_name = f"CLOUDREQ_{case_id}_paste.txt"
    manifest_name = f"CLOUDREQ_{case_id}_manifest.json"

    system_path = out / system_name
    user_path = out / user_name
    paste_path = out / paste_name
    manifest_path = out / manifest_name

    # Exact bytes only — no trailing newline unless present in the frozen messages.
    system_path.write_bytes(system.encode("utf-8"))
    user_path.write_bytes(user_message.encode("utf-8"))

    paste = (
        "===== SYSTEM MESSAGE =====\n"
        "\n"
        f"{system}\n"
        "\n"
        "===== USER MESSAGE =====\n"
        "\n"
        f"{user_message}"
    )
    paste_path.write_bytes(paste.encode("utf-8"))

    system_sha = _sha256_text(system)
    user_sha = _sha256_text(user_message)

    manifest = {
        "case_id": case_id,
        "ask": ask,
        "source_fixture_filename": path.name,
        "fixture_sha256": fixture_sha,
        "source_commit": source_commit,
        "system_bytes": system_bytes,
        "user_bytes": user_bytes,
        "total_request_bytes": request_bytes,
        "estimated_input_tokens": int(req.get("estimated_input_tokens") or _estimate_tokens(system, user_message)),
        "temperature": req.get("temperature"),
        "json_mode": bool(req.get("json_mode", True)),
        "system_sha256": system_sha,
        "user_sha256": user_sha,
        "system_file": system_name,
        "user_file": user_name,
        "paste_file": paste_name,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "ok": True,
        "case_id": case_id,
        "out_dir": str(out),
        "files": {
            "system": {
                "filename": system_name,
                "path": str(system_path),
                "bytes": system_path.stat().st_size,
                "sha256": system_sha,
            },
            "user": {
                "filename": user_name,
                "path": str(user_path),
                "bytes": user_path.stat().st_size,
                "sha256": user_sha,
            },
            "paste": {
                "filename": paste_name,
                "path": str(paste_path),
                "bytes": paste_path.stat().st_size,
            },
            "manifest": {
                "filename": manifest_name,
                "path": str(manifest_path),
                "bytes": manifest_path.stat().st_size,
            },
        },
        "manifest": manifest,
        "matches_request_construction": (
            system_path.stat().st_size == system_bytes
            and user_path.stat().st_size == user_bytes
        ),
    }


def export_cloud_request_cli(
    *,
    fixture: str,
    out_dir: Path | str | None = None,
) -> dict[str, Any]:
    if not fixture:
        raise ValueError("--fixture is required")
    return export_cloud_request(fixture, out_dir=out_dir)
