"""Story Service — I10A drafts, saved versions, Ask-current pointer.

Working versions use story_versions.version = 0 and lifecycle='working'.
Ask joins stories.current_saved_version_id only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from memorybox.db import connection

REL_ABOUT_PERSON = "about_person"
REL_CITES_EVIDENCE = "cites_evidence"
WORKING_VERSION_NUMBER = 0
SOURCE_KINDS = frozenset(
    {
        "photo",
        "video",
        "email_thread",
        "sms_conversation",
        "calendar_event",
        "artifact",
        "journal",
        "audio",
        "evidence",
    }
)
BLOCK_KINDS = frozenset({"heading", "paragraph", "memory_ref"})
AI_ACTORS = frozenset({"ai", "llm", "model", "assistant"})


class StoryServiceError(Exception):
    pass


def _parse_uuid(value: str, *, field: str) -> UUID:
    raw = (value or "").strip()
    if not raw:
        raise StoryServiceError(f"{field} is required")
    try:
        return UUID(raw)
    except (ValueError, TypeError, AttributeError) as exc:
        raise StoryServiceError(f"{field} must be a UUID (got {raw!r}).") from exc


def _as_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return UUID(raw)
    except (ValueError, TypeError, AttributeError):
        return None


def _optional_uuids(values: list[str] | None, *, field: str) -> list[UUID]:
    out: list[UUID] = []
    for v in values or []:
        raw = (v or "").strip()
        if not raw:
            continue
        out.append(_parse_uuid(raw, field=field))
    return out


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _reject_ai(actor_key: str) -> None:
    if (actor_key or "").lower() in AI_ACTORS:
        raise StoryServiceError(
            "AI-generated content cannot be persisted as owner Story evidence"
        )


def _owner_person_id() -> str | None:
    try:
        from memorybox.profile.owner import get_owner_person_id

        return get_owner_person_id()
    except Exception:
        return None


def ensure_person(display_name: str) -> UUID:
    from memorybox.person import resolve_person_by_name

    return UUID(resolve_person_by_name(display_name, create_if_missing=True).person_id)


def _flatten_blocks(blocks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for b in blocks or []:
        if (b.get("kind") or "") == "memory_ref":
            continue
        t = (b.get("text") or "").strip()
        if t:
            parts.append(t)
    return "\n\n".join(parts)


def _person_row(conn, person_id: Any) -> dict[str, Any] | None:
    if not person_id:
        return None
    row = conn.execute(
        "SELECT id, display_name FROM people WHERE id = %s", (person_id,)
    ).fetchone()
    if not row:
        return None
    pid = str(row["id"])
    return {
        "id": pid,
        "display_name": row["display_name"],
        "portrait_url": f"/people/{pid}/portrait",
    }


@dataclass
class StoryVersionView:
    id: str
    story_id: str
    version: int
    body_text: str
    actor_key: str
    note: str | None
    created_at: str | None
    lifecycle: str = "saved"
    title: str | None = None
    description: str | None = None
    narrator_person_id: str | None = None
    editor_person_id: str | None = None
    described_start_date: str | None = None
    described_end_date: str | None = None
    described_precision: str = "unknown"
    place_id: str | None = None
    place_label: str | None = None
    frozen_at: str | None = None
    blocks: list[dict[str, Any]] = field(default_factory=list)
    memories: list[dict[str, Any]] = field(default_factory=list)
    people: list[dict[str, Any]] = field(default_factory=list)

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
    visibility: str = "private"
    ask_available: bool = False
    has_working_draft: bool = False
    current_saved_version_id: str | None = None
    working_version_id: str | None = None
    lifecycle: str = "saved"
    description: str | None = None
    editor_person_id: str | None = None
    editor_display_name: str | None = None
    people: list[dict[str, Any]] = field(default_factory=list)
    memories: list[dict[str, Any]] = field(default_factory=list)
    blocks: list[dict[str, Any]] = field(default_factory=list)
    described_start_date: str | None = None
    described_end_date: str | None = None
    place_label: str | None = None
    cover_thumb_url: str | None = None

    def to_dict(self, *, include_body: bool = True) -> dict[str, Any]:
        d = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "narrator_person_id": self.narrator_person_id,
            "narrator_display_name": self.narrator_display_name,
            "current_version": self.current_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version.to_dict(include_body=include_body)
            if self.version
            else None,
            "person_ids": list(self.person_ids),
            "evidence_ids": list(self.evidence_ids),
            "provenance_kind": "owner_narrator_recollection",
            "visibility": self.visibility,
            "ask_available": self.ask_available,
            "has_working_draft": self.has_working_draft,
            "current_saved_version_id": self.current_saved_version_id,
            "working_version_id": self.working_version_id,
            "lifecycle": self.lifecycle,
            "description": self.description,
            "editor_person_id": self.editor_person_id,
            "editor_display_name": self.editor_display_name,
            "people": list(self.people),
            "memories": list(self.memories),
            "blocks": list(self.blocks),
            "described_start_date": self.described_start_date,
            "described_end_date": self.described_end_date,
            "place_label": self.place_label,
            "cover_thumb_url": self.cover_thumb_url,
            "current_saved_version_number": self.current_version if self.ask_available else None,
        }
        return d


def _load_version_children(conn, version_id: UUID) -> tuple[list, list, list]:
    blocks = conn.execute(
        """
        SELECT id, position, kind, text, memory_id
        FROM story_version_blocks
        WHERE version_id = %s
        ORDER BY position ASC
        """,
        (version_id,),
    ).fetchall()
    memories = conn.execute(
        """
        SELECT id, position, source_kind, source_id, label_snapshot,
               occurred_on, thumb_url, attributes_json
        FROM story_version_memories
        WHERE version_id = %s
        ORDER BY position ASC
        """,
        (version_id,),
    ).fetchall()
    people = conn.execute(
        """
        SELECT p.id, p.display_name, sp.position
        FROM story_version_people sp
        JOIN people p ON p.id = sp.person_id
        WHERE sp.version_id = %s
        ORDER BY sp.position ASC, p.display_name ASC
        """,
        (version_id,),
    ).fetchall()
    b_out = [
        {
            "id": str(r["id"]),
            "position": int(r["position"]),
            "kind": r["kind"],
            "text": r["text"] or "",
            "memory_id": str(r["memory_id"]) if r["memory_id"] else None,
        }
        for r in blocks
    ]
    m_out = [
        {
            "id": str(r["id"]),
            "position": int(r["position"]),
            "source_kind": r["source_kind"],
            "source_id": r["source_id"],
            "label_snapshot": r["label_snapshot"],
            "occurred_on": _iso(r["occurred_on"]),
            "thumb_url": r["thumb_url"],
            "attributes_json": r["attributes_json"] or {},
        }
        for r in memories
    ]
    p_out = [
        {
            "id": str(r["id"]),
            "display_name": r["display_name"],
            "portrait_url": f"/people/{r['id']}/portrait",
            "position": int(r["position"] or 0),
        }
        for r in people
    ]
    return b_out, m_out, p_out


def _version_view(conn, row: dict[str, Any]) -> StoryVersionView:
    vid = UUID(str(row["id"]))
    blocks, memories, people = _load_version_children(conn, vid)
    body = row.get("body_text") or _flatten_blocks(blocks)
    return StoryVersionView(
        id=str(row["id"]),
        story_id=str(row["story_id"]),
        version=int(row["version"]),
        body_text=body,
        actor_key=row.get("actor_key") or "owner",
        note=row.get("note"),
        created_at=_iso(row.get("created_at")),
        lifecycle=row.get("lifecycle") or "saved",
        title=row.get("title"),
        description=row.get("description"),
        narrator_person_id=str(row["narrator_person_id"])
        if row.get("narrator_person_id")
        else None,
        editor_person_id=str(row["editor_person_id"])
        if row.get("editor_person_id")
        else None,
        described_start_date=_iso(row.get("described_start_date")),
        described_end_date=_iso(row.get("described_end_date")),
        described_precision=row.get("described_precision") or "unknown",
        place_id=str(row["place_id"]) if row.get("place_id") else None,
        place_label=row.get("place_label"),
        frozen_at=_iso(row.get("frozen_at")),
        blocks=blocks,
        memories=memories,
        people=people,
    )


def _story_view(
    conn,
    story_row: dict[str, Any],
    version_row: dict[str, Any] | None,
) -> StoryView:
    sid = UUID(str(story_row["id"]))
    vv = _version_view(conn, version_row) if version_row else None
    saved_id = story_row.get("current_saved_version_id")
    work_id = story_row.get("working_version_id")
    narrator = _person_row(conn, (vv.narrator_person_id if vv else None) or story_row.get("narrator_person_id"))
    editor = _person_row(conn, vv.editor_person_id if vv else None)
    people = list(vv.people) if vv else []
    memories = list(vv.memories) if vv else []
    cover = None
    for m in memories:
        if m.get("thumb_url"):
            cover = m["thumb_url"]
            break
        if m.get("source_kind") == "photo" and m.get("source_id"):
            cover = f"/library/media/photo/{m['source_id']}"
            break
    lifecycle = "saved"
    if saved_id and work_id:
        lifecycle = "saved_with_draft"
    elif work_id and not saved_id:
        lifecycle = "draft_only"
    cur_n = int(story_row.get("current_version") or 1)
    if vv and vv.lifecycle == "saved":
        cur_n = vv.version
    elif saved_id:
        srow = conn.execute(
            "SELECT version FROM story_versions WHERE id = %s", (saved_id,)
        ).fetchone()
        if srow:
            cur_n = int(srow["version"])
    return StoryView(
        id=str(sid),
        title=(vv.title if vv and vv.title else story_row.get("title")),
        status=story_row["status"],
        narrator_person_id=narrator["id"] if narrator else None,
        narrator_display_name=narrator["display_name"] if narrator else None,
        current_version=cur_n,
        created_at=_iso(story_row.get("created_at")),
        updated_at=_iso(story_row.get("updated_at")),
        version=vv,
        person_ids=[p["id"] for p in people],
        evidence_ids=[
            m["source_id"]
            for m in memories
            if m.get("source_kind") in {"evidence", "photo"}
        ],
        visibility=story_row.get("visibility") or "private",
        ask_available=bool(saved_id) and story_row.get("status") == "active",
        has_working_draft=bool(work_id),
        current_saved_version_id=str(saved_id) if saved_id else None,
        working_version_id=str(work_id) if work_id else None,
        lifecycle=lifecycle,
        description=vv.description if vv else None,
        editor_person_id=editor["id"] if editor else None,
        editor_display_name=editor["display_name"] if editor else None,
        people=people,
        memories=memories,
        blocks=list(vv.blocks) if vv else [],
        described_start_date=vv.described_start_date if vv else None,
        described_end_date=vv.described_end_date if vv else None,
        place_label=vv.place_label if vv else None,
        cover_thumb_url=cover,
    )


def _replace_children(
    conn,
    version_id: UUID,
    *,
    blocks: list[dict[str, Any]] | None,
    memories: list[dict[str, Any]] | None,
    person_ids: list[str] | None,
) -> None:
    mem_ids: dict[str, UUID] = {}
    if memories is not None:
        conn.execute(
            "DELETE FROM story_version_memories WHERE version_id = %s", (version_id,)
        )
        pos = 0
        for m in memories:
            kind = (m.get("source_kind") or "").strip()
            if kind == "story":
                raise StoryServiceError("A Story cannot support another Story")
            if kind not in SOURCE_KINDS:
                raise StoryServiceError(f"unsupported source_kind {kind!r}")
            sid = str(m.get("source_id") or "").strip()
            if not sid:
                continue
            mid = uuid4()
            key = str(m.get("client_key") or m.get("id") or "")
            if key:
                mem_ids[key] = mid
            conn.execute(
                """
                INSERT INTO story_version_memories (
                    id, version_id, position, source_kind, source_id,
                    label_snapshot, occurred_on, thumb_url, attributes_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, '{}'::jsonb)
                ON CONFLICT (version_id, source_kind, source_id) DO NOTHING
                """,
                (
                    mid,
                    version_id,
                    int(m.get("position") if m.get("position") is not None else pos),
                    kind,
                    sid,
                    (m.get("label_snapshot") or m.get("title") or None),
                    m.get("occurred_on") or None,
                    m.get("thumb_url") or None,
                ),
            )
            pos += 1
    if blocks is not None:
        conn.execute(
            "DELETE FROM story_version_blocks WHERE version_id = %s", (version_id,)
        )
        for i, b in enumerate(blocks):
            kind = (b.get("kind") or "paragraph").strip()
            if kind not in BLOCK_KINDS:
                raise StoryServiceError(f"unsupported block kind {kind!r}")
            memory_id = None
            ref = b.get("memory_id") or b.get("memory_client_key")
            if ref and str(ref) in mem_ids:
                memory_id = mem_ids[str(ref)]
            elif b.get("memory_id"):
                try:
                    memory_id = UUID(str(b["memory_id"]))
                except (ValueError, TypeError):
                    memory_id = None
            conn.execute(
                """
                INSERT INTO story_version_blocks (
                    id, version_id, position, kind, text, memory_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid4(),
                    version_id,
                    int(b.get("position") if b.get("position") is not None else i),
                    kind,
                    (b.get("text") or None),
                    memory_id,
                ),
            )
    if person_ids is not None:
        conn.execute(
            "DELETE FROM story_version_people WHERE version_id = %s", (version_id,)
        )
        for i, pid in enumerate(person_ids):
            raw = (pid or "").strip()
            if not raw:
                continue
            conn.execute(
                """
                INSERT INTO story_version_people (version_id, person_id, position)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (version_id, _parse_uuid(raw, field="person_id"), i),
            )


def _copy_children(conn, src: UUID, dest: UUID) -> None:
    conn.execute(
        """
        INSERT INTO story_version_memories (
            id, version_id, position, source_kind, source_id,
            label_snapshot, occurred_on, thumb_url, attributes_json
        )
        SELECT gen_random_uuid(), %s, position, source_kind, source_id,
               label_snapshot, occurred_on, thumb_url, attributes_json
        FROM story_version_memories
        WHERE version_id = %s
        """,
        (dest, src),
    )
    # Remap memory ids for blocks via source_kind+source_id
    conn.execute(
        """
        INSERT INTO story_version_blocks (id, version_id, position, kind, text, memory_id)
        SELECT gen_random_uuid(), %s, b.position, b.kind, b.text,
               nm.id
        FROM story_version_blocks b
        LEFT JOIN story_version_memories om ON om.id = b.memory_id
        LEFT JOIN story_version_memories nm
          ON nm.version_id = %s
         AND om.source_kind = nm.source_kind
         AND om.source_id = nm.source_id
        WHERE b.version_id = %s
        """,
        (dest, dest, src),
    )
    conn.execute(
        """
        INSERT INTO story_version_people (version_id, person_id, position)
        SELECT %s, person_id, position
        FROM story_version_people
        WHERE version_id = %s
        ON CONFLICT DO NOTHING
        """,
        (dest, src),
    )


def _insert_working_version(
    conn,
    story_id: UUID,
    *,
    title: str | None,
    description: str | None,
    body_text: str,
    narrator_id: UUID | None,
    editor_id: UUID | None,
    note: str | None,
    described_start: str | None = None,
    described_end: str | None = None,
    place_id: str | None = None,
    place_label: str | None = None,
) -> UUID:
    vid = uuid4()
    conn.execute(
        """
        INSERT INTO story_versions (
            id, story_id, version, lifecycle, body_text, actor_key, note,
            title, description, narrator_person_id, editor_person_id,
            described_start_date, described_end_date, place_id, place_label
        )
        VALUES (
            %s, %s, %s, 'working', %s, 'owner', %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            vid,
            story_id,
            WORKING_VERSION_NUMBER,
            body_text or "",
            note,
            (title or "").strip() or None,
            (description or "").strip() or None,
            narrator_id,
            editor_id,
            described_start or None,
            described_end or None,
            place_id or None,
            (place_label or "").strip() or None,
        ),
    )
    return vid


