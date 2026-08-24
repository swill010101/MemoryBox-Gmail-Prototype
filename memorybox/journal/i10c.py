"""P2-I10C family Journal: working drafts vs Ask-current saved versions."""
from __future__ import annotations

import json
from datetime import date, time
from typing import Any
from uuid import UUID, uuid4

from memorybox.db import connection
from memorybox.journal import (
    DESCRIBED_PRECISIONS,
    REL_ABOUT_PERSON,
    JournalServiceError,
    _add_relationship,
    _iso,
    _normalize_temporal,
    _parse_date,
    _parse_uuid,
    ensure_person,
)

WORKING_VERSION = 0
SOURCE_KINDS = frozenset(
    {
        "photo",
        "video",
        "email_thread",
        "sms_conversation",
        "calendar_event",
        "artifact",
        "audio",
        "evidence",
    }
)
I10C_PRECISIONS = frozenset({"day", "month", "year", "approximate", "unknown"})


def _reject_ai(actor_key: str) -> None:
    if (actor_key or "").lower() in {
        "ai",
        "llm",
        "model",
        "assistant",
        "stt",
        "whisper",
    }:
        raise JournalServiceError(
            "STT/AI output cannot be persisted as Journal truth without owner Save actor"
        )


def _author_person_id() -> UUID:
    try:
        from memorybox.profile.owner import get_owner_person_id

        oid = get_owner_person_id()
        if oid:
            return UUID(str(oid))
    except Exception:
        pass
    return ensure_person("MemoryBox Owner")


def first_meaningful_line(body: str | None) -> str:
    for line in str(body or "").splitlines():
        s = line.strip()
        if s:
            return s
    return ""


def display_title(title: str | None, body: str | None) -> str:
    t = (title or "").strip()
    if t:
        return t
    return first_meaningful_line(body)


def format_entry_date(
    start: Any,
    precision: str | None,
    described_time: Any = None,
) -> str:
    """UI date string — never invent a calendar day for month/year."""
    prec = (precision or "unknown").strip().lower()
    if prec in {"", "unknown"} or start is None:
        return ""
    raw = start
    if hasattr(start, "isoformat") and not isinstance(start, str):
        raw = start.isoformat()
    ds = str(raw)[:10]
    try:
        d = date.fromisoformat(ds)
    except ValueError:
        return ""
    if prec == "year":
        return str(d.year)
    if prec == "month":
        return f"{d.year:04d}-{d.month:02d}"
    if prec == "approximate":
        return f"about {d.year}"
    clock = ""
    if described_time is not None and str(described_time).strip():
        clock = " " + str(described_time)[:8]
        if len(clock.strip()) >= 5:
            clock = " " + str(described_time)[:5]
    return ds + clock


def _parse_time(value: str | time | None) -> time | None:
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    parts = raw.replace(".", ":").split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(float(parts[2])) if len(parts) > 2 else 0
        return time(h, m, s)
    except (ValueError, TypeError) as exc:
        raise JournalServiceError(f"described_time must be HH:MM (got {raw!r})") from exc


def _coerce_entry_dates(
    *,
    described_start_date: str | date | None,
    described_end_date: str | date | None,
    described_precision: str | None,
) -> tuple[date | None, date | None, str]:
    prec = (described_precision or "unknown").strip().lower()
    if prec == "range":
        return _normalize_temporal(
            described_start_date=described_start_date,
            described_end_date=described_end_date,
            described_precision="range",
        )
    if prec not in DESCRIBED_PRECISIONS:
        raise JournalServiceError(
            f"described_precision must be one of {sorted(DESCRIBED_PRECISIONS)}"
        )
    start = _parse_date(described_start_date, field="described_start_date")
    if prec == "unknown":
        return None, None, prec
    if start is None:
        raise JournalServiceError("Entry date is required unless precision is unknown")
    if prec == "month":
        start = date(start.year, start.month, 1)
    elif prec in {"year", "approximate"}:
        start = date(start.year, 1, 1)
    return start, start, prec


def _place_id(place_id: str | None, place_label: str | None) -> UUID | None:
    if place_id and str(place_id).strip():
        return _parse_uuid(str(place_id), field="place_id")
    label = (place_label or "").strip()
    if not label:
        return None
    from memorybox.correlate.store import upsert_place

    row = upsert_place(label)
    return UUID(str(row["id"]))


