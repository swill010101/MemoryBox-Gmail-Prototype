"""Exemplar persist + pragmatic diversity selector (cap, dups, date buckets)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from memorybox.db import connection
from memorybox.person.face_evidence import upsert_face_evidence
from memorybox.recognition.constants import MAX_EXEMPLARS, NEAR_DUP_COSINE
from memorybox.recognition.embeddings import cosine


def _year(capture_at: Any) -> int:
    if capture_at is None:
        return 0
    if isinstance(capture_at, datetime):
        return int(capture_at.year)
    s = str(capture_at)
    try:
        return int(s[:4])
    except ValueError:
        return 0


def select_exemplars(
    candidates: list[dict[str, Any]],
    *,
    cap: int = MAX_EXEMPLARS,
) -> list[dict[str, Any]]:
    """Reject unusable, drop near-dups, favor year/pose diversity, cap the set."""
    usable = [c for c in candidates if c.get("usable", True) and c.get("embedding")]
    usable.sort(key=lambda c: (_year(c.get("capture_at")), str(c.get("pose") or ""), str(c.get("id") or "")))
    selected: list[dict[str, Any]] = []
    seen_years: set[int] = set()
    # Pass 1: one per year when possible
    for c in usable:
        if len(selected) >= cap:
            break
        y = _year(c.get("capture_at"))
        if y and y in seen_years:
            continue
        if _is_near_dup(c, selected):
            continue
        selected.append(c)
        if y:
            seen_years.add(y)
    # Pass 2: fill remaining with pose diversity then leftovers
    poses_have = {str(c.get("pose") or "") for c in selected}
    for c in usable:
        if len(selected) >= cap:
            break
        if c in selected:
            continue
        pose = str(c.get("pose") or "")
        if pose and pose in poses_have:
            continue
        if _is_near_dup(c, selected):
            continue
        selected.append(c)
        if pose:
            poses_have.add(pose)
    for c in usable:
        if len(selected) >= cap:
            break
        if c in selected:
            continue
        if _is_near_dup(c, selected):
            continue
        selected.append(c)
    return selected


def _is_near_dup(cand: dict[str, Any], selected: list[dict[str, Any]]) -> bool:
    emb = cand.get("embedding") or []
    for s in selected:
        if cosine(emb, s.get("embedding") or []) >= NEAR_DUP_COSINE:
            return True
    return False


def persist_exemplar(
    *,
    person_id: str | UUID,
    source_type: str,
    provider_key: str,
    method: str,
    authority: str,
    confirmation_state: str,
    embedding: list[float],
    embedding_model: str,
    external_face_id: str | None = None,
    external_person_id: str | None = None,
    source_asset_id: str | None = None,
    bbox: dict[str, Any] | None = None,
    capture_at: datetime | None = None,
    quality: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    row = upsert_face_evidence(
        person_id=person_id,
        provider_key=provider_key,
        method=method,
        authority=authority,
        confirmation_state=confirmation_state,
        external_face_id=external_face_id,
        external_person_id=external_person_id,
        source_asset_id=source_asset_id,
        bbox=bbox,
        confidence=confidence,
        exemplar_meta=meta,
    )
    with connection() as conn:
        conn.execute(
            """
            UPDATE face_evidence SET
                source_type = %s,
                embedding_json = %s::jsonb,
                embedding_model = %s,
                quality_json = COALESCE(quality_json, '{}'::jsonb) || %s::jsonb,
                capture_at = COALESCE(%s, capture_at),
                withdrawn = false,
                updated_at = now()
            WHERE id = %s::uuid
            """,
            (
                source_type,
                json.dumps(embedding),
                embedding_model,
                json.dumps(quality or {}),
                capture_at,
                row["id"],
            ),
        )
    return get_exemplar(row["id"]) or row


def get_exemplar(exemplar_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        r = conn.execute(
            """
            SELECT id::text, person_id::text, provider_key, method, source_type,
                   external_face_id, external_person_id, source_asset_id,
                   bbox_json, embedding_json, embedding_model, quality_json,
                   capture_at, withdrawn, authority, confirmation_state,
                   exemplar_meta_json, created_at, updated_at
            FROM face_evidence
            WHERE id = %s::uuid
            """,
            (exemplar_id,),
        ).fetchone()
    return _ex_row(r) if r else None


def list_active_exemplars(person_id: str | UUID) -> list[dict[str, Any]]:
    try:
        with connection() as conn:
            rows = conn.execute(
                """
                SELECT id::text, person_id::text, provider_key, method, source_type,
                       external_face_id, external_person_id, source_asset_id,
                       bbox_json, embedding_json, embedding_model, quality_json,
                       capture_at, withdrawn, authority, confirmation_state,
                       exemplar_meta_json, created_at, updated_at
                FROM face_evidence
                WHERE person_id = %s::uuid
                  AND COALESCE(withdrawn, false) = false
                  AND embedding_json IS NOT NULL
                  AND jsonb_typeof(embedding_json) = 'array'
                  AND jsonb_array_length(embedding_json) > 0
                ORDER BY
                  CASE authority WHEN 'owner_confirmed' THEN 0 ELSE 1 END,
                  created_at ASC
                """,
                (str(person_id),),
            ).fetchall()
    except Exception:
        return []
    return [_ex_row(r) for r in rows]


def withdraw_exemplar(exemplar_id: str) -> None:
    with connection() as conn:
        conn.execute(
            """
            UPDATE face_evidence
            SET withdrawn = true, updated_at = now()
            WHERE id = %s::uuid
            """,
            (exemplar_id,),
        )


def _ex_row(r: Any) -> dict[str, Any]:
    d = dict(r)
    for k in ("created_at", "updated_at", "capture_at"):
        if d.get(k) is not None and hasattr(d[k], "isoformat"):
            d[k] = d[k].isoformat()
    for jk in ("bbox_json", "embedding_json", "quality_json", "exemplar_meta_json"):
        v = d.get(jk)
        if isinstance(v, str):
            try:
                d[jk] = json.loads(v)
            except json.JSONDecodeError:
                pass
    emb = d.get("embedding_json")
    if isinstance(emb, list):
        d["embedding"] = [float(x) for x in emb]
    else:
        d["embedding"] = []
    return d
