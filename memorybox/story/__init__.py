"""Story Service — owner-saved Stories with immutable versions (Increment 5)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from memorybox.db import connection

REL_ABOUT_PERSON = "about_person"
REL_CITES_EVIDENCE = "cites_evidence"


@dataclass
class StoryVersionView:
    id: str
    story_id: str
    version: int
    body_text: str
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
class StoryView:
    id: str
    title: str | None
    status: str
    narrator_person_id: str | None
    narrator_display_name: str | None
    current_version: int
    created_at: str | None
    updated_at: str | None
    version: StoryVersionView | None = None
    person_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self, *, include_body: bool = True) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "narrator_person_id": self.narrator_person_id,
            "narrator_display_name": self.narrator_display_name,
            "current_version": self.current_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version.to_dict(include_body=include_body) if self.version else None,
            "person_ids": list(self.person_ids),
            "evidence_ids": list(self.evidence_ids),
            "provenance_kind": "owner_narrator_recollection",
        }


class StoryServiceError(Exception):
    pass


def _parse_uuid(value: str, *, field: str) -> UUID:
    raw = (value or "").strip()
    if not raw:
        raise StoryServiceError(f"{field} is required")
    try:
        return UUID(raw)
    except (ValueError, TypeError, AttributeError) as exc:
        raise StoryServiceError(
            f"{field} must be a UUID (got {raw!r}). "
            "For a first Save, leave optional Evidence/Person ID fields blank."
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
            raise StoryServiceError(
                f"{field} entries must be UUIDs (got {raw!r}). "
                "Leave blank on first Save if you do not have an Evidence/Person UUID."
            ) from exc
    return out


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def ensure_person(display_name: str) -> UUID:
    """Find or create a Person by display_name (I5 thin; not full Person productization)."""
    name = (display_name or "").strip()
    if len(name) < 2:
        raise StoryServiceError("narrator/person display_name required")
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


def _load_associations(conn, story_id: UUID) -> tuple[list[str], list[str]]:
    rows = conn.execute(
        """
        SELECT relationship_kind, to_type, to_id
        FROM relationships
        WHERE from_type = 'story' AND from_id = %s
          AND status IN ('candidate', 'confirmed')
        """,
        (story_id,),
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


def _version_view(row: dict[str, Any]) -> StoryVersionView:
    return StoryVersionView(
        id=str(row["id"]),
        story_id=str(row["story_id"]),
        version=int(row["version"]),
        body_text=row["body_text"] or "",
        actor_key=row["actor_key"] or "owner",
        note=row.get("note"),
        created_at=_iso(row.get("created_at")),
    )


def _story_view(conn, story_row: dict[str, Any], version_row: dict[str, Any] | None) -> StoryView:
    sid = UUID(str(story_row["id"]))
    people, evidence = _load_associations(conn, sid)
    narrator_name = None
    nid = story_row.get("narrator_person_id")
    if nid:
        prow = conn.execute(
            "SELECT display_name FROM people WHERE id = %s", (nid,)
        ).fetchone()
        if prow:
            narrator_name = prow["display_name"]
    return StoryView(
        id=str(sid),
        title=story_row.get("title"),
        status=story_row["status"],
        narrator_person_id=str(nid) if nid else None,
        narrator_display_name=narrator_name,
        current_version=int(story_row["current_version"]),
        created_at=_iso(story_row.get("created_at")),
        updated_at=_iso(story_row.get("updated_at")),
        version=_version_view(version_row) if version_row else None,
        person_ids=people,
        evidence_ids=evidence,
    )


def _add_relationship(
    conn,
    *,
    kind: str,
    story_id: UUID,
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
        VALUES (%s, %s, 'story', %s, %s, %s, %s, 'confirmed', '{}'::jsonb)
        """,
        (uuid4(), kind, story_id, to_type, to_id, label),
    )


