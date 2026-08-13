"""Background sample ingest — copy videos then run process_videos.py with live status."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from hvrt.schema_r2 import connect as db_connect


PROCESS_STEPS = [
    ("upload", "Save videos into sample\\"),
    ("pipeline", "Run process_videos (metadata / scenes / whisper / faces)"),
    ("verify", "Refresh evidence counts"),
]


class ProcessJobManager:
    def __init__(
        self,
        *,
        db_path: Path | str,
        root: Path | str,
        sample_dir: Path | str,
    ) -> None:
        self.db_path = Path(db_path)
        self.root = Path(root)
        self.sample_dir = Path(sample_dir)
        self.sample_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._state: dict[str, Any] = {
            "status": "idle",
            "progress_pct": 0,
            "current_step": None,
            "message": "",
            "steps": [],
            "log": [],
            "saved": [],
            "background": True,
            "note": "Review stays usable while this runs.",
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            out = dict(self._state)
            out["log"] = list(self._state.get("log") or [])[-40:]
            out["steps"] = [dict(s) for s in (self._state.get("steps") or [])]
            out["saved"] = list(self._state.get("saved") or [])
            return out

    def _set(self, **kwargs: Any) -> None:
        with self._lock:
            self._state.update(kwargs)

    def _append_log(self, line: str) -> None:
        line = (line or "").rstrip()
        if not line:
            return
        with self._lock:
            log = list(self._state.get("log") or [])
            log.append(line)
            self._state["log"] = log[-200:]

    def _set_step(self, key: str, status: str, pct: float, message: str = "") -> None:
        with self._lock:
            steps = [dict(s) for s in (self._state.get("steps") or [])]
            for s in steps:
                if s["key"] == key:
                    s["status"] = status
                    s["progress_pct"] = pct
                    s["message"] = message
            self._state["steps"] = steps
            self._state["current_step"] = key
            self._state["progress_pct"] = pct
            if message:
                self._state["message"] = message

    def busy(self) -> bool:
        return self.status()["status"] in ("queued", "running")

    def start(self, saved_files: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        with self._lock:
            if self._state["status"] in ("queued", "running"):
                return self.status()
            self._state = {
                "status": "queued",
                "progress_pct": 0,
                "current_step": "upload",
                "message": "Queued",
                "steps": [
                    {"key": k, "label": lab, "status": "queued", "progress_pct": 0, "message": ""}
                    for k, lab in PROCESS_STEPS
                ],
                "log": [],
                "saved": list(saved_files or []),
                "background": True,
                "note": "Review stays usable while this runs.",
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "finished_at": None,
            }
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self.status()

    def _db_counts(self) -> dict[str, int]:
        out = {"videos": 0, "transcripts": 0, "faces": 0, "passes_done": 0, "passes_running": 0}
        if not self.db_path.is_file():
            return out
        try:
            conn = db_connect(self.db_path)
            conn.row_factory = sqlite3.Row

            def q(sql: str) -> int:
                try:
                    return int(conn.execute(sql).fetchone()[0])
                except sqlite3.Error:
                    return 0

            out["videos"] = q("SELECT COUNT(*) FROM videos")
            out["transcripts"] = q("SELECT COUNT(*) FROM transcript_segments")
            out["faces"] = q("SELECT COUNT(*) FROM face_appearances")
            out["passes_done"] = q(
                "SELECT COUNT(*) FROM analysis_passes WHERE status='done'"
            )
            out["passes_running"] = q(
                "SELECT COUNT(*) FROM analysis_passes WHERE status IN ('running','queued')"
            )
            conn.close()
        except sqlite3.Error:
            pass
        return out

    def _run(self) -> None:
        self._set(status="running", message="Starting")
        try:
            saved = self.status().get("saved") or []
            self._set_step(
                "upload",
                "done",
                15,
                f"{len(saved)} file(s) in sample\\" if saved else "Using existing sample\\ files",
            )
            for s in saved:
                self._append_log(f"Saved {s.get('filename')} ({s.get('bytes', 0)} bytes)")

            self._set_step("pipeline", "running", 20, "Launching process_videos.py")
            script = self.root / "scripts" / "process_videos.py"
            if not script.is_file():
                raise FileNotFoundError(
                    f"Missing {script} — keep your Desktop process_videos.py in scripts\\"
                )

            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            proc = subprocess.Popen(
                [sys.executable, "-u", str(script)],
                cwd=str(self.root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            self._append_log(f"$ {sys.executable} -u scripts\\process_videos.py")
            assert proc.stdout is not None
            baseline = self._db_counts()
            last_beat = time.time()
            for line in proc.stdout:
                self._append_log(line.rstrip())
                now = time.time()
                if now - last_beat >= 2.0:
                    last_beat = now
                    counts = self._db_counts()
                    msg = (
                        f"videos {counts['videos']} · transcripts {counts['transcripts']} · "
                        f"faces {counts['faces']} · passes done {counts['passes_done']}"
                    )
                    growth = (
                        (counts["transcripts"] - baseline["transcripts"])
                        + (counts["faces"] - baseline["faces"])
                        + (counts["passes_done"] - baseline["passes_done"])
                    )
                    pct = min(90.0, 25.0 + max(0, growth) * 2.0)
                    self._set_step("pipeline", "running", pct, msg)

            rc = proc.wait()
            if rc != 0:
                self._set_step("pipeline", "error", 90, f"process_videos exited {rc}")
                self._set(
                    status="error",
                    progress_pct=90,
                    message=f"process_videos failed (exit {rc})",
                    finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                )
                return

            self._set_step("pipeline", "done", 92, "process_videos finished")
            counts = self._db_counts()
            self._set_step(
                "verify",
                "done",
                100,
                (
                    f"videos {counts['videos']} · transcripts {counts['transcripts']} · "
                    f"faces {counts['faces']}"
                ),
            )
            self._set(
                status="done",
                progress_pct=100,
                message="Sample ingest complete — Load hits to refresh",
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            self._append_log("Done.")
        except Exception as e:  # noqa: BLE001
            self._append_log(f"ERROR: {e}")
            self._set(
                status="error",
                message=str(e),
                finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            key = self.status().get("current_step") or "pipeline"
            self._set_step(key, "error", self.status().get("progress_pct") or 0, str(e))


def safe_sample_name(filename: str) -> str:
    name = Path(filename).name.strip().replace("\x00", "")
    if not name or name in (".", ".."):
        raise ValueError("invalid filename")
    return name