def save_draft(
    *,
    story_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    body_text: str | None = None,
    blocks: list[dict[str, Any]] | None = None,
    memories: list[dict[str, Any]] | None = None,
    person_ids: list[str] | None = None,
    narrator_person_id: str | None = None,
    narrator_display_name: str | None = None,
    described_start_date: str | None = None,
    described_end_date: str | None = None,
    place_id: str | None = None,
    place_label: str | None = None,
    visibility: str | None = None,
    actor_key: str = "owner",
    composed_by_model: bool = False,
) -> StoryView:
    """Persist a working draft. Never sets Ask-current."""
    _reject_ai(actor_key)
    if composed_by_model:
        raise StoryServiceError(
            "AI-generated content cannot be persisted as owner Story evidence"
        )
    body_provided = blocks is not None or body_text is not None
    body = _flatten_blocks(blocks) if blocks else (body_text or "")
    narrator_id = None
    if narrator_person_id:
        narrator_id = _parse_uuid(narrator_person_id, field="narrator_person_id")
    elif narrator_display_name:
        narrator_id = ensure_person(narrator_display_name)
    editor_raw = _owner_person_id()
    editor_id = UUID(editor_raw) if editor_raw else narrator_id
    vis = None
    if visibility is not None:
        vis = (visibility or "").strip() or "private"
        if vis not in {"private", "shared_with_family"}:
            raise StoryServiceError("visibility must be private or shared_with_family")
    pid_place = None
    if place_id:
        pid_place = str(_parse_uuid(place_id, field="place_id"))

    with connection() as conn:
        if story_id:
            sid = _parse_uuid(story_id, field="story_id")
            srow = conn.execute(
                "SELECT * FROM stories WHERE id = %s AND status = 'active'", (sid,)
            ).fetchone()
            if not srow:
                raise StoryServiceError("story not found")
            work = srow.get("working_version_id")
            if not work:
                work = _insert_working_version(
                    conn,
                    sid,
                    title=title if title is not None else srow.get("title"),
                    description=description,
                    body_text=body,
                    narrator_id=narrator_id or srow.get("narrator_person_id"),
                    editor_id=editor_id,
                    note=None,
                    described_start=described_start_date,
                    described_end=described_end_date,
                    place_id=pid_place,
                    place_label=place_label,
                )
                conn.execute(
                    """
                    UPDATE stories
                    SET working_version_id = %s,
                        updated_at = now(),
                        visibility = COALESCE(%s, visibility)
                    WHERE id = %s
                    """,
                    (work, vis, sid),
                )
            else:
                conn.execute(
                    """
                    UPDATE story_versions
                    SET title = COALESCE(%s, title),
                        description = COALESCE(%s, description),
                        body_text = CASE WHEN %s THEN %s ELSE body_text END,
                        narrator_person_id = COALESCE(%s, narrator_person_id),
                        editor_person_id = COALESCE(%s, editor_person_id),
                        described_start_date = COALESCE(%s, described_start_date),
                        described_end_date = COALESCE(%s, described_end_date),
                        place_id = COALESCE(%s, place_id),
                        place_label = COALESCE(%s, place_label),
                        updated_at = now()
                    WHERE id = %s AND lifecycle = 'working'
                    """,
                    (
                        (title or "").strip() or None,
                        (description or "").strip() or None,
                        body_provided,
                        body,
                        narrator_id,
                        editor_id,
                        described_start_date,
                        described_end_date,
                        pid_place,
                        (place_label or "").strip() or None,
                        work,
                    ),
                )
                conn.execute(
                    """
                    UPDATE stories
                    SET updated_at = now(), visibility = COALESCE(%s, visibility)
                    WHERE id = %s
                    """,
                    (vis, sid),
                )
            vid = UUID(str(work)) if not isinstance(work, UUID) else work
            _replace_children(
                conn,
                vid,
                blocks=blocks,
                memories=memories,
                person_ids=person_ids,
            )
        else:
            sid = uuid4()
            conn.execute(
                """
                INSERT INTO stories (
                    id, title, status, narrator_person_id, current_version,
                    visibility, current_saved_version_id, working_version_id
                )
                VALUES (%s, %s, 'active', %s, 0, %s, NULL, NULL)
                """,
                (sid, (title or "").strip() or None, narrator_id, vis or "private"),
            )
            vid = _insert_working_version(
                conn,
                sid,
                title=title,
                description=description,
                body_text=body,
                narrator_id=narrator_id,
                editor_id=editor_id,
                note=None,
                described_start=described_start_date,
                described_end=described_end_date,
                place_id=pid_place,
                place_label=place_label,
            )
            conn.execute(
                "UPDATE stories SET working_version_id = %s WHERE id = %s",
                (vid, sid),
            )
            if blocks is None and body:
                blocks = [{"kind": "paragraph", "text": body, "position": 0}]
            people = list(person_ids or [])
            if narrator_id and str(narrator_id) not in people:
                people.append(str(narrator_id))
            _replace_children(
                conn, vid, blocks=blocks, memories=memories, person_ids=people
            )
        srow = conn.execute("SELECT * FROM stories WHERE id = %s", (sid,)).fetchone()
        vrow = conn.execute(
            "SELECT * FROM story_versions WHERE id = %s",
            (srow["working_version_id"],),
        ).fetchone()
        assert srow and vrow
        return _story_view(conn, srow, vrow)


