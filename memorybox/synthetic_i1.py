"""Increment 1 synthetic fixture: Grandpa photo graph (not real archive data).

Idempotent seed keyed by stable UUIDs. Prove retrieves the joined graph after restart.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from memorybox.db import connection

# Stable IDs so re-seed and prove stay deterministic across restarts.
PERSON_ID = UUID("11111111-1111-4111-8111-111111111111")
SOURCE_ID = UUID("22222222-2222-4222-8222-222222222222")
MEDIA_ID = UUID("33333333-3333-4333-8333-333333333333")
MEDIA_REF_ID = UUID("44444444-4444-4444-8444-444444444444")
EVIDENCE_ID = UUID("55555555-5555-4555-8555-555555555555")
ASSERTION_ID = UUID("66666666-6666-4666-8666-666666666666")
STORY_ID = UUID("77777777-7777-4777-8777-777777777777")
STORY_VERSION_ID = UUID("88888888-8888-4888-8888-888888888888")
REL_STORY_PERSON = UUID("99999999-9999-4999-8999-999999999901")
REL_STORY_EVIDENCE = UUID("99999999-9999-4999-8999-999999999902")

FIXTURE_TAG = "i1_synthetic_grandpa"
MEDIA_REF_EXTERNAL = "grandpa_christmas.jpg"


def seed() -> dict[str, Any]:
    """Insert or refresh the synthetic graph. Safe to re-run."""
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO people (id, display_name, status, notes, attributes_json)
            VALUES (%s, 'Grandpa', 'confirmed', 'Synthetic I1 fixture person',
                    %s::jsonb)
            ON CONFLICT (id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                status = EXCLUDED.status,
                notes = EXCLUDED.notes,
                attributes_json = EXCLUDED.attributes_json,
                updated_at = now()
            """,
            (PERSON_ID, f'{{"fixture":"{FIXTURE_TAG}"}}'),
        )

        conn.execute(
            """
            INSERT INTO sources (
                id, source_kind, label, uri, authoritative_original_mode, metadata_json
            )
            VALUES (
                %s, 'filesystem', 'test photo import',
                'synthetic://i1/test-photo-import', 'referenced',
                %s::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                source_kind = EXCLUDED.source_kind,
                label = EXCLUDED.label,
                uri = EXCLUDED.uri,
                metadata_json = EXCLUDED.metadata_json,
                updated_at = now()
            """,
            (SOURCE_ID, f'{{"fixture":"{FIXTURE_TAG}"}}'),
        )

        conn.execute(
            """
            INSERT INTO media_objects (
                id, source_id, media_kind, storage_mode, uri, mime_type, metadata_json
            )
            VALUES (
                %s, %s, 'photo', 'referenced',
                'synthetic://i1/grandpa_christmas.jpg', 'image/jpeg',
                %s::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                source_id = EXCLUDED.source_id,
                media_kind = EXCLUDED.media_kind,
                uri = EXCLUDED.uri,
                metadata_json = EXCLUDED.metadata_json,
                updated_at = now()
            """,
            (MEDIA_ID, SOURCE_ID, f'{{"fixture":"{FIXTURE_TAG}","filename":"{MEDIA_REF_EXTERNAL}"}}'),
        )

        conn.execute(
            """
            INSERT INTO media_refs (
                id, media_object_id, provider_key, external_id, metadata_json
            )
            VALUES (%s, %s, 'filesystem', %s, %s::jsonb)
            ON CONFLICT (id) DO UPDATE SET
                media_object_id = EXCLUDED.media_object_id,
                provider_key = EXCLUDED.provider_key,
                external_id = EXCLUDED.external_id,
                metadata_json = EXCLUDED.metadata_json
            """,
            (
                MEDIA_REF_ID,
                MEDIA_ID,
                MEDIA_REF_EXTERNAL,
                f'{{"fixture":"{FIXTURE_TAG}"}}',
            ),
        )

        conn.execute(
            """
            INSERT INTO evidence (
                id, evidence_kind, source_id, media_object_id, summary, payload_json
            )
            VALUES (
                %s, 'annotation', %s, %s,
                'face detected in that photo',
                %s::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                evidence_kind = EXCLUDED.evidence_kind,
                source_id = EXCLUDED.source_id,
                media_object_id = EXCLUDED.media_object_id,
                summary = EXCLUDED.summary,
                payload_json = EXCLUDED.payload_json,
                updated_at = now()
            """,
            (
                EVIDENCE_ID,
                SOURCE_ID,
                MEDIA_ID,
                f'{{"fixture":"{FIXTURE_TAG}","detection":"face"}}',
            ),
        )

        conn.execute(
            """
            INSERT INTO assertions (
                id, assertion_kind, subject_type, subject_id, predicate,
                object_type, object_id, statement, confidence, authority, status,
                provenance_json
            )
            VALUES (
                %s, 'identity', 'media_object', %s, 'depicts_person',
                'person', %s, 'person shown is Grandpa', 0.95, 'system', 'confirmed',
                %s::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                statement = EXCLUDED.statement,
                object_id = EXCLUDED.object_id,
                status = EXCLUDED.status,
                provenance_json = EXCLUDED.provenance_json,
                updated_at = now()
            """,
            (
                ASSERTION_ID,
                MEDIA_ID,
                PERSON_ID,
                f'{{"fixture":"{FIXTURE_TAG}"}}',
            ),
        )

        conn.execute(
            """
            INSERT INTO assertion_evidence (assertion_id, evidence_id, role)
            VALUES (%s, %s, 'supports')
            ON CONFLICT (assertion_id, evidence_id, role) DO NOTHING
            """,
            (ASSERTION_ID, EVIDENCE_ID),
        )

        conn.execute(
            """
            INSERT INTO stories (id, title, status, narrator_person_id, current_version)
            VALUES (%s, 'Christmas with Grandpa (synthetic)', 'active', %s, 1)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                narrator_person_id = EXCLUDED.narrator_person_id,
                status = EXCLUDED.status,
                updated_at = now()
            """,
            (STORY_ID, PERSON_ID),
        )

        conn.execute(
            """
            INSERT INTO story_versions (
                id, story_id, version, body_text, actor_key, note
            )
            VALUES (
                %s, %s, 1,
                'Simple test Story: Grandpa appears in grandpa_christmas.jpg.',
                'system', 'I1 synthetic fixture'
            )
            ON CONFLICT (id) DO UPDATE SET
                body_text = EXCLUDED.body_text,
                note = EXCLUDED.note
            """,
            (STORY_VERSION_ID, STORY_ID),
        )

        conn.execute(
            """
            INSERT INTO relationships (
                id, relationship_kind, from_type, from_id, to_type, to_id,
                label, status, attributes_json
            )
            VALUES (
                %s, 'about_person', 'story', %s, 'person', %s,
                'Story about Grandpa', 'confirmed', %s::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                label = EXCLUDED.label,
                status = EXCLUDED.status,
                attributes_json = EXCLUDED.attributes_json,
                updated_at = now()
            """,
            (REL_STORY_PERSON, STORY_ID, PERSON_ID, f'{{"fixture":"{FIXTURE_TAG}"}}'),
        )

        conn.execute(
            """
            INSERT INTO relationships (
                id, relationship_kind, from_type, from_id, to_type, to_id,
                label, status, attributes_json
            )
            VALUES (
                %s, 'cites_evidence', 'story', %s, 'evidence', %s,
                'Story cites face evidence', 'confirmed', %s::jsonb
            )
            ON CONFLICT (id) DO UPDATE SET
                label = EXCLUDED.label,
                status = EXCLUDED.status,
                attributes_json = EXCLUDED.attributes_json,
                updated_at = now()
            """,
            (
                REL_STORY_EVIDENCE,
                STORY_ID,
                EVIDENCE_ID,
                f'{{"fixture":"{FIXTURE_TAG}"}}',
            ),
        )

    return {
        "ok": True,
        "fixture": FIXTURE_TAG,
        "ids": {
            "person": str(PERSON_ID),
            "source": str(SOURCE_ID),
            "media_object": str(MEDIA_ID),
            "media_ref": str(MEDIA_REF_ID),
            "evidence": str(EVIDENCE_ID),
            "assertion": str(ASSERTION_ID),
            "story": str(STORY_ID),
        },
    }


