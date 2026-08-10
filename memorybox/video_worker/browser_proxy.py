"""Make source videos browser-playable (H.264/AAC) via ffmpeg.

Chrome often plays audio from HEVC/H.265 MP4s but never reports videoWidth —
the review player stays black. VLC still shows frames. Builds a derived H.264
proxy under the worker derived dir — originals remain untouched.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


def _safe_key(video_external_id: str) -> str:
    raw = (video_external_id or "").strip()
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return digest


class BrowserProxyManager:
    def __init__(self, working_dir: Path | str) -> None:
        self.working_dir = Path(working_dir)
        self.proxy_dir = self.working_dir / "browser_proxies"
        self.proxy_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def proxy_path(self, video_external_id: str) -> Path:
        return self.proxy_dir / f"{_safe_key(video_external_id)}.mp4"

    def has_ready_proxy(self, video_external_id: str, source: Path) -> bool:
        dest = self.proxy_path(video_external_id)
        if not dest.is_file() or dest.stat().st_size < 1000:
            return False
        try:
            return dest.stat().st_mtime >= source.stat().st_mtime
        except OSError:
            return False

    def status(
        self, video_external_id: str, source: Path | None = None
    ) -> dict[str, Any]:
        vid = (video_external_id or "").strip()
        with self._lock:
            job = dict(self._jobs.get(vid) or {})
        ready = bool(source and self.has_ready_proxy(vid, source))
        stream = f"/media/{vid}?proxy=1"
        if ready and job.get("status") not in ("running", "queued"):
            return {
                "video_external_id": vid,
                "status": "ready",
                "progress_pct": 100,
                "message": "Browser-playable copy ready",
                "proxy_path": str(self.proxy_path(vid)),
                "stream_url": stream,
            }
        if not job:
            return {
                "video_external_id": vid,
                "status": "missing",
                "progress_pct": 0,
                "message": "No browser proxy yet",
                "stream_url": stream,
            }
        job["video_external_id"] = vid
        job["stream_url"] = stream
        return job

    def start(self, video_external_id: str, source: Path) -> dict[str, Any]:
        vid = (video_external_id or "").strip()
        source = Path(source)
        if not vid:
            raise ValueError("video_external_id required")
        if not source.is_file():
            raise FileNotFoundError(f"missing source: {source}")
        if self.has_ready_proxy(vid, source):
            return self.status(vid, source)
        with self._lock:
            cur = self._jobs.get(vid) or {}
            if cur.get("status") in ("queued", "running"):
                return self.status(vid, source)
            self._jobs[vid] = {
                "status": "queued",
                "progress_pct": 0,
                "message": "Queued ffmpeg H.264 convert",
                "log": [],
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "finished_at": None,
                "error": None,
            }
        t = threading.Thread(
            target=self._run,
            args=(vid, source),
            daemon=True,
            name=f"browser-proxy-{_safe_key(vid)}",
        )
        t.start()
        return self.status(vid, source)

    def _append(self, video_external_id: str, line: str) -> None:
        line = (line or "").rstrip()
        if not line:
            return
        with self._lock:
            job = self._jobs.setdefault(video_external_id, {})
            log = list(job.get("log") or [])
            log.append(line)
            job["log"] = log[-80:]

    def _set(self, video_external_id: str, **kwargs: Any) -> None:
        with self._lock:
            job = self._jobs.setdefault(video_external_id, {})
            job.update(kwargs)

    def _probe_codec(self, source: Path) -> str:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return "unknown"
        try:
            proc = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_name",
                    "-of",
                    "json",
                    str(source),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            data = json.loads(proc.stdout or "{}")
            streams = data.get("streams") or []
            if streams:
                return str(streams[0].get("codec_name") or "unknown")
        except (OSError, json.JSONDecodeError, subprocess.SubprocessError):
            pass
        return "unknown"

    def _find_ffmpeg(self) -> str | None:
        found = shutil.which("ffmpeg")
        if found:
            return found
        try:
            import imageio_ffmpeg  # type: ignore

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:  # noqa: BLE001
            return None

    def _run(self, video_external_id: str, source: Path) -> None:
        dest = self.proxy_path(video_external_id)
        tmp = dest.with_suffix(".tmp.mp4")
        ffmpeg = self._find_ffmpeg()
        if not ffmpeg:
            self._set(
                video_external_id,
                status="error",
                progress_pct=0,
                message="ffmpeg not found — install ffmpeg or: pip install imageio-ffmpeg",
                error="ffmpeg missing",
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            return
        codec = self._probe_codec(source)
        self._set(
            video_external_id,
            status="running",
            progress_pct=5,
            message=f"Converting {source.name} ({codec}) → H.264 for Chrome",
        )
        self._append(video_external_id, f"source codec: {codec}")
        self._append(video_external_id, f"ffmpeg → {dest}")
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(tmp),
        ]
        try:
            if tmp.exists():
                tmp.unlink()
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            last_pct = 5.0
            for line in proc.stdout:
                self._append(video_external_id, line)
                if "time=" in line and last_pct < 90:
                    last_pct = min(90.0, last_pct + 0.4)
                    self._set(
                        video_external_id,
                        progress_pct=last_pct,
                        message=f"Converting… {line.strip()[:120]}",
                    )
            rc = proc.wait()
            if rc != 0 or not tmp.is_file() or tmp.stat().st_size < 1000:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
                self._set(
                    video_external_id,
                    status="error",
                    progress_pct=last_pct,
                    message=f"ffmpeg failed (exit {rc})",
                    error=f"ffmpeg exit {rc}",
                    finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                )
                return
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                dest.unlink()
            tmp.replace(dest)
            self._set(
                video_external_id,
                status="ready",
                progress_pct=100,
                message="Browser-playable copy ready — reloading player",
                proxy_path=str(dest),
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                error=None,
            )
            self._append(video_external_id, "done")
        except Exception as e:  # noqa: BLE001
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            self._set(
                video_external_id,
                status="error",
                message=str(e),
                error=str(e),
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            self._append(video_external_id, f"ERROR: {e}")
