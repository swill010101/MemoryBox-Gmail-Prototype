"""
HVRT R2 Review App — evidence console + background learning.

  python scripts/review_app.py
  http://127.0.0.1:8788
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hvrt.annotations import (  # noqa: E402
    add_annotation,
    delete_exemplar,
    delete_exemplar_by_index,
    ensure_gallery_dir,
    list_people,
    list_person_exemplars,
    list_places,
    sync_people_from_gallery,
    upsert_person,
    upsert_place,
)
from hvrt.learning import LearningManager  # noqa: E402
from hvrt.schema_r2 import init_r2_schema  # noqa: E402

DEFAULT_DB = ROOT / "database" / "hvrt.sqlite"
DEFAULT_GALLERY = ROOT / "gallery"
STATIC = ROOT / "hvrt" / "static" / "review.html"
HOST = "127.0.0.1"
PORT = 8788

app = FastAPI(title="HVRT Review R2", version="0.2.0")


class MarkPlaceIn(BaseModel):
    video_id: int
    start_sec: float
    end_sec: float
    place_name: str
    address_label: str | None = None
    use_video_gps: bool = False
    save_frame: bool = True
    frame_jpeg_base64: str | None = None


class MarkDateIn(BaseModel):
    video_id: int
    start_sec: float
    end_sec: float
    date_text: str


class EnrollFaceIn(BaseModel):
    video_id: int
    start_sec: float
    end_sec: float | None = None
    person_name: str | None = None
    person_id: int | None = None
    create_person: bool = False
    crop_jpeg_base64: str = Field(..., min_length=32)


class EnrollVoiceIn(BaseModel):
    video_id: int
    start_sec: float
    end_sec: float
    person_id: int | None = None
    person_name: str | None = None


class OcrConfirmIn(BaseModel):
    video_id: int
    start_sec: float
    end_sec: float
    text: str


class DeleteExemplarIn(BaseModel):
    """Prefer index (safe). path is accepted only as a fallback with ownership check."""
    index: int | None = None
    path: str | None = None
    person_id: int | None = None


def _load_hvrt_config() -> dict[str, Any]:
    cfg_path = ROOT / "config" / "hvrt.json"
    if cfg_path.is_file():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {}


def cfg_db() -> Path:
    return Path(getattr(app.state, "db_path", DEFAULT_DB))


def cfg_working() -> Path:
    return Path(getattr(app.state, "working_dir", ROOT / "working"))


def cfg_gallery_dirs() -> list[Path]:
    dirs = getattr(app.state, "gallery_dirs", None)
    if dirs:
        return [Path(d) for d in dirs]
    return [DEFAULT_GALLERY, cfg_working() / "exemplars" / "people"]


def conn():
    return init_r2_schema(cfg_db())


def learner() -> LearningManager:
    mgr = getattr(app.state, "learner", None)
    if mgr is None:
        mgr = LearningManager(cfg_db(), cfg_working())
        app.state.learner = mgr
    return mgr


@app.on_event("startup")
def _startup() -> None:
    init_r2_schema(cfg_db())
    cfg_working().mkdir(parents=True, exist_ok=True)
    (cfg_working() / "exemplars").mkdir(parents=True, exist_ok=True)
    (cfg_working() / "exemplars" / "people").mkdir(parents=True, exist_ok=True)
    DEFAULT_GALLERY.mkdir(parents=True, exist_ok=True)
    # Sync gallery folders (Peggy/Andy/Carri/...) into people table for dropdowns
    sync_people_from_gallery(conn(), cfg_gallery_dirs())


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    path = STATIC if STATIC.is_file() else ROOT / "hvrt" / "static" / "viewer.html"
    if not path.is_file():
        raise HTTPException(404, f"UI missing: {STATIC}")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "release": "R2",
        "build": "gallery-cache-fix-8662a3d",
        "database": str(cfg_db()),
        "gallery_dirs": [str(p) for p in cfg_gallery_dirs()],
        "settings_engine": False,
        "place_recognition_engine": False,
        "decision_model": "owner>user>ai",
    }


@app.get("/api/people")
def api_people() -> dict[str, Any]:
    c = conn()
    # Sync filesystem gallery folders into DB so dropdown shows Peggy/Andy/Carri/etc.
    people = sync_people_from_gallery(c, cfg_gallery_dirs())
    out = []
    for p in people:
        # Same merge as Load hits so dropdown count matches the sidebar
        n = len(_merged_face_hits(c, person_id=int(p["id"])))
        out.append({**p, "hit_count": n})
    return {"people": out, "gallery_dirs": [str(p) for p in cfg_gallery_dirs()]}


@app.get("/api/people/{person_id}/exemplars")
def api_person_exemplars(person_id: int) -> dict[str, Any]:
    c = conn()
    person = c.execute(
        "SELECT id, name, gallery_path FROM people WHERE id=?", (person_id,)
    ).fetchone()
    if not person:
        raise HTTPException(404, "person not found")
    exemplars = list_person_exemplars(c, person_id, extra_dirs=cfg_gallery_dirs())
    # Add stable URLs for browser display (cache-bust with mtime so re-enroll
    # after Remove does not show the previous sliver from browser cache).
    for i, ex in enumerate(exemplars):
        mtime = 0
        try:
            mtime = int(Path(ex["path"]).stat().st_mtime)
        except OSError:
            pass
        ex["index"] = i
        ex["url"] = f"/api/people/{person_id}/exemplars/{i}/image?v={mtime}"
    return {
        "person": dict(person),
        "count": len(exemplars),
        "exemplars": exemplars,
    }


@app.get("/api/people/{person_id}/exemplars/{index}/image")
def api_person_exemplar_image(person_id: int, index: int):
    c = conn()
    exemplars = list_person_exemplars(c, person_id, extra_dirs=cfg_gallery_dirs())
    if index < 0 or index >= len(exemplars):
        raise HTTPException(404, "exemplar not found")
    path = Path(exemplars[index]["path"])
    if not path.is_file():
        raise HTTPException(404, f"missing file: {path}")
    media_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.delete("/api/people/{person_id}/exemplars")
def api_delete_exemplar(
    person_id: int,
    path: str | None = Query(None),
    index: int | None = Query(None),
) -> dict[str, Any]:
    c = conn()
    person = c.execute("SELECT id, name FROM people WHERE id=?", (person_id,)).fetchone()
    if not person:
        raise HTTPException(404, "person not found")
    try:
        if index is not None:
            result = delete_exemplar_by_index(
                c, person_id, index, extra_dirs=cfg_gallery_dirs()
            )
        elif path:
            result = delete_exemplar(
                c, path, person_id=person_id, extra_dirs=cfg_gallery_dirs()
            )
        else:
            raise HTTPException(400, "index or path required")
    except IndexError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    return {"ok": True, "person": dict(person), **result}


@app.post("/api/people/{person_id}/exemplars/delete")
def api_delete_exemplar_post(person_id: int, body: DeleteExemplarIn) -> dict[str, Any]:
    c = conn()
    person = c.execute("SELECT id, name FROM people WHERE id=?", (person_id,)).fetchone()
    if not person:
        raise HTTPException(404, "person not found")
    try:
        if body.index is not None:
            result = delete_exemplar_by_index(
                c, person_id, body.index, extra_dirs=cfg_gallery_dirs()
            )
        elif body.path:
            result = delete_exemplar(
                c, body.path, person_id=person_id, extra_dirs=cfg_gallery_dirs()
            )
        else:
            raise HTTPException(400, "index or path required")
    except IndexError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    return {"ok": True, "person": dict(person), **result}


@app.get("/api/places")
def api_places() -> dict[str, Any]:
    return {"places": list_places(conn())}


@app.get("/api/videos")
def api_videos() -> dict[str, Any]:
    c = conn()
    rows = c.execute(
        """
        SELECT id, filename, path, duration_sec, recording_date, file_mtime,
               gps_lat, gps_lon, camera, device
        FROM videos ORDER BY id
        """
    ).fetchall()
    return {"count": len(rows), "videos": [dict(r) for r in rows]}


@app.get("/api/hits/faces")
def hits_faces(
    name: str | None = Query(None),
    person_id: int | None = Query(None),
) -> dict[str, Any]:
    """Return owner/user face marks AND Phase-1 AI face appearances.

    One owner row in evidence_effective must not hide face_appearances.
    Prefer person_id from the Person dropdown when provided.
    """
    if person_id is None and not (name or "").strip():
        raise HTTPException(400, "person_id or name required")
    c = conn()
    hits = _merged_face_hits(
        c,
        person_id=person_id,
        name=(name or "").strip() or None,
    )
    label = name
    if person_id is not None:
        prow = c.execute("SELECT name FROM people WHERE id=?", (person_id,)).fetchone()
        if prow:
            label = prow["name"]
    eff_n = sum(1 for h in hits if str(h.get("source", "")).startswith("eff") or h.get("source") == "effective")
    fa_n = len(hits) - eff_n
    return {
        "query": label or name or str(person_id),
        "person_id": person_id,
        "count": len(hits),
        "effective_count": eff_n,
        "ai_count": fa_n,
        "hits": hits,
    }


def _ranges_overlap(
    a0: float, a1: float, b0: float, b1: float, *, pad: float = 0.75
) -> bool:
    return a0 < (b1 + pad) and b0 < (a1 + pad)


def _table_columns(c, table: str) -> set[str]:
    try:
        return {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:  # noqa: BLE001
        return set()


def _load_face_appearances(
    c,
    *,
    person_id: int | None,
    name: str | None,
) -> list[Any]:
    """Load Phase-1 AI face hits; tolerate schema drift and missing passes."""
    cols = _table_columns(c, "face_appearances")
    if not cols:
        return []

    start_col = "start_sec" if "start_sec" in cols else ("start_time" if "start_time" in cols else None)
    end_col = "end_sec" if "end_sec" in cols else ("end_time" if "end_time" in cols else None)
    if not start_col:
        return []

    end_expr = f"f.{end_col}" if end_col else f"f.{start_col}"
    has_pass = "pass_id" in cols and bool(_table_columns(c, "analysis_passes"))

    def run(where_sql: str, params: tuple[Any, ...], *, require_done_pass: bool) -> list[Any]:
        pass_join = ""
        if require_done_pass and has_pass:
            pass_join = "JOIN analysis_passes p ON p.id = f.pass_id AND p.status = 'done'"
        sql = f"""
            SELECT f.id AS hit_id, f.video_id, f.{start_col} AS start_sec,
                   {end_expr} AS end_sec, f.confidence,
                   'ai' AS actor_key, v.filename, v.path, v.duration_sec,
                   pe.name AS label, f.person_id, NULL AS annotation_id,
                   'face_appearances' AS source
            FROM face_appearances f
            JOIN people pe ON pe.id = f.person_id
            JOIN videos v ON v.id = f.video_id
            {pass_join}
            WHERE {where_sql}
            ORDER BY f.confidence DESC, v.filename, f.{start_col}
        """
        return list(c.execute(sql, params).fetchall())

    rows: list[Any] = []
    try:
        if person_id is not None:
            # Prefer done analysis passes, then fall back to all rows for that person
            rows = run("f.person_id = ?", (person_id,), require_done_pass=True)
            if not rows:
                rows = run("f.person_id = ?", (person_id,), require_done_pass=False)
        elif name:
            rows = run("pe.name = ? COLLATE NOCASE", (name,), require_done_pass=True)
            if not rows:
                rows = run("pe.name = ? COLLATE NOCASE", (name,), require_done_pass=False)
            if not rows:
                rows = run(
                    "pe.name LIKE ? COLLATE NOCASE",
                    (f"%{name}%",),
                    require_done_pass=False,
                )
    except Exception:  # noqa: BLE001
        rows = []
    return rows


def _merged_face_hits(
    c,
    *,
    name: str | None = None,
    person_id: int | None = None,
) -> list[dict[str, Any]]:
    """Merge evidence_effective face marks with Phase-1 face_appearances."""
    if person_id is None and not name:
        return []

    if person_id is not None:
        person_filter_eff = "e.person_id = ?"
        params: tuple[Any, ...] = (person_id,)
    else:
        person_filter_eff = "pe.name = ? COLLATE NOCASE"
        params = (name.strip(),)

    eff_sql = f"""
        SELECT e.id AS hit_id, e.video_id, e.start_sec, e.end_sec, e.confidence,
               e.actor_key, v.filename, v.path, v.duration_sec, pe.name AS label,
               e.person_id, e.annotation_id, 'effective' AS source
        FROM evidence_effective e
        JOIN videos v ON v.id = e.video_id
        JOIN people pe ON pe.id = e.person_id
        WHERE e.kind='person_face' AND {person_filter_eff}
        ORDER BY e.confidence DESC, v.filename, e.start_sec
    """
    eff_rows = list(c.execute(eff_sql, params).fetchall())

    if not eff_rows and name and person_id is None:
        eff_rows = list(
            c.execute(
                """
                SELECT e.id AS hit_id, e.video_id, e.start_sec, e.end_sec, e.confidence,
                       e.actor_key, v.filename, v.path, v.duration_sec, pe.name AS label,
                       e.person_id, e.annotation_id, 'effective' AS source
                FROM evidence_effective e
                JOIN videos v ON v.id = e.video_id
                JOIN people pe ON pe.id = e.person_id
                WHERE e.kind='person_face' AND pe.name LIKE ? COLLATE NOCASE
                ORDER BY e.confidence DESC, v.filename, e.start_sec
                """,
                (f"%{name.strip()}%",),
            ).fetchall()
        )

    fa_rows = _load_face_appearances(c, person_id=person_id, name=name)

    hits: list[dict[str, Any]] = []
    covered: list[tuple[int, float, float]] = []

    def add_row(r: Any, *, source_prefix: str) -> None:
        h = _hit(r, "face")
        h["hit_id"] = f"{source_prefix}:{r['hit_id']}"
        h["source"] = r["source"] if "source" in r.keys() else source_prefix
        hits.append(h)
        covered.append(
            (
                int(r["video_id"]),
                float(r["start_sec"] or 0),
                float(r["end_sec"] or r["start_sec"] or 0),
            )
        )

    for r in eff_rows:
        add_row(r, source_prefix="eff")

    for r in fa_rows:
        vid = int(r["video_id"])
        s0 = float(r["start_sec"] or 0)
        s1 = float(r["end_sec"] or s0)
        if any(vid == cv and _ranges_overlap(s0, s1, c0, c1) for cv, c0, c1 in covered):
            continue
        add_row(r, source_prefix="fa")

    hits.sort(
        key=lambda h: (
            -float(h.get("confidence") or 0),
            str(h.get("filename") or ""),
            float(h.get("start_sec") or 0),
        )
    )
    return hits


@app.get("/api/hits/places")
def hits_places(name: str = Query(..., min_length=1)) -> dict[str, Any]:
    c = conn()
    rows = c.execute(
        """
        SELECT e.id AS hit_id, e.video_id, e.start_sec, e.end_sec, e.confidence,
               e.actor_key, v.filename, v.path, v.duration_sec,
               COALESCE(pl.name, e.label_text) AS label, e.place_id, e.annotation_id
        FROM evidence_effective e
        JOIN videos v ON v.id = e.video_id
        LEFT JOIN places pl ON pl.id = e.place_id
        WHERE e.kind='place' AND (
            pl.name LIKE ? COLLATE NOCASE OR e.label_text LIKE ? COLLATE NOCASE
        )
        ORDER BY e.confidence DESC, v.filename, e.start_sec
        """,
        (f"%{name}%", f"%{name}%"),
    ).fetchall()
    # GPS whole-video proximity for named places with coords
    gps_hits = []
    place = c.execute(
        "SELECT * FROM places WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
        (f"%{name}%",),
    ).fetchone()
    if place and place["lat"] is not None and place["lon"] is not None:
        # rough degree radius from meters (~111km per degree lat)
        deg = float(place["radius_m"] or 100) / 111_000.0
        vids = c.execute(
            """
            SELECT id, filename, path, duration_sec, gps_lat, gps_lon
            FROM videos
            WHERE gps_lat IS NOT NULL AND gps_lon IS NOT NULL
              AND ABS(gps_lat - ?) <= ? AND ABS(gps_lon - ?) <= ?
            """,
            (place["lat"], deg, place["lon"], deg),
        ).fetchall()
        for v in vids:
            gps_hits.append(
                {
                    "kind": "place_gps",
                    "hit_id": f"gps-{v['id']}",
                    "video_id": v["id"],
                    "filename": v["filename"],
                    "path": v["path"],
                    "start_sec": 0.0,
                    "end_sec": float(v["duration_sec"] or 0),
                    "confidence": 1.0,
                    "duration_sec": v["duration_sec"],
                    "label": place["name"],
                    "actor_key": "owner",
                    "stream_url": f"/api/media/{v['id']}",
                    "note": "Whole-video GPS near place pin",
                }
            )
    hits = [_hit(r, "place") for r in rows] + gps_hits
    return {"query": name, "count": len(hits), "hits": hits}


@app.get("/api/hits/text")
def hits_text(q: str = Query(..., min_length=1)) -> dict[str, Any]:
    c = conn()
    try:
        rows = c.execute(
            """
            SELECT s.id AS hit_id, s.video_id, s.start_sec, s.end_sec, s.confidence,
                   'ai' AS actor_key, v.filename, v.path, v.duration_sec,
                   s.text AS label, NULL AS annotation_id
            FROM transcript_segments s
            JOIN videos v ON v.id = s.video_id
            WHERE s.text LIKE ? COLLATE NOCASE
            ORDER BY v.filename, s.start_sec
            """,
            (f"%{q}%",),
        ).fetchall()
    except Exception:  # noqa: BLE001
        rows = []
    return {"query": q, "count": len(rows), "hits": [_hit(r, "text") for r in rows]}


def _hit(r: Any, kind: str) -> dict[str, Any]:
    start = float(r["start_sec"] or 0)
    return {
        "kind": kind,
        "hit_id": r["hit_id"],
        "video_id": r["video_id"],
        "filename": r["filename"],
        "path": r["path"],
        "start_sec": start,
        "end_sec": float(r["end_sec"] or start),
        "confidence": r["confidence"],
        "duration_sec": r["duration_sec"],
        "label": r["label"] if "label" in r.keys() else None,
        "actor_key": r["actor_key"] if "actor_key" in r.keys() else None,
        "annotation_id": r["annotation_id"] if "annotation_id" in r.keys() else None,
        "stream_url": f"/api/media/{r['video_id']}",
    }


@app.get("/api/media/{video_id}")
def stream_media(video_id: int, request: Request):
    c = conn()
    row = c.execute(
        "SELECT path, filename FROM videos WHERE id=?", (video_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "video not found")
    path = Path(row["path"])
    if not path.is_file():
        raise HTTPException(404, f"missing file: {path}")
    media_type = mimetypes.guess_type(str(path))[0] or "video/mp4"
    file_size = path.stat().st_size
    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(
            path,
            media_type=media_type,
            filename=row["filename"],
            headers={"Accept-Ranges": "bytes"},
        )
    units, _, rng = range_header.partition("=")
    if units.strip() != "bytes":
        raise HTTPException(416, "Only bytes ranges supported")
    start_s, _, end_s = rng.partition("-")
    start = int(start_s) if start_s else 0
    end = int(end_s) if end_s else file_size - 1
    end = min(end, file_size - 1)
    length = end - start + 1

    def iter_range():
        with path.open("rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                data = f.read(min(1024 * 1024, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        iter_range(),
        status_code=206,
        media_type=media_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        },
    )


def _save_b64_jpeg(data_b64: str, dest: Path) -> Path:
    raw = data_b64.split(",", 1)[-1]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(base64.b64decode(raw))
    return dest


@app.post("/api/annotations/place")
def mark_place(body: MarkPlaceIn) -> dict[str, Any]:
    c = conn()
    v = c.execute("SELECT * FROM videos WHERE id=?", (body.video_id,)).fetchone()
    if not v:
        raise HTTPException(404, "video not found")
    lat = lon = None
    if body.use_video_gps:
        lat, lon = v["gps_lat"], v["gps_lon"]
    gallery = ensure_gallery_dir(cfg_working() / "exemplars", "places", body.place_name)
    place_id = upsert_place(
        c,
        body.place_name,
        address_label=body.address_label,
        lat=lat,
        lon=lon,
        gallery_path=str(gallery),
        actor_key="owner",
    )
    exemplar = None
    if body.save_frame and body.frame_jpeg_base64:
        exemplar = str(
            _save_b64_jpeg(
                body.frame_jpeg_base64,
                gallery / f"frame_{body.video_id}_{int(body.start_sec)}_{uuid.uuid4().hex[:8]}.jpg",
            )
        )
    ann_id = add_annotation(
        c,
        video_id=body.video_id,
        kind="place",
        start_sec=body.start_sec,
        end_sec=body.end_sec,
        actor_key="owner",
        label_text=body.place_name,
        place_id=place_id,
        exemplar_path=exemplar,
        provenance={"use_video_gps": body.use_video_gps},
    )
    return {"annotation_id": ann_id, "place_id": place_id, "confidence": 1.0}


@app.post("/api/annotations/date")
def mark_date(body: MarkDateIn) -> dict[str, Any]:
    ann_id = add_annotation(
        conn(),
        video_id=body.video_id,
        kind="date",
        start_sec=body.start_sec,
        end_sec=body.end_sec,
        actor_key="owner",
        label_text=body.date_text.strip(),
        payload={"date_text": body.date_text.strip()},
    )
    return {"annotation_id": ann_id, "confidence": 1.0}


@app.post("/api/annotations/face")
def enroll_face(body: EnrollFaceIn) -> dict[str, Any]:
    c = conn()
    name = (body.person_name or "").strip()
    person_id = body.person_id
    primary_gallery = cfg_gallery_dirs()[0]

    if body.create_person:
        if not name:
            raise HTTPException(400, "person_name required to create")
        existing = c.execute(
            "SELECT id, name FROM people WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if existing:
            raise HTTPException(
                409,
                f"Person '{existing['name']}' already exists — pick from dropdown",
            )
        person_id = upsert_person(c, name, str((primary_gallery / name).resolve()))
    elif person_id is not None:
        prow = c.execute(
            "SELECT name, gallery_path FROM people WHERE id=?", (person_id,)
        ).fetchone()
        if not prow:
            raise HTTPException(404, "person_id not found")
        name = prow["name"]
        upsert_person(c, name, str((primary_gallery / name).resolve()))
    elif name:
        row = c.execute(
            "SELECT id, name, gallery_path FROM people WHERE name = ? COLLATE NOCASE",
            (name,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Person not found — enable create or pick dropdown")
        person_id = int(row["id"])
        name = row["name"]
        upsert_person(c, name, str((primary_gallery / name).resolve()))
    else:
        raise HTTPException(400, "person_id or person_name required")

    # Always save into gallery/<PersonName>/ — never a stale/wrong gallery_path
    gallery = primary_gallery / name
    gallery.mkdir(parents=True, exist_ok=True)
    dest = gallery / f"face_{body.video_id}_{int(body.start_sec)}_{uuid.uuid4().hex[:8]}.jpg"
    exemplar = str(_save_b64_jpeg(body.crop_jpeg_base64, dest))
    # Sanity: refuse empty/tiny writes so a bad crop cannot silently land
    if Path(exemplar).stat().st_size < 500:
        Path(exemplar).unlink(missing_ok=True)
        raise HTTPException(400, "Crop image was empty — box the face again")
    end = body.end_sec if body.end_sec is not None else body.start_sec + 1.0
    ann_id = add_annotation(
        c,
        video_id=body.video_id,
        kind="person_face",
        start_sec=body.start_sec,
        end_sec=end,
        actor_key="owner",
        label_text=name,
        person_id=person_id,
        exemplar_path=exemplar,
        payload={"enroll": True, "bytes": Path(exemplar).stat().st_size},
    )
    return {
        "annotation_id": ann_id,
        "person_id": person_id,
        "person_name": name,
        "exemplar_path": exemplar,
        "exemplar_filename": Path(exemplar).name,
        "confidence": 1.0,
    }


@app.post("/api/annotations/voice")
def enroll_voice(body: EnrollVoiceIn) -> dict[str, Any]:
    c = conn()
    person_id = body.person_id
    name = (body.person_name or "").strip()
    if person_id is None:
        if not name:
            raise HTTPException(400, "person required")
        person_id = upsert_person(c, name)
        name_row = c.execute("SELECT name FROM people WHERE id=?", (person_id,)).fetchone()
        name = name_row["name"]
    else:
        name_row = c.execute("SELECT name FROM people WHERE id=?", (person_id,)).fetchone()
        if not name_row:
            raise HTTPException(404, "person not found")
        name = name_row["name"]

    # Span marker; audio extract can be filled by learning job / ffmpeg later
    stub = cfg_working() / "exemplars" / "voice" / f"person_{person_id}"
    stub.mkdir(parents=True, exist_ok=True)
    marker = stub / f"span_{body.video_id}_{int(body.start_sec)}_{int(body.end_sec)}.json"
    marker.write_text(
        json.dumps(
            {
                "video_id": body.video_id,
                "start_sec": body.start_sec,
                "end_sec": body.end_sec,
                "person_id": person_id,
            }
        ),
        encoding="utf-8",
    )
    ann_id = add_annotation(
        c,
        video_id=body.video_id,
        kind="person_voice",
        start_sec=body.start_sec,
        end_sec=body.end_sec,
        actor_key="owner",
        label_text=name,
        person_id=person_id,
        exemplar_path=str(marker),
        payload={"voice_enroll": True},
    )
    c.execute(
        """
        INSERT INTO voice_samples (person_id, video_id, annotation_id, path, start_sec, end_sec, actor_key)
        VALUES (?,?,?,?,?,?, 'owner')
        """,
        (person_id, body.video_id, ann_id, str(marker), body.start_sec, body.end_sec),
    )
    c.commit()
    return {"annotation_id": ann_id, "person_id": person_id, "confidence": 1.0}


@app.post("/api/annotations/ocr")
def confirm_ocr(body: OcrConfirmIn) -> dict[str, Any]:
    ann_id = add_annotation(
        conn(),
        video_id=body.video_id,
        kind="ocr",
        start_sec=body.start_sec,
        end_sec=body.end_sec,
        actor_key="owner",
        label_text=body.text.strip(),
        payload={"text": body.text.strip()},
    )
    return {"annotation_id": ann_id, "confidence": 1.0}


@app.get("/api/annotations")
def list_annotations(video_id: int | None = None) -> dict[str, Any]:
    c = conn()
    if video_id is None:
        rows = c.execute(
            "SELECT * FROM annotations WHERE revoked=0 ORDER BY id DESC LIMIT 200"
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM annotations WHERE revoked=0 AND video_id=? ORDER BY start_sec",
            (video_id,),
        ).fetchall()
    return {"count": len(rows), "annotations": [dict(r) for r in rows]}


@app.post("/api/learn/start")
def learn_start() -> dict[str, Any]:
    return learner().start()


@app.get("/api/learn/status")
def learn_status() -> dict[str, Any]:
    st = learner().active_run()
    return st or {"status": "idle", "steps": [], "background": True}


def main() -> None:
    parser = argparse.ArgumentParser(description="HVRT R2 Review App")
    parser.add_argument("--db", default=None)
    parser.add_argument("--working", default=None)
    parser.add_argument("--gallery", default=None, help="Primary face gallery dir")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    file_cfg = _load_hvrt_config()
    db_path = Path(args.db or file_cfg.get("database_path") or DEFAULT_DB)
    working = Path(args.working or file_cfg.get("working_dir") or (ROOT / "working"))
    gallery = Path(args.gallery or file_cfg.get("gallery_dir") or DEFAULT_GALLERY)
    host = args.host or file_cfg.get("api", {}).get("host", HOST)
    # Review UI stays on 8788 by default so it doesn't collide with run_api.py (8787).
    port = int(args.port or file_cfg.get("api", {}).get("review_port") or PORT)

    app.state.db_path = db_path
    app.state.working_dir = working
    app.state.gallery_dirs = [gallery, working / "exemplars" / "people"]
    app.state.learner = LearningManager(db_path, working)
    init_r2_schema(db_path)
    gallery.mkdir(parents=True, exist_ok=True)
    (working / "exemplars" / "people").mkdir(parents=True, exist_ok=True)
    sync_people_from_gallery(conn(), app.state.gallery_dirs)

    print(f"HVRT Review R2   http://{host}:{port}")
    print(f"Database         {db_path}")
    print(f"Gallery dirs     {app.state.gallery_dirs}")
    print("Settings engine  disabled (placeholder)")
    print("Place recognition disabled (annotate/exemplars only)")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