def _memory_thumb(source_kind: str | None, source_id: str | None, existing: str | None) -> str | None:
    if existing:
        return str(existing)
    kind = (source_kind or "").strip()
    sid = (source_id or "").strip()
    if kind == "photo" and sid:
        return f"/library/media/photo/{sid}"
    if kind == "video" and sid:
        return f"/library/media/video-poster?video={sid}&t=0.000"
    return None


def _replace_version_children(
    conn,
    version_id: UUID,
    *,
    memories: list[dict[str, Any]] | None,
    person_ids: list[str] | None,
) -> None:
    if person_ids is not None:
        conn.execute(
            "DELETE FROM journal_version_people WHERE version_id = %s", (version_id,)
        )
        for i, raw in enumerate(person_ids):
            pid = str(raw or "").strip()
            if not pid:
                continue
            conn.execute(
                """
                INSERT INTO journal_version_people (version_id, person_id, position)
                VALUES (%s, %s, %s)
                ON CONFLICT (version_id, person_id) DO UPDATE SET position = EXCLUDED.position
                """,
                (version_id, UUID(pid), i),
            )
    if memories is None:
        return
    conn.execute(
        "DELETE FROM journal_version_memories WHERE version_id = %s", (version_id,)
    )
    for i, mem in enumerate(memories):
        kind = str(mem.get("source_kind") or "").strip()
        sid = str(mem.get("source_id") or "").strip()
        if not kind or not sid:
            continue
        if kind == "journal":
            raise JournalServiceError("Journal entries cannot link to other Journals as memories")
        if kind not in SOURCE_KINDS:
            raise JournalServiceError(f"unsupported source_kind {kind!r}")
        occurred = mem.get("occurred_on")
        occurred_d = None
        if occurred:
            occurred_d = _parse_date(str(occurred)[:10], field="occurred_on")
        attrs = mem.get("attributes_json") if isinstance(mem.get("attributes_json"), dict) else {}
        conn.execute(
            """
            INSERT INTO journal_version_memories (
                id, version_id, position, source_kind, source_id, label_snapshot,
                occurred_on, thumb_url, attributes_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (version_id, source_kind, source_id) DO NOTHING
            """,
            (
                uuid4(),
                version_id,
                int(mem.get("position") or i),
                kind,
                sid,
                (mem.get("label_snapshot") or mem.get("title") or "").strip() or None,
                occurred_d,
                _memory_thumb(kind, sid, mem.get("thumb_url")),
                json.dumps(attrs),
            ),
        )


def _copy_version_children(conn, src_id: UUID, dest_id: UUID) -> None:
    conn.execute(
        """
        INSERT INTO journal_version_memories (
            id, version_id, position, source_kind, source_id, label_snapshot,
            occurred_on, thumb_url, attributes_json
        )
        SELECT gen_random_uuid(), %s, position, source_kind, source_id, label_snapshot,
               occurred_on, thumb_url, attributes_json
        FROM journal_version_memories WHERE version_id = %s
        """,
        (dest_id, src_id),
    )
    conn.execute(
        """
        INSERT INTO journal_version_people (version_id, person_id, position)
        SELECT %s, person_id, position FROM journal_version_people WHERE version_id = %s
        """,
        (dest_id, src_id),
    )


def _load_memories(conn, version_id: UUID) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, position, source_kind, source_id, label_snapshot,
               occurred_on, thumb_url, attributes_json
        FROM journal_version_memories
        WHERE version_id = %s
        ORDER BY position, source_kind, source_id
        """,
        (version_id,),
    ).fetchall()
    out = []
    for r in rows:
        kind = r["source_kind"]
        sid = r["source_id"]
        out.append(
            {
                "id": str(r["id"]),
                "position": int(r["position"]),
                "source_kind": kind,
                "source_id": sid,
                "label_snapshot": r.get("label_snapshot"),
                "occurred_on": _iso(r.get("occurred_on")),
                "thumb_url": _memory_thumb(kind, sid, r.get("thumb_url")),
                "attributes_json": r.get("attributes_json") or {},
            }
        )
    return out


def _load_people(conn, version_id: UUID) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT vp.person_id, vp.position, p.display_name
        FROM journal_version_people vp
        JOIN people p ON p.id = vp.person_id
        WHERE vp.version_id = %s
        ORDER BY vp.position, p.display_name
        """,
        (version_id,),
    ).fetchall()
    return [
        {
            "id": str(r["person_id"]),
            "person_id": str(r["person_id"]),
            "display_name": r.get("display_name"),
            "portrait_url": f"/people/{r['person_id']}/portrait",
            "position": int(r["position"]),
        }
        for r in rows
    ]