def _freeze(conn, story_id: UUID, *, actor_key: str) -> StoryView:
    _reject_ai(actor_key)
    srow = conn.execute(
        "SELECT * FROM stories WHERE id = %s AND status = 'active'", (story_id,)
    ).fetchone()
    if not srow:
        raise StoryServiceError("story not found")
    work = srow.get("working_version_id")
    if not work:
        raise StoryServiceError("no working draft to save")
    wrow = conn.execute(
        "SELECT * FROM story_versions WHERE id = %s AND lifecycle = 'working'",
        (work,),
    ).fetchone()
    if not wrow:
        raise StoryServiceError("no working draft to save")
    title = (wrow.get("title") or srow.get("title") or "").strip()
    if not title:
        raise StoryServiceError("title is required to save a Story")
    saved = srow.get("current_saved_version_id")
    next_n = 1
    if saved:
        crow = conn.execute(
            "SELECT version FROM story_versions WHERE id = %s", (saved,)
        ).fetchone()
        next_n = int(crow["version"]) + 1 if crow else 1
    editor_raw = _owner_person_id()
    editor_id = UUID(editor_raw) if editor_raw else wrow.get("editor_person_id")
    conn.execute(
        """
        UPDATE story_versions
        SET version = %s,
            lifecycle = 'saved',
            frozen_at = now(),
            editor_person_id = COALESCE(%s, editor_person_id),
            updated_at = now()
        WHERE id = %s
        """,
        (next_n, editor_id, work),
    )
    conn.execute(
        """
        UPDATE stories
        SET title = %s,
            narrator_person_id = %s,
            current_version = %s,
            current_saved_version_id = %s,
            working_version_id = NULL,
            updated_at = now()
        WHERE id = %s
        """,
        (
            title,
            wrow.get("narrator_person_id"),
            next_n,
            work,
            story_id,
        ),
    )
    srow = conn.execute("SELECT * FROM stories WHERE id = %s", (story_id,)).fetchone()
    vrow = conn.execute(
        "SELECT * FROM story_versions WHERE id = %s", (work,)
    ).fetchone()
    assert srow and vrow
    return _story_view(conn, srow, vrow)


