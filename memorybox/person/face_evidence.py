"""P2-I1 face evidence — Immich assets + owner confirm/correct (higher authority)."""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from memorybox.db import connection
from memorybox.person import (
    AUTHORITY_AI_INFERRED,
    AUTHORITY_OWNER_CONFIRMED,
    AUTHORITY_TRUSTED_PROVIDER,
)

CONFIRM_UNCONFIRMED = "unconfirmed"
CONFIRM_SYSTEM = "system_associated"
CONFIRM_OWNER = "owner_confirmed"
CONFIRM_CORRECTED = "owner_corrected"


def upsert_face_evidence(
    *,
    person_id: str | UUID,
    provider_key: str,
    method: str,
    authority: str,
    confirmation_state: str,
    external_face_id: str | None = None,
    external_person_id: str | None = None,
    source_asset_id: str | None = None,
    bbox: dict[str, Any] | None = None,
    confidence: float | None = None,
    exemplar_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth = authority.strip()
    if auth not in {
        AUTHORITY_OWNER_CONFIRMED,
        AUTHORITY_TRUSTED_PROVIDER,
        AUTHORITY_AI_INFERRED,
    }:
        raise ValueError(f"invalid authority {auth}")
    with connection() as conn:
        # Prefer update by provider+external_face when present
        if external_face_id:
            existing = conn.execute(
                """
                SELECT id::text, authority FROM face_evidence
                WHERE person_id = %s::uuid AND provider_key = %s AND external_face_id = %s
                LIMIT 1
                """,
                (str(person_id), provider_key, external_face_id),
            ).fetchone()
        else:
            existing = None
        if existing:
            # Owner-confirmed never downgraded by AI
            new_auth = existing["authority"]
            if existing["authority"] != AUTHORITY_OWNER_CONFIRMED:
                new_auth = auth
            if auth == AUTHORITY_OWNER_CONFIRMED:
                new_auth = AUTHORITY_OWNER_CONFIRMED
            row = conn.execute(
                """
                UPDATE face_evidence SET
                    method = %s,
                    authority = %s,
                    confirmation_state = %s,
                    confidence = COALESCE(%s, confidence),
                    bbox_json = COALESCE(%s::jsonb, bbox_json),
                    source_asset_id = COALESCE(%s, source_asset_id),
                    external_person_id = COALESCE(%s, external_person_id),
                    exemplar_meta_json = exemplar_meta_json || %s::jsonb,
                    updated_at = now()
                WHERE id = %s::uuid
                RETURNING id::text, person_id::text, provider_key, external_face_id,
                          external_person_id, source_asset_id, method, confidence,
                          confirmation_state, authority, exemplar_meta_json, created_at, updated_at
                """,
                (
                    method,
                    new_auth,
                    confirmation_state,
                    confidence,
                    json.dumps(bbox) if bbox is not None else None,
                    source_asset_id,
                    external_person_id,
                    json.dumps(exemplar_meta or {}),
                    existing["id"],
                ),
            ).fetchone()
        else:
            row = conn.execute(
                """
                INSERT INTO face_evidence (
                    person_id, provider_key, external_face_id, external_person_id,
                    source_asset_id, bbox_json, method, confidence,
                    confirmation_state, authority, exemplar_meta_json
                ) VALUES (
                    %s::uuid, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb
                )
                RETURNING id::text, person_id::text, provider_key, external_face_id,
                          external_person_id, source_asset_id, method, confidence,
                          confirmation_state, authority, exemplar_meta_json, created_at, updated_at
                """,
                (
                    str(person_id),
                    provider_key,
                    external_face_id,
                    external_person_id,
                    source_asset_id,
                    json.dumps(bbox or {}),
                    method,
                    confidence,
                    confirmation_state,
                    auth,
                    json.dumps(exemplar_meta or {}),
                ),
            ).fetchone()
    return _row(row)


def list_face_evidence(person_id: str | UUID) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id::text, person_id::text, provider_key, external_face_id,
                   external_person_id, source_asset_id, bbox_json, method, confidence,
                   confirmation_state, authority, exemplar_meta_json, created_at, updated_at
            FROM face_evidence
            WHERE person_id = %s::uuid
            ORDER BY
              CASE authority
                WHEN 'owner_confirmed' THEN 0
                WHEN 'trusted_provider' THEN 1
                ELSE 2
              END,
              created_at ASC
            """,
            (str(person_id),),
        ).fetchall()
    return [_row(r) for r in rows]


def owner_confirm_or_correct(
    *,
    person_id: str | UUID,
    provider_key: str,
    method: str = "owner_correct",
    external_face_id: str | None = None,
    source_asset_id: str | None = None,
    bbox: dict[str, Any] | None = None,
    confidence: float | None = 1.0,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = CONFIRM_CORRECTED if method == "owner_correct" else CONFIRM_OWNER
    return upsert_face_evidence(
        person_id=person_id,
        provider_key=provider_key,
        method=method,
        authority=AUTHORITY_OWNER_CONFIRMED,
        confirmation_state=state,
        external_face_id=external_face_id,
        source_asset_id=source_asset_id,
        bbox=bbox,
        confidence=confidence,
        exemplar_meta=meta,
    )


def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    for k in ("created_at", "updated_at"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    for jk in ("bbox_json", "exemplar_meta_json"):
        if isinstance(d.get(jk), str):
            d[jk] = json.loads(d[jk])
    return d
