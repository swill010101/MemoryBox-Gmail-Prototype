"""Sibling Video Intelligence worker — derived evidence only; originals read-only.

Run: python -m memorybox.video_worker
Config (env only — no hard-coded hosts):
  MEMORYBOX_VIDEO_MEDIA_ROOT   — family-video library (FlightSim: P:/photos/home videos)
  MEMORYBOX_VIDEO_DERIVED_DIR  — rebuildable derived detections store
  MEMORYBOX_VIDEO_PRESENCE_GAP_SEC — merge gap (default 60)
  MEMORYBOX_VIDEO_WORKER_HOST / MEMORYBOX_VIDEO_WORKER_PORT
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

# Browser/player cancel (seek, tab close, new range) — not a worker fault.
_CLIENT_DISCONNECT = (
    ConnectionResetError,
    ConnectionAbortedError,
    BrokenPipeError,
    TimeoutError,
)


def _is_client_disconnect(exc: BaseException) -> bool:
    if isinstance(exc, _CLIENT_DISCONNECT):
        return True
    if isinstance(exc, OSError):
        # WinError 10054/10053, POSIX EPIPE/ECONNRESET
        return getattr(exc, "winerror", None) in (10054, 10053) or getattr(
            exc, "errno", None
        ) in (32, 104, 54)
    return False

from memorybox.providers.video.merge import (
    DEFAULT_PRESENCE_GAP_SEC,
    RawDetection,
    merge_presence_spans,
)
from memorybox.video_worker.browser_proxy import BrowserProxyManager

VIDEO_EXTS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".m4v",
    ".webm",
    ".mts",
    ".m2ts",
    ".mpg",
    ".mpeg",
    ".wmv",
    ".ts",
    ".3gp",
    ".mod",
    ".tod",
    ".flv",
    ".vob",
}

_proxies: BrowserProxyManager | None = None


def _proxies_mgr() -> BrowserProxyManager:
    global _proxies
    if _proxies is None:
        _proxies = BrowserProxyManager(_derived_dir())
    return _proxies


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip()


def _gap_sec() -> float:
    raw = _env("MEMORYBOX_VIDEO_PRESENCE_GAP_SEC", str(DEFAULT_PRESENCE_GAP_SEC))
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_PRESENCE_GAP_SEC


def _media_root() -> Path | None:
    raw = _env("MEMORYBOX_VIDEO_MEDIA_ROOT")
    if not raw:
        return None
    return Path(raw)


def _derived_dir() -> Path:
    raw = _env("MEMORYBOX_VIDEO_DERIVED_DIR")
    if raw:
        p = Path(raw)
    else:
        p = Path(os.environ.get("TEMP", ".")).joinpath("memorybox_video_derived")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _derived_path() -> Path:
    return _derived_dir() / "detections.json"


def _load_derived() -> dict[str, Any]:
    path = _derived_path()
    if not path.is_file():
        return {"detections": [], "faces": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"detections": [], "faces": {}}


def _save_derived(data: dict[str, Any]) -> None:
    path = _derived_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _rel_hint(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return path.name


def _stable_id_from_key(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"vid-{digest}"


def _stable_video_id(path: Path, root: Path) -> str:
    return _stable_id_from_key(_rel_hint(path, root))


def _alias_ids(path: Path, root: Path) -> list[str]:
    """I1 rows may hash slash-normalized rel, Windows rel, or filename only."""
    rel = _rel_hint(path, root)
    try:
        win_rel = str(path.relative_to(root))
    except ValueError:
        win_rel = path.name
    keys = [rel, rel.lower(), win_rel, win_rel.lower(), path.name, path.name.lower()]
    out: list[str] = []
    seen: set[str] = set()
    for key in keys:
        vid = _stable_id_from_key(key)
        if vid not in seen:
            seen.add(vid)
            out.append(vid)
    return out


def _scan_videos(limit: int = 100) -> list[dict[str, Any]]:
    root = _media_root()
    if root is None or not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _exc: None):
        dirnames.sort()
        filenames.sort()
        for name in filenames:
            suffix = Path(name).suffix.lower()
            if suffix not in VIDEO_EXTS:
                continue
            path = Path(dirpath) / name
            if not path.is_file():
                continue
            rel = _rel_hint(path, root)
            aliases = _alias_ids(path, root)
            out.append(
                {
                    "external_id": aliases[0],
                    "alias_ids": aliases[1:],
                    "title": path.stem,
                    "path_hint": rel,
                    "duration_sec": None,
                }
            )
            if len(out) >= limit:
                return out
    return out


_VIDEO_INDEX: tuple[float, list[dict[str, Any]]] | None = None
_VIDEO_BY_ID: dict[str, dict[str, Any]] = {}
_VIDEO_INDEX_TTL_SEC = 300.0


def invalidate_video_index() -> None:
    """Drop the 5-minute walk cache so a newly copied file is visible."""
    global _VIDEO_INDEX, _VIDEO_BY_ID
    _VIDEO_INDEX = None
    _VIDEO_BY_ID = {}


def list_owned_folder_videos(*, limit: int = 100000) -> list[dict[str, Any]]:
    """Recursive walk of MEMORYBOX_VIDEO_MEDIA_ROOT (MB-owned tapes, not Immich)."""
    invalidate_video_index()
    return _scan_videos(limit=int(limit))


def _index_lookup() -> dict[str, dict[str, Any]]:
    _video_index()
    return _VIDEO_BY_ID


def _video_index() -> list[dict[str, Any]]:
    """Full library index (cached). Lookup by id must not stop at 5000 files."""
    global _VIDEO_INDEX, _VIDEO_BY_ID
    now = time.monotonic()
    if _VIDEO_INDEX and (now - _VIDEO_INDEX[0]) < _VIDEO_INDEX_TTL_SEC:
        return _VIDEO_INDEX[1]
    rows = _scan_videos(limit=100000)
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_id[str(row["external_id"])] = row
        for alias in row.get("alias_ids") or []:
            by_id.setdefault(str(alias), row)
    _VIDEO_BY_ID = by_id
    _VIDEO_INDEX = (now, rows)
    return rows


def _resolve_video_path(external_id: str) -> Path | None:
    root = _media_root()
    if root is None:
        return None
    want = (external_id or "").strip()
    if not want:
        return None
    row = _index_lookup().get(want)
    if not row:
        return None
    hint = row.get("path_hint") or ""
    candidate = root / hint
    if candidate.is_file():
        return candidate
    return None


def resolve_owned_folder_path(external_id: str) -> Path | None:
    """Resolve a vid-* id against the MB-owned folder. Refresh cache on miss."""
    found = _resolve_video_path(external_id)
    if found is not None:
        return found
    invalidate_video_index()
    return _resolve_video_path(external_id)


def _spans_payload(
    *,
    video_external_id: str | None = None,
    face_external_id: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    data = _load_derived()
    dets_raw = data.get("detections") or []
    by_video: dict[str, list[RawDetection]] = {}
    for row in dets_raw:
        vid = str(row.get("video_external_id") or "")
        if video_external_id and vid != video_external_id:
            continue
        cid = str(row.get("face_external_id") or row.get("candidate_id") or "")
        if face_external_id and cid != face_external_id:
            continue
        by_video.setdefault(vid, []).append(
            RawDetection(
                candidate_id=cid,
                t_sec=float(row.get("t_sec") or 0),
                end_sec=(
                    float(row["end_sec"])
                    if row.get("end_sec") is not None
                    else None
                ),
                label=row.get("label"),
            )
        )
    gap = _gap_sec()
    out: list[dict[str, Any]] = []
    for vid, dets in by_video.items():
        merged = merge_presence_spans(dets, gap_sec=gap)
        for i, s in enumerate(merged):
            out.append(
                {
                    "external_id": f"{vid}:{s.candidate_id}:{i}",
                    "video_external_id": vid,
                    "face_external_id": s.candidate_id,
                    "start_sec": s.start_sec,
                    "end_sec": s.end_sec,
                    "label": s.label,
                    "detection_count": s.detection_count,
                }
            )
    return out[:limit]


class Handler(BaseHTTPRequestHandler):
    server_version = "MemoryBoxVideoWorker/0.7"

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter default
        pass

    def log_error(self, fmt: str, *args: Any) -> None:
        # Suppress traceback spam when the player closes the socket mid-stream.
        if args and _is_client_disconnect(args[0] if isinstance(args[0], BaseException) else Exception()):
            return
        msg = fmt % args if args else fmt
        if "10054" in msg or "10053" in msg or "forcibly closed" in msg.lower():
            return
        super().log_error(fmt, *args)

    def handle(self) -> None:
        try:
            super().handle()
        except Exception as exc:  # noqa: BLE001
            if _is_client_disconnect(exc):
                return
            raise

    def finish(self) -> None:
        try:
            super().finish()
        except Exception as exc:  # noqa: BLE001
            if _is_client_disconnect(exc):
                return
            raise

    def _write_chunk(self, chunk: bytes) -> bool:
        """Write one chunk. False if the client already hung up."""
        try:
            self.wfile.write(chunk)
            return True
        except Exception as exc:  # noqa: BLE001
            if _is_client_disconnect(exc):
                return False
            raise

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self._write_chunk(raw)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range")
        self.send_header("Access-Control-Expose-Headers", "Accept-Ranges, Content-Range, Content-Length")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/health":
            root = _media_root()
            media_ok = bool(root and root.is_dir())
            self._json(
                200,
                {
                    "ok": True,
                    "detail": "video worker",
                    "provider_key": "hvrt",
                    "presence_gap_sec": _gap_sec(),
                    "media_root_configured": root is not None,
                    "media_root_readable": media_ok,
                    "media_root": str(root) if root else None,
                    "video_count": (
                        len(_VIDEO_INDEX[1]) if _VIDEO_INDEX is not None else None
                    ),
                    "derived_dir": str(_derived_dir()),
                    "originals_read_only": True,
                },
            )
            return

        if path == "/poster":
            vid = (qs.get("video_external_id") or [None])[0]
            if not vid:
                self._json(400, {"ok": False, "detail": "video_external_id required"})
                return
            try:
                t_sec = float((qs.get("t") or ["0"])[0])
            except ValueError:
                t_sec = 0.0
            source = _resolve_video_path(vid)
            if not source or not source.is_file():
                self._json(404, {"ok": False, "detail": "video not found"})
                return
            poster = _proxies_mgr().ensure_poster(vid, source, t_sec)
            if not poster or not poster.is_file():
                self._json(
                    503,
                    {
                        "ok": False,
                        "detail": "poster extract failed (ffmpeg missing or decode error)",
                    },
                )
                return
            data = poster.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/videos/count":
            snap = _VIDEO_INDEX
            if snap:
                self._json(
                    200,
                    {
                        "ok": True,
                        "ready": True,
                        "indexed": len(snap[1]),
                    },
                )
            else:
                self._json(200, {"ok": True, "ready": False, "indexed": None})
            return

        if path == "/videos":
            refresh = str((qs.get("refresh") or ["0"])[0]).strip().lower()
            if refresh in {"1", "true", "yes", "on"}:
                invalidate_video_index()
            limit = int((qs.get("limit") or ["100"])[0])
            n = max(1, min(limit, 100000))
            videos = [
                {k: v for k, v in row.items() if k != "alias_ids"}
                for row in _video_index()[:n]
            ]
            self._json(200, {"ok": True, "videos": videos, "indexed": len(_video_index())})
            return

        if path.startswith("/videos/") and not path.endswith("/browser-proxy"):
            vid = path[len("/videos/") :].strip("/")
            if vid and "/" not in vid:
                row = _index_lookup().get(vid)
                source = _resolve_video_path(vid)
                if not row and not source:
                    self._json(404, {"ok": False, "detail": "video not found"})
                    return
                payload = {k: v for k, v in dict(row or {"external_id": vid}).items() if k != "alias_ids"}
                payload["external_id"] = vid
                payload["canonical_id"] = (row or {}).get("external_id")
                payload["exists"] = bool(source and source.is_file())
                self._json(200, {"ok": True, "video": payload})
                return

        if path == "/faces":
            limit = int((qs.get("limit") or ["100"])[0])
            video_id = (qs.get("video_external_id") or [None])[0]
            data = _load_derived()
            faces = data.get("faces") or {}
            out = []
            for fid, meta in faces.items():
                if video_id and meta.get("video_external_id") != video_id:
                    continue
                out.append(
                    {
                        "external_id": fid,
                        "label": meta.get("label"),
                        "video_external_id": meta.get("video_external_id"),
                        "bbox": meta.get("bbox"),
                        "boxed": bool(meta.get("bbox")),
                        "created_at_t_sec": meta.get("created_at_t_sec"),
                    }
                )
            self._json(200, {"ok": True, "faces": out[:limit]})
            return

        if path == "/spans":
            limit = int((qs.get("limit") or ["200"])[0])
            video_id = (qs.get("video_external_id") or [None])[0]
            face_id = (qs.get("face_external_id") or [None])[0]
            spans = _spans_payload(
                video_external_id=video_id,
                face_external_id=face_id,
                limit=limit,
            )
            self._json(200, {"ok": True, "spans": spans, "gap_sec": _gap_sec()})
            return

        if path.startswith("/segments/"):
            seg_id = path[len("/segments/") :]
            for sp in _spans_payload(limit=5000):
                if sp["external_id"] == seg_id:
                    self._json(200, {"ok": True, "hit": sp})
                    return
            self._json(404, {"ok": False, "detail": "segment not found"})
            return

        if path.startswith("/media/"):
            vid = path[len("/media/") :]
            # strip query already parsed — path is only path component
            use_proxy = (qs.get("proxy") or ["0"])[0] in ("1", "true", "yes")
            source = _resolve_video_path(vid)
            if use_proxy:
                file_path = _proxies_mgr().proxy_path(vid)
                if not file_path.is_file():
                    self._json(
                        404,
                        {
                            "ok": False,
                            "detail": "Browser proxy not ready — POST /videos/{id}/browser-proxy first",
                        },
                    )
                    return
            else:
                file_path = source
            if not file_path or not file_path.is_file():
                self._json(404, {"ok": False, "detail": "media not found"})
                return
            self._serve_media_file(file_path)
            return

        if path.startswith("/videos/") and path.endswith("/browser-proxy"):
            # GET /videos/{id}/browser-proxy
            mid = path[len("/videos/") : -len("/browser-proxy")]
            source = _resolve_video_path(mid)
            st = _proxies_mgr().status(mid, source if source and source.is_file() else None)
            self._json(200, st)
            return

        self._json(404, {"ok": False, "detail": "not found"})

    def _serve_media_file(self, file_path: Path) -> None:
        """Read-only byte serve with Accept-Ranges / 206 Partial Content (scrubbing)."""
        ctype = mimetypes.guess_type(str(file_path))[0] or "video/mp4"
        file_size = file_path.stat().st_size
        range_header = self.headers.get("Range") or self.headers.get("range")
        if not range_header:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Expose-Headers", "Accept-Ranges, Content-Range, Content-Length")
            self.end_headers()
            with file_path.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    if not self._write_chunk(chunk):
                        return
            return

        units, _, rng = range_header.partition("=")
        if units.strip().lower() != "bytes":
            self.send_error(416, "Only bytes ranges supported")
            return
        start_s, _, end_s = rng.partition("-")
        try:
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else file_size - 1
        except ValueError:
            self.send_error(416, "Invalid range")
            return
        start = max(0, start)
        end = min(end, file_size - 1)
        if start > end:
            self.send_error(416, "Invalid range")
            return
        length = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Expose-Headers", "Accept-Ranges, Content-Range, Content-Length")
        self.end_headers()
        with file_path.open("rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                if not self._write_chunk(chunk):
                    return

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json()
        if path.startswith("/faces/"):
            face_id = path[len("/faces/") :]
            data = _load_derived()
            faces = data.setdefault("faces", {})
            if face_id not in faces:
                self._json(404, {"ok": False, "detail": "face not found"})
                return
            bbox = body.get("bbox")
            if bbox is not None:
                faces[face_id]["bbox"] = bbox
            if body.get("label") is not None:
                faces[face_id]["label"] = body.get("label")
            if body.get("crop_jpeg_base64"):
                # Optional derived crop preview — not original video mutation
                crop_dir = _derived_dir() / "crops"
                crop_dir.mkdir(parents=True, exist_ok=True)
                import base64

                raw = str(body["crop_jpeg_base64"]).split(",", 1)[-1]
                crop_path = crop_dir / f"{face_id}.jpg"
                crop_path.write_bytes(base64.b64decode(raw))
                faces[face_id]["crop_path"] = str(crop_path.name)
            _save_derived(data)
            meta = faces[face_id]
            self._json(
                200,
                {
                    "ok": True,
                    "face": {
                        "external_id": face_id,
                        "label": meta.get("label"),
                        "video_external_id": meta.get("video_external_id"),
                        "bbox": meta.get("bbox"),
                        "boxed": bool(meta.get("bbox")),
                    },
                },
            )
            return
        self._json(404, {"ok": False, "detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        if path.startswith("/videos/") and path.endswith("/browser-proxy"):
            mid = path[len("/videos/") : -len("/browser-proxy")]
            source = _resolve_video_path(mid)
            if not source or not source.is_file():
                self._json(404, {"ok": False, "detail": f"missing source for {mid}"})
                return
            try:
                st = _proxies_mgr().start(mid, source)
            except FileNotFoundError as exc:
                self._json(404, {"ok": False, "detail": str(exc)})
                return
            self._json(200, st)
            return

        if path == "/search":
            wanted = set(body.get("person_external_ids") or [])
            video_id = body.get("video_external_id")
            text = (body.get("text") or "").lower()
            limit = int(body.get("limit") or 50)
            hits = []
            for sp in _spans_payload(video_external_id=video_id, limit=5000):
                if wanted and sp["face_external_id"] not in wanted:
                    continue
                if text and text not in (sp.get("label") or "").lower():
                    if not wanted:
                        continue
                hits.append(
                    {
                        **sp,
                        "play_url": (
                            f"/media/{sp['video_external_id']}"
                            f"?t={float(sp.get('start_sec') or 0)}"
                        ),
                    }
                )
            self._json(200, {"ok": True, "hits": hits[:limit]})
            return

        if path == "/faces":
            video_id = str(body.get("video_external_id") or "").strip()
            t_sec = float(body.get("t_sec") or 0)
            label = body.get("label")
            bbox = body.get("bbox")
            if not video_id:
                self._json(400, {"ok": False, "detail": "video_external_id required"})
                return
            face_id = f"face-{uuid.uuid4().hex[:12]}"
            data = _load_derived()
            faces = data.setdefault("faces", {})
            faces[face_id] = {
                "video_external_id": video_id,
                "label": label,
                "created_at_t_sec": t_sec,
                "bbox": bbox,
            }
            dets = data.setdefault("detections", [])
            dets.append(
                {
                    "video_external_id": video_id,
                    "face_external_id": face_id,
                    "t_sec": t_sec,
                    "end_sec": t_sec + 1.0,
                    "label": label,
                }
            )
            _save_derived(data)
            self._json(
                200,
                {
                    "ok": True,
                    "face": {
                        "external_id": face_id,
                        "label": label,
                        "video_external_id": video_id,
                        "bbox": bbox,
                        "boxed": bool(bbox),
                    },
                    "archive_note": "derived_only",
                    "needs_box": not bool(bbox),
                },
            )
            return

        if path == "/detections/seed":
            # Harness / ops: inject derived detections (never touches originals)
            rows = body.get("detections") or []
            data = _load_derived()
            dets = data.setdefault("detections", [])
            faces = data.setdefault("faces", {})
            for row in rows:
                cid = str(row.get("face_external_id") or row.get("candidate_id") or "")
                vid = str(row.get("video_external_id") or "")
                if not cid or not vid:
                    continue
                faces.setdefault(
                    cid,
                    {
                        "video_external_id": vid,
                        "label": row.get("label"),
                    },
                )
                dets.append(
                    {
                        "video_external_id": vid,
                        "face_external_id": cid,
                        "t_sec": float(row.get("t_sec") or 0),
                        "end_sec": row.get("end_sec"),
                        "label": row.get("label"),
                    }
                )
            _save_derived(data)
            self._json(200, {"ok": True, "count": len(rows)})
            return

        if path == "/derived/reset":
            _save_derived({"detections": [], "faces": {}})
            self._json(200, {"ok": True, "reset": True})
            return

        self._json(404, {"ok": False, "detail": "not found"})


def serve() -> None:
    host = _env("MEMORYBOX_VIDEO_WORKER_HOST", "127.0.0.1") or "127.0.0.1"
    port = int(_env("MEMORYBOX_VIDEO_WORKER_PORT", "8791") or "8791")
    httpd = ThreadingHTTPServer((host, port), Handler)

    def _warm() -> None:
        try:
            n = len(_video_index())
            print(json.dumps({"ok": True, "event": "video_index_ready", "video_count": n}), flush=True)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "event": "video_index_failed", "detail": str(exc)[:240]}), flush=True)

    threading.Thread(target=_warm, name="video-index-warm", daemon=True).start()
    print(
        json.dumps(
            {
                "ok": True,
                "service": "memorybox-video-worker",
                "host": host,
                "port": port,
                "presence_gap_sec": _gap_sec(),
                "media_root": str(_media_root()) if _media_root() else None,
            }
        ),
        flush=True,
    )
    httpd.serve_forever()


def main() -> None:
    try:
        from memorybox.profile.bootstrap import ensure_default_owner_session

        boot = ensure_default_owner_session()
        if not boot.get("skipped"):
            print(f"owner bootstrap: {boot}", flush=True)
    except Exception as exc:  # noqa: BLE001 — worker must still start
        print(f"owner bootstrap skipped: {exc}", flush=True)
    serve()
