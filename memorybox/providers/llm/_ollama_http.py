"""Ollama HTTP helpers (in-package; no POC path dependency)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def ollama_embed(
    base_url: str, model: str, text: str, *, query: bool = False, timeout: int = 120
) -> list[float]:
    prefix = "search_query: " if query else "search_document: "
    prompt = text if text.startswith("search_") else prefix + text
    prompt = "".join(ch if (ord(ch) >= 32 or ch in "\n\t") else " " for ch in prompt)[
        :5000
    ]
    payload = json.dumps({"model": model, "prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    emb = data.get("embedding")
    if not emb:
        raise RuntimeError("empty embedding")
    return emb


def ollama_chat(
    base_url: str,
    model: str,
    system: str,
    user: str,
    *,
    format_json: bool = False,
    temperature: float = 0.1,
    timeout: int = 300,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "stream": False,
        "options": {"temperature": temperature},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if format_json:
        payload["format"] = "json"
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ollama chat HTTP {e.code}: {body[:400]}") from e
    msg = data.get("message") or {}
    content = msg.get("content")
    if not content:
        raise RuntimeError(f"empty chat response: {str(data)[:300]}")
    return content


def ollama_tags(base_url: str, timeout: int = 15) -> dict[str, Any]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout) as resp:
        return json.load(resp)
