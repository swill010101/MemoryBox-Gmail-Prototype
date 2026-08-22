"""Whisper transcription client (OpenAI-compatible endpoint)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from . import db as store

log = logging.getLogger("marvin.whisper")


def transcribe_file(
    path: Path,
    *,
    endpoint: str,
    api_key: str = "",
    model: str = "whisper-1",
    timeout_seconds: float = 300,
) -> str:
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    with path.open("rb") as fh:
        files = {"file": (path.name, fh, "application/octet-stream")}
        data = {"model": model}
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(endpoint, headers=headers, data=data, files=files)
            resp.raise_for_status()
            payload = resp.json()
            if isinstance(payload, dict):
                text = payload.get("text")
                if text is not None:
                    return str(text)
            return str(payload)


def process_pending_transcriptions(
    conn: Any,
    whisper_cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """Transcribe pending audio; originals remain on disk untouched."""
    results: list[dict[str, Any]] = []
    pending = store.list_pending_transcriptions(conn)
    for att in pending:
        path = Path(att["storage_path"])
        if not path.is_file():
            store.update_transcript(conn, att["id"], transcript=None, status="error")
            results.append({"id": att["id"], "status": "error", "error": "missing file"})
            continue
        try:
            text = transcribe_file(
                path,
                endpoint=whisper_cfg["endpoint"],
                api_key=whisper_cfg.get("api_key") or "",
                model=whisper_cfg.get("model") or "whisper-1",
                timeout_seconds=float(whisper_cfg.get("timeout_seconds") or 300),
            )
            # Store transcript beside original — never replace audio
            store.update_transcript(conn, att["id"], transcript=text, status="done")
            promoted = store.maybe_promote_transcript_to_answer(conn, att["id"], text)
            results.append(
                {
                    "id": att["id"],
                    "status": "done",
                    "chars": len(text),
                    "promoted_to_answer": promoted,
                }
            )
            log.info(
                "transcribed attachment %s (%s chars)%s",
                att["id"],
                len(text),
                " → answer text" if promoted else "",
            )
        except Exception as exc:  # noqa: BLE001 — keep queue healthy
            store.update_transcript(conn, att["id"], transcript=None, status="error")
            results.append({"id": att["id"], "status": "error", "error": str(exc)})
            log.warning("transcription failed for %s: %s", att["id"], exc)
    return results
