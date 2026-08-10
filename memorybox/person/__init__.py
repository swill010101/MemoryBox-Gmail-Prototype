"""Person & Identity Service — central MB Person resolution (Increment 6).

Story/Journal and Ask must use this module. Do not mint People via raw
name matching outside this service after I6.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from memorybox.db import connection

PROVIDER_IMMICH = "immich"
KIND_EXTERNAL_PERSON = "external_person"


class PersonServiceError(Exception):
    pass


@dataclass
class PersonView:
    id: str
    display_name: str | None
    status: str
    merged_into_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    provider_mappings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResolveResult:
    person_id: str
    display_name: str | None
    status: str
    created: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _parse_uuid(value: str, *, field: str) -> UUID:
    raw = (value or "").strip()
    if not raw:
        raise PersonServiceError(f"{field} is required")
    try:
        return UUID(raw)
    except (ValueError, TypeError, AttributeError) as exc:
        raise PersonServiceError(f"{field} must be a UUID (got {raw!r})") from exc


def _person_row(conn, person_id: UUID) -> dict[str, Any] | None:
    return conn.execute("SELECT * FROM people WHERE id = %s", (person_id,)).fetchone()


def _mappings(conn, person_id: UUID) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, provider_key, identity_kind, external_id, label,
               confirmed_at, confirmed_by, created_at
        FROM provider_identities
        WHERE person_id = %s
        ORDER BY created_at ASC
        """,
        (person_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": str(r["id"]),
                "provider_key": r["provider_key"],
                "identity_kind": r["identity_kind"],
                "external_id": r["external_id"],
                "label": r.get("label"),
                "confirmed_at": _iso(r.get("confirmed_at")),
                "confirmed_by": r.get("confirmed_by"),
                "created_at": _iso(r.get("created_at")),
            }
        )
    return out


def _view(conn, row: dict[str, Any]) -> PersonView:
    pid = UUID(str(row["id"]))
    return PersonView(
        id=str(pid),
        display_name=row.get("display_name"),
        status=row["status"],
        merged_into_id=str(row["merged_into_id"]) if row.get("merged_into_id") else None,
        created_at=_iso(row.get("created_at")),
        updated_at=_iso(row.get("updated_at")),
        provider_mappings=_mappings(conn, pid),
    )


def get_person(person_id: str) -> PersonView | None:
    try:
        pid = _parse_uuid(person_id, field="person_id")
    except PersonServiceError:
        return None
    with connection() as conn:
        row = _person_row(conn, pid)
        if not row:
            return None
        return _view(conn, row)


def list_people(*, limit: int = 100, include_merged_away: bool = False) -> list[dict[str, Any]]:
    with connection() as conn:
        if include_merged_away:
            rows = conn.execute(
                """
                SELECT id, display_name, status, merged_into_id, created_at, updated_at
                FROM people
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, display_name, status, merged_into_id, created_at, updated_at
                FROM people
                WHERE status IN ('unresolved', 'confirmed')
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": str(r["id"]),
                "display_name": r.get("display_name"),
                "status": r["status"],
                "merged_into_id": str(r["merged_into_id"]) if r.get("merged_into_id") else None,
                "created_at": _iso(r.get("created_at")),
                "updated_at": _iso(r.get("updated_at")),
            }
            for r in rows
        ]


def resolve_person_by_name(
    display_name: str,
    *,
    create_if_missing: bool = True,
    confirm: bool = False,
) -> ResolveResult:
    """Central Person resolution — Story/Journal/Ask must use this."""
    name = (display_name or "").strip()
    if len(name) < 2:
        raise PersonServiceError("display_name required")
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id, display_name, status FROM people
            WHERE lower(display_name) = lower(%s)
              AND status IN ('unresolved', 'confirmed')
            ORDER BY
              CASE status WHEN 'confirmed' THEN 0 ELSE 1 END,
              created_at ASC
            LIMIT 1
            """,
            (name,),
        ).fetchone()
        if row:
            pid = UUID(str(row["id"]))
            if confirm and row["status"] != "confirmed":
                conn.execute(
                    """
                    UPDATE people
                    SET status = 'confirmed', updated_at = now()
                    WHERE id = %s
                    """,
                    (pid,),
                )
                status = "confirmed"
            else:
                status = row["status"]
            return ResolveResult(
                person_id=str(pid),
                display_name=row.get("display_name") or name,
                status=status,
                created=False,
            )
        if not create_if_missing:
            raise PersonServiceError(f"person not found: {name!r}")
        pid = uuid4()
        status = "confirmed" if confirm else "unresolved"
        conn.execute(
            """
            INSERT INTO people (id, display_name, status)
            VALUES (%s, %s, %s)
            """,
            (pid, name, status),
        )
        return ResolveResult(
            person_id=str(pid),
            display_name=name,
            status=status,
            created=True,
        )


