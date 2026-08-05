"""Read-only evidence search across existing POC databases (+ optional Immich)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import httpx

from api import config


def _connect_ro(path: Path) -> sqlite3.Connection | None:
    if not path.is_file():
        return None
    try:
        # uri read-only avoids accidental writes to POC DBs
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        return conn
    except sqlite3.Error:
        return None


def _tables(conn: sqlite3.Connection) -> set[str]:
    try:
        return {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    except sqlite3.Error:
        return set()


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def source_status() -> dict[str, Any]:
    mb = config.MEMORYBOX_DB
    hv = config.HVRT_DB
    return {
        "memorybox_db": str(mb),
        "memorybox_present": mb.is_file(),
        "hvrt_db": str(hv),
        "hvrt_present": hv.is_file(),
        "immich_configured": bool(config.IMMICH_BASE_URL and config.IMMICH_API_KEY),
    }


def _like_tokens(q: str) -> list[str]:
    # Keep meaningful tokens; drop ultra-common ask words
    stop = {
        "a", "an", "the", "of", "to", "for", "and", "or", "in", "on", "at", "is", "are",
        "me", "my", "some", "any", "show", "find", "tell", "about", "pictures", "picture",
        "photos", "photo", "videos", "video", "please", "what", "who", "where", "when",
    }
    toks = []
    for raw in q.replace("?", " ").replace(",", " ").split():
        t = raw.strip().lower()
        if len(t) < 2 or t in stop:
            continue
        toks.append(t)
    # Also keep full phrase
    phrase = " ".join(toks)
    out = []
    if phrase and phrase not in out:
        out.append(phrase)
    for t in toks:
        if t not in out:
            out.append(t)
    return out[:8] or [q.strip().lower()]


def search_all(q: str, *, limit: int = 40) -> list[dict[str, Any]]:
    q = (q or "").strip()
    if not q:
        return []
    hits: list[dict[str, Any]] = []
    hits.extend(search_hvrt(q, limit=limit))
    hits.extend(search_memorybox(q, limit=limit))
    hits.extend(search_immich(q, limit=min(12, limit)))
    # de-dupe by type+id
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for h in hits:
        key = f"{h.get('type')}:{h.get('id')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
        if len(out) >= limit:
            break
    return out


def search_hvrt(q: str, *, limit: int = 24) -> list[dict[str, Any]]:
    conn = _connect_ro(config.HVRT_DB)
    if not conn:
        return []
    tokens = _like_tokens(q)
    tables = _tables(conn)
    out: list[dict[str, Any]] = []
    try:
        # People / faces
        if "people" in tables:
            for tok in tokens[:4]:
                rows = conn.execute(
                    """
                    SELECT id, name FROM people
                    WHERE name LIKE ? COLLATE NOCASE
                    ORDER BY name LIMIT 8
                    """,
                    (f"%{tok}%",),
                ).fetchall()
                for r in rows:
                    pid = int(r["id"])
                    name = r["name"]
                    face_n = 0
                    video_names: list[str] = []
                    if "face_appearances" in tables:
                        try:
                            face_n = int(conn.execute(
                                "SELECT COUNT(*) FROM face_appearances WHERE person_id=?",
                                (pid,),
                            ).fetchone()[0])
                        except sqlite3.Error:
                            face_n = 0
                        try:
                            vids = conn.execute(
                                """
                                SELECT DISTINCT v.filename FROM face_appearances f
                                JOIN videos v ON v.id=f.video_id
                                WHERE f.person_id=?
                                ORDER BY v.filename LIMIT 5
                                """,
                                (pid,),
                            ).fetchall()
                            video_names = [v["filename"] for v in vids]
                        except sqlite3.Error:
                            video_names = []
                    snip = f"{face_n} face hit(s) in HVRT"
                    if video_names:
                        snip += " · " + ", ".join(video_names[:3])
                    out.append({
                        "type": "hvrt_person",
                        "id": pid,
                        "title": name,
                        "snippet": snip,
                        "modality": "video_face",
                        "open_hint": f"Review → Faces → {name}",
                        "source": "hvrt.sqlite",
                    })

        # Spoken transcript lines
        if "transcript_segments" in tables:
            cols = _cols(conn, "transcript_segments")
            if "text" in cols:
                for tok in tokens[:3]:
                    try:
                        rows = conn.execute(
                            """
                            SELECT s.id, s.text, s.start_sec, s.end_sec, v.filename, s.video_id
                            FROM transcript_segments s
                            JOIN videos v ON v.id=s.video_id
                            WHERE s.text LIKE ? COLLATE NOCASE
                            ORDER BY v.filename, s.start_sec
                            LIMIT 8
                            """,
                            (f"%{tok}%",),
                        ).fetchall()
                    except sqlite3.Error:
                        rows = []
                    for r in rows:
                        out.append({
                            "type": "hvrt_transcript",
                            "id": int(r["id"]),
                            "title": r["filename"],
                            "snippet": (r["text"] or "")[:240],
                            "modality": "video_speech",
                            "start_sec": r["start_sec"],
                            "video_id": r["video_id"],
                            "open_hint": "Review → Spoken text",
                            "source": "hvrt.sqlite",
                        })

        # Places
        if "places" in tables:
            for tok in tokens[:3]:
                try:
                    rows = conn.execute(
                        "SELECT id, name FROM places WHERE name LIKE ? COLLATE NOCASE LIMIT 6",
                        (f"%{tok}%",),
                    ).fetchall()
                except sqlite3.Error:
                    rows = []
                for r in rows:
                    out.append({
                        "type": "hvrt_place",
                        "id": int(r["id"]),
                        "title": r["name"],
                        "snippet": "Place marked in HVRT",
                        "modality": "place",
                        "source": "hvrt.sqlite",
                    })
    finally:
        conn.close()
    return out[:limit]


def search_memorybox(q: str, *, limit: int = 24) -> list[dict[str, Any]]:
    conn = _connect_ro(config.MEMORYBOX_DB)
    if not conn:
        return []
    tokens = _like_tokens(q)
    tables = _tables(conn)
    out: list[dict[str, Any]] = []
    try:
        # People hubs
        if "person_memory" in tables:
            for tok in tokens[:4]:
                try:
                    rows = conn.execute(
                        """
                        SELECT id, display_name, role, notes FROM person_memory
                        WHERE display_name LIKE ? COLLATE NOCASE
                           OR IFNULL(role,'') LIKE ? COLLATE NOCASE
                        LIMIT 8
                        """,
                        (f"%{tok}%", f"%{tok}%"),
                    ).fetchall()
                except sqlite3.Error:
                    rows = []
                for r in rows:
                    out.append({
                        "type": "person",
                        "id": int(r["id"]),
                        "title": r["display_name"],
                        "snippet": (r["role"] or r["notes"] or "Person in memorybox")[:200],
                        "modality": "person",
                        "source": "memorybox.db",
                    })

        # Email
        if "messages" in tables:
            for tok in tokens[:3]:
                try:
                    rows = conn.execute(
                        """
                        SELECT id, subject, from_addr, date_utc, body_text
                        FROM messages
                        WHERE subject LIKE ? COLLATE NOCASE
                           OR from_addr LIKE ? COLLATE NOCASE
                           OR body_text LIKE ? COLLATE NOCASE
                        ORDER BY date_utc DESC
                        LIMIT 8
                        """,
                        (f"%{tok}%", f"%{tok}%", f"%{tok}%"),
                    ).fetchall()
                except sqlite3.Error:
                    rows = []
                for r in rows:
                    subj = (r["subject"] or "(no subject)").strip()
                    body = (r["body_text"] or "").strip().replace("\n", " ")
                    out.append({
                        "type": "email",
                        "id": int(r["id"]),
                        "title": subj[:120],
                        "snippet": f"From {r['from_addr'] or '?'} · {(r['date_utc'] or '')[:10]} · {body[:160]}",
                        "modality": "email",
                        "source": "memorybox.db",
                    })

        # SMS
        if "text_messages" in tables:
            for tok in tokens[:3]:
                try:
                    rows = conn.execute(
                        """
                        SELECT id, sender, body, timestamp, chat_id
                        FROM text_messages
                        WHERE body LIKE ? COLLATE NOCASE
                           OR IFNULL(sender,'') LIKE ? COLLATE NOCASE
                        ORDER BY timestamp DESC
                        LIMIT 8
                        """,
                        (f"%{tok}%", f"%{tok}%"),
                    ).fetchall()
                except sqlite3.Error:
                    rows = []
                for r in rows:
                    out.append({
                        "type": "sms",
                        "id": int(r["id"]),
                        "title": f"Text · {r['sender'] or r['chat_id'] or 'chat'}",
                        "snippet": (r["body"] or "")[:220],
                        "modality": "sms",
                        "when": r["timestamp"],
                        "source": "memorybox.db",
                    })

        # Calendar
        if "calendar_events" in tables:
            for tok in tokens[:3]:
                try:
                    rows = conn.execute(
                        """
                        SELECT id, summary, start_utc, location
                        FROM calendar_events
                        WHERE summary LIKE ? COLLATE NOCASE
                           OR IFNULL(location,'') LIKE ? COLLATE NOCASE
                        ORDER BY start_utc DESC LIMIT 6
                        """,
                        (f"%{tok}%", f"%{tok}%"),
                    ).fetchall()
                except sqlite3.Error:
                    rows = []
                for r in rows:
                    out.append({
                        "type": "calendar",
                        "id": int(r["id"]),
                        "title": r["summary"] or "Event",
                        "snippet": f"{(r['start_utc'] or '')[:16]} · {r['location'] or ''}",
                        "modality": "calendar",
                        "source": "memorybox.db",
                    })

        # Local Immich import cache
        if "photo_assets" in tables:
            for tok in tokens[:3]:
                try:
                    rows = conn.execute(
                        """
                        SELECT id, original_file_name, taken_at, people_json, description,
                               city, immich_id, thumb_url, web_url
                        FROM photo_assets
                        WHERE original_file_name LIKE ? COLLATE NOCASE
                           OR IFNULL(description,'') LIKE ? COLLATE NOCASE
                           OR IFNULL(people_json,'') LIKE ? COLLATE NOCASE
                           OR IFNULL(city,'') LIKE ? COLLATE NOCASE
                        ORDER BY taken_at DESC LIMIT 10
                        """,
                        (f"%{tok}%", f"%{tok}%", f"%{tok}%", f"%{tok}%"),
                    ).fetchall()
                except sqlite3.Error:
                    rows = []
                for r in rows:
                    people = r["people_json"] or ""
                    out.append({
                        "type": "photo",
                        "id": int(r["id"]),
                        "title": r["original_file_name"] or r["immich_id"],
                        "snippet": f"{(r['taken_at'] or '')[:10]} · {r['city'] or ''} · {people[:120]}",
                        "modality": "photo",
                        "thumb_url": r["thumb_url"],
                        "web_url": r["web_url"],
                        "immich_id": r["immich_id"],
                        "source": "memorybox.db",
                    })
    finally:
        conn.close()
    return out[:limit]


def _load_immich_env() -> None:
    """Fill config from config/immich.env if env vars empty."""
    if config.IMMICH_BASE_URL and config.IMMICH_API_KEY:
        return
    env_path = config.ROOT / "config" / "immich.env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k == "IMMICH_BASE_URL" and not config.IMMICH_BASE_URL:
            config.IMMICH_BASE_URL = v.rstrip("/")
        if k == "IMMICH_API_KEY" and not config.IMMICH_API_KEY:
            config.IMMICH_API_KEY = v


def search_immich(q: str, *, limit: int = 12) -> list[dict[str, Any]]:
    _load_immich_env()
    base = config.IMMICH_BASE_URL
    key = config.IMMICH_API_KEY
    if not base or not key or "REPLACE" in key or "IMMICH-SERVER" in base:
        return []
    tokens = _like_tokens(q)
    # Prefer person-name style queries for Immich people search
    name_guess = " ".join(t.capitalize() for t in tokens[:3]) if tokens else q
    headers = {"x-api-key": key, "Accept": "application/json"}
    out: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=12.0) as client:
            # Search people by name
            pr = client.get(f"{base}/search/person", params={"name": name_guess}, headers=headers)
            if pr.status_code >= 400:
                # try first token only
                pr = client.get(
                    f"{base}/search/person",
                    params={"name": tokens[0] if tokens else q},
                    headers=headers,
                )
            people = pr.json() if pr.status_code < 400 else []
            if not isinstance(people, list):
                people = []
            for person in people[:5]:
                pid = person.get("id")
                pname = person.get("name") or "Person"
                out.append({
                    "type": "immich_person",
                    "id": pid,
                    "title": pname,
                    "snippet": "Immich person · photos available",
                    "modality": "photo",
                    "source": "immich",
                })
                if not pid:
                    continue
                # Assets for person
                ar = client.post(
                    f"{base}/search/metadata",
                    headers=headers,
                    json={"personIds": [pid], "size": min(limit, 20), "type": "IMAGE"},
                )
                if ar.status_code >= 400:
                    continue
                payload = ar.json() or {}
                assets = (
                    (payload.get("assets") or {}).get("items")
                    or payload.get("assets")
                    or []
                )
                if isinstance(assets, dict):
                    assets = assets.get("items") or []
                for a in (assets or [])[:8]:
                    aid = a.get("id")
                    fn = (a.get("originalFileName") or a.get("originalPath") or aid)
                    when = ((a.get("exifInfo") or {}).get("dateTimeOriginal")
                            or a.get("fileCreatedAt") or "")
                    thumb = f"{base}/assets/{aid}/thumbnail" if aid else None
                    out.append({
                        "type": "immich_photo",
                        "id": aid,
                        "title": fn,
                        "snippet": f"{str(when)[:10]} · {pname}",
                        "modality": "photo",
                        "person": pname,
                        "thumb_url": thumb,
                        "source": "immich",
                    })
    except httpx.HTTPError:
        return out[:limit]
    return out[:limit]


def list_hvrt_people(*, limit: int = 40) -> list[dict[str, Any]]:
    conn = _connect_ro(config.HVRT_DB)
    if not conn:
        return []
    out: list[dict[str, Any]] = []
    try:
        if "people" not in _tables(conn):
            return []
        for r in conn.execute(
            "SELECT id, name FROM people ORDER BY name LIMIT ?", (limit,)
        ).fetchall():
            out.append({
                "type": "hvrt_person",
                "id": int(r["id"]),
                "title": r["name"],
                "snippet": "Person in HVRT gallery / face index",
                "modality": "video_face",
                "source": "hvrt.sqlite",
            })
    finally:
        conn.close()
    return out


def compose_answer(q: str, evidence: list[dict[str, Any]], sources: dict[str, Any]) -> str:
    if not evidence:
        missing = []
        if not sources.get("hvrt_present"):
            missing.append(f"HVRT DB not found at {sources.get('hvrt_db')}")
        if not sources.get("memorybox_present"):
            missing.append(f"memorybox.db not found at {sources.get('memorybox_db')}")
        if not sources.get("immich_configured"):
            missing.append("Immich not configured (config/immich.env)")
        tip = (" · ".join(missing) if missing
               else "No rows matched — try a person name from HVRT (e.g. Eugene Will) or a word from email/SMS.")
        return f"Nothing matched “{q}” in the connected archives yet.\n{tip}"

    by_mod: dict[str, int] = {}
    for e in evidence:
        m = e.get("modality") or e.get("type") or "other"
        by_mod[m] = by_mod.get(m, 0) + 1
    parts = [f"Found {len(evidence)} piece(s) of evidence for “{q}”:"]
    for m, n in sorted(by_mod.items(), key=lambda x: -x[1]):
        parts.append(f"· {n} × {m}")
    for e in evidence[:6]:
        parts.append(f"• {e.get('title')}: {(e.get('snippet') or '')[:140]}")
    return "\n".join(parts)
