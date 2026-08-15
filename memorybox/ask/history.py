"""Last-100 Ask command history — survives serve shutdown (owner machine file)."""
from __future__ import annotations

import json
import os
from pathlib import Path

HISTORY_MAX = 100


def history_path() -> Path:
    raw = (os.environ.get("MEMORYBOX_ASK_HISTORY_PATH") or "").strip()
    if raw:
        return Path(raw)
    home = (
        os.environ.get("MEMORYBOX_HOME")
        or os.environ.get("MEMORYBOX_DATA_DIR")
        or ""
    ).strip()
    if home:
        return Path(home) / ".memorybox_ask_history.json"
    # Repo/install root — not process cwd — so history survives serve-from-anywhere.
    return Path(__file__).resolve().parents[2] / ".memorybox_ask_history.json"


def read_asks() -> list[str]:
    path = history_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        t = str(item or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= HISTORY_MAX:
            break
    return out


def remember_ask(text: str) -> list[str]:
    t = str(text or "").strip()
    current = read_asks()
    if t:
        current = [t] + [x for x in current if x != t]
    current = current[:HISTORY_MAX]
    path = history_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, ensure_ascii=False, indent=0), encoding="utf-8")
    except OSError:
        pass
    return current
