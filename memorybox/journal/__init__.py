"""Journal Service — owner Journals with immutable versions (Increment 5A).

Distinct from Story. Author SoT is journal_entries.author_person_id only
(no authored_by dual-write). Capture/STT is consumed via draft inputs — this
module never imports Whisper.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from memorybox.db import connection

REL_ABOUT_PERSON = "about_person"
REL_ABOUT_PLACE = "about_place"
REL_CITES_EVIDENCE = "cites_evidence"

DESCRIBED_PRECISIONS = frozenset(
    {"day", "month", "year", "range", "approximate", "unknown"}
)


@dataclass
class JournalVersionView:
    id: str
    journal_id: str
    version: int
    body_text: str
    audio_uri: str | None
    actor_key: str
    note: str | None
    created_at: str | None

    def to_dict(self, *, include_body: bool = True) -> dict[str, Any]:
        d = asdict(self)
        if not include_body:
            d.pop("body_text", None)
            d["body_present"] = True
        return d


@dataclass
class JournalView:
    id: str
    title: str | None
    status: str
    author_person_id: str
    author_display_name: str | None
    current_version: int
    captured_at: str | None
    described_start_date: str | None
    described_end_date: str | None
    described_precision: str
    channel: str | None
    audio_uri: str | None
    created_at: str | None
    updated_at: str | None
    version: JournalVersionView | None = None
    person_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self, *, include_body: bool = True) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "author_person_id": self.author_person_id,
            "author_display_name": self.author_display_name,
            "current_version": self.current_version,
            "captured_at": self.captured_at,
            "described_start_date": self.described_start_date,
            "described_end_date": self.described_end_date,
            "described_precision": self.described_precision,
            "channel": self.channel,
            "audio_uri": self.audio_uri,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version.to_dict(include_body=include_body) if self.version else None,
            "person_ids": list(self.person_ids),
            "evidence_ids": list(self.evidence_ids),
            "provenance_kind": "owner_journal",
        }


class JournalServiceError(Exception):
    pass


def _parse_uuid(value: str, *, field: str) -> UUID:
    raw = (value or "").strip()
    if not raw:
        raise JournalServiceError(f"{field} is required")
    try:
        return UUID(raw)
    except (ValueError, TypeError, AttributeError) as exc:
        raise JournalServiceError(
            f"{field} must be a UUID (got {raw!r}). "
            "Leave optional ID fields blank on first Save."
        ) from exc


def _optional_uuids(values: list[str] | None, *, field: str) -> list[UUID]:
    out: list[UUID] = []
    for v in values or []:
        raw = (v or "").strip()
        if not raw:
            continue
        try:
            out.append(UUID(raw))
        except (ValueError, TypeError, AttributeError) as exc:
            raise JournalServiceError(
                f"{field} entries must be UUIDs (got {raw!r}). Leave blank if unknown."
            ) from exc
    return out


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _parse_date(value: str | date | None, *, field: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise JournalServiceError(f"{field} must be YYYY-MM-DD (got {raw!r})") from exc


def ensure_person(display_name: str) -> UUID:
    name = (display_name or "").strip()
    if len(name) < 2:
        raise JournalServiceError("author display_name required")
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id FROM people
            WHERE lower(display_name) = lower(%s)
              AND status IN ('unresolved', 'confirmed')
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (name,),
        ).fetchone()
        if row:
            return UUID(str(row["id"]))
        pid = uuid4()
        conn.execute(
            """
            INSERT INTO people (id, display_name, status)
            VALUES (%s, %s, 'confirmed')
            """,
            (pid, name),
        )
        return pid


def _load_associations(conn, journal_id: UUID) -> tuple[list[str], list[str]]:
    rows = conn.execute(
        """
        SELECT relationship_kind, to_type, to_id
        FROM relationships
        WHERE from_type = 'journal' AND from_id = %s
          AND status IN ('candidate', 'confirmed')
        """,
        (journal_id,),
    ).fetchall()
    people: list[str] = []
    evidence: list[str] = []
    for r in rows:
        tid = str(r["to_id"])
        if r["to_type"] == "person" and tid not in people:
            people.append(tid)
        if r["to_type"] == "evidence" and tid not in evidence:
            evidence.append(tid)
    return people, evidence


def _version_view(row: dict[str, Any]) -> JournalVersionView:
    return JournalVersionView(
        id=str(row["id"]),
        journal_id=str(row["journal_id"]),
        version=int(row["version"]),
        body_text=row["body_text"] or "",
        audio_uri=row.get("audio_uri"),
        actor_key=row["actor_key"] or "owner",
        note=row.get("note"),
        created_at=_iso(row.get("created_at")),
    )


def _journal_view(
    conn, journal_row: dict[str, Any], version_row: dict[str, Any] | None
) -> JournalView:
    jid = UUID(str(journal_row["id"]))
    people, evidence = _load_associations(conn, jid)
    author_name = None
    aid = journal_row.get("author_person_id")
    if aid:
        prow = conn.execute(
            "SELECT display_name FROM people WHERE id = %s", (aid,)
        ).fetchone()
        if prow:
            author_name = prow["display_name"]
    return JournalView(
        id=str(jid),
        title=journal_row.get("title"),
        status=journal_row["status"],
        author_person_id=str(aid),
        author_display_name=author_name,
        current_version=int(journal_row.get("current_version") or 1),
        captured_at=_iso(journal_row.get("captured_at")),
        described_start_date=_iso(journal_row.get("described_start_date")),
        described_end_date=_iso(journal_row.get("described_end_date")),
        described_precision=journal_row.get("described_precision") or "unknown",
        channel=journal_row.get("channel"),
        audio_uri=journal_row.get("audio_uri"),
        created_at=_iso(journal_row.get("created_at")),
        updated_at=_iso(journal_row.get("updated_at")),
        version=_version_view(version_row) if version_row else None,
        person_ids=people,
        evidence_ids=evidence,
    )


def _add_relationship(
    conn,
    *,
    kind: str,
    journal_id: UUID,
    to_type: str,
    to_id: UUID,
    label: str,
) -> None:
    conn.execute(
        """
        INSERT INTO relationships (
            id, relationship_kind, from_type, from_id, to_type, to_id,
            label, status, attributes_json
        )
        VALUES (%s, %s, 'journal', %s, %s, %s, %s, 'confirmed', '{}'::jsonb)
        """,
        (uuid4(), kind, journal_id, to_type, to_id, label),
    )


def _normalize_temporal(
    *,
    described_start_date: str | date | None,
    described_end_date: str | date | None,
    described_precision: str | None,
) -> tuple[date | None, date | None, str]:
    precision = (described_precision or "unknown").strip().lower()
    if precision not in DESCRIBED_PRECISIONS:
        raise JournalServiceError(
            f"described_precision must be one of {sorted(DESCRIBED_PRECISIONS)}"
        )
    start = _parse_date(described_start_date, field="described_start_date")
    end = _parse_date(described_end_date, field="described_end_date")
    if precision == "unknown":
        if start is not None or end is not None:
            raise JournalServiceError(
                "described_precision=unknown requires both described dates NULL"
            )
        return None, None, precision
    if (start is None) != (end is None):
        raise JournalServiceError(
            "described_start_date and described_end_date must both be set or both NULL"
        )
    if start is not None and end is not None and start > end:
        raise JournalServiceError("described_start_date must be <= described_end_date")
    return start, end, precision


def create_journal(
    *,
    title: str | None,
    body_text: str,
    author_display_name: str | None = None,
    author_person_id: str | None = None,
    channel: str | None = None,
    audio_uri: str | None = None,
    described_start_date: str | date | None = None,
    described_end_date: str | date | None = None,
    described_precision: str | None = "unknown",
    person_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    actor_key: str = "owner",
    note: str | None = None,
) -> JournalView:
    """Explicit Save of a new Journal as version 1. Draft STT is not enough."""
    body = (body_text or "").strip()
    if not body:
        raise JournalServiceError("body_text required")
    if (actor_key or "").lower() in {"ai", "llm", "model", "assistant", "stt", "whisper"}:
        raise JournalServiceError(
            "STT/AI output cannot be persisted as Journal truth without owner Save actor"
        )

    if author_person_id and str(author_person_id).strip():
        author_id = _parse_uuid(str(author_person_id), field="author_person_id")
    elif author_display_name:
        author_id = ensure_person(author_display_name)
    else:
        author_id = ensure_person("MemoryBox Owner")

    start, end, precision = _normalize_temporal(
        described_start_date=described_start_date,
        described_end_date=described_end_date,
        described_precision=described_precision,
    )
    person_uuids = _optional_uuids(person_ids, field="person_ids")
    evidence_uuids = _optional_uuids(evidence_ids, field="evidence_ids")
    ch = (channel or "ui").strip() or "ui"
    audio = (audio_uri or "").strip() or None

    journal_id = uuid4()
    version_id = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO journal_entries (
                id, title, body_text, channel, audio_uri, status,
                author_person_id, current_version, captured_at,
                described_start_date, described_end_date, described_precision
            )
            VALUES (
                %s, %s, %s, %s, %s, 'active',
                %s, 1, now(),
                %s, %s, %s
            )
            """,
            (
                journal_id,
                (title or "").strip() or None,
                body,
                ch,
                audio,
                author_id,
                start,
                end,
                precision,
            ),
        )
        conn.execute(
            """
            INSERT INTO journal_versions (
                id, journal_id, version, body_text, audio_uri, actor_key, note
            )
            VALUES (%s, %s, 1, %s, %s, %s, %s)
            """,
            (version_id, journal_id, body, audio, actor_key or "owner", note),
        )
        for pid in person_uuids:
            _add_relationship(
                conn,
                kind=REL_ABOUT_PERSON,
                journal_id=journal_id,
                to_type="person",
                to_id=pid,
                label="Journal about person",
            )
        for eid in evidence_uuids:
            _add_relationship(
                conn,
                kind=REL_CITES_EVIDENCE,
                journal_id=journal_id,
                to_type="evidence",
                to_id=eid,
                label="Journal cites evidence",
            )
        jrow = conn.execute(
            "SELECT * FROM journal_entries WHERE id = %s", (journal_id,)
        ).fetchone()
        vrow = conn.execute(
            "SELECT * FROM journal_versions WHERE journal_id = %s AND version = 1",
            (journal_id,),
        ).fetchone()
        assert jrow and vrow
        return _journal_view(conn, jrow, vrow)


