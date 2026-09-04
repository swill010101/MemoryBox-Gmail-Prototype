"""Learn-from-annotations: re-identify faces in videos using gallery exemplars.

Requires InsightFace (same stack as Desktop process_videos). Scans video frames,
matches detections to enrolled gallery centroids, writes face_appearances.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

import numpy as np

FACE_SIM_THRESHOLD = 0.38  # cosine on insightface embeddings (tuned for buffalo_l)
MAX_FRAME_SAMPLES = 80
MIN_INTERVAL_SEC = 2.0
MAX_INTERVAL_SEC = 10.0


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def ensure_face_tables(conn: sqlite3.Connection) -> None:
    """Create Phase-1-compatible tables if the Desktop DB is missing them."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_passes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER,
            engine TEXT,
            model_version TEXT,
            status TEXT,
            started_at TEXT,
            finished_at TEXT,
            message TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS face_appearances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            pass_id INTEGER,
            start_sec REAL NOT NULL,
            end_sec REAL,
            sample_frame_sec REAL,
            confidence REAL,
            bbox_json TEXT,
            embedding_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    # Soft-migrate common missing columns on older Desktop Phase-1 DBs
    ap = _cols(conn, "analysis_passes")
    for col, decl in (
        ("engine", "TEXT"),
        ("model_version", "TEXT"),
        ("status", "TEXT"),
        ("started_at", "TEXT"),
        ("finished_at", "TEXT"),
        ("message", "TEXT"),
        ("video_id", "INTEGER"),
    ):
        if col not in ap:
            try:
                conn.execute(f"ALTER TABLE analysis_passes ADD COLUMN {col} {decl}")
            except sqlite3.Error:
                pass
    fa = _cols(conn, "face_appearances")
    for col, decl in (
        ("end_sec", "REAL"),
        ("sample_frame_sec", "REAL"),
        ("bbox_json", "TEXT"),
        ("embedding_json", "TEXT"),
        ("pass_id", "INTEGER"),
        ("confidence", "REAL"),
    ):
        if col not in fa:
            try:
                conn.execute(f"ALTER TABLE face_appearances ADD COLUMN {col} {decl}")
            except sqlite3.Error:
                pass
    conn.commit()


def _insert_pass(
    conn: sqlite3.Connection,
    *,
    video_id: int,
    message: str,
) -> int:
    """Insert a learn_faces analysis pass using only columns that exist."""
    cols = _cols(conn, "analysis_passes")
    fields: dict[str, Any] = {}
    if "video_id" in cols:
        fields["video_id"] = video_id
    if "engine" in cols:
        fields["engine"] = "learn_faces"
    elif "pass_type" in cols:
        fields["pass_type"] = "learn_faces"
    elif "kind" in cols:
        fields["kind"] = "learn_faces"
    if "model_version" in cols:
        fields["model_version"] = "insightface-buffalo_l"
    if "status" in cols:
        fields["status"] = "running"
    if "started_at" in cols:
        fields["started_at"] = time_now()
    if "message" in cols:
        fields["message"] = message
    if not fields:
        # Last resort: minimal insert
        cur = conn.execute("INSERT INTO analysis_passes DEFAULT VALUES")
        return int(cur.lastrowid)
    keys = ", ".join(fields.keys())
    placeholders = ", ".join("?" for _ in fields)
    cur = conn.execute(
        f"INSERT INTO analysis_passes ({keys}) VALUES ({placeholders})",
        tuple(fields.values()),
    )
    return int(cur.lastrowid)


def _finish_pass(conn: sqlite3.Connection, pass_id: int, message: str) -> None:
    cols = _cols(conn, "analysis_passes")
    sets: list[str] = []
    vals: list[Any] = []
    if "status" in cols:
        sets.append("status=?")
        vals.append("done")
    if "finished_at" in cols:
        sets.append("finished_at=?")
        vals.append(time_now())
    if "message" in cols:
        sets.append("message=?")
        vals.append(message)
    if not sets:
        return
    vals.append(pass_id)
    conn.execute(
        f"UPDATE analysis_passes SET {', '.join(sets)} WHERE id=?",
        tuple(vals),
    )


def time_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _load_insightface():
    try:
        from insightface.app import FaceAnalysis  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "InsightFace not installed in this venv — "
            "use the same .venv as process_videos (pip install insightface onnxruntime opencv-python)"
        ) from e
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    return app


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float64).ravel()
    b = b.astype(np.float64).ravel()
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return -1.0
    return float(np.dot(a, b) / (na * nb))


