"""Shared life events — marriage/anniversary class (Increment 9A)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any
from uuid import uuid4

from memorybox.db import connection
from memorybox.profile.owner import (
    ProfileServiceError,
    ensure_person,
    iso,
    parse_date,
    parse_uuid,
    prov,
)


@dataclass
class LifeEventView:
    id: str
    event_kind: str
    event_date: str | None
    label: str | None
    status: str
    actor_key: str
    note: str | None
    provenance: dict[str, Any]
    created_at: str | None
    participants: list[dict[str, Any]] = field(default_factory=list)
    superseded_by_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_marriage_event(
    *,
    person_a_id: str,
    person_b_id: str,
    event_date: str | date | None,
    label: str | None = None,
    actor_key: str = "owner",
    note: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> LifeEventView:
    a = ensure_person(person_a_id)
    b = ensure_person(person_b_id)
    if a == b:
        raise ProfileServiceError("marriage requires two distinct people")
    vd = parse_date(event_date, field="event_date")
    eid = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO shared_life_events (
                id, event_kind, event_date, label, status,
                actor_key, note, provenance_json
            ) VALUES (%s, 'marriage', %s, %s, 'confirmed', %s, %s, %s::jsonb)
            """,
            (
                eid,
                vd,
                label or "Marriage",
                actor_key,
                note,
                json.dumps(provenance or {"source": "owner"}),
            ),
        )
        for pid in (a, b):
            conn.execute(
                """
                INSERT INTO shared_life_event_participants
                    (event_id, person_id, participant_role)
                VALUES (%s, %s, 'spouse')
                """,
                (eid, pid),
            )
    return get_life_event(str(eid))


def get_life_event(event_id: str) -> LifeEventView:
    eid = parse_uuid(event_id, field="event_id")
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM shared_life_events WHERE id = %s", (eid,)
        ).fetchone()
        if not row:
            raise ProfileServiceError(f"life event not found: {eid}")
        parts = conn.execute(
            """
            SELECT p.person_id, p.participant_role, pe.display_name
            FROM shared_life_event_participants p
            JOIN people pe ON pe.id = p.person_id
            WHERE p.event_id = %s
            ORDER BY pe.display_name NULLS LAST
            """,
            (eid,),
        ).fetchall()
    return LifeEventView(
        id=str(row["id"]),
        event_kind=row["event_kind"],
        event_date=iso(row.get("event_date")),
        label=row.get("label"),
        status=row["status"],
        actor_key=row.get("actor_key") or "owner",
        note=row.get("note"),
        provenance=prov(row.get("provenance_json")),
        created_at=iso(row.get("created_at")),
        participants=[
            {
                "person_id": str(p["person_id"]),
                "participant_role": p["participant_role"],
                "display_name": p.get("display_name"),
            }
            for p in parts
        ],
        superseded_by_id=str(row["superseded_by_id"]) if row.get("superseded_by_id") else None,
    )


def find_marriage_between(person_a_id: str, person_b_id: str) -> list[LifeEventView]:
    a = ensure_person(person_a_id)
    b = ensure_person(person_b_id)
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT e.id
            FROM shared_life_events e
            JOIN shared_life_event_participants pa
                ON pa.event_id = e.id AND pa.person_id = %s
            JOIN shared_life_event_participants pb
                ON pb.event_id = e.id AND pb.person_id = %s
            WHERE e.event_kind = 'marriage' AND e.status = 'confirmed'
            ORDER BY e.event_date NULLS LAST, e.created_at ASC
            """,
            (a, b),
        ).fetchall()
    return [get_life_event(str(r["id"])) for r in rows]


def list_life_events_for_person(person_id: str) -> list[LifeEventView]:
    pid = ensure_person(person_id)
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT e.id
            FROM shared_life_events e
            JOIN shared_life_event_participants p ON p.event_id = e.id
            WHERE p.person_id = %s AND e.status = 'confirmed'
            ORDER BY e.event_date NULLS LAST, e.created_at ASC
            """,
            (pid,),
        ).fetchall()
    return [get_life_event(str(r["id"])) for r in rows]