def save_story(story_id: str | None = None, **payload: Any) -> StoryView:
    """Save Story / Save revision: persist working then freeze Ask-current."""
    view = save_draft(story_id=story_id, **payload)
    with connection() as conn:
        return _freeze(conn, UUID(view.id), actor_key=payload.get("actor_key") or "owner")


def begin_edit(story_id: str) -> StoryView:
    """Clone current saved version into a working draft. Ask pointer unchanged."""
    sid = _parse_uuid(story_id, field="story_id")
    with connection() as conn:
        srow = conn.execute(
            "SELECT * FROM stories WHERE id = %s AND status = 'active'", (sid,)
        ).fetchone()
        if not srow:
            raise StoryServiceError("story not found")
        if srow.get("working_version_id"):
            vrow = conn.execute(
                "SELECT * FROM story_versions WHERE id = %s",
                (srow["working_version_id"],),
            ).fetchone()
            return _story_view(conn, srow, vrow)
        saved = srow.get("current_saved_version_id")
        if not saved:
            raise StoryServiceError("no saved version to edit")
        src = conn.execute(
            "SELECT * FROM story_versions WHERE id = %s", (saved,)
        ).fetchone()
        if not src:
            raise StoryServiceError("saved version missing")
        dest = _insert_working_version(
            conn,
            sid,
            title=src.get("title") or srow.get("title"),
            description=src.get("description"),
            body_text=src.get("body_text") or "",
            narrator_id=src.get("narrator_person_id") or srow.get("narrator_person_id"),
            editor_id=_as_uuid(_owner_person_id()) or _as_uuid(src.get("editor_person_id")),
            note=src.get("note"),
            described_start=src.get("described_start_date"),
            described_end=src.get("described_end_date"),
            place_id=str(src["place_id"]) if src.get("place_id") else None,
            place_label=src.get("place_label"),
        )
        _copy_children(conn, UUID(str(saved)), dest)
        conn.execute(
            """
            UPDATE stories SET working_version_id = %s, updated_at = now()
            WHERE id = %s
            """,
            (dest, sid),
        )
        srow = conn.execute("SELECT * FROM stories WHERE id = %s", (sid,)).fetchone()
        vrow = conn.execute(
            "SELECT * FROM story_versions WHERE id = %s", (dest,)
        ).fetchone()
        return _story_view(conn, srow, vrow)