def prove() -> dict[str, Any]:
    """Retrieve the joined synthetic graph; fail closed if any link is missing."""
    with connection() as conn:
        row = conn.execute(
            """
            SELECT
                p.display_name AS person_name,
                p.status AS person_status,
                s.label AS source_label,
                s.source_kind,
                mr.external_id AS media_ref,
                mo.uri AS media_uri,
                e.summary AS evidence_summary,
                a.statement AS assertion_statement,
                a.status AS assertion_status,
                st.title AS story_title,
                sv.body_text AS story_body,
                st.narrator_person_id,
                rel_p.label AS story_person_rel,
                rel_e.label AS story_evidence_rel
            FROM people p
            JOIN assertions a
              ON a.object_type = 'person' AND a.object_id = p.id AND a.id = %s
            JOIN assertion_evidence ae
              ON ae.assertion_id = a.id AND ae.evidence_id = %s
            JOIN evidence e ON e.id = ae.evidence_id
            JOIN media_objects mo ON mo.id = e.media_object_id
            JOIN media_refs mr ON mr.media_object_id = mo.id AND mr.id = %s
            JOIN sources s ON s.id = mo.source_id
            JOIN stories st ON st.id = %s AND st.narrator_person_id = p.id
            JOIN story_versions sv ON sv.story_id = st.id AND sv.version = st.current_version
            JOIN relationships rel_p
              ON rel_p.id = %s
             AND rel_p.from_type = 'story' AND rel_p.from_id = st.id
             AND rel_p.to_type = 'person' AND rel_p.to_id = p.id
            JOIN relationships rel_e
              ON rel_e.id = %s
             AND rel_e.from_type = 'story' AND rel_e.from_id = st.id
             AND rel_e.to_type = 'evidence' AND rel_e.to_id = e.id
            WHERE p.id = %s
            """,
            (
                ASSERTION_ID,
                EVIDENCE_ID,
                MEDIA_REF_ID,
                STORY_ID,
                REL_STORY_PERSON,
                REL_STORY_EVIDENCE,
                PERSON_ID,
            ),
        ).fetchone()

    if not row:
        return {
            "ok": False,
            "fixture": FIXTURE_TAG,
            "error": "synthetic graph not retrieved — missing rows or broken FKs",
        }

    expected = {
        "person_name": "Grandpa",
        "source_label": "test photo import",
        "media_ref": MEDIA_REF_EXTERNAL,
        "evidence_summary": "face detected in that photo",
        "assertion_statement": "person shown is Grandpa",
        "story_title": "Christmas with Grandpa (synthetic)",
    }
    mismatches = {
        k: {"expected": v, "got": row.get(k)}
        for k, v in expected.items()
        if row.get(k) != v
    }
    ok = not mismatches
    return {
        "ok": ok,
        "fixture": FIXTURE_TAG,
        "graph": dict(row),
        "mismatches": mismatches,
        "checks": {
            "person_linked_as_narrator": str(row["narrator_person_id"]) == str(PERSON_ID),
            "story_person_relationship": bool(row["story_person_rel"]),
            "story_evidence_relationship": bool(row["story_evidence_rel"]),
            "assertion_confirmed": row["assertion_status"] == "confirmed",
        },
    }