def _place_label(conn, place_id: Any) -> str | None:
    if not place_id:
        return None
    row = conn.execute(
        "SELECT display_name FROM places WHERE id = %s", (place_id,)
    ).fetchone()
    return row["display_name"] if row else None


def _sync_entry_people(conn, journal_id: UUID, version_id: UUID) -> None:
    conn.execute(
        """
        DELETE FROM relationships
        WHERE from_type = 'journal' AND from_id = %s
          AND relationship_kind = %s AND to_type = 'person'
        """,
        (journal_id, REL_ABOUT_PERSON),
    )
    for p in _load_people(conn, version_id):
        _add_relationship(
            conn,
            kind=REL_ABOUT_PERSON,
            journal_id=journal_id,
            to_type="person",
            to_id=UUID(p["person_id"]),
            label="about",
        )


def payload(conn, jrow: dict[str, Any], vrow: dict[str, Any] | None) -> dict[str, Any]:
    jid = UUID(str(jrow["id"]))
    vid = UUID(str(vrow["id"])) if vrow else None
    memories = _load_memories(conn, vid) if vid else []
    people = _load_people(conn, vid) if vid else []
    author_name = None
    aid = jrow.get("author_person_id")
    if aid:
        prow = conn.execute(
            "SELECT display_name FROM people WHERE id = %s", (aid,)
        ).fetchone()
        if prow:
            author_name = prow["display_name"]
    title = None
    body = jrow.get("body_text") or ""
    start = jrow.get("described_start_date")
    end = jrow.get("described_end_date")
    precision = jrow.get("described_precision") or "unknown"
    dtime = jrow.get("described_time")
    place_id = jrow.get("place_id")
    vis = jrow.get("visibility") or "private"
    audio = jrow.get("audio_uri")
    if vrow:
        title = vrow.get("title") if vrow.get("title") is not None else jrow.get("title")
        body = vrow.get("body_text") or ""
        if vrow.get("described_start_date") is not None or (vrow.get("described_precision") or "") == "unknown":
            start = vrow.get("described_start_date")
            end = vrow.get("described_end_date")
            precision = vrow.get("described_precision") or precision
        if vrow.get("described_time") is not None or vrow.get("lifecycle") == "working":
            dtime = vrow.get("described_time")
        if vrow.get("place_id") is not None or vrow.get("lifecycle") == "working":
            place_id = vrow.get("place_id")
        if vrow.get("visibility"):
            vis = vrow.get("visibility")
        if vrow.get("audio_uri") is not None:
            audio = vrow.get("audio_uri")
    saved = jrow.get("current_saved_version")
    work = jrow.get("working_version")
    return {
        "id": str(jid),
        "title": title,
        "display_title": display_title(title, body),
        "body_text": body,
        "status": jrow["status"],
        "author_person_id": str(aid) if aid else None,
        "author_display_name": author_name,
        "current_version": int(jrow.get("current_version") or 0),
        "current_saved_version": int(saved) if saved is not None else None,
        "working_version": int(work) if work is not None else None,
        "ask_available": saved is not None and jrow.get("status") == "active",
        "has_working_draft": work is not None,
        "captured_at": _iso(jrow.get("captured_at")),
        "described_start_date": _iso(start),
        "described_end_date": _iso(end),
        "described_precision": precision,
        "described_time": str(dtime)[:8] if dtime else None,
        "entry_date_display": format_entry_date(start, precision, dtime),
        "channel": jrow.get("channel"),
        "audio_uri": audio,
        "visibility": vis,
        "place_id": str(place_id) if place_id else None,
        "place_label": _place_label(conn, place_id),
        "created_at": _iso(jrow.get("created_at")),
        "updated_at": _iso(jrow.get("updated_at")),
        "version": int(vrow["version"]) if vrow else None,
        "lifecycle": (vrow.get("lifecycle") if vrow else None) or None,
        "version_id": str(vid) if vid else None,
        "person_ids": [p["person_id"] for p in people],
        "people": people,
        "memories": memories,
        "memory_count": len(memories),
        "provenance_kind": "owner_journal",
    }