def rename_person(person_id: str, display_name: str) -> PersonView:
    """Minimal owner correction of canonical/display name."""
    name = (display_name or "").strip()
    if len(name) < 2:
        raise PersonServiceError("display_name required")
    pid = _parse_uuid(person_id, field="person_id")
    with connection() as conn:
        row = _person_row(conn, pid)
        if not row:
            raise PersonServiceError("person not found")
        if row["status"] == "merged_away":
            raise PersonServiceError("cannot rename a merged_away person")
        conn.execute(
            """
            UPDATE people
            SET display_name = %s, updated_at = now()
            WHERE id = %s
            """,
            (name, pid),
        )
        row = _person_row(conn, pid)
        assert row
        return _view(conn, row)


def is_negative(
    *,
    provider_key: str,
    external_id: str,
    person_id: str,
    identity_kind: str = KIND_EXTERNAL_PERSON,
) -> bool:
    pid = _parse_uuid(person_id, field="person_id")
    with connection() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM identity_negatives
            WHERE provider_key = %s
              AND identity_kind = %s
              AND external_id = %s
              AND person_id = %s
            LIMIT 1
            """,
            (provider_key, identity_kind, external_id, pid),
        ).fetchone()
        return bool(row)


def reject_mapping(
    *,
    provider_key: str,
    external_id: str,
    person_id: str,
    identity_kind: str = KIND_EXTERNAL_PERSON,
    note: str | None = None,
    actor_key: str = "owner",
) -> dict[str, Any]:
    """Durable: provider identity X is not MB Person Y."""
    pid = _parse_uuid(person_id, field="person_id")
    ext = (external_id or "").strip()
    if not ext:
        raise PersonServiceError("external_id required")
    pk = (provider_key or "").strip()
    if not pk:
        raise PersonServiceError("provider_key required")
    with connection() as conn:
        prow = _person_row(conn, pid)
        if not prow or prow["status"] == "merged_away":
            raise PersonServiceError("person not found or merged_away")
        # Detach current binding of this external id to Y if present
        conn.execute(
            """
            UPDATE provider_identities
            SET person_id = NULL, confirmed_at = NULL, confirmed_by = NULL
            WHERE provider_key = %s
              AND identity_kind = %s
              AND external_id = %s
              AND person_id = %s
            """,
            (pk, identity_kind, ext, pid),
        )
        nid = uuid4()
        conn.execute(
            """
            INSERT INTO identity_negatives (
                id, provider_key, identity_kind, external_id, person_id, actor_key, note
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (provider_key, identity_kind, external_id, person_id)
            DO UPDATE SET note = EXCLUDED.note, actor_key = EXCLUDED.actor_key
            """,
            (nid, pk, identity_kind, ext, pid, actor_key or "owner", note),
        )
        # Owner-authority assertion for provenance
        conn.execute(
            """
            INSERT INTO assertions (
                id, assertion_kind, subject_type, subject_id, predicate,
                object_type, object_id, statement, authority, status, provenance_json
            )
            VALUES (
                %s, 'identity_negative', 'person', %s, 'is_not',
                'provider_identity', NULL, %s, 'owner', 'confirmed',
                %s::jsonb
            )
            """,
            (
                uuid4(),
                pid,
                f"{pk}:{identity_kind}:{ext} is not person {pid}",
                __import__("json").dumps(
                    {
                        "provider_key": pk,
                        "identity_kind": identity_kind,
                        "external_id": ext,
                        "person_id": str(pid),
                    }
                ),
            ),
        )
    return {
        "ok": True,
        "provider_key": pk,
        "identity_kind": identity_kind,
        "external_id": ext,
        "person_id": str(pid),
        "negative": True,
    }


def map_provider_identity(
    *,
    person_id: str,
    provider_key: str,
    external_id: str,
    label: str | None = None,
    identity_kind: str = KIND_EXTERNAL_PERSON,
    actor_key: str = "owner",
    confirm_person: bool = True,
) -> PersonView:
    """Map provider identity → MB Person. Respects negatives for this pair."""
    pid = _parse_uuid(person_id, field="person_id")
    ext = (external_id or "").strip()
    if not ext:
        raise PersonServiceError("external_id required")
    # Guard: never use Immich UUID as people.id (caller must pass MB person_id)
    if str(pid) == ext:
        raise PersonServiceError(
            "people.id must not equal provider external_id (Immich UUID is not Person PK)"
        )
    pk = (provider_key or "").strip() or PROVIDER_IMMICH
    if is_negative(
        provider_key=pk, external_id=ext, person_id=str(pid), identity_kind=identity_kind
    ):
        raise PersonServiceError(
            f"negative identity blocks mapping {pk}:{ext} → person {pid}"
        )
    with connection() as conn:
        prow = _person_row(conn, pid)
        if not prow:
            raise PersonServiceError("person not found")
        if prow["status"] == "merged_away":
            raise PersonServiceError("cannot map to a merged_away person")
        if confirm_person and prow["status"] != "confirmed":
            conn.execute(
                """
                UPDATE people SET status = 'confirmed', updated_at = now()
                WHERE id = %s
                """,
                (pid,),
            )
        existing = conn.execute(
            """
            SELECT id, person_id FROM provider_identities
            WHERE provider_key = %s AND identity_kind = %s AND external_id = %s
            """,
            (pk, identity_kind, ext),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE provider_identities
                SET person_id = %s,
                    label = COALESCE(%s, label),
                    confirmed_at = now(),
                    confirmed_by = %s
                WHERE id = %s
                """,
                (pid, label, actor_key or "owner", existing["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO provider_identities (
                    id, person_id, provider_key, identity_kind, external_id,
                    label, confirmed_at, confirmed_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, now(), %s)
                """,
                (
                    uuid4(),
                    pid,
                    pk,
                    identity_kind,
                    ext,
                    label,
                    actor_key or "owner",
                ),
            )
        # Teach assertion
        conn.execute(
            """
            INSERT INTO assertions (
                id, assertion_kind, subject_type, subject_id, predicate,
                object_type, object_id, statement, authority, status, provenance_json
            )
            VALUES (
                %s, 'identity_mapping', 'person', %s, 'mapped_to',
                'provider_identity', NULL, %s, 'owner', 'confirmed',
                %s::jsonb
            )
            """,
            (
                uuid4(),
                pid,
                f"person {pid} mapped to {pk}:{ext}",
                __import__("json").dumps(
                    {
                        "provider_key": pk,
                        "identity_kind": identity_kind,
                        "external_id": ext,
                        "person_id": str(pid),
                    }
                ),
            ),
        )
        row = _person_row(conn, pid)
        assert row
        return _view(conn, row)


def teach_provider_person(
    *,
    display_name: str,
    provider_key: str,
    external_id: str,
    label: str | None = None,
    identity_kind: str = KIND_EXTERNAL_PERSON,
    actor_key: str = "owner",
) -> PersonView:
    """EVS-022 thin: resolve/create confirmed Person and map provider identity."""
    resolved = resolve_person_by_name(display_name, create_if_missing=True, confirm=True)
    return map_provider_identity(
        person_id=resolved.person_id,
        provider_key=provider_key,
        external_id=external_id,
        label=label or display_name,
        identity_kind=identity_kind,
        actor_key=actor_key,
        confirm_person=True,
    )


def bulk_confirm_provider_identities(
    *,
    display_name: str,
    provider_key: str,
    external_ids: list[str],
    identity_kind: str = KIND_EXTERNAL_PERSON,
    actor_key: str = "owner",
) -> PersonView:
    """EVS-023 thin: map many provider identities onto one confirmed Person."""
    resolved = resolve_person_by_name(display_name, create_if_missing=True, confirm=True)
    view: PersonView | None = None
    for ext in external_ids:
        raw = (ext or "").strip()
        if not raw:
            continue
        if is_negative(
            provider_key=provider_key,
            external_id=raw,
            person_id=resolved.person_id,
            identity_kind=identity_kind,
        ):
            continue
        view = map_provider_identity(
            person_id=resolved.person_id,
            provider_key=provider_key,
            external_id=raw,
            label=display_name,
            identity_kind=identity_kind,
            actor_key=actor_key,
            confirm_person=True,
        )
    if view is None:
        raise PersonServiceError("no external_ids mapped")
    return view


def list_immich_external_ids_for_person(person_id: str) -> list[str]:
    pid = _parse_uuid(person_id, field="person_id")
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT external_id FROM provider_identities
            WHERE person_id = %s
              AND provider_key = %s
            """,
            (pid, PROVIDER_IMMICH),
        ).fetchall()
        return [str(r["external_id"]) for r in rows]


def find_confirmed_person_by_name(display_name: str) -> PersonView | None:
    name = (display_name or "").strip()
    if len(name) < 2:
        return None
    with connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM people
            WHERE lower(display_name) = lower(%s)
              AND status = 'confirmed'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (name,),
        ).fetchone()
        if not row:
            return None
        return _view(conn, row)


