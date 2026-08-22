"""Person aliases, facts, and contact points (Increment 9A)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from memorybox.db import connection
from memorybox.profile.owner import (
    ALIAS_KINDS,
    CONTACT_KINDS,
    FACT_KINDS,
    ProfileServiceError,
    ensure_person,
    iso,
    parse_date,
    parse_uuid,
    prov,
)


@dataclass
class AliasView:
    id: str
    person_id: str
    alias_kind: str
    alias_text: str
    status: str
    actor_key: str
    note: str | None
    provenance: dict[str, Any]
    created_at: str | None
    superseded_by_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FactView:
    id: str
    person_id: str
    fact_kind: str
    value_text: str | None
    value_date: str | None
    status: str
    actor_key: str
    note: str | None
    provenance: dict[str, Any]
    created_at: str | None
    superseded_by_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContactView:
    id: str
    person_id: str
    contact_kind: str
    value_text: str
    status: str
    actor_key: str
    note: str | None
    provenance: dict[str, Any]
    created_at: str | None
    superseded_by_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _alias_view(row: dict[str, Any]) -> AliasView:
    return AliasView(
        id=str(row["id"]),
        person_id=str(row["person_id"]),
        alias_kind=row["alias_kind"],
        alias_text=row["alias_text"],
        status=row["status"],
        actor_key=row.get("actor_key") or "owner",
        note=row.get("note"),
        provenance=prov(row.get("provenance_json")),
        created_at=iso(row.get("created_at")),
        superseded_by_id=str(row["superseded_by_id"]) if row.get("superseded_by_id") else None,
    )


def _fact_view(row: dict[str, Any]) -> FactView:
    return FactView(
        id=str(row["id"]),
        person_id=str(row["person_id"]),
        fact_kind=row["fact_kind"],
        value_text=row.get("value_text"),
        value_date=iso(row.get("value_date")),
        status=row["status"],
        actor_key=row.get("actor_key") or "owner",
        note=row.get("note"),
        provenance=prov(row.get("provenance_json")),
        created_at=iso(row.get("created_at")),
        superseded_by_id=str(row["superseded_by_id"]) if row.get("superseded_by_id") else None,
    )


def _contact_view(row: dict[str, Any]) -> ContactView:
    return ContactView(
        id=str(row["id"]),
        person_id=str(row["person_id"]),
        contact_kind=row["contact_kind"],
        value_text=row["value_text"],
        status=row["status"],
        actor_key=row.get("actor_key") or "owner",
        note=row.get("note"),
        provenance=prov(row.get("provenance_json")),
        created_at=iso(row.get("created_at")),
        superseded_by_id=str(row["superseded_by_id"]) if row.get("superseded_by_id") else None,
    )


def add_alias(
    person_id: str,
    *,
    alias_kind: str,
    alias_text: str,
    actor_key: str = "owner",
    note: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> AliasView:
    pid = ensure_person(person_id)
    kind = (alias_kind or "").strip().lower()
    if kind not in ALIAS_KINDS:
        raise ProfileServiceError(f"alias_kind must be one of {sorted(ALIAS_KINDS)}")
    text = (alias_text or "").strip()
    if len(text) < 1:
        raise ProfileServiceError("alias_text required")
    aid = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO person_aliases (
                id, person_id, alias_kind, alias_text, status, actor_key, note, provenance_json
            ) VALUES (%s, %s, %s, %s, 'confirmed', %s, %s, %s::jsonb)
            """,
            (aid, pid, kind, text, actor_key, note, json.dumps(provenance or {"source": "owner"})),
        )
        row = conn.execute("SELECT * FROM person_aliases WHERE id = %s", (aid,)).fetchone()
    return _alias_view(row)