def save_new_version(
    journal_id: str,
    *,
    body_text: str,
    title: str | None = None,
    audio_uri: str | None = None,
    described_start_date: str | date | None = None,
    described_end_date: str | date | None = None,
    described_precision: str | None = None,
    actor_key: str = "owner",
    note: str | None = None,
) -> JournalView:
    body = (body_text or "").strip()
    if not body:
        raise JournalServiceError("body_text required")
    if (actor_key or "").lower() in {"ai", "llm", "model", "assistant", "stt", "whisper"}:
        raise JournalServiceError(
            "STT/AI output cannot be persisted as Journal truth without owner Save actor"
        )
    jid = _parse_uuid(journal_id, field="journal_id")
    with connection() as conn:
        jrow = conn.execute(
            "SELECT * FROM journal_entries WHERE id = %s AND status = 'active'", (jid,)
        ).fetchone()
        if not jrow:
            raise JournalServiceError("journal not found")
        next_v = int(jrow.get("current_version") or 1) + 1
        audio = audio_uri if audio_uri is not None else jrow.get("audio_uri")
        audio = (audio or "").strip() or None

        if described_precision is not None or described_start_date is not None or described_end_date is not None:
            start, end, precision = _normalize_temporal(
                described_start_date=described_start_date
                if described_start_date is not None
                else jrow.get("described_start_date"),
                described_end_date=described_end_date
                if described_end_date is not None
                else jrow.get("described_end_date"),
                described_precision=described_precision
                if described_precision is not None
                else jrow.get("described_precision"),
            )
        else:
            start = jrow.get("described_start_date")
            end = jrow.get("described_end_date")
            precision = jrow.get("described_precision") or "unknown"

        conn.execute(
            """
            INSERT INTO journal_versions (
                id, journal_id, version, body_text, audio_uri, actor_key, note
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (uuid4(), jid, next_v, body, audio, actor_key or "owner", note),
        )
        conn.execute(
            """
            UPDATE journal_entries
            SET title = COALESCE(%s, title),
                body_text = %s,
                audio_uri = %s,
                current_version = %s,
                described_start_date = %s,
                described_end_date = %s,
                described_precision = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (
                (title or "").strip() or None if title is not None else None,
                body,
                audio,
                next_v,
                start,
                end,
                precision,
                jid,
            ),
        )
        # Fix title coalesce: when title is None we pass None and COALESCE keeps old —
        # but we used COALESCE(%s, title) with None which works. When title="" we want clear?
        # Keep as-is: empty title means keep previous via None only when title arg is None.
        jrow = conn.execute("SELECT * FROM journal_entries WHERE id = %s", (jid,)).fetchone()
        vrow = conn.execute(
            "SELECT * FROM journal_versions WHERE journal_id = %s AND version = %s",
            (jid, next_v),
        ).fetchone()
        assert jrow and vrow
        return _journal_view(conn, jrow, vrow)