def _gallery_images(conn: sqlite3.Connection, gallery_dirs: list[Path]) -> dict[int, list[Path]]:
    """person_id → image paths from gallery folders + face annotation exemplars."""
    out: dict[int, list[Path]] = {}
    people = conn.execute("SELECT id, name, gallery_path FROM people").fetchall()
    name_to_id = {str(p["name"]).lower(): int(p["id"]) for p in people}

    for p in people:
        pid = int(p["id"])
        paths: list[Path] = []
        gp = p["gallery_path"]
        candidates: list[Path] = []
        if gp:
            candidates.append(Path(gp))
        for root in gallery_dirs:
            candidates.append(Path(root) / p["name"])
        seen: set[str] = set()
        for folder in candidates:
            if not folder.is_dir():
                continue
            for img in sorted(folder.glob("*")):
                if img.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                    continue
                key = str(img.resolve()).lower()
                if key in seen:
                    continue
                seen.add(key)
                paths.append(img)
        out[pid] = paths

    # Annotation exemplars
    for r in conn.execute(
        """
        SELECT person_id, exemplar_path FROM annotations
        WHERE kind='person_face' AND revoked=0 AND exemplar_path IS NOT NULL
          AND person_id IS NOT NULL
        """
    ):
        pid = int(r["person_id"])
        path = Path(r["exemplar_path"])
        if path.is_file():
            out.setdefault(pid, [])
            key = str(path.resolve()).lower()
            if key not in {str(p.resolve()).lower() for p in out[pid]}:
                out[pid].append(path)

    # Also pick up gallery folders for people not yet in DB? sync should have run.
    _ = name_to_id
    return {k: v for k, v in out.items() if v}


def _embed_images(app, images: list[Path]) -> list[np.ndarray]:
    import cv2  # type: ignore

    embs: list[np.ndarray] = []
    for path in images:
        img = cv2.imread(str(path))
        if img is None:
            continue
        faces = app.get(img)
        if not faces:
            # Crop may already be a face — try as whole image via get anyway failed
            continue
        # Prefer largest face in the exemplar
        face = max(faces, key=lambda f: float((f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])))
        if getattr(face, "normed_embedding", None) is not None:
            embs.append(np.asarray(face.normed_embedding, dtype=np.float32))
        elif getattr(face, "embedding", None) is not None:
            e = np.asarray(face.embedding, dtype=np.float32)
            n = np.linalg.norm(e)
            embs.append(e / n if n > 1e-9 else e)
    return embs


def _person_centroids(
    app, gallery: dict[int, list[Path]]
) -> dict[int, np.ndarray]:
    centroids: dict[int, np.ndarray] = {}
    for pid, images in gallery.items():
        embs = _embed_images(app, images[:12])
        if not embs:
            continue
        mat = np.stack(embs, axis=0)
        c = mat.mean(axis=0)
        n = np.linalg.norm(c)
        centroids[pid] = (c / n) if n > 1e-9 else c
    return centroids


def _match(emb: np.ndarray, centroids: dict[int, np.ndarray]) -> tuple[int | None, float]:
    best_id = None
    best = -1.0
    for pid, c in centroids.items():
        s = _cosine(emb, c)
        if s > best:
            best = s
            best_id = pid
    if best_id is None or best < FACE_SIM_THRESHOLD:
        return None, best
    return best_id, best


def _sample_times(duration: float) -> list[float]:
    if duration <= 0 or duration != duration:
        duration = 60.0
    interval = max(MIN_INTERVAL_SEC, min(MAX_INTERVAL_SEC, duration / 40.0))
    times: list[float] = []
    t = 0.5
    while t < duration and len(times) < MAX_FRAME_SAMPLES:
        times.append(round(t, 2))
        t += interval
    if not times:
        times = [0.5]
    return times