def discard_working(story_id: str) -> dict[str, Any]:
    sid = _parse_uuid(story_id, field="story_id")
    with connection() as conn:
        srow = conn.execute(
            "SELECT * FROM stories WHERE id = %s AND status = 'active'", (sid,)
        ).fetchone()
        if not srow:
            raise StoryServiceError("story not found")
        work = srow.get("working_version_id")
        saved = srow.get("current_saved_version_id")
        if not work:
            return {"ok": True, "discarded": False, "story_id": str(sid)}
        conn.execute(
            "UPDATE stories SET working_version_id = NULL, updated_at = now() WHERE id = %s",
            (sid,),
        )
        conn.execute("DELETE FROM story_versions WHERE id = %s", (work,))
        if not saved:
            conn.execute(
                "UPDATE stories SET status = 'removed', updated_at = now() WHERE id = %s",
                (sid,),
            )
            return {"ok": True, "discarded": True, "removed": True, "story_id": str(sid)}
        return {"ok": True, "discarded": True, "removed": False, "story_id": str(sid)}


def remove_story(story_id: str) -> dict[str, Any]:
    """Soft-remove a Story. Panel and Ask hide it. History rows stay."""
    sid = _parse_uuid(story_id, field="story_id")
    with connection() as conn:
        srow = conn.execute(
            "SELECT id FROM stories WHERE id = %s AND status = 'active'", (sid,)
        ).fetchone()
        if not srow:
            raise StoryServiceError("story not found")
        conn.execute(
            """
            UPDATE stories
            SET status = 'removed', working_version_id = NULL, updated_at = now()
            WHERE id = %s
            """,
            (sid,),
        )
    return {"ok": True, "removed": True, "story_id": str(sid)}