def create_story(
    *,
    title: str | None,
    body_text: str,
    narrator_display_name: str | None = None,
    narrator_person_id: str | None = None,
    person_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    actor_key: str = "owner",
    note: str | None = None,
) -> StoryView:
    """Explicit Save of a new Story as version 1. Rejects AI actor persistence."""
    body = (body_text or "").strip()
    if not body:
        raise StoryServiceError("body_text required")
    if (actor_key or "").lower() in {"ai", "llm", "model", "assistant"}:
        raise StoryServiceError(
            "AI-generated content cannot be persisted as owner Story evidence"
        )

    narrator_id: UUID | None = None
    if narrator_person_id and str(narrator_person_id).strip():
        narrator_id = _parse_uuid(str(narrator_person_id), field="narrator_person_id")
    elif narrator_display_name:
        narrator_id = ensure_person(narrator_display_name)

    person_uuids = _optional_uuids(person_ids, field="person_ids")
    evidence_uuids = _optional_uuids(evidence_ids, field="evidence_ids")

    story_id = uuid4()
    version_id = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO stories (
                id, title, status, narrator_person_id, current_version
            )
            VALUES (%s, %s, 'active', %s, 1)
            """,
            (story_id, (title or "").strip() or None, narrator_id),
        )
        conn.execute(
            """
            INSERT INTO story_versions (
                id, story_id, version, body_text, actor_key, note
            )
            VALUES (%s, %s, 1, %s, %s, %s)
            """,
            (version_id, story_id, body, actor_key or "owner", note),
        )
        for pid in person_uuids:
            _add_relationship(
                conn,
                kind=REL_ABOUT_PERSON,
                story_id=story_id,
                to_type="person",
                to_id=pid,
                label="Story about person",
            )
        for eid in evidence_uuids:
            _add_relationship(
                conn,
                kind=REL_CITES_EVIDENCE,
                story_id=story_id,
                to_type="evidence",
                to_id=eid,
                label="Story cites evidence",
            )
        # Narrator also counts as person association when present
        if narrator_id and all(pid != narrator_id for pid in person_uuids):
            _add_relationship(
                conn,
                kind=REL_ABOUT_PERSON,
                story_id=story_id,
                to_type="person",
                to_id=narrator_id,
                label="Story narrator",
            )
        srow = conn.execute("SELECT * FROM stories WHERE id = %s", (story_id,)).fetchone()
        vrow = conn.execute(
            "SELECT * FROM story_versions WHERE story_id = %s AND version = 1",
            (story_id,),
        ).fetchone()
        assert srow and vrow
        return _story_view(conn, srow, vrow)


def save_new_version(
    story_id: str,
    *,
    body_text: str,
    title: str | None = None,
    actor_key: str = "owner",
    note: str | None = None,
) -> StoryView:
    """Edit + Save: create next immutable version; do not overwrite prior."""
    body = (body_text or "").strip()
    if not body:
        raise StoryServiceError("body_text required")
    if (actor_key or "").lower() in {"ai", "llm", "model", "assistant"}:
        raise StoryServiceError(
            "AI-generated content cannot be persisted as owner Story evidence"
        )
    sid = _parse_uuid(story_id, field="story_id")
    with connection() as conn:
        srow = conn.execute(
            "SELECT * FROM stories WHERE id = %s AND status = 'active'", (sid,)
        ).fetchone()
        if not srow:
            raise StoryServiceError("story not found")
        next_v = int(srow["current_version"]) + 1
        conn.execute(
            """
            INSERT INTO story_versions (
                id, story_id, version, body_text, actor_key, note
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (uuid4(), sid, next_v, body, actor_key or "owner", note),
        )
        if title is not None:
            conn.execute(
                """
                UPDATE stories
                SET title = %s, current_version = %s, updated_at = now()
                WHERE id = %s
                """,
                ((title or "").strip() or None, next_v, sid),
            )
        else:
            conn.execute(
                """
                UPDATE stories
                SET current_version = %s, updated_at = now()
                WHERE id = %s
                """,
                (next_v, sid),
            )
        srow = conn.execute("SELECT * FROM stories WHERE id = %s", (sid,)).fetchone()
        vrow = conn.execute(
            "SELECT * FROM story_versions WHERE story_id = %s AND version = %s",
            (sid, next_v),
        ).fetchone()
        assert srow and vrow
        return _story_view(conn, srow, vrow)


def get_story(story_id: str, *, version: int | None = None) -> StoryView | None:
    try:
        sid = _parse_uuid(story_id, field="story_id")
    except StoryServiceError:
        return None
    with connection() as conn:
        srow = conn.execute("SELECT * FROM stories WHERE id = %s", (sid,)).fetchone()
        if not srow:
            return None
        ver = int(version) if version is not None else int(srow["current_version"])
        vrow = conn.execute(
            "SELECT * FROM story_versions WHERE story_id = %s AND version = %s",
            (sid, ver),
        ).fetchone()
        if not vrow:
            return None
        return _story_view(conn, srow, vrow)


def list_stories(*, limit: int = 50) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, status, narrator_person_id, current_version,
                   created_at, updated_at
            FROM stories
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
                    "narrator_person_id": str(r["narrator_person_id"])
                    if r["narrator_person_id"]
                    else None,
                    "current_version": int(r["current_version"]),
                    "created_at": _iso(r["created_at"]),
                    "updated_at": _iso(r["updated_at"]),
                }
            )
        return out


def associate_person(story_id: str, person_id: str) -> StoryView:
    sid = _parse_uuid(story_id, field="story_id")
    pid = _parse_uuid(person_id, field="person_id")
    with connection() as conn:
        exists = conn.execute(
            """
            SELECT 1 FROM relationships
            WHERE from_type='story' AND from_id=%s AND to_type='person' AND to_id=%s
            LIMIT 1
            """,
            (sid, pid),
        ).fetchone()
        if not exists:
            _add_relationship(
                conn,
                kind=REL_ABOUT_PERSON,
                story_id=sid,
                to_type="person",
                to_id=pid,
                label="Story about person",
            )
    view = get_story(story_id)
    if not view:
        raise StoryServiceError("story not found")
    return view


def associate_evidence(story_id: str, evidence_id: str) -> StoryView:
    sid = _parse_uuid(story_id, field="story_id")
    eid = _parse_uuid(evidence_id, field="evidence_id")
    with connection() as conn:
        exists = conn.execute(
            """
            SELECT 1 FROM relationships
            WHERE from_type='story' AND from_id=%s AND to_type='evidence' AND to_id=%s
            LIMIT 1
            """,
            (sid, eid),
        ).fetchone()
        if not exists:
            _add_relationship(
                conn,
                kind=REL_CITES_EVIDENCE,
                story_id=sid,
                to_type="evidence",
                to_id=eid,
                label="Story cites evidence",
            )
    view = get_story(story_id)
    if not view:
        raise StoryServiceError("story not found")
    return view