def _get_version_row(conn, journal_id: UUID, version: int) -> dict[str, Any] | None:
    return conn.execute(
        "SELECT * FROM journal_versions WHERE journal_id = %s AND version = %s",
        (journal_id, version),
    ).fetchone()


def get_saved(journal_id: str) -> dict[str, Any] | None:
    try:
        jid = _parse_uuid(journal_id, field="journal_id")
    except JournalServiceError:
        return None
    with connection() as conn:
        jrow = conn.execute(
            "SELECT * FROM journal_entries WHERE id = %s", (jid,)
        ).fetchone()
        if not jrow or jrow.get("status") == "removed":
            return None
        saved = jrow.get("current_saved_version")
        if saved is None:
            return None
        vrow = _get_version_row(conn, jid, int(saved))
        if not vrow:
            return None
        return payload(conn, jrow, vrow)


def get_working(journal_id: str) -> dict[str, Any] | None:
    jid = _parse_uuid(journal_id, field="journal_id")
    with connection() as conn:
        jrow = conn.execute(
            "SELECT * FROM journal_entries WHERE id = %s AND status = 'active'", (jid,)
        ).fetchone()
        if not jrow:
            return None
        work = jrow.get("working_version")
        if work is None:
            return None
        vrow = _get_version_row(conn, jid, int(work))
        if not vrow:
            return None
        return payload(conn, jrow, vrow)


