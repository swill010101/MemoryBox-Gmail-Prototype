"""Reusable derived semantic observations with provenance and invalidation."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

METHOD_VERSION = "i11a_person_obs_v1"


def source_hash(evidence_ids: list[str]) -> str:
    ids = sorted({str(x) for x in evidence_ids if str(x).strip()})
    return hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()[:40]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_observation(
    *,
    person_id: str | None,
    method: str,
    evidence_ids: list[str],
    method_version: str = METHOD_VERSION,
) -> dict[str, Any] | None:
    if not evidence_ids:
        return None
    digest = source_hash(evidence_ids)
    try:
        from memorybox.db import connection

        with connection() as conn:
            row = conn.execute(
                """
                SELECT payload, observation_id, model, confidence, uncertainty, created_at
                FROM semantic_observations
                WHERE method = %s
                  AND method_version = %s
                  AND source_hash = %s
                  AND invalidated_at IS NULL
                  AND (person_id IS NOT DISTINCT FROM %s)
                LIMIT 1
                """,
                (method, method_version, digest, person_id),
            ).fetchone()
        if not row:
            return None
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            return None
        payload["_cache"] = {
            "hit": True,
            "observation_id": row["observation_id"],
            "method": method,
            "method_version": method_version,
            "model": row.get("model"),
            "created_at": str(row.get("created_at") or ""),
            "source_hash": digest,
            "invalidation": "source_hash_mismatch_or_owner_correction",
        }
        return payload
    except Exception:  # noqa: BLE001
        return None


def save_observation(
    *,
    person_id: str | None,
    method: str,
    evidence_ids: list[str],
    payload: dict[str, Any],
    model: str | None = None,
    confidence: str | None = "medium",
    uncertainty: str | None = None,
    method_version: str = METHOD_VERSION,
) -> str | None:
    ids = [str(x) for x in evidence_ids if str(x).strip()]
    if not ids:
        return None
    digest = source_hash(ids)
    oid = str(uuid4())
    body = dict(payload)
    body["provenance"] = {
        "method": method,
        "method_version": method_version,
        "model": model or "deterministic",
        "source_evidence_ids": ids,
        "timestamp": _now(),
        "confidence": confidence,
        "uncertainty": uncertainty,
        "invalidation": "recompute when source_hash changes or owner corrects identity/facts",
    }
    try:
        from memorybox.db import connection
        from psycopg.types.json import Json

        with connection() as conn:
            conn.execute(
                """
                INSERT INTO semantic_observations (
                    observation_id, person_id, method, method_version, model,
                    source_evidence_ids, source_hash, payload, confidence, uncertainty
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (observation_id) DO NOTHING
                """,
                (
                    oid,
                    person_id,
                    method,
                    method_version,
                    model or "deterministic",
                    ids,
                    digest,
                    Json(body),
                    confidence,
                    uncertainty,
                ),
            )
        return oid
    except Exception:  # noqa: BLE001
        return None
