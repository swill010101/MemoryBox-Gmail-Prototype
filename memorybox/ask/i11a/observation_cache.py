"""Reusable derived semantic observations with provenance and invalidation."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

METHOD_VERSION = "i11a_obs_v2"
EXTRACT_METHOD = "observation_extract"
# Bump when the extract prompt, normalizer, or episode window rules change.
EXTRACT_VERSION = "i11a_extract_v3|episode_v1"

_MEM: dict[tuple[str, str, str, str], dict[str, Any]] = {}


def source_hash(evidence_ids: list[str]) -> str:
    ids = sorted({str(x) for x in evidence_ids if str(x).strip()})
    return hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()[:40]


def unit_source_hash(unit: dict[str, Any] | None) -> str:
    """Fingerprint evidence identity plus authored content (not IDs alone)."""
    if not isinstance(unit, dict):
        return source_hash([])
    parts: list[str] = []
    msgs = unit.get("messages") if isinstance(unit.get("messages"), list) else []
    if msgs:
        for m in msgs:
            if not isinstance(m, dict):
                continue
            parts.append(
                "|".join(
                    [
                        str(m.get("evidence_id") or "").strip(),
                        str(m.get("time") or "").strip(),
                        str(m.get("sender") or "").strip(),
                        str(m.get("text") or "").strip(),
                    ]
                )
            )
    else:
        eids = [
            str(x).strip()
            for x in list(unit.get("source_evidence_ids") or [])
            + list(unit.get("extra_ids") or [])
            + [str(unit.get("evidence_id") or "")]
            if str(x).strip()
        ]
        parts.append("|".join(sorted(set(eids))))
        parts.append(str(unit.get("content") or unit.get("authored_text") or "").strip())
        parts.append(str(unit.get("time") or "").strip())
    blob = "\n".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:40]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mem_key(
    *,
    person_id: str | None,
    method: str,
    method_version: str,
    digest: str,
) -> tuple[str, str, str, str]:
    return (str(person_id or ""), method, method_version, digest)


def clear_memory_cache() -> None:
    _MEM.clear()


def cache_stats() -> dict[str, int]:
    return {"memory_entries": len(_MEM)}


def _deterministic_id(
    *,
    person_id: str | None,
    method: str,
    method_version: str,
    digest: str,
) -> str:
    raw = f"{method}|{method_version}|{digest}|{person_id or ''}"
    return "sob-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def load_observation(
    *,
    person_id: str | None,
    method: str,
    evidence_ids: list[str],
    method_version: str = METHOD_VERSION,
    source_digest: str | None = None,
) -> dict[str, Any] | None:
    digest = source_digest or (source_hash(evidence_ids) if evidence_ids else "")
    if not digest:
        return None
    mem = _MEM.get(_mem_key(person_id=person_id, method=method, method_version=method_version, digest=digest))
    if isinstance(mem, dict) and mem.get("payload"):
        payload = dict(mem["payload"])
        payload["_cache"] = {
            "hit": True,
            "observation_id": mem.get("observation_id"),
            "method": method,
            "method_version": method_version,
            "source_hash": digest,
            "store": "memory",
            "invalidation": "source_fingerprint_mismatch_or_owner_correction",
        }
        return payload
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
            "store": "db",
            "invalidation": "source_fingerprint_mismatch_or_owner_correction",
        }
        _MEM[_mem_key(person_id=person_id, method=method, method_version=method_version, digest=digest)] = {
            "payload": {k: v for k, v in payload.items() if k != "_cache"},
            "observation_id": row["observation_id"],
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
    source_digest: str | None = None,
) -> str | None:
    ids = [str(x) for x in evidence_ids if str(x).strip()]
    digest = source_digest or (source_hash(ids) if ids else "")
    if not digest:
        return None
    oid = _deterministic_id(
        person_id=person_id, method=method, method_version=method_version, digest=digest
    )
    body = dict(payload)
    body.pop("_cache", None)
    body["provenance"] = {
        "method": method,
        "method_version": method_version,
        "model": model or "deterministic",
        "source_evidence_ids": ids,
        "timestamp": _now(),
        "confidence": confidence,
        "uncertainty": uncertainty,
        "invalidation": "recompute when source fingerprint changes or owner corrects identity/facts",
    }
    _MEM[_mem_key(person_id=person_id, method=method, method_version=method_version, digest=digest)] = {
        "payload": body,
        "observation_id": oid,
    }
    try:
        from memorybox.db import connection
        from psycopg.types.json import Json

        with connection() as conn:
            conn.execute(
                """
                INSERT INTO semantic_observations (
                    observation_id, person_id, method, method_version, model,
                    source_evidence_ids, source_hash, payload, confidence, uncertainty,
                    invalidated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                ON CONFLICT (observation_id) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    source_evidence_ids = EXCLUDED.source_evidence_ids,
                    source_hash = EXCLUDED.source_hash,
                    model = EXCLUDED.model,
                    confidence = EXCLUDED.confidence,
                    uncertainty = EXCLUDED.uncertainty,
                    invalidated_at = NULL
                """,
                (
                    oid,
                    person_id,
                    method,
                    method_version,
                    model or "deterministic",
                    ids or [],
                    digest,
                    Json(body),
                    confidence,
                    uncertainty,
                ),
            )
    except Exception:  # noqa: BLE001
        pass
    return oid


def load_episode_observations(unit: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    """Return cached validated observations for an extract unit, or None on miss."""
    if not isinstance(unit, dict):
        return None
    digest = unit_source_hash(unit)
    hit = load_observation(
        person_id=None,
        method=EXTRACT_METHOD,
        evidence_ids=[],
        method_version=EXTRACT_VERSION,
        source_digest=digest,
    )
    if not isinstance(hit, dict):
        return None
    rows = hit.get("observations")
    if not isinstance(rows, list):
        if hit.get("text") and hit.get("supporting_evidence_ids"):
            rows = [hit]
        else:
            rows = []
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            item = dict(row)
            item["_cache"] = hit.get("_cache")
            out.append(item)
    return out


def save_episode_observations(
    unit: dict[str, Any],
    observations: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> str | None:
    """Persist only the validated observation list for this episode fingerprint."""
    digest = unit_source_hash(unit)
    eids: list[str] = []
    for extra in list(unit.get("source_evidence_ids") or []) + list(unit.get("extra_ids") or []):
        s = str(extra or "").strip()
        if s and s not in eids:
            eids.append(s)
    if unit.get("evidence_id"):
        s = str(unit.get("evidence_id"))
        if s not in eids:
            eids.append(s)
    clean: list[dict[str, Any]] = []
    for row in observations:
        if not isinstance(row, dict):
            continue
        item = {k: v for k, v in row.items() if k != "_cache"}
        clean.append(item)
    return save_observation(
        person_id=None,
        method=EXTRACT_METHOD,
        evidence_ids=eids,
        payload={"observations": clean, "unit_id": unit.get("unit_id")},
        model=model or "observation_extract",
        method_version=EXTRACT_VERSION,
        source_digest=digest,
    )


def invalidate_extract_cache(*, method_version: str | None = None) -> int:
    """Mark derived extract observations stale so the next Ask rebuilds them."""
    version = method_version or EXTRACT_VERSION
    n_mem = 0
    for key in list(_MEM):
        if key[1] == EXTRACT_METHOD and (version is None or key[2] == version):
            _MEM.pop(key, None)
            n_mem += 1
    n_db = 0
    try:
        from memorybox.db import connection

        with connection() as conn:
            cur = conn.execute(
                """
                UPDATE semantic_observations
                SET invalidated_at = now()
                WHERE method = %s
                  AND method_version = %s
                  AND invalidated_at IS NULL
                """,
                (EXTRACT_METHOD, version),
            )
            n_db = int(getattr(cur, "rowcount", 0) or 0)
    except Exception:  # noqa: BLE001
        n_db = 0
    return n_mem + n_db