def set_visibility(story_id: str, visibility: str) -> StoryView:
    vis = (visibility or "").strip()
    if vis not in {"private", "shared_with_family"}:
        raise StoryServiceError("visibility must be private or shared_with_family")
    sid = _parse_uuid(story_id, field="story_id")
    with connection() as conn:
        conn.execute(
            "UPDATE stories SET visibility = %s, updated_at = now() WHERE id = %s",
            (vis, sid),
        )
    view = get_story(story_id)
    if not view:
        raise StoryServiceError("story not found")
    return view


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
    description: str | None = None,
    memories: list[dict[str, Any]] | None = None,
    blocks: list[dict[str, Any]] | None = None,
    visibility: str | None = None,
    place_id: str | None = None,
    place_label: str | None = None,
    described_start_date: str | None = None,
    described_end_date: str | None = None,
    story_id: str | None = None,
    composed_by_model: bool = False,
) -> StoryView:
    """Compat: explicit Save Story as version 1 (Ask-visible)."""
    _reject_ai(actor_key)
    if composed_by_model:
        raise StoryServiceError(
            "AI-generated content cannot be persisted as owner Story evidence"
        )
    body = (body_text or "").strip()
    mems = list(memories or [])
    for eid in evidence_ids or []:
        raw = (eid or "").strip()
        if raw:
            mems.append({"source_kind": "evidence", "source_id": raw})
    if note:
        import re

        photo = re.search(r"mb_source_photo=(\S+)", note)
        thumb = re.search(r"mb_thumb=(\S+)", note)
        if photo:
            mems.append(
                {
                    "source_kind": "photo",
                    "source_id": photo.group(1),
                    "thumb_url": thumb.group(1) if thumb else None,
                }
            )
    blks = blocks
    if blks is None and body:
        blks = [{"kind": "paragraph", "text": body, "position": 0}]
    draft = save_draft(
        story_id=story_id,
        title=title or "Untitled story",
        description=description,
        body_text=body,
        blocks=blks,
        memories=mems,
        person_ids=person_ids,
        narrator_person_id=narrator_person_id,
        narrator_display_name=narrator_display_name,
        actor_key=actor_key,
        visibility=visibility,
        place_id=place_id,
        place_label=place_label,
        described_start_date=described_start_date,
        described_end_date=described_end_date,
        composed_by_model=composed_by_model,
    )
    return save_story(
        draft.id,
        title=title or "Untitled story",
        description=description,
        body_text=body,
        blocks=blks,
        memories=mems,
        person_ids=person_ids,
        narrator_person_id=narrator_person_id,
        narrator_display_name=narrator_display_name,
        actor_key=actor_key,
        visibility=visibility,
        place_id=place_id,
        place_label=place_label,
        described_start_date=described_start_date,
        described_end_date=described_end_date,
        composed_by_model=composed_by_model,
    )


