"""Origin video date/filename/thumb for Explore appearance cards."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any


def looks_like_uuid(value: str) -> bool:
    raw = (value or "").strip()
    return len(raw) == 36 and raw.count("-") == 4


def origin_thumb_url(video_external_id: str, *, t_sec: float = 0.0) -> str:
    """Gallery entry frame at appearance start — not the first frame of the file."""
    vid = (video_external_id or "").strip()
    if not vid or vid.startswith(("video-peggy-", "video-library-")):
        return ""
    return f"/library/media/video-poster?video={vid}&t={max(0.0, float(t_sec)):.3f}"


@lru_cache(maxsize=512)
def origin_asset_meta(video_external_id: str) -> tuple[str, str]:
    """(taken_at iso, original_filename) from Immich when the id is an asset UUID."""
    vid = (video_external_id or "").strip()
    if not looks_like_uuid(vid):
        return "", ""
    try:
        from memorybox.ask.deps import build_photo

        photo = build_photo()
        client = getattr(photo, "_client", None)
        getter = getattr(client, "get_asset", None)
        raw = getter(vid) if callable(getter) else None
    except Exception:
        return "", ""
    if not isinstance(raw, dict):
        return "", ""
    name = str(raw.get("originalFileName") or raw.get("originalPath") or "").strip()
    if name:
        name = Path(name.replace("\\", "/")).name
    taken = ""
    from memorybox.recognition.seed import _capture_at

    dt = _capture_at(raw)
    if dt is not None:
        taken = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
    return taken, name


def origin_card_fields(video_external_id: str, *, t_sec: float = 0.0) -> dict[str, Any]:
    taken, filename = origin_asset_meta(video_external_id)
    return {
        "taken_at": taken or None,
        "original_filename": filename or None,
        "thumb_url": origin_thumb_url(video_external_id, t_sec=t_sec),
    }


def _ffmpeg_bin() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _poster_cache_path(video_external_id: str, t_sec: float) -> Path:
    digest = hashlib.sha256((video_external_id or "").encode("utf-8")).hexdigest()[:24]
    bucket = int(round(max(0.0, float(t_sec)) * 10))
    root = Path(tempfile.gettempdir()) / "mb-video-posters"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{digest}_{bucket}.jpg"


def extract_poster_from_path(source: Path, t_sec: float, dest: Path) -> bool:
    ffmpeg = _ffmpeg_bin()
    if not ffmpeg or not source.is_file():
        return False
    t = max(0.0, float(t_sec))
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{t:.3f}",
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-q:v",
        "3",
        "-y",
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=False, timeout=45, capture_output=True)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return dest.is_file() and dest.stat().st_size > 100


def poster_jpeg_bytes(video_external_id: str, t_sec: float) -> bytes | None:
    """JPEG at appearance start. Worker first (HVRT), then Immich/local file + ffmpeg."""
    vid = (video_external_id or "").strip()
    t = max(0.0, float(t_sec))
    if not vid:
        return None
    cached = _poster_cache_path(vid, t)
    if cached.is_file() and cached.stat().st_size > 100:
        return cached.read_bytes()
    base = (os.environ.get("MEMORYBOX_VIDEO_WORKER_URL") or "").strip().rstrip("/")
    if base:
        import urllib.error
        import urllib.parse
        import urllib.request

        q = urllib.parse.urlencode({"video_external_id": vid, "t": f"{t:.3f}"})
        try:
            with urllib.request.urlopen(f"{base}/poster?{q}", timeout=45) as resp:
                data = resp.read()
            if data:
                cached.write_bytes(data)
                return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            pass
    source = None
    try:
        from memorybox.recognition.frames import resolve_immich_video_path

        source = resolve_immich_video_path(vid)
    except Exception:
        source = None
    if source is None:
        try:
            from memorybox.ask.deps import build_video
            from memorybox.recognition.frames import resolve_local_video_path

            source = resolve_local_video_path(build_video(), vid)
        except Exception:
            source = None
    if source is None or not extract_poster_from_path(Path(source), t, cached):
        return None
    return cached.read_bytes() if cached.is_file() else None
