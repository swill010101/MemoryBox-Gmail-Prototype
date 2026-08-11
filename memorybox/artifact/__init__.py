"""Increment 9 — Artifact service (conceptual object ≠ representation file)."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from memorybox.db import connection
from memorybox.story import StoryServiceError, create_story

ARTIFACT_KINDS = (
    "keepsake_object",
    "letter",
    "document",
    "recipe_card",
    "clipping",
    "photograph_of_object",
    "other",
)

REL_ABOUT_PERSON = "about_person"
REL_CITES_EVIDENCE = "cites_evidence"
REL_ABOUT_ARTIFACT = "about_artifact"  # story → artifact
REL_ABOUT_PLACE = "about_place"
REL_ABOUT_EVENT = "about_event"


class ArtifactServiceError(Exception):
    pass


def _parse_uuid(value: str, *, field: str) -> UUID:
    raw = (value or "").strip()
    if not raw:
        raise ArtifactServiceError(f"{field} is required")
    try:
        return UUID(raw)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ArtifactServiceError(f"{field} must be a UUID") from exc


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    s = str(v).strip()
    return s or None


def artifact_media_root() -> Path:
    """Durable SoT for MB-managed representation originals (D7 config-only).

    FlightSim PostgreSQL holds Artifact domain knowledge and URI/hash refs.
    Binary originals live on media-server under MEMORYBOX_ARTIFACT_MEDIA_ROOT
    (P1 ops: MemoryBox\\Artifacts under the established photos\\MemoryBox tree —
    see docs/ops/FLIGHTSIM_I9_ARTIFACT_RUNBOOK.md). Never hard-code UNC here.
    """
    raw = (os.environ.get("MEMORYBOX_ARTIFACT_MEDIA_ROOT") or "").strip()
    if raw:
        return Path(raw)
    if (os.environ.get("MEMORYBOX_ALLOW_DEV_DEFAULTS") or "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        # Desktop/prove only — never the FlightSim archive SoT.
        p = Path(os.environ.get("TEMP") or ".") / "memorybox_artifact_media"
        p.mkdir(parents=True, exist_ok=True)
        return p
    raise ArtifactServiceError(
        "MEMORYBOX_ARTIFACT_MEDIA_ROOT is required for MB-managed Artifact uploads "
        "(media-server durable path under MemoryBox tree; not FlightSim local disk "
        "as archive SoT; see docs/ops/FLIGHTSIM_I9_ARTIFACT_RUNBOOK.md)"
    )


def _safe_filename(name: str) -> str:
    base = Path(name or "upload.bin").name
    base = re.sub(r"[^\w.\-]+", "_", base).strip("._") or "upload.bin"
    return base[:180]


@dataclass
class ArtifactRepresentationView:
    id: str
    artifact_id: str
    representation_kind: str
    evidence_id: str | None = None
    media_object_id: str | None = None
    uri: str | None = None
    content_hash: str | None = None
    mime_type: str | None = None
    original_filename: str | None = None
    byte_size: int | None = None
    sort_order: int = 0
    label: str | None = None
    created_at: str | None = None
    download_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ArtifactView:
    id: str
    kind: str
    label: str
    description: str | None
    status: str
    current_metadata_revision: int
    unresolved_context: dict[str, Any]
    person_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    story_ids: list[str] = field(default_factory=list)
    representations: list[ArtifactRepresentationView] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["representations"] = [r.to_dict() for r in self.representations]
        return d


def _rep_from_row(r: dict[str, Any]) -> ArtifactRepresentationView:
    rid = str(r["id"])
    aid = str(r["artifact_id"])
    kind = str(r["representation_kind"])
    download = None
    if kind == "mb_managed":
        download = f"/artifact/{aid}/representations/{rid}/bytes"
    return ArtifactRepresentationView(
        id=rid,
        artifact_id=aid,
        representation_kind=kind,
        evidence_id=str(r["evidence_id"]) if r.get("evidence_id") else None,
        media_object_id=str(r["media_object_id"]) if r.get("media_object_id") else None,
        uri=r.get("uri"),
        content_hash=r.get("content_hash"),
        mime_type=r.get("mime_type"),
        original_filename=r.get("original_filename"),
        byte_size=int(r["byte_size"]) if r.get("byte_size") is not None else None,
        sort_order=int(r.get("sort_order") or 0),
        label=r.get("label"),
        created_at=_iso(r.get("created_at")),
        download_url=download,
    )


def _load_reps(conn, artifact_id: UUID) -> list[ArtifactRepresentationView]:
    rows = conn.execute(
        """
        SELECT * FROM artifact_representations
        WHERE artifact_id = %s
        ORDER BY sort_order ASC, created_at ASC
        """,
        (artifact_id,),
    ).fetchall()
    return [_rep_from_row(dict(r)) for r in rows]


def _load_links(conn, artifact_id: UUID) -> tuple[list[str], list[str], list[str]]:
    people: list[str] = []
    evidence: list[str] = []
    stories: list[str] = []
    rows = conn.execute(
        """
        SELECT relationship_kind, from_type, from_id, to_type, to_id, status
        FROM relationships
        WHERE status IN ('candidate', 'confirmed')
          AND (
            (from_type = 'artifact' AND from_id = %s)
            OR (to_type = 'artifact' AND to_id = %s)
          )
        """,
        (artifact_id, artifact_id),
    ).fetchall()
    for r in rows:
        if r["from_type"] == "artifact" and r["to_type"] == "person":
            people.append(str(r["to_id"]))
        elif r["from_type"] == "artifact" and r["to_type"] == "evidence":
            evidence.append(str(r["to_id"]))
        elif r["from_type"] == "story" and r["to_type"] == "artifact":
            stories.append(str(r["from_id"]))
        elif r["from_type"] == "artifact" and r["to_type"] == "story":
            stories.append(str(r["to_id"]))
    return (
        list(dict.fromkeys(people)),
        list(dict.fromkeys(evidence)),
        list(dict.fromkeys(stories)),
    )


def _view(conn, row: dict[str, Any]) -> ArtifactView:
    aid = row["id"]
    unresolved = row.get("unresolved_context_json") or {}
    if isinstance(unresolved, str):
        try:
            unresolved = json.loads(unresolved)
        except (TypeError, ValueError, json.JSONDecodeError):
            unresolved = {}
    people, evidence, stories = _load_links(conn, aid)
    return ArtifactView(
        id=str(aid),
        kind=str(row["kind"]),
        label=str(row["label"] or ""),
        description=row.get("description"),
        status=str(row["status"]),
        current_metadata_revision=int(row.get("current_metadata_revision") or 1),
        unresolved_context=dict(unresolved),
        person_ids=people,
        evidence_ids=evidence,
        story_ids=stories,
        representations=_load_reps(conn, aid),
        created_at=_iso(row.get("created_at")),
        updated_at=_iso(row.get("updated_at")),
    )


def _add_rel(
    conn,
    *,
    kind: str,
    from_type: str,
    from_id: UUID,
    to_type: str,
    to_id: UUID,
    label: str,
) -> None:
    exists = conn.execute(
        """
        SELECT 1 FROM relationships
        WHERE from_type=%s AND from_id=%s AND to_type=%s AND to_id=%s
          AND relationship_kind=%s
        LIMIT 1
        """,
        (from_type, from_id, to_type, to_id, kind),
    ).fetchone()
    if exists:
        return
    conn.execute(
        """
        INSERT INTO relationships (
            id, relationship_kind, from_type, from_id, to_type, to_id,
            label, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'confirmed')
        """,
        (uuid4(), kind, from_type, from_id, to_type, to_id, label),
    )


def create_artifact(
    *,
    kind: str,
    label: str,
    description: str | None = None,
    unresolved_context: dict[str, Any] | None = None,
    person_ids: list[str] | None = None,
    actor_key: str = "owner",
) -> ArtifactView:
    k = (kind or "").strip()
    if k not in ARTIFACT_KINDS:
        raise ArtifactServiceError(
            f"kind must be one of: {', '.join(ARTIFACT_KINDS)}"
        )
    lab = (label or "").strip()
    if not lab:
        raise ArtifactServiceError("label is required")
    desc = (description or "").strip() or None
    unresolved = unresolved_context or {"person": True, "place": True, "event": True}
    aid = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO artifacts (
                id, kind, label, description, status, current_metadata_revision,
                unresolved_context_json
            )
            VALUES (%s, %s, %s, %s, 'active', 1, %s::jsonb)
            """,
            (aid, k, lab, desc, json.dumps(unresolved)),
        )
        conn.execute(
            """
            INSERT INTO artifact_metadata_revisions (
                id, artifact_id, revision, kind, label, description,
                unresolved_context_json, actor_key, note
            )
            VALUES (%s, %s, 1, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            (
                uuid4(),
                aid,
                k,
                lab,
                desc,
                json.dumps(unresolved),
                actor_key or "owner",
                "create",
            ),
        )
        for pid in person_ids or []:
            if not str(pid).strip():
                continue
            _add_rel(
                conn,
                kind=REL_ABOUT_PERSON,
                from_type="artifact",
                from_id=aid,
                to_type="person",
                to_id=_parse_uuid(str(pid), field="person_id"),
                label="Artifact about person",
            )
            # Person known → clear person unresolved flag
            unresolved = dict(unresolved)
            unresolved["person"] = False
            conn.execute(
                """
                UPDATE artifacts
                SET unresolved_context_json = %s::jsonb, updated_at = now()
                WHERE id = %s
                """,
                (json.dumps(unresolved), aid),
            )
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert row
        return _view(conn, dict(row))


def get_artifact(artifact_id: str) -> ArtifactView | None:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            return None
        return _view(conn, dict(row))


def list_artifacts(
    *,
    limit: int = 50,
    kind: str | None = None,
    person_id: str | None = None,
    query: str | None = None,
) -> list[ArtifactView]:
    lim = max(1, min(int(limit or 50), 200))
    clauses = ["a.status = 'active'"]
    params: list[Any] = []
    if kind:
        if kind not in ARTIFACT_KINDS:
            raise ArtifactServiceError("invalid kind filter")
        clauses.append("a.kind = %s")
        params.append(kind)
    if person_id:
        pid = _parse_uuid(person_id, field="person_id")
        clauses.append(
            """
            EXISTS (
              SELECT 1 FROM relationships r
              WHERE r.from_type = 'artifact' AND r.from_id = a.id
                AND r.to_type = 'person' AND r.to_id = %s
                AND r.relationship_kind = %s
                AND r.status IN ('candidate', 'confirmed')
            )
            """
        )
        params.extend([pid, REL_ABOUT_PERSON])
    if query and query.strip():
        needle = f"%{query.strip()}%"
        clauses.append("(a.label ILIKE %s OR COALESCE(a.description,'') ILIKE %s)")
        params.extend([needle, needle])
    params.append(lim)
    sql = f"""
        SELECT a.* FROM artifacts a
        WHERE {' AND '.join(clauses)}
        ORDER BY a.updated_at DESC
        LIMIT %s
    """
    with connection() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [_view(conn, dict(r)) for r in rows]


def revise_metadata(
    artifact_id: str,
    *,
    kind: str | None = None,
    label: str | None = None,
    description: str | None = None,
    unresolved_context: dict[str, Any] | None = None,
    actor_key: str = "owner",
    note: str | None = None,
) -> ArtifactView:
    """Immutable metadata revision — does not touch representation bytes."""
    aid = _parse_uuid(artifact_id, field="artifact_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        new_kind = (kind or row["kind"]).strip()
        if new_kind not in ARTIFACT_KINDS:
            raise ArtifactServiceError("invalid kind")
        new_label = (label if label is not None else row["label"] or "").strip()
        if not new_label:
            raise ArtifactServiceError("label is required")
        if description is None:
            new_desc = row.get("description")
        else:
            new_desc = description.strip() or None
        prev_unresolved = row.get("unresolved_context_json") or {}
        if isinstance(prev_unresolved, str):
            try:
                prev_unresolved = json.loads(prev_unresolved)
            except (TypeError, ValueError, json.JSONDecodeError):
                prev_unresolved = {}
        new_unresolved = (
            unresolved_context if unresolved_context is not None else dict(prev_unresolved)
        )
        rev = int(row["current_metadata_revision"] or 1) + 1
        conn.execute(
            """
            INSERT INTO artifact_metadata_revisions (
                id, artifact_id, revision, kind, label, description,
                unresolved_context_json, actor_key, note
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            (
                uuid4(),
                aid,
                rev,
                new_kind,
                new_label,
                new_desc,
                json.dumps(new_unresolved),
                actor_key or "owner",
                note,
            ),
        )
        conn.execute(
            """
            UPDATE artifacts
            SET kind = %s, label = %s, description = %s,
                unresolved_context_json = %s::jsonb,
                current_metadata_revision = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (new_kind, new_label, new_desc, json.dumps(new_unresolved), rev, aid),
        )
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def add_mb_managed_representation(
    artifact_id: str,
    *,
    data: bytes,
    filename: str | None = None,
    content_type: str | None = None,
    label: str | None = None,
    sort_order: int | None = None,
) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    if not data:
        raise ArtifactServiceError("empty upload")
    digest = hashlib.sha256(data).hexdigest()
    root = artifact_media_root()
    root.mkdir(parents=True, exist_ok=True)
    art_dir = root / str(aid)
    art_dir.mkdir(parents=True, exist_ok=True)
    safe = _safe_filename(filename or "upload.bin")
    # Content-addressed filename prevents silent overwrite of distinct bytes.
    dest_name = f"{digest[:16]}_{safe}"
    dest = art_dir / dest_name
    if dest.is_file():
        # Same hash already stored — reuse path; do not rewrite bytes.
        pass
    else:
        tmp = art_dir / f".tmp_{uuid4().hex}"
        tmp.write_bytes(data)
        tmp.replace(dest)

    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        # Idempotent: same artifact + hash → return existing
        existing = conn.execute(
            """
            SELECT id FROM artifact_representations
            WHERE artifact_id = %s AND content_hash = %s
              AND representation_kind = 'mb_managed'
            LIMIT 1
            """,
            (aid, digest),
        ).fetchone()
        if existing:
            return _view(conn, dict(row))

        # Also register media_object for domain consistency
        mid = uuid4()
        sid = uuid4()
        rel_uri = str(dest)
        conn.execute(
            """
            INSERT INTO sources (id, source_kind, label, uri, content_hash, authoritative_original_mode)
            VALUES (%s, 'artifact_upload', %s, %s, %s, 'memorybox_managed')
            """,
            (sid, f"Artifact {aid}", rel_uri, digest),
        )
        conn.execute(
            """
            INSERT INTO media_objects (
                id, source_id, media_kind, storage_mode, uri, content_hash, mime_type
            )
            VALUES (%s, %s, 'document', 'memorybox_managed', %s, %s, %s)
            """,
            (mid, sid, rel_uri, digest, content_type),
        )
        order = sort_order
        if order is None:
            mx = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) AS m FROM artifact_representations WHERE artifact_id = %s",
                (aid,),
            ).fetchone()
            order = int(mx["m"] if mx else -1) + 1
        conn.execute(
            """
            INSERT INTO artifact_representations (
                id, artifact_id, representation_kind, media_object_id,
                uri, content_hash, mime_type, original_filename, byte_size,
                sort_order, label
            )
            VALUES (%s, %s, 'mb_managed', %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                uuid4(),
                aid,
                mid,
                rel_uri,
                digest,
                content_type,
                safe,
                len(data),
                order,
                (label or "").strip() or None,
            ),
        )
        conn.execute(
            "UPDATE artifacts SET updated_at = now() WHERE id = %s", (aid,)
        )
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def add_evidence_ref_representation(
    artifact_id: str,
    *,
    evidence_id: str,
    label: str | None = None,
    sort_order: int | None = None,
) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    eid = _parse_uuid(evidence_id, field="evidence_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        ev = conn.execute("SELECT id FROM evidence WHERE id = %s", (eid,)).fetchone()
        if not ev:
            raise ArtifactServiceError("evidence not found")
        existing = conn.execute(
            """
            SELECT id FROM artifact_representations
            WHERE artifact_id = %s AND evidence_id = %s
              AND representation_kind = 'evidence_ref'
            LIMIT 1
            """,
            (aid, eid),
        ).fetchone()
        if existing:
            return _view(conn, dict(row))
        order = sort_order
        if order is None:
            mx = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) AS m FROM artifact_representations WHERE artifact_id = %s",
                (aid,),
            ).fetchone()
            order = int(mx["m"] if mx else -1) + 1
        conn.execute(
            """
            INSERT INTO artifact_representations (
                id, artifact_id, representation_kind, evidence_id,
                sort_order, label
            )
            VALUES (%s, %s, 'evidence_ref', %s, %s, %s)
            """,
            (uuid4(), aid, eid, order, (label or "").strip() or None),
        )
        _add_rel(
            conn,
            kind=REL_CITES_EVIDENCE,
            from_type="artifact",
            from_id=aid,
            to_type="evidence",
            to_id=eid,
            label="Artifact cites evidence representation",
        )
        conn.execute(
            "UPDATE artifacts SET updated_at = now() WHERE id = %s", (aid,)
        )
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def associate_person(artifact_id: str, person_id: str) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    pid = _parse_uuid(person_id, field="person_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        person = conn.execute(
            "SELECT id, status FROM people WHERE id = %s", (pid,)
        ).fetchone()
        if not person or person["status"] == "merged_away":
            raise ArtifactServiceError("person not found")
        _add_rel(
            conn,
            kind=REL_ABOUT_PERSON,
            from_type="artifact",
            from_id=aid,
            to_type="person",
            to_id=pid,
            label="Artifact about person",
        )
        unresolved = row.get("unresolved_context_json") or {}
        if isinstance(unresolved, str):
            try:
                unresolved = json.loads(unresolved)
            except (TypeError, ValueError, json.JSONDecodeError):
                unresolved = {}
        unresolved = dict(unresolved)
        unresolved["person"] = False
        conn.execute(
            """
            UPDATE artifacts
            SET unresolved_context_json = %s::jsonb, updated_at = now()
            WHERE id = %s
            """,
            (json.dumps(unresolved), aid),
        )
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def associate_story(artifact_id: str, story_id: str) -> ArtifactView:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    sid = _parse_uuid(story_id, field="story_id")
    with connection() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        if not row or row["status"] == "removed":
            raise ArtifactServiceError("artifact not found")
        st = conn.execute(
            "SELECT id, status FROM stories WHERE id = %s", (sid,)
        ).fetchone()
        if not st or st["status"] != "active":
            raise ArtifactServiceError("story not found")
        _add_rel(
            conn,
            kind=REL_ABOUT_ARTIFACT,
            from_type="story",
            from_id=sid,
            to_type="artifact",
            to_id=aid,
            label="Story about artifact",
        )
        conn.execute(
            "UPDATE artifacts SET updated_at = now() WHERE id = %s", (aid,)
        )
        out = conn.execute("SELECT * FROM artifacts WHERE id = %s", (aid,)).fetchone()
        assert out
        return _view(conn, dict(out))


