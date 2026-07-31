"""Background learning job — scan new owner annotations; update galleries.

No auto place-recognition engine. Places step only indexes saved exemplars.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

STEPS = [
    ("rescoring", "Rebuild effective evidence"),
    ("faces_gallery", "Update face gallery from exemplars"),
    ("voice_gallery", "Index voice enrollments"),
    ("places_gallery", "Index place exemplars (no recognition)"),
    ("ocr_lexicon", "Refresh OCR confirm lexicon"),
]


class LearningManager:
    def __init__(self, db_path: Path | str, working_dir: Path | str) -> None:
        self.db_path = Path(db_path)
        self.working_dir = Path(working_dir)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def active_run(self) -> dict[str, Any] | None:
        conn = self.connect()
        row = conn.execute(
            """
            SELECT * FROM learning_runs
            WHERE status IN ('queued','running')
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
        if not row:
            latest = conn.execute(
                "SELECT * FROM learning_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return self._run_dict(conn, latest) if latest else None
        return self._run_dict(conn, row)

    def start(self) -> dict[str, Any]:
        with self._lock:
            cur = self.active_run()
            if cur and cur["status"] in ("queued", "running"):
                return cur
            conn = self.connect()
            run_id = conn.execute(
                """
                INSERT INTO learning_runs (status, progress_pct, current_step, steps_json)
                VALUES ('queued', 0, ?, ?)
                """,
                (STEPS[0][0], json.dumps([{"key": k, "label": lab} for k, lab in STEPS])),
            ).lastrowid
            for key, label in STEPS:
                conn.execute(
                    """
                    INSERT INTO learning_run_steps (run_id, step_key, label, status)
                    VALUES (?,?,?,'queued')
                    """,
                    (run_id, key, label),
                )
            conn.commit()
            self._thread = threading.Thread(
                target=self._run, args=(int(run_id),), daemon=True
            )
            self._thread.start()
            return self._run_dict(conn, conn.execute(
                "SELECT * FROM learning_runs WHERE id=?", (run_id,)
            ).fetchone())

    def _run_dict(self, conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        steps = conn.execute(
            "SELECT step_key, label, status, progress_pct, message FROM learning_run_steps "
            "WHERE run_id=? ORDER BY id",
            (row["id"],),
        ).fetchall()
        return {
            "id": row["id"],
            "status": row["status"],
            "progress_pct": row["progress_pct"],
            "current_step": row["current_step"],
            "message": row["message"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "steps": [dict(s) for s in steps],
            "background": True,
            "note": "You can keep reviewing while this runs.",
        }

    def _set_step(
        self,
        conn: sqlite3.Connection,
        run_id: int,
        key: str,
        status: str,
        pct: float,
        message: str | None = None,
    ) -> None:
        if status == "running":
            conn.execute(
                """
                UPDATE learning_run_steps SET status=?, progress_pct=?, message=?,
                    started_at=COALESCE(started_at, datetime('now'))
                WHERE run_id=? AND step_key=?
                """,
                (status, pct, message, run_id, key),
            )
        else:
            conn.execute(
                """
                UPDATE learning_run_steps SET status=?, progress_pct=?, message=?,
                    finished_at=datetime('now')
                WHERE run_id=? AND step_key=?
                """,
                (status, pct, message, run_id, key),
            )
        done = conn.execute(
            "SELECT COUNT(*) AS c FROM learning_run_steps WHERE run_id=? AND status='done'",
            (run_id,),
        ).fetchone()["c"]
        overall = 100.0 * done / max(len(STEPS), 1)
        if status == "running":
            overall = 100.0 * (done + pct / 100.0) / max(len(STEPS), 1)
        conn.execute(
            """
            UPDATE learning_runs SET status='running', progress_pct=?, current_step=?,
                message=?, started_at=COALESCE(started_at, datetime('now'))
            WHERE id=?
            """,
            (overall, key, message, run_id),
        )
        conn.commit()

    def _run(self, run_id: int) -> None:
        conn = self.connect()
        try:
            handlers: dict[str, Callable[[sqlite3.Connection, int], str]] = {
                "rescoring": self._step_rescoring,
                "faces_gallery": self._step_faces,
                "voice_gallery": self._step_voice,
                "places_gallery": self._step_places,
                "ocr_lexicon": self._step_ocr,
            }
            for key, _label in STEPS:
                self._set_step(conn, run_id, key, "running", 5, "starting")
                time.sleep(0.15)  # yield so UI can poll
                msg = handlers[key](conn, run_id)
                self._set_step(conn, run_id, key, "done", 100, msg)
            conn.execute(
                """
                UPDATE learning_runs SET status='done', progress_pct=100,
                    current_step=NULL, message='Learning complete',
                    finished_at=datetime('now')
                WHERE id=?
                """,
                (run_id,),
            )
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            conn.execute(
                """
                UPDATE learning_runs SET status='error', message=?,
                    finished_at=datetime('now')
                WHERE id=?
                """,
                (str(exc), run_id),
            )
            conn.commit()

    def _step_rescoring(self, conn: sqlite3.Connection, run_id: int) -> str:
        from hvrt.rescoring import rebuild_effective_evidence

        self._set_step(conn, run_id, "rescoring", "running", 40, "rebuilding")
        n = rebuild_effective_evidence(conn)
        return f"{n} effective evidence rows"

    def _step_faces(self, conn: sqlite3.Connection, run_id: int) -> str:
        self._set_step(conn, run_id, "faces_gallery", "running", 30, "scanning exemplars")
        rows = conn.execute(
            """
            SELECT id, person_id, exemplar_path FROM annotations
            WHERE kind='person_face' AND revoked=0 AND actor_key IN ('owner','user')
              AND exemplar_path IS NOT NULL
            """
        ).fetchall()
        # Index only — Phase-1 face re-embed is optional if insightface present
        counted = 0
        for r in rows:
            if r["exemplar_path"] and Path(r["exemplar_path"]).is_file():
                counted += 1
        self._set_step(
            conn, run_id, "faces_gallery", "running", 80, f"{counted} face files"
        )
        return f"Indexed {counted} owner face exemplars (recognition re-run optional)"

    def _step_voice(self, conn: sqlite3.Connection, run_id: int) -> str:
        self._set_step(conn, run_id, "voice_gallery", "running", 50, "indexing")
        n = conn.execute("SELECT COUNT(*) AS c FROM voice_samples").fetchone()["c"]
        return f"{n} voice samples on file (diarization bind later)"

    def _step_places(self, conn: sqlite3.Connection, run_id: int) -> str:
        """Exemplars only — no place recognition engine."""
        self._set_step(conn, run_id, "places_gallery", "running", 40, "exemplars only")
        rows = conn.execute(
            """
            SELECT exemplar_path FROM annotations
            WHERE kind='place' AND revoked=0 AND exemplar_path IS NOT NULL
            """
        ).fetchall()
        n = sum(1 for r in rows if r["exemplar_path"] and Path(r["exemplar_path"]).is_file())
        return f"{n} place exemplars stored (recognition deferred)"

    def _step_ocr(self, conn: sqlite3.Connection, run_id: int) -> str:
        self._set_step(conn, run_id, "ocr_lexicon", "running", 50, "lexicon")
        n = conn.execute(
            """
            SELECT COUNT(*) AS c FROM annotations
            WHERE kind='ocr' AND revoked=0 AND actor_key IN ('owner','user')
            """
        ).fetchone()["c"]
        return f"{n} human-confirmed OCR strings"