def _insert_appearance(
    conn: sqlite3.Connection,
    *,
    video_id: int,
    person_id: int,
    pass_id: int,
    t: float,
    conf: float,
    bbox: list[float],
    emb: np.ndarray,
) -> bool:
    """Insert unless a close duplicate already exists for this video/person/time."""
    existing = conn.execute(
        """
        SELECT id FROM face_appearances
        WHERE video_id=? AND person_id=?
          AND ABS(COALESCE(sample_frame_sec, start_sec) - ?) < 1.5
        LIMIT 1
        """,
        (video_id, person_id, t),
    ).fetchone()
    if existing:
        # Bump confidence if we scored higher
        try:
            conn.execute(
                "UPDATE face_appearances SET confidence=?, pass_id=? WHERE id=?",
                (conf, pass_id, existing["id"]),
            )
        except sqlite3.Error:
            conn.execute(
                "UPDATE face_appearances SET confidence=? WHERE id=?",
                (conf, existing["id"]),
            )
        return False

    cols = _cols(conn, "face_appearances")
    fields = {
        "video_id": video_id,
        "person_id": person_id,
        "pass_id": pass_id,
        "start_sec": max(0.0, t - 0.5),
        "end_sec": t + 0.5,
        "sample_frame_sec": t,
        "confidence": conf,
        "bbox_json": json.dumps(bbox),
        "embedding_json": json.dumps(emb.astype(float).tolist()),
    }
    use = {k: v for k, v in fields.items() if k in cols}
    if "video_id" not in use or "person_id" not in use:
        return False
    if "start_sec" not in use and "start_time" in cols:
        use["start_time"] = fields["start_sec"]
    keys = ", ".join(use.keys())
    placeholders = ", ".join("?" for _ in use)
    conn.execute(
        f"INSERT INTO face_appearances ({keys}) VALUES ({placeholders})",
        tuple(use.values()),
    )
    return True


def rescan_faces(
    conn: sqlite3.Connection,
    *,
    gallery_dirs: list[Path],
    working_dir: Path,
    progress: Callable[[float, str], None] | None = None,
) -> str:
    """Embed gallery exemplars and scan all videos for matching faces."""
    from memorybox.processing.scope import deny_legacy
    deny_legacy()
    ensure_face_tables(conn)

    def prog(pct: float, msg: str) -> None:
        if progress:
            progress(pct, msg)

    prog(2, "Loading InsightFace")
    try:
        app = _load_insightface()
    except RuntimeError as e:
        return str(e)

    prog(8, "Building gallery centroids")
    gallery = _gallery_images(conn, gallery_dirs)
    if not gallery:
        return "No face exemplars in gallery — enroll a face first"
    centroids = _person_centroids(app, gallery)
    if not centroids:
        return (
            f"Found {sum(len(v) for v in gallery.values())} gallery images but could not "
            "embed faces — check crops"
        )

    videos = conn.execute(
        "SELECT id, path, filename, duration_sec FROM videos ORDER BY id"
    ).fetchall()
    if not videos:
        return "No videos in database"

    import cv2  # type: ignore

    inserted = 0
    updated = 0
    scanned = 0
    for i, v in enumerate(videos):
        path = Path(v["path"])
        pct = 10 + 85 * (i / max(len(videos), 1))
        prog(pct, f"Scanning {v['filename']}")
        if not path.is_file():
            continue
        try:
            pass_id = _insert_pass(
                conn, video_id=int(v["id"]), message=f"centroids={len(centroids)}"
            )
            conn.commit()
        except sqlite3.Error as e:
            return f"Could not create analysis_passes row: {e}"

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            _finish_pass(conn, pass_id, "could not open video")
            conn.commit()
            continue
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or 25.0
        frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = float(v["duration_sec"] or 0) or (frame_count / fps if fps else 0)
        vid_new = 0
        for t in _sample_times(duration):
            frame_idx = int(t * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_idx))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            scanned += 1
            faces = app.get(frame)
            for face in faces:
                emb = getattr(face, "normed_embedding", None)
                if emb is None:
                    emb = getattr(face, "embedding", None)
                    if emb is None:
                        continue
                    emb = np.asarray(emb, dtype=np.float32)
                    n = np.linalg.norm(emb)
                    emb = emb / n if n > 1e-9 else emb
                else:
                    emb = np.asarray(emb, dtype=np.float32)
                pid, score = _match(emb, centroids)
                if pid is None:
                    continue
                bbox = [float(x) for x in face.bbox.tolist()]
                is_new = _insert_appearance(
                    conn,
                    video_id=int(v["id"]),
                    person_id=pid,
                    pass_id=pass_id,
                    t=t,
                    conf=score,
                    bbox=bbox,
                    emb=emb,
                )
                if is_new:
                    inserted += 1
                    vid_new += 1
                else:
                    updated += 1
            # Release write lock between sample frames so Load hits can read
            conn.commit()
        cap.release()
        _finish_pass(conn, pass_id, f"new_hits={vid_new}")
        conn.commit()

    prog(100, "Face rescan done")
    names = conn.execute(
        f"SELECT name FROM people WHERE id IN ({','.join('?'*len(centroids))})",
        tuple(centroids.keys()),
    ).fetchall()
    who = ", ".join(r["name"] for r in names) or f"{len(centroids)} people"
    return (
        f"Rescanned {len(videos)} videos · {inserted} new face hits · "
        f"{updated} refreshed · gallery: {who}"
    )
