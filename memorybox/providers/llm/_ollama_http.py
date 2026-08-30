"""Ollama HTTP helpers (in-package; no POC path dependency)."""
from __future__ import annotations

import json
import re
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
    num_ctx: int | None = None,
) -> tuple[str, dict[str, Any]]:
    options: dict[str, Any] = {"temperature": temperature}
    if num_ctx is not None and int(num_ctx) > 0:
        options["num_ctx"] = int(num_ctx)
    payload: dict[str, Any] = {
        "model": model,
        "stream": False,
        "keep_alive": keep_alive,
        "options": options,
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
        "options": dict(options),
        "num_ctx": options.get("num_ctx"),
        "num_ctx_note": (
            "FEV2/historian set options.num_ctx so a large paste is not tail-truncated"
            if options.get("num_ctx")
            else "Chat options set temperature only; num_ctx is the model default"
        ),
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


def ollama_show(base_url: str, model: str, *, timeout: int = 15) -> dict[str, Any]:
    """Model metadata from /api/show. Does not generate tokens."""
    return _post_json(
        f"{base_url.rstrip('/')}/api/show",
        {"name": model},
        timeout=timeout,
    )


def ollama_context_length(show: dict[str, Any] | None) -> int | None:
    """Best-effort context window from /api/show. None if unknown."""
    if not isinstance(show, dict):
        return None
    info = show.get("model_info") or show.get("details") or {}
    if isinstance(info, dict):
        for key in (
            "llama.context_length",
            "gemma.context_length",
            "general.context_length",
            "context_length",
        ):
            raw = info.get(key)
            if raw is not None and str(raw).isdigit():
                return int(raw)
        for key, raw in info.items():
            if "context_length" in str(key).lower() and str(raw).isdigit():
                return int(raw)
    params = str(show.get("parameters") or "")
    match = re.search(r"num_ctx\s+(\d+)", params, re.I)
    if match:
        return int(match.group(1))
    return None


def ollama_tokenize(
    base_url: str, model: str, text: str, *, timeout: int = 120
) -> list[int] | None:
    """Token ids from /api/tokenize when the daemon supports it. Not a chat."""
    try:
        data = _post_json(
            f"{base_url.rstrip('/')}/api/tokenize",
            {"model": model, "prompt": text},
            timeout=timeout,
        )
    except Exception:
        return None
    tokens = data.get("tokens")
    if isinstance(tokens, list):
        return tokens
    return None


def ollama_has_model(base_url: str, model: str, *, timeout: float = 8.0) -> bool:
    """True when /api/tags lists this model (e.g. gemma4:26b or gemma4:26b:latest)."""
    want = (model or "").strip()
    if not want or not ollama_reachable(base_url, timeout=min(timeout, 2.5)):
        return False
    try:
        data = ollama_tags(base_url, timeout=int(max(timeout, 2)))
    except Exception:
        return False
    names: list[str] = []
    for row in data.get("models") or []:
        if isinstance(row, dict):
            names.append(str(row.get("name") or row.get("model") or "").strip())
        else:
            names.append(str(row).strip())
    norms = [n.split("@")[0].strip() for n in names if n and n.strip()]
    return want in norms or any(
        n == f"{want}:latest" or n.startswith(f"{want}:") for n in norms
    )
