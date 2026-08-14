"""Sibling Video Intelligence worker — derived evidence only; originals read-only.

Run: python -m memorybox.video_worker
Config (env + thin Settings):
  MEMORYBOX_VIDEO_MEDIA_ROOT   — bootstrap / fallback family-video library path
  Settings → Home Videos library path overrides env (sidecar in derived dir)
  MEMORYBOX_VIDEO_DERIVED_DIR  — rebuildable derived detections store
  MEMORYBOX_VIDEO_PRESENCE_GAP_SEC — merge gap (default 60)
  MEMORYBOX_VIDEO_WORKER_HOST / MEMORYBOX_VIDEO_WORKER_PORT
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from memorybox.providers.video.merge import (
    DEFAULT_PRESENCE_GAP_SEC,
    RawDetection,
    merge_presence_spans,
)
from memorybox.video_worker.browser_proxy import BrowserProxyManager

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}

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
    try:
        from memorybox.settings.video_root import resolve_video_media_root

        raw = resolve_video_media_root()
    except Exception:  # noqa: BLE001 — worker must still boot if Settings import fails
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


def _stable_video_id(path: Path, root: Path) -> str:
    try:
        rel = str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        rel = path.name
    digest = hashlib.sha256(rel.encode("utf-8")).hexdigest()[:16]
    return f"vid-{digest}"


def _scan_videos(limit: int = 100) -> list[dict[str, Any]]:
    root = _media_root()
    if root is None or not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in VIDEO_EXTS:
            continue
        # Never open for write — metadata only
        try:
            rel = str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            rel = path.name
        out.append(
            {
                "external_id": _stable_video_id(path, root),
                "title": path.stem,
                "path_hint": rel,
                "duration_sec": None,
            }
        )
        if len(out) >= limit:
            break
    return out


def _resolve_video_path(external_id: str) -> Path | None:
    root = _media_root()
    if root is None:
        return None
    for row in _scan_videos(limit=5000):
        if row["external_id"] == external_id:
            hint = row.get("path_hint") or ""
            candidate = root / hint
            if candidate.is_file():
                return candidate
    return None


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

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

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

        if path == "/videos":
            limit = int((qs.get("limit") or ["100"])[0])
            videos = _scan_videos(limit=limit)
            self._json(200, {"ok": True, "videos": videos})
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
                    self.wfile.write(chunk)
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
                self.wfile.write(chunk)

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
