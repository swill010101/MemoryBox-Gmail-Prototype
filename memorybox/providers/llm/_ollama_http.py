"""Ollama HTTP helpers (in-package; no POC path dependency)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def _post_json(url: str, payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except TimeoutError as exc:
        raise TimeoutError(f"timed out after {timeout}s") from exc
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc) or exc).lower()
        if "timed out" in reason or "timeout" in reason:
            raise TimeoutError(f"timed out after {timeout}s") from exc
        raise


def ollama_embed(
    base_url: str, model: str, text: str, *, query: bool = False, timeout: int = 120
) -> list[float]:
    prefix = "search_query: " if query else "search_document: "
    prompt = text if text.startswith("search_") else prefix + text
    prompt = "".join(ch if (ord(ch) >= 32 or ch in "\n\t") else " " for ch in prompt)[
        :5000
    ]
    base = base_url.rstrip("/")

    # Newer Ollama: POST /api/embed  {"model","input"}
    try:
        data = _post_json(
            f"{base}/api/embed",
            {"model": model, "input": prompt},
            timeout=timeout,
        )
        emb = data.get("embeddings") or data.get("embedding")
        if isinstance(emb, list) and emb and isinstance(emb[0], list):
            emb = emb[0]
        if emb:
            return list(emb)
    except urllib.error.HTTPError as e:
        if e.code not in (404, 405):
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ollama embed HTTP {e.code}: {body[:400]}") from e
    except Exception:
        pass

    # Older Ollama: POST /api/embeddings  {"model","prompt"}
    try:
        data = _post_json(
            f"{base}/api/embeddings",
            {"model": model, "prompt": prompt},
            timeout=timeout,
        )
        emb = data.get("embedding")
        if emb:
            return list(emb)
        raise RuntimeError("empty embedding")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ollama embeddings HTTP {e.code}: {body[:400]}") from e


def ollama_chat(
    base_url: str,
    model: str,
    system: str,
    user: str,
    *,
    format_json: bool = False,
    temperature: float = 0.1,
    timeout: int = 600,
    keep_alive: str = "30m",
) -> tuple[str, dict[str, Any]]:
    payload: dict[str, Any] = {
        "model": model,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"temperature": temperature},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if format_json:
        payload["format"] = "json"
    try:
        data = _post_json(
            f"{base_url.rstrip('/')}/api/chat", payload, timeout=timeout
        )
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ollama chat HTTP {e.code}: {body[:400]}") from e
    msg = data.get("message") or {}
    content = msg.get("content")
    if not content:
        raise RuntimeError(f"empty chat response: {str(data)[:300]}")
    usage = {
        "total_duration": data.get("total_duration"),
        "load_duration": data.get("load_duration"),
        "prompt_eval_count": data.get("prompt_eval_count"),
        "prompt_eval_duration": data.get("prompt_eval_duration"),
        "eval_count": data.get("eval_count"),
        "eval_duration": data.get("eval_duration"),
        "timeout_seconds": timeout,
        "keep_alive": keep_alive,
        "options": {"temperature": temperature},
        "num_ctx": (data.get("options") or {}).get("num_ctx")
        if isinstance(data.get("options"), dict)
        else None,
        "num_ctx_note": "Chat options set temperature only; num_ctx is the model default",
        "done_reason": data.get("done_reason"),
    }
    return str(content), usage


def ollama_reachable(base_url: str, timeout: float = 1.5) -> bool:
    """True when /api/tags answers. Used so Ask can find a local daemon without env."""
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout) as resp:
            return 200 <= int(getattr(resp, "status", 200) or 200) < 300
    except Exception:
        return False


def ollama_tags(base_url: str, timeout: int = 15) -> dict[str, Any]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout) as resp:
        return json.load(resp)