def create_story_for_artifact(
    artifact_id: str,
    *,
    title: str | None,
    body_text: str,
    narrator_display_name: str | None = None,
) -> dict[str, Any]:
    """Typed Story association earn-in (optional voice path saves body via STT then calls this)."""
    view = get_artifact(artifact_id)
    if not view:
        raise ArtifactServiceError("artifact not found")
    try:
        story = create_story(
            title=title or f"About {view.label}",
            body_text=body_text,
            narrator_display_name=narrator_display_name,
            person_ids=list(view.person_ids) or None,
        )
    except StoryServiceError as exc:
        raise ArtifactServiceError(str(exc)) from exc
    associate_story(artifact_id, story.id)
    return {"artifact": get_artifact(artifact_id).to_dict(), "story": story.to_dict()}


def read_representation_bytes(
    artifact_id: str, representation_id: str
) -> tuple[bytes, str, str]:
    aid = _parse_uuid(artifact_id, field="artifact_id")
    rid = _parse_uuid(representation_id, field="representation_id")
    with connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM artifact_representations
            WHERE id = %s AND artifact_id = %s
            """,
            (rid, aid),
        ).fetchone()
        if not row:
            raise ArtifactServiceError("representation not found")
        if row["representation_kind"] != "mb_managed":
            raise ArtifactServiceError("only mb_managed representations are byte-served here")
        uri = row.get("uri")
        if not uri:
            raise ArtifactServiceError("representation uri missing")
        path = Path(uri)
        if not path.is_file():
            raise ArtifactServiceError("representation file missing on durable store")
        # Integrity check
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if row.get("content_hash") and digest != row["content_hash"]:
            raise ArtifactServiceError("content hash mismatch — refuse to serve")
        mime = row.get("mime_type") or "application/octet-stream"
        name = row.get("original_filename") or path.name
        return data, mime, name


def search_artifacts_for_ask(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Thin Ask earn-in: match label/description/kind — not filename-as-meaning."""
    q = (query or "").strip()
    if len(q) < 2:
        return []
    rows = list_artifacts(limit=limit, query=q)
    # Also kind token match
    low = q.lower()
    kind_hits = []
    for k in ARTIFACT_KINDS:
        token = k.replace("_", " ")
        if token in low or k in low:
            kind_hits.extend(list_artifacts(limit=limit, kind=k))
    by_id = {r.id: r for r in rows}
    for h in kind_hits:
        by_id.setdefault(h.id, h)
    out = []
    for a in by_id.values():
        out.append(
            {
                "artifact_id": a.id,
                "kind": a.kind,
                "label": a.label,
                "description": a.description,
                "person_ids": a.person_ids,
                "story_ids": a.story_ids,
                "representation_count": len(a.representations),
                "deep_link": f"/artifact/ui?id={a.id}",
                "provenance": {
                    "kind": "artifact",
                    "note": "Matched Artifact identity/metadata — not upload filename alone",
                },
            }
        )
    return out[:limit]