def list_aliases(person_id: str, *, include_withdrawn: bool = False) -> list[AliasView]:
    pid = ensure_person(person_id)
    with connection() as conn:
        if include_withdrawn:
            rows = conn.execute(
                "SELECT * FROM person_aliases WHERE person_id = %s ORDER BY created_at ASC",
                (pid,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM person_aliases
                WHERE person_id = %s AND status = 'confirmed'
                ORDER BY created_at ASC
                """,
                (pid,),
            ).fetchall()
    return [_alias_view(r) for r in rows]


def add_fact(
    person_id: str,
    *,
    fact_kind: str,
    value_date: str | date | None = None,
    value_text: str | None = None,
    actor_key: str = "owner",
    note: str | None = None,
    provenance: dict[str, Any] | None = None,
    supersede_current: bool = True,
) -> FactView:
    pid = ensure_person(person_id)
    kind = (fact_kind or "").strip().lower()
    if kind not in FACT_KINDS:
        raise ProfileServiceError(f"fact_kind must be one of {sorted(FACT_KINDS)}")
    vd = parse_date(value_date, field="value_date") if kind != "note" else None
    vt = (value_text or "").strip() or None
    if kind in ("birth_date", "death_date"):
        if not vd:
            raise ProfileServiceError(f"{kind} requires value_date")
        vt = vt or vd.isoformat()
    elif kind == "note" and not vt:
        raise ProfileServiceError("note requires value_text")
    fid = uuid4()
    with connection() as conn:
        if supersede_current and kind in ("birth_date", "death_date"):
            for o in conn.execute(
                """
                SELECT id FROM person_facts
                WHERE person_id = %s AND fact_kind = %s AND status = 'confirmed'
                """,
                (pid, kind),
            ).fetchall():
                conn.execute(
                    """
                    UPDATE person_facts
                    SET status = 'superseded', superseded_by_id = %s, updated_at = now()
                    WHERE id = %s
                    """,
                    (fid, o["id"]),
                )
        conn.execute(
            """
            INSERT INTO person_facts (
                id, person_id, fact_kind, value_text, value_date,
                status, actor_key, note, provenance_json
            ) VALUES (%s, %s, %s, %s, %s, 'confirmed', %s, %s, %s::jsonb)
            """,
            (fid, pid, kind, vt, vd, actor_key, note, json.dumps(provenance or {"source": "owner"})),
        )
        row = conn.execute("SELECT * FROM person_facts WHERE id = %s", (fid,)).fetchone()
    return _fact_view(row)


def list_facts(person_id: str, *, include_withdrawn: bool = False) -> list[FactView]:
    pid = ensure_person(person_id)
    with connection() as conn:
        if include_withdrawn:
            rows = conn.execute(
                "SELECT * FROM person_facts WHERE person_id = %s ORDER BY created_at ASC",
                (pid,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM person_facts
                WHERE person_id = %s AND status = 'confirmed'
                ORDER BY created_at ASC
                """,
                (pid,),
            ).fetchall()
    return [_fact_view(r) for r in rows]


def get_current_fact(person_id: str, fact_kind: str) -> FactView | None:
    kind = (fact_kind or "").strip().lower()
    for f in list_facts(person_id):
        if f.fact_kind == kind:
            return f
    return None


def add_contact(
    person_id: str,
    *,
    contact_kind: str,
    value_text: str,
    actor_key: str = "owner",
    note: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> ContactView:
    pid = ensure_person(person_id)
    kind = (contact_kind or "").strip().lower()
    if kind not in CONTACT_KINDS:
        raise ProfileServiceError(f"contact_kind must be one of {sorted(CONTACT_KINDS)}")
    text = (value_text or "").strip()
    if len(text) < 2:
        raise ProfileServiceError("value_text required")
    cid = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO person_contact_points (
                id, person_id, contact_kind, value_text, status,
                actor_key, note, provenance_json
            ) VALUES (%s, %s, %s, %s, 'confirmed', %s, %s, %s::jsonb)
            """,
            (cid, pid, kind, text, actor_key, note, json.dumps(provenance or {"source": "owner"})),
        )
        row = conn.execute("SELECT * FROM person_contact_points WHERE id = %s", (cid,)).fetchone()
    return _contact_view(row)


def supersede_contact(
    contact_id: str,
    *,
    value_text: str,
    actor_key: str = "owner",
    note: str | None = None,
) -> ContactView:
    old_id = parse_uuid(contact_id, field="contact_id")
    text = (value_text or "").strip()
    if len(text) < 2:
        raise ProfileServiceError("value_text required")
    new_id = uuid4()
    with connection() as conn:
        old = conn.execute(
            "SELECT * FROM person_contact_points WHERE id = %s", (old_id,)
        ).fetchone()
        if not old:
            raise ProfileServiceError(f"contact not found: {old_id}")
        if old["status"] != "confirmed":
            raise ProfileServiceError("only confirmed contacts can be superseded")
        conn.execute(
            """
            UPDATE person_contact_points
            SET status = 'superseded', superseded_by_id = %s, updated_at = now()
            WHERE id = %s
            """,
            (new_id, old_id),
        )
        conn.execute(
            """
            INSERT INTO person_contact_points (
                id, person_id, contact_kind, value_text, status,
                actor_key, note, provenance_json
            ) VALUES (%s, %s, %s, %s, 'confirmed', %s, %s, %s::jsonb)
            """,
            (
                new_id,
                old["person_id"],
                old["contact_kind"],
                text,
                actor_key,
                note,
                json.dumps(
                    {
                        "source": "owner_correction",
                        "supersedes": str(old_id),
                        "prior_value": old["value_text"],
                    }
                ),
            ),
        )
        row = conn.execute(
            "SELECT * FROM person_contact_points WHERE id = %s", (new_id,)
        ).fetchone()
    return _contact_view(row)


def list_contacts(person_id: str, *, include_withdrawn: bool = False) -> list[ContactView]:
    pid = ensure_person(person_id)
    with connection() as conn:
        if include_withdrawn:
            rows = conn.execute(
                """
                SELECT * FROM person_contact_points WHERE person_id = %s
                ORDER BY created_at ASC
                """,
                (pid,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM person_contact_points
                WHERE person_id = %s AND status = 'confirmed'
                ORDER BY created_at ASC
                """,
                (pid,),
            ).fetchall()
    return [_contact_view(r) for r in rows]
