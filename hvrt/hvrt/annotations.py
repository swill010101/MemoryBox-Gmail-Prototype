"""Annotation + place helpers for HVRT R2."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from hvrt.rescoring import human_confidence, load_rules, rebuild_effective_evidence

SAFE_NAME = re.compile(r"[^\w\s\-'.]", re.UNICODE)


def list_people(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, name, gallery_path FROM people ORDER BY name COLLATE NOCASE"
    ).fetchall()
    return [dict(r) for r in rows]


def list_places(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM places ORDER BY name COLLATE NOCASE"
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_person(conn: sqlite3.Connection, name: str, gallery_path: str | None = None) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Person name required")
    existing = conn.execute(
        "SELECT id FROM people WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if existing:
        if gallery_path:
            conn.execute(
                "UPDATE people SET gallery_path=COALESCE(?, gallery_path) WHERE id=?",
                (gallery_path, existing["id"]),
            )
            conn.commit()
        return int(existing["id"])
    cur = conn.execute(
        "INSERT INTO people (name, gallery_path) VALUES (?,?)",
        (name, gallery_path),
    )
    conn.commit()
    return int(cur.lastrowid)


def upsert_place(
    conn: sqlite3.Connection,
    name: str,
    *,
    address_label: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_m: float = 100.0,
    gallery_path: str | None = None,
    actor_key: str = "owner",
) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Place name required")
    existing = conn.execute(
        "SELECT id FROM places WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE places SET
                address_label=COALESCE(?, address_label),
                lat=COALESCE(?, lat),
                lon=COALESCE(?, lon),
                radius_m=COALESCE(?, radius_m),
                gallery_path=COALESCE(?, gallery_path)
            WHERE id=?
            """,
            (address_label, lat, lon, radius_m, gallery_path, existing["id"]),
        )
        conn.commit()
        return int(existing["id"])
    cur = conn.execute(
        """
        INSERT INTO places (name, address_label, lat, lon, radius_m, gallery_path, created_by_actor)
        VALUES (?,?,?,?,?,?,?)
        """,
        (name, address_label, lat, lon, radius_m, gallery_path, actor_key),
    )
    conn.commit()
    return int(cur.lastrowid)


def add_annotation(
    conn: sqlite3.Connection,
    *,
    video_id: int,
    kind: str,
    start_sec: float,
    end_sec: float,
    actor_key: str = "owner",
    confidence: float | None = None,
    label_text: str | None = None,
    place_id: int | None = None,
    person_id: int | None = None,
    payload: dict[str, Any] | None = None,
    exemplar_path: str | None = None,
    supersedes_id: int | None = None,
    provenance: dict[str, Any] | None = None,
) -> int:
    rules = load_rules(conn)
    if confidence is None:
        confidence = human_confidence(rules, actor_key, 0.5)
    else:
        confidence = human_confidence(rules, actor_key, confidence)

    prov = {
        "source": "review_ui",
        "actor_key": actor_key,
        **(provenance or {}),
    }
    cur = conn.execute(
        """
        INSERT INTO annotations (
            video_id, kind, start_sec, end_sec, label_text, place_id, person_id,
            payload_json, actor_key, confidence, provenance_json, supersedes_id,
            exemplar_path
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            video_id,
            kind,
            float(start_sec),
            float(max(end_sec, start_sec)),
            label_text,
            place_id,
            person_id,
            json.dumps(payload or {}),
            actor_key,
            float(confidence),
            json.dumps(prov),
            supersedes_id,
            exemplar_path,
        ),
    )
    conn.commit()
    ann_id = int(cur.lastrowid)
    rebuild_effective_evidence(conn)
    return ann_id


def folder_name(name: str) -> str:
    cleaned = SAFE_NAME.sub("", name).strip() or "unnamed"
    return cleaned


def ensure_gallery_dir(root: Path, kind: str, name: str) -> Path:
    path = root / kind / folder_name(name)
    path.mkdir(parents=True, exist_ok=True)
    return path
