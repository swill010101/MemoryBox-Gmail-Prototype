"""Sample video frames and detect faces with MemoryBox buffalo_l (POC path)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from memorybox.recognition.constants import (
    MAX_FRAME_SAMPLES,
    MAX_INTERVAL_SEC,
    MIN_INTERVAL_SEC,
)
from memorybox.recognition.embeddings import _face_app, insightface_available


def sample_times(duration_sec: float, *, max_samples: int = MAX_FRAME_SAMPLES) -> list[float]:
    duration = float(duration_sec or 0)
    if duration <= 0 or duration != duration:
        duration = 60.0
    cap = max(1, int(max_samples))
    interval = max(MIN_INTERVAL_SEC, min(MAX_INTERVAL_SEC, duration / 40.0))
    times: list[float] = []
    t = 0.5
    while t < duration and len(times) < cap:
        times.append(round(t, 2))
        t += interval
    return times or [0.5]


def resolve_local_video_path(video_provider: Any, video_external_id: str) -> Path | None:
    vid = (video_external_id or "").strip()
    if not vid:
        return None
    hint = None
    try:
        for v in video_provider.list_videos(limit=5000) or []:
            if str(getattr(v, "external_id", "")) == vid:
                hint = getattr(v, "path_hint", None)
                break
    except Exception:
        hint = None
    roots: list[Path] = []
    for env_name in (
        "MEMORYBOX_VIDEO_MEDIA_ROOT",
        "HVRT_MEDIA_ROOT",
        "MEMORYBOX_SOURCES_ROOT",
    ):
        raw = (os.environ.get(env_name) or "").strip()
        if raw:
            roots.append(Path(raw))
    candidates: list[Path] = []
    if hint:
        p = Path(str(hint))
        if p.is_file():
            return p
        candidates.append(p)
        for root in roots:
            candidates.append(root / str(hint).replace("\\", "/"))
            candidates.append(root / Path(str(hint)).name)
    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    try:
        from memorybox.video_worker import resolve_owned_folder_path

        owned = resolve_owned_folder_path(vid)
        if owned is not None:
            return owned
    except Exception:
        pass
    return None


def video_duration_sec(video_provider: Any, video_external_id: str) -> float:
    try:
        for v in video_provider.list_videos(limit=5000) or []:
            if str(getattr(v, "external_id", "")) == video_external_id:
                d = getattr(v, "duration_sec", None)
                if d is not None:
                    return float(d)
    except Exception:
        pass
    return 0.0


def sample_faces_from_path(
    path: Path,
    *,
    duration_sec: float = 0.0,
    max_samples: int = MAX_FRAME_SAMPLES,
    extra_times: list[float] | None = None,
) -> list[dict[str, Any]]:
    if not insightface_available():
        return []
    try:
        import cv2
    except ImportError:
        return []
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return []
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or 25.0
        frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = float(duration_sec or 0) or (frame_count / fps if fps else 0)
        interval = max(MIN_INTERVAL_SEC, min(MAX_INTERVAL_SEC, (duration or 90.0) / 40.0))
        times = sample_times(duration or 90.0, max_samples=max_samples)
        for t in extra_times or []:
            try:
                ft = round(float(t), 2)
            except (TypeError, ValueError):
                continue
            if ft not in times:
                times.append(ft)
        times = sorted(times)[: max(1, int(max_samples) + len(extra_times or []))]
        app = _face_app()
        out: list[dict[str, Any]] = []
        for t in times:
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t * 1000.0))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            faces = app.get(frame)
            for face in faces or []:
                emb = getattr(face, "embedding", None)
                if emb is None:
                    continue
                bbox = None
                try:
                    bb = [float(x) for x in list(face.bbox[:4])]
                    bbox = {"x1": bb[0], "y1": bb[1], "x2": bb[2], "y2": bb[3]}
                except Exception:
                    bbox = None
                out.append(
                    {
                        "t_sec": float(t),
                        "sample_interval_sec": interval,
                        "embedding": [float(x) for x in list(emb)],
                        "bbox": bbox,
                    }
                )
        return out
    finally:
        cap.release()


def sample_faces_from_posters(
    video_provider: Any,
    video_external_id: str,
    times: list[float],
) -> tuple[list[dict[str, Any]], str | None]:
    fetch = getattr(video_provider, "fetch_poster", None)
    if not callable(fetch):
        return [], "poster_api_unavailable"
    if not insightface_available():
        return [], "insightface_unavailable"
    from memorybox.recognition.embeddings import _face_app, decode_to_bgr

    app = _face_app()
    out: list[dict[str, Any]] = []
    last_err: str | None = None
    for t in times:
        try:
            jpeg = fetch(video_external_id, float(t))
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)[:200]
            continue
        if not jpeg or jpeg[:1] in (b"{", b"["):
            last_err = last_err or "poster_not_jpeg"
            continue
        frame = decode_to_bgr(jpeg)
        if frame is None:
            last_err = last_err or "poster_decode_failed"
            continue
        faces = app.get(frame)
        for face in faces or []:
            emb = getattr(face, "embedding", None)
            if emb is None:
                continue
            bbox = None
            try:
                bb = [float(x) for x in list(face.bbox[:4])]
                bbox = {"x1": bb[0], "y1": bb[1], "x2": bb[2], "y2": bb[3]}
            except Exception:
                bbox = None
            out.append(
                {
                    "t_sec": float(t),
                    "embedding": [float(x) for x in list(emb)],
                    "bbox": bbox,
                }
            )
    if out:
        return out, None
    return [], last_err or "poster_no_faces"


def looks_like_uuid(value: str) -> bool:
    raw = (value or "").strip()
    if len(raw) != 36 or raw.count("-") != 4:
        return False
    hexpart = raw.replace("-", "")
    return all(c in "0123456789abcdefABCDEF" for c in hexpart)


def resolve_immich_video_path(asset_id: str) -> Path | None:
    """Ask/Explore Immich videos (encoded-video on disk, then originalPath if local)."""
    aid = (asset_id or "").strip()
    if not looks_like_uuid(aid):
        return None
    try:
        from memorybox.ask.deps import build_photo

        photo = build_photo()
    except Exception:
        return None
    client = getattr(photo, "_client", None)
    finder = getattr(client, "find_local_encoded_video", None)
    if callable(finder):
        try:
            found = finder(aid)
        except Exception:
            found = None
        if found is not None:
            p = Path(str(found))
            if p.is_file():
                return p
    getter = getattr(client, "get_asset", None)
    if callable(getter):
        try:
            asset = getter(aid) or {}
        except Exception:
            asset = {}
        for key in ("originalPath", "encodedVideoPath", "path"):
            raw = str(asset.get(key) or "").strip()
            if not raw:
                continue
            p = Path(raw)
            if p.is_file():
                return p
    opener = getattr(client, "open_video_playback", None)
    if callable(opener):
        dest = Path(tempfile.gettempdir()) / f"mb-i8b-{aid}.mp4"
        try:
            if dest.is_file() and dest.stat().st_size > 64:
                return dest
        except OSError:
            pass
        try:
            resp = opener(aid, None)
        except Exception:
            resp = None
        if resp is not None:
            written = 0
            limit = 250 * 1024 * 1024
            try:
                with dest.open("wb") as fh:
                    while written < limit:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        fh.write(chunk)
                        written += len(chunk)
            except Exception:
                dest = dest if dest.is_file() else None
            finally:
                try:
                    resp.close()
                except Exception:
                    pass
            if dest is not None and dest.is_file() and dest.stat().st_size > 64:
                return dest
    return None


def collect_insightface_scan_samples(
    video_provider: Any,
    video_external_id: str,
    *,
    max_samples: int = MAX_FRAME_SAMPLES,
    extra_times: list[float] | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    duration = video_duration_sec(video_provider, video_external_id)
    times = sample_times(duration or 90.0, max_samples=max_samples)
    for t in extra_times or []:
        try:
            ft = round(float(t), 2)
        except (TypeError, ValueError):
            continue
        if ft not in times:
            times.append(ft)
    times = sorted(times)[: max(1, int(max_samples) + len(extra_times or []))]
    path = resolve_local_video_path(video_provider, video_external_id)
    if path is None:
        path = resolve_immich_video_path(video_external_id)
    if path is not None:
        samples = sample_faces_from_path(
            path,
            duration_sec=duration,
            max_samples=max_samples,
            extra_times=extra_times,
        )
        if samples:
            return samples, None
    posters, err = sample_faces_from_posters(video_provider, video_external_id, times)
    if posters:
        interval = max(MIN_INTERVAL_SEC, min(MAX_INTERVAL_SEC, (duration or 90.0) / 40.0))
        for sample in posters:
            sample["sample_interval_sec"] = interval
        return posters, None
    if path is None:
        return [], err or "video_file_not_found"
    return [], err or "no_faces_in_samples"
