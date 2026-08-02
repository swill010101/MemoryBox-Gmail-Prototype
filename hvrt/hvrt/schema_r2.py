"""HVRT R2 schema — annotations, places, decision model, learning jobs.

Safe to apply beside Phase 1 tables (videos, people, faces, transcripts, …).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

R2_SCHEMA_SQL = """
PRAGMA foreign_keys=ON;

-- Actor ranks: owner > user > ai (multi-user auth deferred; ranks still stored)
CREATE TABLE IF NOT EXISTS actors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    rank INTEGER NOT NULL,
    CHECK (rank >= 1)
);

INSERT OR IGNORE INTO actors (key, display_name, rank) VALUES
    ('owner', 'Owner', 3),
    ('user', 'User', 2),
    ('ai', 'AI', 1);

CREATE TABLE IF NOT EXISTS places (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    address_label TEXT,
    lat REAL,
    lon REAL,
    radius_m REAL NOT NULL DEFAULT 100.0,
    gallery_path TEXT,
    created_by_actor TEXT NOT NULL DEFAULT 'owner',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN (
        'place','person_face','person_voice','ocr','date','setting_placeholder'
    )),
    start_sec REAL NOT NULL,
    end_sec REAL NOT NULL,
    label_text TEXT,
    place_id INTEGER REFERENCES places(id) ON DELETE SET NULL,
    person_id INTEGER,
    payload_json TEXT,
    actor_key TEXT NOT NULL DEFAULT 'owner',
    confidence REAL NOT NULL,
    provenance_json TEXT,
    supersedes_id INTEGER REFERENCES annotations(id) ON DELETE SET NULL,
    exemplar_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    revoked INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ann_video ON annotations(video_id, start_sec);
CREATE INDEX IF NOT EXISTS idx_ann_kind ON annotations(kind, revoked);
CREATE INDEX IF NOT EXISTS idx_ann_place ON annotations(place_id);
CREATE INDEX IF NOT EXISTS idx_ann_person ON annotations(person_id);

-- Effective evidence after Owner>User>AI rescoring (materialized for search)
CREATE TABLE IF NOT EXISTS evidence_effective (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    start_sec REAL NOT NULL,
    end_sec REAL NOT NULL,
    label_text TEXT,
    place_id INTEGER,
    person_id INTEGER,
    annotation_id INTEGER NOT NULL UNIQUE REFERENCES annotations(id) ON DELETE CASCADE,
    actor_key TEXT NOT NULL,
    confidence REAL NOT NULL,
    decision_json TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_eff_video ON evidence_effective(video_id);
CREATE INDEX IF NOT EXISTS idx_eff_kind ON evidence_effective(kind);
CREATE INDEX IF NOT EXISTS idx_eff_place ON evidence_effective(place_id);
CREATE INDEX IF NOT EXISTS idx_eff_person ON evidence_effective(person_id);

CREATE TABLE IF NOT EXISTS decision_model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    version TEXT NOT NULL,
    rules_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO decision_model (name, version, rules_json) VALUES (
    'hvrt_rescoring',
    '1.0',
    '{"ranks":{"owner":3,"user":2,"ai":1},"human_confirm_confidence":1.0,"human_supersedes_ai":true,"human_supersedes_human":true,"owner_is_king":true}'
);

CREATE TABLE IF NOT EXISTS learning_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL CHECK (status IN (
        'queued','running','done','error','cancelled'
    )),
    progress_pct REAL NOT NULL DEFAULT 0,
    current_step TEXT,
    steps_json TEXT,
    message TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS learning_run_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES learning_runs(id) ON DELETE CASCADE,
    step_key TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'queued','running','done','error','skipped'
    )),
    progress_pct REAL NOT NULL DEFAULT 0,
    message TEXT,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS voice_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL,
    video_id INTEGER,
    annotation_id INTEGER REFERENCES annotations(id) ON DELETE SET NULL,
    path TEXT NOT NULL,
    start_sec REAL,
    end_sec REAL,
    actor_key TEXT NOT NULL DEFAULT 'owner',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open SQLite with WAL + busy timeout so Learn/process can write while review reads."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()
        if mode and str(mode[0]).lower() == "wal":
            conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.Error:
        pass
    return conn


def init_r2_schema(db_path: Path | str) -> sqlite3.Connection:
    """Create/migrate R2 tables. Call at process startup — not on every request."""
    conn = connect(db_path)
    conn.executescript(R2_SCHEMA_SQL)
    # Ensure Phase-1 people table exists for FK-less person_id usage
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            gallery_path TEXT,
            embedding_json TEXT,
            enrolled_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            filename TEXT NOT NULL,
            content_hash TEXT UNIQUE,
            duration_sec REAL,
            recording_date TEXT,
            file_mtime TEXT,
            gps_lat REAL,
            gps_lon REAL,
            camera TEXT,
            device TEXT
        )
        """
    )
    conn.commit()
    return conn