def save_new_version(
    story_id: str,
    *,
    body_text: str,
    title: str | None = None,
    actor_key: str = "owner",
    note: str | None = None,
) -> StoryView:
    """Compat: freeze next saved version (Save revision without a long-lived draft)."""
    _reject_ai(actor_key)
    body = (body_text or "").strip()
    if not body:
        raise StoryServiceError("body_text required")
    begin_edit(story_id)
    save_draft(
        story_id=story_id,
        title=title,
        body_text=body,
        blocks=[{"kind": "paragraph", "text": body, "position": 0}],
        actor_key=actor_key,
    )
    with connection() as conn:
        return _freeze(conn, _parse_uuid(story_id, field="story_id"), actor_key=actor_key)


def get_story(
    story_id: str,
    *,
    version: int | None = None,
    working: bool = False,
) -> StoryView | None:
    try:
        sid = _parse_uuid(story_id, field="story_id")
    except StoryServiceError:
        return None
    with connection() as conn:
        srow = conn.execute("SELECT * FROM stories WHERE id = %s", (sid,)).fetchone()
        if not srow:
            return None
        if working:
            wid = srow.get("working_version_id")
            if not wid:
                return None
            vrow = conn.execute(
                "SELECT * FROM story_versions WHERE id = %s", (wid,)
            ).fetchone()
            return _story_view(conn, srow, vrow) if vrow else None
        if version is not None:
            vrow = conn.execute(
                """
                SELECT * FROM story_versions
                WHERE story_id = %s AND version = %s AND lifecycle = 'saved'
                """,
                (sid, int(version)),
            ).fetchone()
            return _story_view(conn, srow, vrow) if vrow else None
        saved = srow.get("current_saved_version_id")
        if saved:
            vrow = conn.execute(
                "SELECT * FROM story_versions WHERE id = %s", (saved,)
            ).fetchone()
            return _story_view(conn, srow, vrow) if vrow else None
        work = srow.get("working_version_id")
        if work:
            vrow = conn.execute(
                "SELECT * FROM story_versions WHERE id = %s", (work,)
            ).fetchone()
            return _story_view(conn, srow, vrow) if vrow else None
        return _story_view(conn, srow, None)


def list_version_history(story_id: str) -> list[dict[str, Any]]:
    sid = _parse_uuid(story_id, field="story_id")
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, version, title, frozen_at, created_at, editor_person_id
            FROM story_versions
            WHERE story_id = %s AND lifecycle = 'saved'
            ORDER BY version DESC
            """,
            (sid,),
        ).fetchall()
        out = []
        for r in rows:
            ed = _person_row(conn, r.get("editor_person_id"))
            out.append(
                {
                    "id": str(r["id"]),
                    "version": int(r["version"]),
                    "title": r["title"],
                    "frozen_at": _iso(r["frozen_at"]),
                    "created_at": _iso(r["created_at"]),
                    "editor": ed,
                }
            )
        return out


def list_stories(
    *,
    limit: int = 50,
    status_filter: str | None = None,
    visibility: str | None = None,
    person_id: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """Panel list. status_filter: all|drafts|saved."""
    filt = (status_filter or "all").strip().lower()
    vis = (visibility or "").strip() or None
    needle = (q or "").strip().lower()
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT s.*,
                   sv_saved.version AS saved_n,
                   COALESCE(sv_work.title, sv_saved.title, s.title) AS display_title,
                   COALESCE(sv_work.description, sv_saved.description) AS display_description,
                   COALESCE(sv_work.described_start_date, sv_saved.described_start_date) AS d0,
                   COALESCE(sv_work.described_end_date, sv_saved.described_end_date) AS d1,
                   COALESCE(sv_work.id, sv_saved.id) AS display_version_id
            FROM stories s
            LEFT JOIN story_versions sv_saved ON sv_saved.id = s.current_saved_version_id
            LEFT JOIN story_versions sv_work ON sv_work.id = s.working_version_id
            WHERE s.status = 'active'
            ORDER BY s.updated_at DESC
            LIMIT %s
            """,
            (max(limit * 8, 100),),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            has_saved = bool(r.get("current_saved_version_id"))
            has_work = bool(r.get("working_version_id"))
            if filt == "drafts" and not has_work:
                continue
            if filt == "saved" and not has_saved:
                continue
            if vis and (r.get("visibility") or "private") != vis:
                continue
            display_vid = r.get("display_version_id")
            people: list[dict[str, Any]] = []
            mem_n = 0
            cover = None
            if display_vid:
                people = [
                    {
                        "id": str(p["id"]),
                        "display_name": p["display_name"],
                        "portrait_url": f"/people/{p['id']}/portrait",
                    }
                    for p in conn.execute(
                        """
                        SELECT p.id, p.display_name
                        FROM story_version_people sp
                        JOIN people p ON p.id = sp.person_id
                        WHERE sp.version_id = %s
                        ORDER BY sp.position
                        """,
                        (display_vid,),
                    ).fetchall()
                ]
                mrows = conn.execute(
                    """
                    SELECT source_kind, source_id, thumb_url
                    FROM story_version_memories
                    WHERE version_id = %s
                    ORDER BY position
                    """,
                    (display_vid,),
                ).fetchall()
                mem_n = len(mrows)
                for m in mrows:
                    if m.get("thumb_url"):
                        cover = m["thumb_url"]
                        break
                    if m.get("source_kind") == "photo" and m.get("source_id"):
                        cover = f"/library/media/photo/{m['source_id']}"
                        break
            if person_id and not any(p["id"] == person_id for p in people):
                continue
            block_blob = ""
            if display_vid:
                brows = conn.execute(
                    """
                    SELECT text FROM story_version_blocks
                    WHERE version_id = %s AND text IS NOT NULL
                    """,
                    (display_vid,),
                ).fetchall()
                block_blob = " ".join(b.get("text") or "" for b in brows)
            blob = " ".join(
                [
                    r.get("display_title") or "",
                    r.get("display_description") or "",
                    " ".join(p.get("display_name") or "" for p in people),
                    block_blob,
                ]
            ).lower()
            if needle and needle not in blob:
                continue
            badge = "draft" if (has_work and not has_saved) else (
                "draft" if has_work else "saved"
            )
            if has_saved and not has_work:
                badge = "saved"
            out.append(
                {
                    "id": str(r["id"]),
                    "title": r.get("display_title"),
                    "description": r.get("display_description"),
                    "status": r["status"],
                    "visibility": r.get("visibility") or "private",
                    "ask_available": has_saved,
                    "has_working_draft": has_work,
                    "badge": badge,
                    "lifecycle": (
                        "saved_with_draft"
                        if has_saved and has_work
                        else ("draft_only" if has_work else "saved")
                    ),
                    "narrator_person_id": str(r["narrator_person_id"])
                    if r.get("narrator_person_id")
                    else None,
                    "current_version": int(r["saved_n"] or r.get("current_version") or 0),
                    "created_at": _iso(r["created_at"]),
                    "updated_at": _iso(r["updated_at"]),
                    "people": people,
                    "memory_count": mem_n,
                    "described_start_date": _iso(r.get("d0")),
                    "described_end_date": _iso(r.get("d1")),
                    "cover_thumb_url": cover,
                }
            )
            if len(out) >= limit:
                break
        return out