def _insert_working(
    conn,
    journal_id: UUID,
    *,
    title: str | None,
    body: str,
    audio: str | None,
    start: date | None,
    end: date | None,
    precision: str,
    dtime: time | None,
    place_id: UUID | None,
    visibility: str,
    actor_key: str,
) -> UUID:
    vid = uuid4()
    conn.execute(
        """
        INSERT INTO journal_versions (
            id, journal_id, version, body_text, audio_uri, actor_key, note,
            lifecycle, title, described_start_date, described_end_date,
            described_precision, described_time, place_id, visibility
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, NULL,
            'working', %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            vid,
            journal_id,
            WORKING_VERSION,
            body or "",
            audio,
            actor_key or "owner",
            (title or "").strip() or None,
            start,
            end,
            precision,
            dtime,
            place_id,
            visibility,
        ),
    )
    return vid


def save_draft(
    *,
    journal_id: str | None = None,
    title: str | None = None,
    body_text: str | None = None,
    audio_uri: str | None = None,
    described_start_date: str | date | None = None,
    described_end_date: str | date | None = None,
    described_precision: str | None = None,
    described_time: str | time | None = None,
    place_id: str | None = None,
    place_label: str | None = None,
    visibility: str | None = None,
    person_ids: list[str] | None = None,
    memories: list[dict[str, Any]] | None = None,
    actor_key: str = "owner",
) -> dict[str, Any]:
    _reject_ai(actor_key)
    vis = (visibility or "private").strip() or "private"
    if vis not in {"private", "shared_with_family"}:
        raise JournalServiceError("visibility must be private or shared_with_family")
    if described_precision is None and journal_id is None:
        described_precision = "day"
        if described_start_date is None:
            described_start_date = date.today()
    start = end = None
    precision = "unknown"
    if (
        described_precision is not None
        or described_start_date is not None
        or described_end_date is not None
    ):
        start, end, precision = _coerce_entry_dates(
            described_start_date=described_start_date,
            described_end_date=described_end_date,
            described_precision=described_precision or "unknown",
        )
    dtime = _parse_time(described_time)
    pid_place = _place_id(place_id, place_label)
    audio = (audio_uri or "").strip() or None
    body = body_text if body_text is not None else ""
    author = _author_person_id()

    with connection() as conn:
        if journal_id:
            jid = _parse_uuid(journal_id, field="journal_id")
            jrow = conn.execute(
                "SELECT * FROM journal_entries WHERE id = %s AND status = 'active'",
                (jid,),
            ).fetchone()
            if not jrow:
                raise JournalServiceError("journal not found")
            work = jrow.get("working_version")
            if work is None:
                if start is None and described_precision is None:
                    start = jrow.get("described_start_date")
                    end = jrow.get("described_end_date")
                    precision = jrow.get("described_precision") or "unknown"
                if dtime is None:
                    dtime = jrow.get("described_time")
                if pid_place is None:
                    pid_place = jrow.get("place_id")
                vid = _insert_working(
                    conn,
                    jid,
                    title=title if title is not None else jrow.get("title"),
                    body=body if body_text is not None else (jrow.get("body_text") or ""),
                    audio=audio if audio_uri is not None else jrow.get("audio_uri"),
                    start=start if described_start_date is not None or described_precision else jrow.get("described_start_date"),
                    end=end if described_end_date is not None or described_precision else jrow.get("described_end_date"),
                    precision=precision if described_precision else (jrow.get("described_precision") or "unknown"),
                    dtime=dtime,
                    place_id=pid_place,
                    visibility=vis if visibility is not None else (jrow.get("visibility") or "private"),
                    actor_key=actor_key,
                )
                conn.execute(
                    """
                    UPDATE journal_entries
                    SET working_version = %s, updated_at = now(),
                        visibility = COALESCE(%s, visibility)
                    WHERE id = %s
                    """,
                    (WORKING_VERSION, vis if visibility is not None else None, jid),
                )
            else:
                vrow = _get_version_row(conn, jid, int(work))
                if not vrow:
                    raise JournalServiceError("working draft missing")
                vid = UUID(str(vrow["id"]))
                conn.execute(
                    """
                    UPDATE journal_versions
                    SET title = COALESCE(%s, title),
                        body_text = CASE WHEN %s THEN %s ELSE body_text END,
                        audio_uri = COALESCE(%s, audio_uri),
                        described_start_date = CASE WHEN %s THEN %s ELSE described_start_date END,
                        described_end_date = CASE WHEN %s THEN %s ELSE described_end_date END,
                        described_precision = CASE WHEN %s THEN %s ELSE described_precision END,
                        described_time = CASE WHEN %s THEN %s ELSE described_time END,
                        place_id = CASE WHEN %s THEN %s ELSE place_id END,
                        visibility = COALESCE(%s, visibility)
                    WHERE id = %s AND lifecycle = 'working'
                    """,
                    (
                        (title or "").strip() or None if title is not None else None,
                        body_text is not None,
                        body,
                        audio,
                        described_precision is not None or described_start_date is not None,
                        start,
                        described_precision is not None or described_end_date is not None,
                        end,
                        described_precision is not None,
                        precision,
                        described_time is not None,
                        dtime,
                        place_id is not None or (place_label or "").strip() != "",
                        pid_place,
                        vis if visibility is not None else None,
                        vid,
                    ),
                )
                conn.execute(
                    """
                    UPDATE journal_entries SET updated_at = now(),
                        visibility = COALESCE(%s, visibility)
                    WHERE id = %s
                    """,
                    (vis if visibility is not None else None, jid),
                )
            _replace_version_children(
                conn, vid, memories=memories, person_ids=person_ids
            )
        else:
            jid = uuid4()
            if described_precision is None:
                start, end, precision = date.today(), date.today(), "day"
            conn.execute(
                """
                INSERT INTO journal_entries (
                    id, title, body_text, channel, audio_uri, status,
                    author_person_id, current_version, current_saved_version,
                    working_version, captured_at, described_start_date,
                    described_end_date, described_precision, described_time,
                    visibility, place_id
                )
                VALUES (
                    %s, %s, %s, %s, %s, 'active',
                    %s, 0, NULL, %s, now(), %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    jid,
                    (title or "").strip() or None,
                    body or "",
                    "ui",
                    audio,
                    author,
                    WORKING_VERSION,
                    start,
                    end,
                    precision,
                    dtime,
                    vis,
                    pid_place,
                ),
            )
            vid = _insert_working(
                conn,
                jid,
                title=title,
                body=body or "",
                audio=audio,
                start=start,
                end=end,
                precision=precision,
                dtime=dtime,
                place_id=pid_place,
                visibility=vis,
                actor_key=actor_key,
            )
            _replace_version_children(
                conn, vid, memories=memories, person_ids=person_ids
            )
        jrow = conn.execute("SELECT * FROM journal_entries WHERE id = %s", (jid,)).fetchone()
        vrow = conn.execute(
            "SELECT * FROM journal_versions WHERE id = %s", (vid,)
        ).fetchone()
        assert jrow and vrow
        return payload(conn, jrow, vrow)


