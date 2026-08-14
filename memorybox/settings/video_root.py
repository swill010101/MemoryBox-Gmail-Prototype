"""Physical Home Videos / HVRT media-root resolution.

Explore/Person collect video from every known MB source (Immich library clips
via the photo provider, plus HVRT moments). This module is only the *file*
root the sibling video worker scans — not Immich.

Precedence (owner Settings must win on FlightSim, where startmb always loads
``config/video_worker.env``):

1. Sidecar file in the derived dir (last Settings save)
2. ``memorybox_runtime_settings.video_media_root`` (durable; can rebuild sidecar)
3. ``MEMORYBOX_VIDEO_MEDIA_ROOT`` env (ops / startmb bootstrap default)

Clearing Settings removes sidecar + DB row so env is the default again.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

KEY_VIDEO_MEDIA_ROOT = "video_media_root"
ENV_VIDEO_MEDIA_ROOT = "MEMORYBOX_VIDEO_MEDIA_ROOT"
ENV_VIDEO_DERIVED_DIR = "MEMORYBOX_VIDEO_DERIVED_DIR"
SIDECAR_NAME = "media_root.txt"
_MAX_PATH = 2048


def derived_dir() -> Path:
    raw = (os.environ.get(ENV_VIDEO_DERIVED_DIR) or "").strip()
    if raw:
        p = Path(raw)
    else:
        p = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".").joinpath(
            "memorybox_video_derived"
        )
    p.mkdir(parents=True, exist_ok=True)
    return p


def sidecar_path() -> Path:
    return derived_dir() / SIDECAR_NAME


def _clean_path(raw: str | None) -> str:
    if raw is None:
        return ""
    text = str(raw).strip().strip('"').strip("'")
    if "\n" in text or "\r" in text:
        text = text.splitlines()[0].strip()
    if len(text) > _MAX_PATH:
        text = text[:_MAX_PATH]
    return text


def _read_sidecar() -> str:
    path = sidecar_path()
    if not path.is_file():
        return ""
    try:
        return _clean_path(path.read_text(encoding="utf-8-sig"))
    except OSError:
        return ""


def _write_sidecar(value: str) -> None:
    path = sidecar_path()
    if not value:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return
    path.write_text(value + "\n", encoding="utf-8")


def _read_db() -> str:
    try:
        from memorybox.db import connection

        with connection() as conn:
            row = conn.execute(
                """
                SELECT value_text FROM memorybox_runtime_settings
                WHERE setting_key = %s
                """,
                (KEY_VIDEO_MEDIA_ROOT,),
            ).fetchone()
        if not row:
            return ""
        return _clean_path(row.get("value_text"))
    except Exception:  # noqa: BLE001 — table/DB may be down; sidecar/env still work
        return ""


def _write_db(value: str, *, actor_key: str) -> bool:
    try:
        from memorybox.db import connection

        with connection() as conn:
            if not value:
                conn.execute(
                    "DELETE FROM memorybox_runtime_settings WHERE setting_key = %s",
                    (KEY_VIDEO_MEDIA_ROOT,),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO memorybox_runtime_settings
                        (setting_key, value_text, actor_key, updated_at)
                    VALUES (%s, %s, %s, now())
                    ON CONFLICT (setting_key) DO UPDATE
                    SET value_text = EXCLUDED.value_text,
                        actor_key = EXCLUDED.actor_key,
                        updated_at = now()
                    """,
                    (KEY_VIDEO_MEDIA_ROOT, value, actor_key),
                )
        return True
    except Exception:  # noqa: BLE001
        return False


def resolve_video_media_root() -> str | None:
    """Effective filesystem root, or None when unset."""
    for candidate in (_read_sidecar(), _read_db(), _clean_path(os.environ.get(ENV_VIDEO_MEDIA_ROOT))):
        if candidate:
            return candidate
    return None


def _reachable(root: str) -> bool:
    if not root:
        return False
    try:
        return Path(root).is_dir()
    except OSError:
        return False


def describe_video_media_root() -> dict[str, Any]:
    sidecar = _read_sidecar()
    stored = _read_db()
    env = _clean_path(os.environ.get(ENV_VIDEO_MEDIA_ROOT))
    if sidecar:
        source = "settings_sidecar"
        effective = sidecar
    elif stored:
        source = "settings_db"
        effective = stored
    elif env:
        source = "env"
        effective = env
    else:
        source = "unset"
        effective = ""
    return {
        "ok": True,
        "key": KEY_VIDEO_MEDIA_ROOT,
        "effective_root": effective or None,
        "source": source,
        "stored_root": stored or None,
        "sidecar_root": sidecar or None,
        "sidecar_path": str(sidecar_path()),
        "env_root": env or None,
        "env_name": ENV_VIDEO_MEDIA_ROOT,
        "reachable": _reachable(effective) if effective else False,
        "settings_overrides_env": bool(sidecar or stored),
        "note": (
            "Saved Settings override MEMORYBOX_VIDEO_MEDIA_ROOT until cleared. "
            "The video worker re-reads this path on the next library scan."
        ),
    }


def set_video_media_root(path: str | None, *, actor_key: str = "owner") -> dict[str, Any]:
    """Persist owner path (empty clears Settings and falls back to env)."""
    value = _clean_path(path)
    _write_sidecar(value)
    db_ok = _write_db(value, actor_key=actor_key)
    status = describe_video_media_root()
    status["saved_root"] = value or None
    status["db_ok"] = db_ok
    if value and not db_ok:
        status["note"] = (
            (status.get("note") or "")
            + " Database save failed; sidecar was written so the worker can still pick this up."
        ).strip()
    return status
