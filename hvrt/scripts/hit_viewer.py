"""HVRT Hit Viewer — light local UI to pick evidence hits and play video.

Reads hvrt.sqlite (same DB as the pipeline). Serves video bytes over HTTP
so the browser can seek to start_sec. Original files stay read-only.

  cd C:\\memorybox\\hvrt
  .\\.venv\\Scripts\\Activate.ps1
  python scripts\\hit_viewer.py
  # open http://127.0.0.1:8788
"""
from __future__ import annotations

import argparse
import mimetypes
import sqlite3
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "database" / "hvrt.sqlite"
STATIC = ROOT / "hvrt" / "static" / "viewer.html"
HOST = "127.0.0.1"
PORT = 8788

app = FastAPI(title="HVRT Hit Viewer", version="0.1.0")


def _db_path() -> Path:
    return Path(getattr(app.state, "db_path", DEFAULT_DB))


def connect() -> sqlite3.Connection:
    path = _db_path()
    if not path.is_file():
        raise HTTPException(404, f"Database not found: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    if STATIC.is_file():
        return HTMLResponse(STATIC.read_text(encoding="utf-8"))
    raise HTTPException(404, f"Missing UI file: {STATIC}")


@app.get("/api/people")
def list_people():
    conn = connect()
    rows = conn.execute(
        """
        SELECT pe.id, pe.name, COUNT(f.id) AS hit_count
        FROM people pe
        LEFT JOIN face_appearances f ON f.person_id = pe.id
        LEFT JOIN analysis_passes p ON p.id = f.pass_id AND p.status = 'done'
        GROUP BY pe.id
        ORDER BY pe.name COLLATE NOCASE
        """
    ).fetchall()
    return {
        "people": [
            {"id": r["id"], "name": r["name"], "hit_count": r["hit_count"]}
            for r in rows
        ]
    }


@app.get("/api/hits/faces")
def face_hits(name: str = Query(..., min_length=1)):
    conn = connect()
    rows = conn.execute(
        """
        SELECT f.id AS hit_id, f.video_id, f.start_sec, f.end_sec, f.confidence,
               f.sample_frame_sec, v.filename, v.path, v.duration_sec,
               pe.name AS person_name, p.model_version, p.finished_at
        FROM face_appearances f
        JOIN people pe ON pe.id = f.person_id
        JOIN videos v ON v.id = f.video_id
        JOIN analysis_passes p ON p.id = f.pass_id AND p.status = 'done'
        WHERE pe.name LIKE ? COLLATE NOCASE
        ORDER BY f.confidence DESC, v.filename, f.start_sec
        """,
        (f"%{name}%",),
    ).fetchall()
    return {
        "query": name,
        "count": len(rows),
        "hits": [_hit_dict(r, kind="face") for r in rows],
    }


@app.get("/api/hits/text")
def text_hits(q: str = Query(..., min_length=1)):
    conn = connect()
    rows = conn.execute(
        """
        SELECT s.id AS hit_id, s.video_id, s.start_sec, s.end_sec, s.confidence,
               s.text AS label, v.filename, v.path, v.duration_sec,
               p.model_version, p.finished_at
        FROM transcript_segments s
        JOIN videos v ON v.id = s.video_id
        JOIN analysis_passes p ON p.id = s.pass_id AND p.status = 'done'
        WHERE s.text LIKE ? COLLATE NOCASE
        ORDER BY v.filename, s.start_sec
        """,
        (f"%{q}%",),
    ).fetchall()
    return {
        "query": q,
        "count": len(rows),
        "hits": [_hit_dict(r, kind="text") for r in rows],
    }


def _hit_dict(r: sqlite3.Row, *, kind: str) -> dict:
    start = float(r["start_sec"] or 0)
    d = {
        "kind": kind,
        "hit_id": r["hit_id"],
        "video_id": r["video_id"],
        "filename": r["filename"],
        "path": r["path"],
        "start_sec": start,
        "end_sec": float(r["end_sec"] or start),
        "confidence": r["confidence"],
        "duration_sec": r["duration_sec"],
        "model_version": r["model_version"],
        "processed_at": r["finished_at"],
        "stream_url": f"/api/media/{r['video_id']}",
    }
    if kind == "face":
        d["person_name"] = r["person_name"]
        d["label"] = r["person_name"]
        d["sample_frame_sec"] = r["sample_frame_sec"]
    else:
        d["label"] = r["label"]
    return d


@app.get("/api/media/{video_id}")
def stream_media(video_id: int, request: Request):
    """Stream original video read-only (supports Range for seeking)."""
    conn = connect()
    row = conn.execute(
        "SELECT path, filename FROM videos WHERE id = ?", (video_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "video not found")
    path = Path(row["path"])
    if not path.is_file():
        raise HTTPException(404, f"video file missing on disk: {path}")

    media_type = mimetypes.guess_type(str(path))[0] or "video/mp4"
    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        # bytes=start-end
        units, _, rng = range_header.partition("=")
        if units.strip() != "bytes":
            raise HTTPException(416, "Only bytes ranges supported")
        start_s, _, end_s = rng.partition("-")
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else file_size - 1
        end = min(end, file_size - 1)
        if start > end:
            raise HTTPException(416, "Invalid range")
        length = end - start + 1

        def iter_range():
            with path.open("rb") as f:
                f.seek(start)
                remaining = length
                chunk = 1024 * 1024
                while remaining > 0:
                    data = f.read(min(chunk, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        }
        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=media_type,
            headers=headers,
        )

    return FileResponse(
        path,
        media_type=media_type,
        filename=row["filename"],
        headers={"Accept-Ranges": "bytes"},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="HVRT hit viewer UI")
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="Path to hvrt.sqlite",
    )
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    app.state.db_path = Path(args.db)
    print(f"HVRT Hit Viewer  http://{args.host}:{args.port}")
    print(f"Database         {app.state.db_path}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