def begin_edit(journal_id: str) -> dict[str, Any]:
    jid = _parse_uuid(journal_id, field="journal_id")
    with connection() as conn:
        jrow = conn.execute(
            "SELECT * FROM journal_entries WHERE id = %s AND status = 'active'", (jid,)
        ).fetchone()
        if not jrow:
            raise JournalServiceError("journal not found")
        if jrow.get("working_version") is not None:
            vrow = _get_version_row(conn, jid, int(jrow["working_version"]))
            return payload(conn, jrow, vrow)
        saved = jrow.get("current_saved_version")
        if saved is None:
            raise JournalServiceError("no saved version to edit")
        src = _get_version_row(conn, jid, int(saved))
        if not src:
            raise JournalServiceError("saved version missing")
        vid = _insert_working(
            conn,
            jid,
            title=src.get("title") or jrow.get("title"),
            body=src.get("body_text") or "",
            audio=src.get("audio_uri") or jrow.get("audio_uri"),
            start=src.get("described_start_date") or jrow.get("described_start_date"),
            end=src.get("described_end_date") or jrow.get("described_end_date"),
            precision=src.get("described_precision") or jrow.get("described_precision") or "unknown",
            dtime=src.get("described_time") or jrow.get("described_time"),
            place_id=src.get("place_id") or jrow.get("place_id"),
            visibility=src.get("visibility") or jrow.get("visibility") or "private",
            actor_key="owner",
        )
        _copy_version_children(conn, UUID(str(src["id"])), vid)
        conn.execute(
            """
            UPDATE journal_entries
            SET working_version = %s, updated_at = now()
            WHERE id = %s
            """,
            (WORKING_VERSION, jid),
        )
        jrow = conn.execute("SELECT * FROM journal_entries WHERE id = %s", (jid,)).fetchone()
        vrow = conn.execute("SELECT * FROM journal_versions WHERE id = %s", (vid,)).fetchone()
        return payload(conn, jrow, vrow)


def save_journal(journal_id: str | None = None, **payload_in: Any) -> dict[str, Any]:
    view = save_draft(journal_id=journal_id, **payload_in)
    return freeze(view["id"], actor_key=payload_in.get("actor_key") or "owner")


def freeze(journal_id: str, *, actor_key: str = "owner") -> dict[str, Any]:
    _reject_ai(actor_key)
    jid = _parse_uuid(journal_id, field="journal_id")
    with connection() as conn:
        jrow = conn.execute(
            "SELECT * FROM journal_entries WHERE id = %s AND status = 'active'", (jid,)
        ).fetchone()
        if not jrow:
            raise JournalServiceError("journal not found")
        work = jrow.get("working_version")
        if work is None:
            raise JournalServiceError("no working draft to save")
        wrow = _get_version_row(conn, jid, int(work))
        if not wrow or wrow.get("lifecycle") != "working":
            raise JournalServiceError("no working draft to save")
        body = (wrow.get("body_text") or "").strip()
        if not body:
            raise JournalServiceError("body_text required")
        next_n = int(jrow.get("current_saved_version") or 0) + 1
        audio = (wrow.get("audio_uri") or "").strip() or None
        channel = "voice" if audio else "ui"
        conn.execute(
            """
            UPDATE journal_versions
            SET version = %s,
                lifecycle = 'saved',
                frozen_at = now()
            WHERE id = %s
            """,
            (next_n, wrow["id"]),
        )
        conn.execute(
            """
            UPDATE journal_entries
            SET title = %s,
                body_text = %s,
                audio_uri = %s,
                channel = %s,
                current_version = %s,
                current_saved_version = %s,
                working_version = NULL,
                described_start_date = %s,
                described_end_date = %s,
                described_precision = %s,
                described_time = %s,
                visibility = COALESCE(%s, visibility),
                place_id = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (
                wrow.get("title"),
                body,
                audio,
                channel,
                next_n,
                next_n,
                wrow.get("described_start_date"),
                wrow.get("described_end_date"),
                wrow.get("described_precision") or "unknown",
                wrow.get("described_time"),
                wrow.get("visibility"),
                wrow.get("place_id"),
                jid,
            ),
        )
        _sync_entry_people(conn, jid, UUID(str(wrow["id"])))
        jrow = conn.execute("SELECT * FROM journal_entries WHERE id = %s", (jid,)).fetchone()
        vrow = conn.execute(
            "SELECT * FROM journal_versions WHERE id = %s", (wrow["id"],)
        ).fetchone()
        assert jrow and vrow
        return payload(conn, jrow, vrow)


def remove_journal(journal_id: str) -> dict[str, Any]:
    jid = _parse_uuid(journal_id, field="journal_id")
    with connection() as conn:
        row = conn.execute(
            """
            UPDATE journal_entries
            SET status = 'removed', updated_at = now()
            WHERE id = %s AND status = 'active'
            RETURNING id
            """,
            (jid,),
        ).fetchone()
        if not row:
            raise JournalServiceError("journal not found")
    return {"ok": True, "id": str(jid), "status": "removed"}


def list_history(journal_id: str) -> list[dict[str, Any]]:
    jid = _parse_uuid(journal_id, field="journal_id")
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT version, title, body_text, frozen_at, created_at, actor_key,
                   described_start_date, described_precision, described_time
            FROM journal_versions
            WHERE journal_id = %s AND lifecycle = 'saved'
            ORDER BY version DESC
            """,
            (jid,),
        ).fetchall()
    out = []
    for r in rows:
        body = r.get("body_text") or ""
        out.append(
            {
                "version": int(r["version"]),
                "title": r.get("title"),
                "display_title": display_title(r.get("title"), body),
                "body_text": body,
                "frozen_at": _iso(r.get("frozen_at")),
                "created_at": _iso(r.get("created_at")),
                "actor_key": r.get("actor_key"),
                "entry_date_display": format_entry_date(
                    r.get("described_start_date"),
                    r.get("described_precision"),
                    r.get("described_time"),
                ),
            }
        )
    return out