def merge_people(
    *,
    survivor_person_id: str,
    loser_person_id: str,
    actor_key: str = "owner",
    note: str | None = None,
) -> PersonView:
    """Owner-led non-destructive merge. Loser remains addressable as merged_away."""
    survivor = _parse_uuid(survivor_person_id, field="survivor_person_id")
    loser = _parse_uuid(loser_person_id, field="loser_person_id")
    if survivor == loser:
        raise PersonServiceError("survivor and loser must differ")
    import json

    with connection() as conn:
        srow = _person_row(conn, survivor)
        lrow = _person_row(conn, loser)
        if not srow or not lrow:
            raise PersonServiceError("survivor or loser not found")
        if lrow["status"] == "merged_away":
            raise PersonServiceError("loser already merged_away")
        if srow["status"] == "merged_away":
            raise PersonServiceError("survivor is merged_away")

        moved = conn.execute(
            """
            SELECT id, provider_key, identity_kind, external_id, label
            FROM provider_identities
            WHERE person_id = %s
            """,
            (loser,),
        ).fetchall()
        snapshot = {
            "survivor_person_id": str(survivor),
            "loser_person_id": str(loser),
            "loser_display_name": lrow.get("display_name"),
            "survivor_display_name": srow.get("display_name"),
            "moved_mappings": [
                {
                    "id": str(m["id"]),
                    "provider_key": m["provider_key"],
                    "identity_kind": m["identity_kind"],
                    "external_id": m["external_id"],
                    "label": m.get("label"),
                    "previous_person_id": str(loser),
                }
                for m in moved
            ],
        }
        # Forward resolution: current mappings point at survivor
        conn.execute(
            """
            UPDATE provider_identities
            SET person_id = %s
            WHERE person_id = %s
            """,
            (survivor, loser),
        )
        conn.execute(
            """
            UPDATE people
            SET status = 'merged_away',
                merged_into_id = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (survivor, loser),
        )
        if srow["status"] != "confirmed":
            conn.execute(
                """
                UPDATE people SET status = 'confirmed', updated_at = now()
                WHERE id = %s
                """,
                (survivor,),
            )
        conn.execute(
            """
            INSERT INTO person_merges (
                id, survivor_person_id, loser_person_id, actor_key, note, snapshot_json
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                uuid4(),
                survivor,
                loser,
                actor_key or "owner",
                note,
                json.dumps(snapshot),
            ),
        )
        # Historical assertion on loser remains — subject still loser id
        conn.execute(
            """
            INSERT INTO assertions (
                id, assertion_kind, subject_type, subject_id, predicate,
                object_type, object_id, statement, authority, status, provenance_json
            )
            VALUES (
                %s, 'person_merge', 'person', %s, 'merged_into',
                'person', %s, %s, 'owner', 'confirmed', %s::jsonb
            )
            """,
            (
                uuid4(),
                loser,
                survivor,
                f"person {loser} merged into {survivor}",
                json.dumps(snapshot),
            ),
        )
        row = _person_row(conn, survivor)
        assert row
        return _view(conn, row)


def confirmed_immich_ids_for_names(names: list[str]) -> dict[str, list[str]]:
    """name(lower) → list of confirmed Immich external_ids for matching confirmed Persons."""
    out: dict[str, list[str]] = {}
    for name in names:
        person = find_confirmed_person_by_name(name)
        if not person:
            continue
        ids = list_immich_external_ids_for_person(person.id)
        if ids:
            out[name.lower()] = ids
    return out