def associate_person(story_id: str, person_id: str) -> StoryView:
    view = get_story(story_id)
    if not view:
        raise StoryServiceError("story not found")
    if view.ask_available and not view.has_working_draft:
        view = begin_edit(story_id)
    elif view.has_working_draft:
        view = get_story(story_id, working=True) or view
    people = list(view.person_ids)
    if person_id not in people:
        people.append(person_id)
    return save_draft(
        story_id=story_id,
        person_ids=people,
        blocks=view.blocks,
        memories=view.memories,
        title=view.title,
        description=view.description,
    )


def associate_evidence(story_id: str, evidence_id: str) -> StoryView:
    view = get_story(story_id)
    if not view:
        raise StoryServiceError("story not found")
    if view.ask_available and not view.has_working_draft:
        begin_edit(story_id)
        view = get_story(story_id, working=True) or view
    mems = list(view.memories)
    if not any(
        m.get("source_id") == evidence_id
        and m.get("source_kind") in {"evidence", "photo"}
        for m in mems
    ):
        mems.append({"source_kind": "evidence", "source_id": evidence_id})
    return save_draft(story_id=story_id, memories=mems, blocks=view.blocks, person_ids=view.person_ids)


def add_working_memory(
    story_id: str,
    *,
    source_kind: str,
    source_id: str,
    label_snapshot: str | None = None,
    thumb_url: str | None = None,
    occurred_on: str | None = None,
) -> StoryView:
    if source_kind == "story":
        raise StoryServiceError("A Story cannot support another Story")
    if source_kind not in SOURCE_KINDS:
        raise StoryServiceError(f"unsupported source_kind {source_kind!r}")
    view = get_story(story_id)
    if not view:
        raise StoryServiceError("story not found")
    if view.ask_available and not view.has_working_draft:
        begin_edit(story_id)
        view = get_story(story_id, working=True) or view
    mems = list(view.memories or [])
    if any(
        m.get("source_kind") == source_kind and m.get("source_id") == source_id
        for m in mems
    ):
        return get_story(story_id, working=True) or view
    mems.append(
        {
            "source_kind": source_kind,
            "source_id": source_id,
            "label_snapshot": label_snapshot,
            "thumb_url": thumb_url,
            "occurred_on": occurred_on,
            "position": len(mems),
        }
    )
    return save_draft(
        story_id=story_id,
        memories=mems,
        blocks=view.blocks,
        person_ids=view.person_ids,
        title=view.title,
        description=view.description,
    )


def stories_using_media(*, source_kind: str, source_id: str) -> list[dict[str, Any]]:
    if source_kind == "story":
        return []
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT s.id
            FROM stories s
            JOIN story_versions sv
              ON sv.id IN (s.working_version_id, s.current_saved_version_id)
            JOIN story_version_memories m ON m.version_id = sv.id
            WHERE s.status = 'active'
              AND m.source_kind = %s
              AND m.source_id = %s
            """,
            (source_kind, source_id),
        ).fetchall()
        # Also match photo note leftovers via source_id on either pointer
        out = []
        seen: set[str] = set()
        for r in rows:
            sid = str(r["id"])
            if sid in seen:
                continue
            seen.add(sid)
            view = get_story(sid)
            if view:
                out.append(view.to_dict(include_body=False))
        return out
