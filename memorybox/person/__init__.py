"""Person & Identity Service — central MB Person resolution (Increment 6+).

Story/Journal and Ask must use this module. Do not mint People via raw
name matching outside this service after I6.

I7 trusted-provider bootstrap: a named Immich (or other trusted photo)
identity may lazily seed a provisional MB Person. Authority levels are
not flattened — owner-confirmed > trusted-provider > AI/inferred.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from memorybox.db import connection

PROVIDER_IMMICH = "immich"
KIND_EXTERNAL_PERSON = "external_person"

# Identity authority (Person-level / mapping provenance). Do not flatten.
AUTHORITY_OWNER_CONFIRMED = "owner_confirmed"
AUTHORITY_TRUSTED_PROVIDER = "trusted_provider"
AUTHORITY_AI_INFERRED = "ai_inferred"

ATTR_IDENTITY_AUTHORITY = "identity_authority"
ATTR_SEEDED_FROM = "seeded_from"


class PersonServiceError(Exception):
    pass


class AmbiguousIdentityError(PersonServiceError):
    """Same-name / multi-match cases that must not silently merge."""

    def __init__(
        self,
        message: str,
        *,
        candidates: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.candidates = candidates or []


@dataclass
class PersonView:
    id: str
    display_name: str | None
    status: str
    merged_into_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    identity_authority: str = AUTHORITY_OWNER_CONFIRMED
    provider_mappings: list[dict[str, Any]] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResolveResult:
    person_id: str
    display_name: str | None
    status: str
    created: bool
    identity_authority: str = AUTHORITY_OWNER_CONFIRMED
    seeded: bool = False

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


def _attrs(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("attributes_json")
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    return {}


def _authority_from_attrs(attrs: dict[str, Any], *, status: str) -> str:
    auth = str(attrs.get(ATTR_IDENTITY_AUTHORITY) or "").strip()
    if auth in {
        AUTHORITY_OWNER_CONFIRMED,
        AUTHORITY_TRUSTED_PROVIDER,
        AUTHORITY_AI_INFERRED,
    }:
        return auth
    # Legacy rows: confirmed status without explicit authority → owner_confirmed
    if status == "confirmed":
        return AUTHORITY_OWNER_CONFIRMED
    return AUTHORITY_TRUSTED_PROVIDER if attrs.get(ATTR_SEEDED_FROM) else AUTHORITY_OWNER_CONFIRMED


def _person_row(conn, person_id: UUID) -> dict[str, Any] | None:
    return conn.execute("SELECT * FROM people WHERE id = %s", (person_id,)).fetchone()


def _mappings(conn, person_id: UUID) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, provider_key, identity_kind, external_id, label,
               confirmed_at, confirmed_by, metadata_json, created_at
        FROM provider_identities
        WHERE person_id = %s
        ORDER BY created_at ASC
        """,
        (person_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        meta = r.get("metadata_json") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (TypeError, ValueError, json.JSONDecodeError):
                meta = {}
        out.append(
            {
                "id": str(r["id"]),
                "provider_key": r["provider_key"],
                "identity_kind": r["identity_kind"],
                "external_id": r["external_id"],
                "label": r.get("label"),
                "confirmed_at": _iso(r.get("confirmed_at")),
                "confirmed_by": r.get("confirmed_by"),
                "identity_authority": (meta or {}).get("identity_authority")
                or (
                    AUTHORITY_OWNER_CONFIRMED
                    if (r.get("confirmed_by") or "")
                    in {"owner", "tom", ""}
                    else AUTHORITY_TRUSTED_PROVIDER
                ),
                "metadata": meta if isinstance(meta, dict) else {},
                "created_at": _iso(r.get("created_at")),
            }
        )
    return out


def _view(conn, row: dict[str, Any]) -> PersonView:
    pid = UUID(str(row["id"]))
    attrs = _attrs(row)
    return PersonView(
        id=str(pid),
        display_name=row.get("display_name"),
        status=row["status"],
        merged_into_id=str(row["merged_into_id"]) if row.get("merged_into_id") else None,
        created_at=_iso(row.get("created_at")),
        updated_at=_iso(row.get("updated_at")),
        identity_authority=_authority_from_attrs(attrs, status=row["status"]),
        provider_mappings=_mappings(conn, pid),
        attributes=attrs,
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
    identity_authority: str = AUTHORITY_OWNER_CONFIRMED,
    assertion_authority: str | None = None,
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
    auth = (identity_authority or AUTHORITY_OWNER_CONFIRMED).strip()
    if auth not in {
        AUTHORITY_OWNER_CONFIRMED,
        AUTHORITY_TRUSTED_PROVIDER,
        AUTHORITY_AI_INFERRED,
    }:
        raise PersonServiceError(f"invalid identity_authority: {auth!r}")
    # assertions.authority CHECK allows only owner|contributor|system —
    # finer identity authority lives in provenance_json / metadata_json.
    if assertion_authority in {"owner", "contributor", "system"}:
        assert_auth = assertion_authority
    elif auth == AUTHORITY_OWNER_CONFIRMED:
        assert_auth = "owner"
    else:
        assert_auth = "system"
    if is_negative(
        provider_key=pk, external_id=ext, person_id=str(pid), identity_kind=identity_kind
    ):
        raise PersonServiceError(
            f"negative identity blocks mapping {pk}:{ext} → person {pid}"
        )
    meta = json.dumps({"identity_authority": auth, "provider_key": pk})
    with connection() as conn:
        prow = _person_row(conn, pid)
        if not prow:
            raise PersonServiceError("person not found")
        if prow["status"] == "merged_away":
            raise PersonServiceError("cannot map to a merged_away person")
        if confirm_person and prow["status"] != "confirmed":
            # Owner confirmation upgrades Person; preserve seeded_from provenance.
            patch = {
                ATTR_IDENTITY_AUTHORITY: AUTHORITY_OWNER_CONFIRMED,
            }
            conn.execute(
                """
                UPDATE people
                SET status = 'confirmed',
                    attributes_json = attributes_json || %s::jsonb,
                    updated_at = now()
                WHERE id = %s
                """,
                (json.dumps(patch), pid),
            )
        existing = conn.execute(
            """
            SELECT id, person_id, metadata_json FROM provider_identities
            WHERE provider_key = %s AND identity_kind = %s AND external_id = %s
            """,
            (pk, identity_kind, ext),
        ).fetchone()
        if existing:
            prev_meta = existing.get("metadata_json") or {}
            if isinstance(prev_meta, str):
                try:
                    prev_meta = json.loads(prev_meta)
                except (TypeError, ValueError, json.JSONDecodeError):
                    prev_meta = {}
            if not isinstance(prev_meta, dict):
                prev_meta = {}
            # Never erase prior trusted-provider provenance when remapping.
            merged_meta = dict(prev_meta)
            if (
                prev_meta.get("identity_authority") == AUTHORITY_TRUSTED_PROVIDER
                and auth == AUTHORITY_OWNER_CONFIRMED
            ):
                merged_meta["identity_authority"] = AUTHORITY_TRUSTED_PROVIDER
                merged_meta["owner_remapped"] = True
                merged_meta["owner_actor"] = actor_key or "owner"
            else:
                merged_meta["identity_authority"] = auth
            conn.execute(
                """
                UPDATE provider_identities
                SET person_id = %s,
                    label = COALESCE(%s, label),
                    confirmed_at = now(),
                    confirmed_by = %s,
                    metadata_json = %s::jsonb
                WHERE id = %s
                """,
                (
                    pid,
                    label,
                    actor_key or "owner",
                    json.dumps(merged_meta),
                    existing["id"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO provider_identities (
                    id, person_id, provider_key, identity_kind, external_id,
                    label, confirmed_at, confirmed_by, metadata_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, now(), %s, %s::jsonb)
                """,
                (
                    uuid4(),
                    pid,
                    pk,
                    identity_kind,
                    ext,
                    label,
                    actor_key or "owner",
                    meta,
                ),
            )
        # Teach / provider assertion — authority must not falsely claim owner when provider-seeded
        conn.execute(
            """
            INSERT INTO assertions (
                id, assertion_kind, subject_type, subject_id, predicate,
                object_type, object_id, statement, authority, status, provenance_json
            )
            VALUES (
                %s, 'identity_mapping', 'person', %s, 'mapped_to',
                'provider_identity', NULL, %s, %s, 'confirmed',
                %s::jsonb
            )
            """,
            (
                uuid4(),
                pid,
                f"person {pid} mapped to {pk}:{ext}",
                assert_auth,
                json.dumps(
                    {
                        "provider_key": pk,
                        "identity_kind": identity_kind,
                        "external_id": ext,
                        "person_id": str(pid),
                        "identity_authority": auth,
                    }
                ),
            ),
        )
        row = _person_row(conn, pid)
        assert row
        return _view(conn, row)


def find_person_by_provider_external_id(
    *,
    provider_key: str,
    external_id: str,
    identity_kind: str = KIND_EXTERNAL_PERSON,
) -> PersonView | None:
    pk = (provider_key or "").strip()
    ext = (external_id or "").strip()
    if not pk or not ext:
        return None
    with connection() as conn:
        row = conn.execute(
            """
            SELECT p.*
            FROM provider_identities pi
            JOIN people p ON p.id = pi.person_id
            WHERE pi.provider_key = %s
              AND pi.identity_kind = %s
              AND pi.external_id = %s
              AND p.status IN ('unresolved', 'confirmed')
            LIMIT 1
            """,
            (pk, identity_kind, ext),
        ).fetchone()
        if not row:
            return None
        return _view(conn, row)


def list_people_by_exact_name(display_name: str) -> list[PersonView]:
    name = (display_name or "").strip()
    if len(name) < 2:
        return []
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM people
            WHERE lower(display_name) = lower(%s)
              AND status IN ('unresolved', 'confirmed')
            ORDER BY
              CASE status WHEN 'confirmed' THEN 0 ELSE 1 END,
              created_at ASC
            """,
            (name,),
        ).fetchall()
        return [_view(conn, r) for r in rows]


def list_people_by_first_token(display_name: str) -> list[PersonView]:
    """Match people whose first display-name token equals the query (case-insensitive).

    Used for short Ask names like \"Peggy\" → \"Peggy George\" when unique.
    Multi-word queries return exact matches only (via list_people_by_exact_name).
    """
    name = (display_name or "").strip()
    if len(name) < 2:
        return []
    if " " in name:
        return list_people_by_exact_name(name)
    token = name.lower()
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM people
            WHERE status IN ('unresolved', 'confirmed')
              AND (
                lower(display_name) = %s
                OR lower(split_part(display_name, ' ', 1)) = %s
              )
            ORDER BY
              CASE status WHEN 'confirmed' THEN 0 ELSE 1 END,
              created_at ASC
            """,
            (token, token),
        ).fetchall()
        return [_view(conn, r) for r in rows]


def _exact_named_photo_people(photo: Any, display_name: str) -> list[Any]:
    """Exact case-insensitive display-name match only (no substring merge)."""
    name = (display_name or "").strip()
    if not photo or len(name) < 2:
        return []
    try:
        refs = photo.list_people(query=name, limit=50) or []
    except Exception:  # noqa: BLE001
        return []
    needle = name.lower()
    return [
        r
        for r in refs
        if (getattr(r, "display_name", None) or "").strip().lower() == needle
    ]


def asked_name_matches_person(asked: str, person_name: str) -> bool:
    """True when Ask 'Peggy George' and Immich/MB 'Peggy' are the same person."""
    from memorybox.providers.photo._immich_http import ImmichHttpClient

    a = (asked or "").strip()
    n = (person_name or "").strip()
    if not a or not n:
        return False
    return ImmichHttpClient._name_matches_person(a, n) or ImmichHttpClient._name_matches_person(
        n, a
    )


def immich_ids_matching_asked_name(
    photo: Any, asked_name: str, mapped_ids: list[str]
) -> list[str]:
    """Keep only Immich person UUIDs whose Immich name matches the Ask.

    Stale provider_identities (Peggy MB Person → Tom's Immich UUID) were
    loading Tom's library and then stamping the asked name on every card.
    """
    asked = (asked_name or "").strip()
    ids = [str(x).strip() for x in (mapped_ids or []) if str(x).strip()]
    if not asked:
        return list(dict.fromkeys(ids))
    client = getattr(photo, "_client", None)
    get_fn = getattr(client, "get_person", None)
    kept: list[str] = []
    if callable(get_fn):
        for eid in ids:
            try:
                row = get_fn(eid)
            except Exception:  # noqa: BLE001
                row = None
            name = ""
            if isinstance(row, dict):
                name = str(row.get("name") or "").strip()
            if name and asked_name_matches_person(asked, name):
                kept.append(eid)
    elif ids:
        # Tests / providers without Immich person GET keep mapped ids.
        kept = list(ids)
    if kept:
        return list(dict.fromkeys(kept))
    try:
        refs = _ask_named_photo_people(photo, asked)
    except Exception:  # noqa: BLE001
        refs = []
    out: list[str] = []
    for r in refs or []:
        ext = str(getattr(r, "external_id", "") or "").strip()
        if ext:
            out.append(ext)
    return list(dict.fromkeys(out))


def _ask_named_photo_people(photo: Any, display_name: str) -> list[Any]:
    """Immich/photo people for Ask: exact name, else unique related first-token.

    Immich often stores ``Peggy`` while MB says ``Peggy George``. A space in
    the Ask name must not skip that match — that was 0 photos / 1 video after
    a stale mapped id.
    """
    exact = _exact_named_photo_people(photo, display_name)
    if exact:
        return exact
    name = (display_name or "").strip()
    if not photo or len(name) < 2:
        return []
    token = name.split()[0]
    try:
        refs = photo.list_people(query=token, limit=50) or []
    except Exception:  # noqa: BLE001
        return []
    q = name.lower()
    token_l = token.lower()
    matched: list[Any] = []
    for r in refs:
        dn = (getattr(r, "display_name", None) or "").strip()
        if not dn:
            continue
        dl = dn.lower()
        first = dl.split()[0] if dl.split() else ""
        if dl == q or dl.startswith(q + " ") or q.startswith(dl + " ") or first == token_l:
            matched.append(r)
    by_ext: dict[str, Any] = {}
    for r in matched:
        ext = str(getattr(r, "external_id", "") or "").strip()
        if ext and ext not in by_ext:
            by_ext[ext] = r
    related = list(by_ext.values())
    if not related:
        return []
    contained = []
    for r in related:
        dl = (getattr(r, "display_name", None) or "").strip().lower()
        if dl == q or dl.startswith(q + " ") or q.startswith(dl + " "):
            contained.append(r)
    if len(contained) == 1:
        return contained
    if len(related) == 1:
        return related
    # Single-token Ask ("Peggy") may be ambiguous — caller clarifies.
    if " " not in name:
        return related
    # Multi-word Ask with several Immich Peggys: do not guess.
    return []


def seed_person_from_trusted_provider(
    *,
    provider_key: str,
    external_id: str,
    display_name: str,
    identity_kind: str = KIND_EXTERNAL_PERSON,
) -> PersonView:
    """Lazy-create a provisional MB Person from a trusted provider identity.

    Does NOT mark owner-confirmed. Never uses provider UUID as people.id.
    """
    name = (display_name or "").strip()
    if len(name) < 2:
        raise PersonServiceError("display_name required")
    pk = (provider_key or "").strip()
    ext = (external_id or "").strip()
    if not pk or not ext:
        raise PersonServiceError("provider_key and external_id required")

    existing = find_person_by_provider_external_id(
        provider_key=pk, external_id=ext, identity_kind=identity_kind
    )
    if existing:
        return existing

    # Negatives against any person for this provider id are checked at map time;
    # also refuse to seed when the only prior knowledge is a rejected pairing to a
    # same-name person (caller should use owner correction path).
    pid = uuid4()
    if str(pid) == ext:
        # Astronomically unlikely; regenerate once.
        pid = uuid4()
        if str(pid) == ext:
            raise PersonServiceError("refusing provider UUID as people.id")

    seed_meta = {
        ATTR_IDENTITY_AUTHORITY: AUTHORITY_TRUSTED_PROVIDER,
        ATTR_SEEDED_FROM: {
            "provider_key": pk,
            "identity_kind": identity_kind,
            "external_id": ext,
            "display_name": name,
        },
    }
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO people (id, display_name, status, attributes_json)
            VALUES (%s, %s, 'unresolved', %s::jsonb)
            """,
            (pid, name, json.dumps(seed_meta)),
        )
    return map_provider_identity(
        person_id=str(pid),
        provider_key=pk,
        external_id=ext,
        label=name,
        identity_kind=identity_kind,
        actor_key=f"{pk}_trusted",
        confirm_person=False,
        identity_authority=AUTHORITY_TRUSTED_PROVIDER,
        assertion_authority=AUTHORITY_TRUSTED_PROVIDER,
    )


def resolve_or_seed_trusted_provider_person(
    display_name: str,
    *,
    photo: Any | None = None,
) -> PersonView | None:
    """If a unique named trusted photo identity exists, resolve or lazily seed it.

    Returns None when no exact trusted-provider name match exists.
    Raises AmbiguousIdentityError when multiple exact Immich names collide or
    when an Immich identity would silently merge onto an existing same-name MB Person.
    """
    name = (display_name or "").strip()
    if len(name) < 2:
        return None
    if photo is None:
        try:
            from memorybox.ask.deps import build_photo

            photo = build_photo()
        except Exception:  # noqa: BLE001
            return None

    matches = _ask_named_photo_people(photo, name)
    if not matches:
        return None
    if len(matches) > 1:
        first = (name.split()[0] if name.split() else name) or "person"
        labels = [
            str(getattr(m, "display_name", "") or "").strip()
            for m in matches
            if str(getattr(m, "display_name", "") or "").strip()
        ]
        raise AmbiguousIdentityError(
            f"Please specify which {first} you would like"
            + (f": {', '.join(labels)}." if labels else "."),
            candidates=[
                {
                    "provider_key": getattr(m, "provider_key", None)
                    or getattr(photo, "provider_key", PROVIDER_IMMICH),
                    "external_id": str(getattr(m, "external_id", "") or ""),
                    "display_name": getattr(m, "display_name", name),
                }
                for m in matches
            ],
        )

    ref = matches[0]
    pk = getattr(ref, "provider_key", None) or getattr(photo, "provider_key", PROVIDER_IMMICH)
    ext = str(getattr(ref, "external_id", "") or "").strip()
    if not ext:
        return None

    mapped = find_person_by_provider_external_id(provider_key=pk, external_id=ext)
    if mapped:
        return mapped

    mb_same = list_people_by_exact_name(name)
    if mb_same:
        # Do not equate Immich Peggy with an existing MB Peggy by display name alone.
        raise AmbiguousIdentityError(
            f"trusted provider identity {name!r} is unmapped, but MB Person(s) "
            f"already use that display name — owner resolution required (no silent merge). "
            f"Map the provider identity onto the correct Person via /people/{{id}}/map.",
            candidates=[
                {
                    "person_id": p.id,
                    "display_name": p.display_name,
                    "status": p.status,
                    "provider_keys": sorted(
                        {
                            str(m.get("provider_key"))
                            for m in (p.provider_mappings or [])
                            if m.get("provider_key")
                        }
                    ),
                }
                for p in mb_same
            ],
        )

    return seed_person_from_trusted_provider(
        provider_key=pk,
        external_id=ext,
        display_name=name,
    )


def resolve_person_for_identity_teach(
    display_name: str,
    *,
    photo: Any | None = None,
    create_if_missing: bool = True,
    confirm: bool = False,
) -> PersonView:
    """Central teach/bootstrap resolution (I6 service — used by I7 Review teach).

    Prefer an existing trusted-provider mapping; else lazy-seed from Immich when
    uniquely named; else reuse a unique MB Person by exact name; else create.
    """
    name = (display_name or "").strip()
    if len(name) < 2:
        raise PersonServiceError("display_name required")

    # Trusted provider bootstrap (may raise AmbiguousIdentityError)
    seeded = resolve_or_seed_trusted_provider_person(name, photo=photo)
    if seeded is not None:
        if confirm and seeded.status != "confirmed":
            with connection() as conn:
                conn.execute(
                    """
                    UPDATE people
                    SET status = 'confirmed',
                        attributes_json = attributes_json || %s::jsonb,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (
                        json.dumps({ATTR_IDENTITY_AUTHORITY: AUTHORITY_OWNER_CONFIRMED}),
                        UUID(seeded.id),
                    ),
                )
            refreshed = get_person(seeded.id)
            if refreshed:
                return refreshed
        return seeded

    mb = list_people_by_exact_name(name)
    if len(mb) > 1:
        raise AmbiguousIdentityError(
            f"ambiguous MB Person name {name!r}: {len(mb)} matches — "
            "owner resolution required",
            candidates=[
                {
                    "person_id": p.id,
                    "display_name": p.display_name,
                    "status": p.status,
                    "provider_keys": sorted(
                        {
                            str(m.get("provider_key"))
                            for m in (p.provider_mappings or [])
                            if m.get("provider_key")
                        }
                    ),
                }
                for p in mb
            ],
        )
    if len(mb) == 1:
        person = mb[0]
        if confirm and person.status != "confirmed":
            with connection() as conn:
                conn.execute(
                    """
                    UPDATE people
                    SET status = 'confirmed',
                        attributes_json = attributes_json || %s::jsonb,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (
                        json.dumps({ATTR_IDENTITY_AUTHORITY: AUTHORITY_OWNER_CONFIRMED}),
                        UUID(person.id),
                    ),
                )
            refreshed = get_person(person.id)
            if refreshed:
                return refreshed
        return person

    if not create_if_missing:
        raise PersonServiceError(f"person not found: {name!r}")
    resolved = resolve_person_by_name(name, create_if_missing=True, confirm=confirm)
    view = get_person(resolved.person_id)
    if not view:
        raise PersonServiceError("person create failed")
    return view


def _pick_unique_ask_person(candidates: list[PersonView]) -> PersonView | None:
    """Return the single usable Ask person, or raise if several distinct people match."""
    if not candidates:
        return None
    # Prefer confirmed, then trusted-provider, then mapped unresolved
    ranked: list[PersonView] = []
    for p in candidates:
        if p.status == "confirmed":
            ranked.append(p)
            continue
        if p.identity_authority == AUTHORITY_TRUSTED_PROVIDER:
            ranked.append(p)
            continue
        if any(
            m.get("provider_key")
            in {PROVIDER_IMMICH, "fake_photo", "immich", "hvrt", "fake_video"}
            for m in p.provider_mappings
        ):
            ranked.append(p)
    if not ranked:
        return None
    by_id: dict[str, PersonView] = {}
    for p in ranked:
        by_id.setdefault(p.id, p)
    unique = list(by_id.values())
    if len(unique) == 1:
        return unique[0]
    first = (unique[0].display_name or "person").strip().split()[0] or "person"
    labels = [str(p.display_name) for p in unique if p.display_name]
    raise AmbiguousIdentityError(
        f"Please specify which {first} you would like"
        + (f": {', '.join(labels)}." if labels else "."),
        candidates=[
            {
                "person_id": p.id,
                "display_name": p.display_name,
                "status": p.status,
                "identity_authority": p.identity_authority,
            }
            for p in unique
        ],
    )


def find_ask_person_by_name(
    display_name: str,
    *,
    photo: Any | None = None,
    lazy_seed: bool = True,
) -> PersonView | None:
    """Resolve a Person usable for Ask retrieval (confirmed or trusted-provider).

    Never returns AI/inferred as confirmed. May lazily seed from Immich when needed.
    Short single-token names (e.g. \"Peggy\") resolve when exactly one MB Person
    shares that first display-name token (e.g. \"Peggy George\").
    """
    name = (display_name or "").strip()
    if len(name) < 2:
        return None
    confirmed = find_confirmed_person_by_name(name)
    if confirmed:
        return confirmed

    # Unresolved / provider-seeded MB Person with exact name
    exact = list_people_by_exact_name(name)
    picked = _pick_unique_ask_person(exact) if exact else None
    if picked:
        return picked

    # Unique first-token match (Peggy → Peggy George) when query is a single token
    if " " not in name:
        token_hits = list_people_by_first_token(name)
        # Exclude already-considered exact (none) — pick unique among token hits
        picked = _pick_unique_ask_person(token_hits) if token_hits else None
        if picked:
            return picked

    if not lazy_seed:
        return None
    try:
        return resolve_or_seed_trusted_provider_person(name, photo=photo)
    except AmbiguousIdentityError:
        # Ask must disclose ambiguity rather than pick silently
        raise


def reconcile_provider_identity(
    *,
    person_id: str,
    provider_key: str,
    new_external_id: str,
    previous_external_id: str | None = None,
    label: str | None = None,
    identity_kind: str = KIND_EXTERNAL_PERSON,
    actor_key: str = "owner",
) -> PersonView:
    """Attach a new provider external id to an existing MB Person after reprocess.

    Durability rules (I10):
    - Canonical MB Person knowledge survives (same people.id).
    - Owner-confirmed assertions / mappings survive; new id is mapped onto that Person.
    - Historical provider mapping provenance survives (previous row retained + marked).
    - Provider external IDs/clusters are NOT assumed permanently stable.
    Never silently mints a duplicate Person; never joins by display name alone.
    """
    new_ext = (new_external_id or "").strip()
    if not new_ext:
        raise PersonServiceError("new_external_id required")
    view = map_provider_identity(
        person_id=person_id,
        provider_key=provider_key,
        external_id=new_ext,
        label=label,
        identity_kind=identity_kind,
        actor_key=actor_key,
        confirm_person=True,
        identity_authority=AUTHORITY_OWNER_CONFIRMED,
        assertion_authority="owner",
    )
    prev = (previous_external_id or "").strip()
    if prev and prev != new_ext:
        pk = (provider_key or "").strip() or PROVIDER_IMMICH
        pid = _parse_uuid(person_id, field="person_id")
        patch = {
            "superseded_by_external_id": new_ext,
            "reprocess_reconcile": True,
            "reconciled_by": actor_key or "owner",
        }
        with connection() as conn:
            conn.execute(
                """
                UPDATE provider_identities
                SET metadata_json = COALESCE(metadata_json, '{}'::jsonb) || %s::jsonb
                WHERE provider_key = %s
                  AND identity_kind = %s
                  AND external_id = %s
                  AND person_id = %s
                """,
                (json.dumps(patch), pk, identity_kind, prev, pid),
            )
            # Provenance assertion: reconcile event (owner knowledge retained)
            conn.execute(
                """
                INSERT INTO assertions (
                    id, assertion_kind, subject_type, subject_id,
                    predicate, object_type, statement, confidence,
                    authority, status, provenance_json
                )
                VALUES (
                    %s, 'provider_identity_reconcile', 'person', %s,
                    'reconciled_to', 'provider_identity', %s, 1.0,
                    'owner', 'confirmed', %s::jsonb
                )
                """,
                (
                    uuid4(),
                    pid,
                    f"{pk}:{prev}→{new_ext}",
                    json.dumps(
                        {
                            "provider_key": pk,
                            "previous_external_id": prev,
                            "new_external_id": new_ext,
                            "actor_key": actor_key or "owner",
                            "note": (
                                "provider reprocess reconcile; "
                                "external ids not assumed stable"
                            ),
                        }
                    ),
                ),
            )
        refreshed = get_person(person_id)
        if refreshed:
            return refreshed
    return view


def provider_mappings_projection(person_id: str) -> dict[str, Any]:
    """Rebuildable projection of provider mappings for a Person (I10 indexes from PG)."""
    view = get_person(person_id)
    if not view:
        raise PersonServiceError("person not found")
    by_provider: dict[str, list[str]] = {}
    for m in view.provider_mappings or []:
        pk = str(m.get("provider_key") or "")
        ext = str(m.get("external_id") or "")
        if not pk or not ext:
            continue
        by_provider.setdefault(pk, []).append(ext)
    return {
        "person_id": view.id,
        "display_name": view.display_name,
        "by_provider": {k: list(dict.fromkeys(v)) for k, v in sorted(by_provider.items())},
        "mappings": list(view.provider_mappings or []),
        "rebuildable_from": "provider_identities + people (PostgreSQL)",
    }


def teach_provider_person(
    *,
    display_name: str,
    provider_key: str,
    external_id: str,
    label: str | None = None,
    identity_kind: str = KIND_EXTERNAL_PERSON,
    actor_key: str = "owner",
    photo: Any | None = None,
) -> PersonView:
    """Resolve/seed Person (trusted Immich bootstrap when needed) and map identity.

    Owner teach confirms the Person for the taught mapping. Immich seed provenance
    on a prior trusted-provider mapping is preserved (not rewritten as owner-origin).
    """
    person = resolve_person_for_identity_teach(
        display_name,
        photo=photo,
        create_if_missing=True,
        confirm=True,
    )
    # Never allow provider UUID to become people.id (guarded in map as well)
    if person.id == (external_id or "").strip():
        raise PersonServiceError(
            "people.id must not equal provider external_id (Immich UUID is not Person PK)"
        )
    return map_provider_identity(
        person_id=person.id,
        provider_key=provider_key,
        external_id=external_id,
        label=label or display_name,
        identity_kind=identity_kind,
        actor_key=actor_key,
        confirm_person=True,
        identity_authority=AUTHORITY_OWNER_CONFIRMED,
        assertion_authority="owner",
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
    return list_provider_external_ids_for_person(person_id, PROVIDER_IMMICH)


def resolve_immich_external_ids_for_person(
    person_id: str, *, photo: Any | None = None
) -> list[str]:
    """Immich person UUIDs for an MB Person — mapped ids, then exact-name Immich match.

    Gallery/Ask already resolve Sue Will via Immich name when provider_identities
    is empty; portraits must use the same path so preferred Immich face shows.
    """
    out: list[str] = []
    try:
        out.extend(list_immich_external_ids_for_person(person_id))
    except PersonServiceError:
        return []

    view = None
    try:
        view = get_person(person_id)
    except Exception:  # noqa: BLE001
        view = None
    if view:
        for m in view.provider_mappings or []:
            if not isinstance(m, dict):
                continue
            if str(m.get("provider_key") or "").strip().lower() not in {
                PROVIDER_IMMICH,
                "immich",
            }:
                continue
            ext = str(m.get("external_id") or "").strip()
            if ext:
                out.append(ext)

    name = (view.display_name if view else "") or ""
    # Same path Gallery/Ask uses when provider_identities has no Immich row yet
    if name and not out:
        provider = photo
        if provider is None:
            try:
                from memorybox.ask.deps import build_photo

                provider = build_photo()
            except Exception:  # noqa: BLE001
                provider = None
        if provider is not None:
            try:
                refs = _exact_named_photo_people(provider, name)
                if not refs:
                    refs = _ask_named_photo_people(provider, name)
            except Exception:  # noqa: BLE001
                refs = []
            # Exact name, or a single unambiguous Immich person hit
            use_refs = []
            needle = name.strip().lower()
            exact = [
                r
                for r in refs
                if (getattr(r, "display_name", None) or "").strip().lower() == needle
            ]
            if exact:
                use_refs = exact
            elif len(refs) == 1:
                use_refs = refs
            for r in use_refs:
                ext = str(getattr(r, "external_id", "") or "").strip()
                if ext:
                    out.append(ext)

    return list(dict.fromkeys(x for x in out if x))


def fetch_person_portrait_bytes(person_id: str) -> tuple[bytes, str] | None:
    """Immich preferred person thumbnail only (People header).

    Never substitute a random face-evidence crop or first library still — those
    are not Immich's feature-face / preferred thumb.
    """
    from memorybox.ask.deps import build_photo

    try:
        photo = build_photo()
    except Exception:  # noqa: BLE001
        return None

    client = getattr(photo, "_client", None)
    fetch_person = getattr(client, "fetch_person_thumbnail_bytes", None)
    if not callable(fetch_person):
        return None
    for ext in resolve_immich_external_ids_for_person(person_id, photo=photo):
        try:
            got = fetch_person(ext)
        except Exception:  # noqa: BLE001
            got = None
        if got:
            data, ctype, _src = got
            if data:
                return data, ctype or "image/jpeg"
    return None


def list_provider_external_ids_for_person(
    person_id: str, provider_key: str
) -> list[str]:
    pid = _parse_uuid(person_id, field="person_id")
    pk = (provider_key or "").strip()
    if not pk:
        raise PersonServiceError("provider_key required")
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT external_id FROM provider_identities
            WHERE person_id = %s
              AND provider_key = %s
            """,
            (pid, pk),
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
