"""
Live watcher for HVRT video processing.

Run this in a **second** PowerShell window while `process_videos.py` is busy:

  cd C:\\memorybox\\hvrt
  .\\.venv\\Scripts\\Activate.ps1
  python scripts\\process_status.py

Refreshes every 2 seconds from hvrt.sqlite (analysis_passes + videos + transcripts + faces).
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "database" / "hvrt.sqlite"


def connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def count(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    try:
        return int(conn.execute(sql, params).fetchone()[0])
    except sqlite3.Error:
        return -1


def snapshot(conn: sqlite3.Connection) -> dict:
    out: dict = {
        "videos": count(conn, "SELECT COUNT(*) FROM videos") if table_exists(conn, "videos") else 0,
        "passes": [],
        "pass_status": {},
        "transcripts": 0,
        "faces": 0,
        "latest": None,
    }
    if table_exists(conn, "transcript_segments"):
        out["transcripts"] = count(conn, "SELECT COUNT(*) FROM transcript_segments")
    if table_exists(conn, "face_appearances"):
        out["faces"] = count(conn, "SELECT COUNT(*) FROM face_appearances")

    if table_exists(conn, "analysis_passes"):
        # Discover columns
        cols = {r[1] for r in conn.execute("PRAGMA table_info(analysis_passes)")}
        status_col = "status" if "status" in cols else None
        if status_col:
            for r in conn.execute(
                f"SELECT {status_col} AS status, COUNT(*) AS c FROM analysis_passes GROUP BY 1"
            ):
                out["pass_status"][r["status"] or "(null)"] = r["c"]
        # Latest rows
        order = "id DESC" if "id" in cols else "rowid DESC"
        select_bits = ["*"]
        try:
            rows = conn.execute(
                f"SELECT * FROM analysis_passes ORDER BY {order} LIMIT 8"
            ).fetchall()
            out["passes"] = [dict(r) for r in rows]
            if rows:
                out["latest"] = dict(rows[0])
        except sqlite3.Error:
            out["passes"] = []
    return out


def fmt_pass(p: dict) -> str:
    engine = p.get("engine") or p.get("kind") or p.get("pass_type") or "?"
    status = p.get("status") or "?"
    vid = p.get("video_id") or p.get("video") or ""
    fn = p.get("filename") or ""
    model = p.get("model_version") or ""
    bits = [f"{engine}", f"status={status}"]
    if vid != "":
        bits.append(f"video_id={vid}")
    if fn:
        bits.append(str(fn)[:40])
    if model:
        bits.append(str(model)[:24])
    return " · ".join(bits)


def render(db: Path, snap: dict, tick: int) -> None:
    # Clear-ish screen without requiring colorama
    sys.stdout.write("\033[H\033[J" if sys.stdout.isatty() else "\n" + "=" * 60 + "\n")
    print(f"HVRT process status  (refresh #{tick})  {time.strftime('%H:%M:%S')}")
    print(f"DB: {db}")
    print()
    print(f"  Videos indexed     : {snap['videos']}")
    print(f"  Transcript lines   : {snap['transcripts']}")
    print(f"  Face appearances   : {snap['faces']}")
    if snap["pass_status"]:
        print("  Analysis passes    :")
        for k, v in sorted(snap["pass_status"].items()):
            print(f"      {k:12} {v}")
    else:
        print("  Analysis passes    : (table missing or empty — pipeline may still be starting)")
    print()
    print("  Recent passes:")
    if not snap["passes"]:
        print("      (none yet — if CPU is busy, metadata/whisper may not have written a row)")
    for p in snap["passes"]:
        print(f"      - {fmt_pass(p)}")
    print()
    print("  Tip: high Python CPU ≈ working. Leave process_videos.py alone until it prints Done.")
    print("  Ctrl+C stops this watcher only (not the processor).")
    sys.stdout.flush()


def main() -> int:
    ap = argparse.ArgumentParser(description="Watch HVRT process_videos progress via SQLite")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--interval", type=float, default=2.0)
    args = ap.parse_args()
    db = args.db
    if not db.is_file():
        print(f"Database not found yet: {db}")
        print("Start process_videos.py first, or pass --db path")
        return 1

    tick = 0
    print(f"Watching {db} every {args.interval}s …")
    try:
        while True:
            tick += 1
            conn = connect(db)
            try:
                snap = snapshot(conn)
            finally:
                conn.close()
            render(db, snap, tick)
            time.sleep(max(0.5, args.interval))
    except KeyboardInterrupt:
        print("\nWatcher stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