def list_family_panel(
    *,
    q: str | None = None,
    person_id: str | None = None,
    year: int | None = None,
    month: int | None = None,
    limit: int = 80,
) -> dict[str, Any]:
    needle = (q or "").strip().lower()
    pid = (person_id or "").strip() or None
    with connection() as conn:
        drafts_rows = conn.execute(
            """
            SELECT j.*, jv.body_text AS v_body, jv.title AS v_title,
                   jv.described_start_date AS v_start,
                   jv.described_precision AS v_prec
            FROM journal_entries j
            JOIN journal_versions jv
              ON jv.journal_id = j.id AND jv.version = j.working_version
            WHERE j.status = 'active'
              AND j.current_saved_version IS NULL
              AND j.working_version IS NOT NULL
            ORDER BY j.updated_at DESC
            LIMIT 20
            """,
        ).fetchall()
        sql = """
            SELECT j.*, jv.body_text AS v_body, jv.title AS v_title,
                   jv.described_start_date AS v_start,
                   jv.described_end_date AS v_end,
                   jv.described_precision AS v_prec,
                   jv.described_time AS v_time,
                   jv.place_id AS v_place,
                   (
                     SELECT COUNT(*) FROM journal_version_memories m
                     WHERE m.version_id = jv.id
                   ) AS memory_count
            FROM journal_entries j
            JOIN journal_versions jv
              ON jv.journal_id = j.id AND jv.version = j.current_saved_version
             AND jv.lifecycle = 'saved'
            WHERE j.status = 'active'
              AND j.current_saved_version IS NOT NULL
        """
        params: list[Any] = []
        if pid:
            sql += """
              AND EXISTS (
                SELECT 1 FROM journal_version_people vp
                WHERE vp.version_id = jv.id AND vp.person_id = %s::uuid
              )
            """
            params.append(pid)
        if year:
            sql += " AND EXTRACT(YEAR FROM COALESCE(jv.described_start_date, j.described_start_date)) = %s"
            params.append(int(year))
        if month:
            sql += " AND EXTRACT(MONTH FROM COALESCE(jv.described_start_date, j.described_start_date)) = %s"
            params.append(int(month))
        sql += " ORDER BY COALESCE(jv.described_start_date, j.captured_at::date) DESC NULLS LAST, j.updated_at DESC LIMIT %s"
        params.append(limit)
        rows = conn.execute(sql, tuple(params)).fetchall()

        def card(r: dict[str, Any], *, draft: bool) -> dict[str, Any]:
            title = r.get("v_title") if r.get("v_title") is not None else r.get("title")
            body = r.get("v_body") or r.get("body_text") or ""
            start = r.get("v_start") if r.get("v_start") is not None else r.get("described_start_date")
            prec = r.get("v_prec") or r.get("described_precision") or "unknown"
            dtime = r.get("v_time") if r.get("v_time") is not None else r.get("described_time")
            dt = display_title(title, body)
            excerpt = first_meaningful_line(body)
            if needle and needle not in (dt + " " + body).lower():
                return {}
            aid = r.get("author_person_id")
            aname = None
            if aid:
                prow = conn.execute(
                    "SELECT display_name FROM people WHERE id = %s", (aid,)
                ).fetchone()
                aname = prow["display_name"] if prow else None
            people = []
            if not draft and r.get("current_saved_version") is not None:
                v = _get_version_row(conn, UUID(str(r["id"])), int(r["current_saved_version"]))
                if v:
                    people = _load_people(conn, UUID(str(v["id"])))
            elif draft and r.get("working_version") is not None:
                v = _get_version_row(conn, UUID(str(r["id"])), int(r["working_version"]))
                if v:
                    people = _load_people(conn, UUID(str(v["id"])))
            return {
                "id": str(r["id"]),
                "title": title,
                "display_title": dt,
                "excerpt": excerpt[:180],
                "entry_date_display": format_entry_date(start, prec, dtime),
                "described_start_date": _iso(start),
                "described_precision": prec,
                "visibility": r.get("visibility") or "private",
                "author_display_name": aname,
                "author_person_id": str(aid) if aid else None,
                "memory_count": int(r.get("memory_count") or 0),
                "people": people,
                "ask_available": (not draft) and r.get("current_saved_version") is not None,
                "is_draft": draft,
                "updated_at": _iso(r.get("updated_at")),
            }

        journals = [c for r in rows if (c := card(r, draft=False)).get("id")]
        drafts = [c for r in drafts_rows if (c := card(r, draft=True)).get("id")]
    return {"ok": True, "journals": journals, "drafts": drafts}