def get_journal(journal_id: str, *, version: int | None = None) -> JournalView | None:
    try:
        jid = _parse_uuid(journal_id, field="journal_id")
    except JournalServiceError:
        return None
    with connection() as conn:
        jrow = conn.execute(
            "SELECT * FROM journal_entries WHERE id = %s", (jid,)
        ).fetchone()
        if not jrow:
            return None
        ver = int(version) if version is not None else int(jrow.get("current_version") or 1)
        vrow = conn.execute(
            "SELECT * FROM journal_versions WHERE journal_id = %s AND version = %s",
            (jid, ver),
        ).fetchone()
        if not vrow:
            return None
        return _journal_view(conn, jrow, vrow)


def list_journals(*, limit: int = 50) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, status, author_person_id, current_version,
                   captured_at, described_start_date, described_end_date,
                   described_precision, channel, created_at, updated_at
            FROM journal_entries
            WHERE status = 'active'
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": str(r["id"]),
                    "title": r["title"],
                    "status": r["status"],
                    "author_person_id": str(r["author_person_id"])
                    if r["author_person_id"]
                    else None,
                    "current_version": int(r.get("current_version") or 1),
                    "captured_at": _iso(r.get("captured_at")),
                    "described_start_date": _iso(r.get("described_start_date")),
                    "described_end_date": _iso(r.get("described_end_date")),
                    "described_precision": r.get("described_precision") or "unknown",
                    "channel": r.get("channel"),
                    "created_at": _iso(r.get("created_at")),
                    "updated_at": _iso(r.get("updated_at")),
                }
            )
        return out
