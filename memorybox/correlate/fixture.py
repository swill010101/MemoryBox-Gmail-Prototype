"""Harness fixture for P2-I10 — Grandpa military-service pack (not FlightSim corpus)."""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from memorybox.correlate.store import reject_link, upsert_event, upsert_link, upsert_place
from memorybox.db import connection
from memorybox.person import resolve_person_by_name


def seed_i10_military_fixture() -> dict[str, Any]:
    """Insert Person + mixed evidence + place/event + one rejected extra + date conflict."""
    person = resolve_person_by_name("Eugene Will", create_if_missing=True, confirm=True)
    pid = person.person_id
    place = upsert_place("Fort Lewis")
    event = upsert_event("military service", event_kind="theme")
    source_id = str(uuid4())
    email_id = str(uuid4())
    letter_good = str(uuid4())
    letter_conflict = str(uuid4())
    noise_id = str(uuid4())
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO sources (id, source_kind, label, uri, authoritative_original_mode)
            VALUES (%s::uuid, 'harness', 'i10-military', 'memorybox://i10', 'referenced')
            ON CONFLICT (id) DO NOTHING
            """,
            (source_id,),
        )
        conn.execute(
            """
            INSERT INTO evidence (
                id, evidence_kind, source_id, summary, payload_json
            ) VALUES
            (
                %s::uuid, 'communication', %s::uuid,
                'Eugene wrote home from the army about Fort Lewis training.',
                %s::jsonb
            ),
            (
                %s::uuid, 'communication', %s::uuid,
                'Discharge letter dated 1968 — military service, Fort Lewis.',
                %s::jsonb
            ),
            (
                %s::uuid, 'communication', %s::uuid,
                'Another copy of the discharge paperwork dated 1969.',
                %s::jsonb
            ),
            (
                %s::uuid, 'communication', %s::uuid,
                'Recipe for walnut rolls from Peggy — not military.',
                %s::jsonb
            )
            ON CONFLICT (id) DO NOTHING
            """,
            (
                email_id,
                source_id,
                json.dumps(
                    {
                        "channel": "email",
                        "sent_at": "1968-03-12T12:00:00Z",
                        "from": "eugene@example.com",
                        "people": ["Eugene Will"],
                        "body": "Army training at Fort Lewis. Military service notes.",
                    }
                ),
                letter_good,
                source_id,
                json.dumps(
                    {
                        "channel": "email",
                        "sent_at": "1968-06-01T12:00:00Z",
                        "from": "eugene@example.com",
                        "people": ["Eugene Will"],
                        "body": "Military discharge 1968 Fort Lewis.",
                    }
                ),
                letter_conflict,
                source_id,
                json.dumps(
                    {
                        "channel": "email",
                        "sent_at": "1969-06-01T12:00:00Z",
                        "from": "eugene@example.com",
                        "people": ["Eugene Will"],
                        "body": "Military discharge 1969 copy.",
                    }
                ),
                noise_id,
                source_id,
                json.dumps(
                    {
                        "channel": "email",
                        "sent_at": "2012-12-01T12:00:00Z",
                        "from": "peggy@example.com",
                        "people": ["Peggy George"],
                        "body": "Walnut roll recipe. Not army.",
                    }
                ),
            ),
        )
        art_id = str(uuid4())
        conn.execute(
            """
            INSERT INTO artifacts (id, kind, label, description, status)
            VALUES (
                %s::uuid, 'letter', 'Eugene army letter',
                'Handwritten letter about military service at Fort Lewis',
                'active'
            )
            ON CONFLICT (id) DO NOTHING
            """,
            (art_id,),
        )

    upsert_link(
        subject_type="evidence",
        subject_id=email_id,
        object_type="event",
        object_id=event["id"],
        predicate="about",
        evidence_id=email_id,
        authority="system",
        status="candidate",
        observed_date="1968-03-12",
        provenance={"fixture": "i10"},
    )
    upsert_link(
        subject_type="evidence",
        subject_id=letter_good,
        object_type="event",
        object_id=event["id"],
        predicate="about",
        evidence_id=letter_good,
        authority="owner",
        status="confirmed",
        observed_date="1968-06-01",
        provenance={"fixture": "i10"},
    )
    upsert_link(
        subject_type="evidence",
        subject_id=letter_conflict,
        object_type="event",
        object_id=event["id"],
        predicate="about",
        evidence_id=letter_conflict,
        authority="system",
        status="candidate",
        observed_date="1969-06-01",
        provenance={"fixture": "i10"},
    )
    noise_link = upsert_link(
        subject_type="evidence",
        subject_id=noise_id,
        object_type="event",
        object_id=event["id"],
        predicate="about",
        evidence_id=noise_id,
        authority="system",
        status="candidate",
        observed_date="2012-12-01",
        provenance={"fixture": "i10-noise"},
    )
    rejected = reject_link(noise_link["id"])
    upsert_link(
        subject_type="artifact",
        subject_id=art_id,
        object_type="event",
        object_id=event["id"],
        predicate="about",
        authority="owner",
        status="confirmed",
        provenance={"fixture": "i10"},
    )
    upsert_link(
        subject_type="person",
        subject_id=pid,
        object_type="event",
        object_id=event["id"],
        predicate="involves",
        authority="owner",
        status="confirmed",
        provenance={"fixture": "i10"},
    )
    upsert_link(
        subject_type="place",
        subject_id=place["id"],
        object_type="event",
        object_id=event["id"],
        predicate="located_at",
        authority="system",
        status="candidate",
        provenance={"fixture": "i10"},
    )
    return {
        "person_id": pid,
        "person_name": "Eugene Will",
        "place_id": place["id"],
        "event_id": event["id"],
        "email_id": email_id,
        "letter_1968": letter_good,
        "letter_1969": letter_conflict,
        "noise_id": noise_id,
        "noise_link_id": noise_link["id"],
        "rejected": rejected,
        "artifact_id": art_id,
    }