def calendar_dots(*, year: int, month: int) -> dict[str, Any]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT j.id, jv.described_start_date
            FROM journal_entries j
            JOIN journal_versions jv
              ON jv.journal_id = j.id AND jv.version = j.current_saved_version
             AND jv.lifecycle = 'saved'
            WHERE j.status = 'active'
              AND j.current_saved_version IS NOT NULL
              AND COALESCE(jv.described_precision, j.described_precision) = 'day'
              AND jv.described_start_date IS NOT NULL
              AND EXTRACT(YEAR FROM jv.described_start_date) = %s
              AND EXTRACT(MONTH FROM jv.described_start_date) = %s
            """,
            (int(year), int(month)),
        ).fetchall()
    days: dict[int, int] = {}
    for r in rows:
        d = r["described_start_date"]
        days[int(d.day)] = days.get(int(d.day), 0) + 1
    return {
        "ok": True,
        "year": int(year),
        "month": int(month),
        "days": [{"day": d, "count": c} for d, c in sorted(days.items())],
    }


def on_this_day(*, viewed: str | date | None = None) -> dict[str, Any]:
    d = _parse_date(viewed, field="viewed") if viewed else date.today()
    if d is None:
        d = date.today()
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT j.id, j.title, jv.title AS v_title, jv.body_text,
                   jv.described_start_date, jv.described_precision
            FROM journal_entries j
            JOIN journal_versions jv
              ON jv.journal_id = j.id AND jv.version = j.current_saved_version
             AND jv.lifecycle = 'saved'
            WHERE j.status = 'active'
              AND j.current_saved_version IS NOT NULL
              AND COALESCE(jv.described_precision, j.described_precision) = 'day'
              AND jv.described_start_date IS NOT NULL
              AND EXTRACT(MONTH FROM jv.described_start_date) = %s
              AND EXTRACT(DAY FROM jv.described_start_date) = %s
              AND EXTRACT(YEAR FROM jv.described_start_date) < %s
            ORDER BY jv.described_start_date DESC
            """,
            (d.month, d.day, d.year),
        ).fetchall()
        items = []
        for r in rows:
            body = r.get("body_text") or ""
            title = r.get("v_title") if r.get("v_title") is not None else r.get("title")
            items.append(
                {
                    "id": str(r["id"]),
                    "display_title": display_title(title, body),
                    "excerpt": first_meaningful_line(body)[:180],
                    "described_start_date": _iso(r.get("described_start_date")),
                    "entry_date_display": format_entry_date(
                        r.get("described_start_date"),
                        r.get("described_precision") or "day",
                    ),
                }
            )
    return {"ok": True, "viewed": d.isoformat(), "items": items}
