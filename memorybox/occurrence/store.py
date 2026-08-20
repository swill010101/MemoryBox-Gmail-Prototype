"""Durable Occurrence + membership SoT. Place is linked, never an Occurrence kind."""
from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from memorybox.db import connection
from memorybox.ingest.store import sanitize_pg, strip_pg_nuls

_WS = re.compile(r"\s+")

MEMBER_STATUSES = frozenset({"candidate", "owner_confirmed", "rejected", "withdrawn"})
OCC_KINDS = frozenset({"event", "trip"})
BLOCKING = frozenset({"rejected", "withdrawn"})


def normalize_label(label: str) -> str:
    s = _WS.sub(" ", strip_pg_nuls(label or "").strip().lower())
    if s.startswith("trip:"):
        s = s[5:].strip()
    return s


def evidence_key(kind: str, ref: dict[str, Any]) -> str:
    if kind == "spoken_moment":
        mid = str(ref.get("spoken_moment_id") or "").strip()
        if mid:
            return f"spoken:{mid}"
        vid = str(ref.get("video_external_id") or "")
        return f"spoken:{vid}:{ref.get('t_start')}:{ref.get('t_end')}"
    if kind == "face_range":
        aid = str(ref.get("appearance_moment_id") or "").strip()
        if aid:
            return f"face:{aid}"
        vid = str(ref.get("video_external_id") or "")
        return f"face:{vid}:{ref.get('start_sec')}:{ref.get('end_sec')}"
    if kind == "photo":
        return f"photo:{ref.get('provider_key') or 'immich'}:{ref.get('external_id')}"
    if kind in ("email", "sms", "calendar", "communication"):
        eid = str(ref.get("evidence_id") or "")
        return f"evidence:{eid}"
    if kind == "artifact":
        return f"artifact:{ref.get('artifact_id')}"
    if kind == "story":
        return f"story:{ref.get('story_id')}"
    return f"{kind}:{json.dumps(ref, sort_keys=True, default=str)}"


def _row(r: Any) -> dict[str, Any]:
    d = dict(r)
    for k, v in list(d.items()):
        if isinstance(v, UUID):
            d[k] = str(v)
        elif hasattr(v, "isoformat") and k in (
            "time_start",
            "time_end",
            "created_at",
            "updated_at",
        ):
            d[k] = v.isoformat()
    ref = d.get("evidence_ref")
    if isinstance(ref, str):
        d["evidence_ref"] = json.loads(ref)
    prov = d.get("provenance_json")
    if isinstance(prov, str):
        d["provenance_json"] = json.loads(prov)
    return d


def upsert_occurrence(
    *,
    kind: str,
    label: str,
    time_start: str | None = None,
    time_end: str | None = None,
    status: str = "candidate",
    actor_key: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if kind not in OCC_KINDS:
        raise ValueError("Occurrence kind must be event or trip (Place is an anchor)")
    if status not in MEMBER_STATUSES:
        raise ValueError(f"bad occurrence status {status}")
    norm = normalize_label(label)
    if not norm:
        raise ValueError("occurrence label required")
    display = strip_pg_nuls(label or "").strip()
    if display.lower().startswith("trip:"):
        display = display[5:].strip()
    with connection() as conn:
        existing = conn.execute(
            """
            SELECT * FROM occurrences
            WHERE kind = %s AND normalized_label = %s
              AND status NOT IN ('rejected', 'withdrawn')
            LIMIT 1
            """,
            (kind, norm),
        ).fetchone()
        if existing:
            row = _row(existing)
            patch: list[str] = []
            args: list[Any] = []
            if time_start and not row.get("time_start"):
                patch.append("time_start = %s::timestamptz")
                args.append(time_start)
            if time_end and not row.get("time_end"):
                patch.append("time_end = %s::timestamptz")
                args.append(time_end)
            if status == "owner_confirmed" and row.get("status") != "owner_confirmed":
                patch.append("status = %s")
                args.append(status)
                patch.append("actor_key = %s")
                args.append(actor_key or "owner")
            if patch:
                patch.append("updated_at = now()")
                args.append(row["id"])
                conn.execute(
                    f"UPDATE occurrences SET {', '.join(patch)} WHERE id = %s::uuid",
                    args,
                )
                fresh = conn.execute(
                    "SELECT * FROM occurrences WHERE id = %s::uuid", (row["id"],)
                ).fetchone()
                return _row(fresh)
            return row
        ins = conn.execute(
            """
            INSERT INTO occurrences (
                kind, label, normalized_label, time_start, time_end,
                status, actor_key, provenance_json
            ) VALUES (
                %s, %s, %s, %s::timestamptz, %s::timestamptz, %s, %s, %s::jsonb
            )
            RETURNING *
            """,
            (
                kind,
                display,
                norm,
                time_start,
                time_end,
                status,
                actor_key,
                json.dumps(sanitize_pg(provenance or {})),
            ),
        ).fetchone()
        return _row(ins)


def get_occurrence(occurrence_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM occurrences WHERE id = %s::uuid", (occurrence_id,)
        ).fetchone()
    return _row(row) if row else None


def find_occurrence(*, kind: str, label: str) -> dict[str, Any] | None:
    norm = normalize_label(label)
    with connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM occurrences
            WHERE kind = %s AND normalized_label = %s
              AND status NOT IN ('rejected', 'withdrawn')
            LIMIT 1
            """,
            (kind, norm),
        ).fetchone()
    return _row(row) if row else None


def link_place(
    occurrence_id: str,
    place_label: str,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    place_ref: dict[str, Any] | None = None,
) -> None:
    label = strip_pg_nuls(place_label or "").strip()
    if not label:
        return
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO occurrence_places (
                occurrence_id, place_label, place_key, latitude, longitude, place_ref
            ) VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (occurrence_id, place_key) DO NOTHING
            """,
            (
                occurrence_id,
                label,
                label.lower(),
                latitude,
                longitude,
                json.dumps(sanitize_pg(place_ref or {})),
            ),
        )


def list_places(occurrence_id: str) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM occurrence_places
            WHERE occurrence_id = %s::uuid
            ORDER BY place_label
            """,
            (occurrence_id,),
        ).fetchall()
    return [_row(r) for r in rows]


def _history(
    conn: Any,
    *,
    membership_id: str,
    occurrence_id: str,
    prior: str | None,
    new: str,
    actor_key: str | None,
    reason: str | None,
    join_method: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO occurrence_membership_history (
            membership_id, occurrence_id, prior_status, new_status,
            actor_key, reason, join_method
        ) VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s)
        """,
        (membership_id, occurrence_id, prior, new, actor_key, reason, join_method),
    )


def upsert_membership(
    *,
    occurrence_id: str,
    evidence_kind: str,
    evidence_ref: dict[str, Any],
    join_method: str,
    status: str = "candidate",
    confidence: float | None = None,
    actor_key: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in MEMBER_STATUSES:
        raise ValueError(f"bad membership status {status}")
    if status == "owner_confirmed" and join_method == "model_proposal":
        raise ValueError("a model proposal alone must not owner-confirm membership")
    kind = str(evidence_kind or "").strip()
    ref = dict(evidence_ref or {})
    if kind == "spoken_moment":
        if ref.get("t_start") is None or ref.get("t_end") is None:
            raise ValueError("spoken_moment membership must retain t_start and t_end")
    key = evidence_key(kind, ref)
    with connection() as conn:
        existing = conn.execute(
            """
            SELECT * FROM occurrence_memberships
            WHERE occurrence_id = %s::uuid AND evidence_kind = %s AND evidence_key = %s
            LIMIT 1
            """,
            (occurrence_id, kind, key),
        ).fetchone()
        if existing:
            row = _row(existing)
            prior = str(row.get("status") or "")
            if prior in BLOCKING and status in ("candidate", "owner_confirmed"):
                return row
            if prior == "owner_confirmed" and status == "candidate":
                return row
            if prior == status and prior != "owner_confirmed":
                return row
            conn.execute(
                """
                UPDATE occurrence_memberships
                SET status = %s, join_method = %s, confidence = %s,
                    actor_key = COALESCE(%s, actor_key),
                    evidence_ref = %s::jsonb,
                    provenance_json = COALESCE(provenance_json, '{}'::jsonb)
                        || %s::jsonb,
                    updated_at = now()
                WHERE id = %s::uuid
                """,
                (
                    status,
                    join_method,
                    confidence,
                    actor_key,
                    json.dumps(sanitize_pg(ref)),
                    json.dumps(sanitize_pg(provenance or {})),
                    row["id"],
                ),
            )
            _history(
                conn,
                membership_id=row["id"],
                occurrence_id=occurrence_id,
                prior=prior,
                new=status,
                actor_key=actor_key,
                reason="upsert",
                join_method=join_method,
            )
            fresh = conn.execute(
                "SELECT * FROM occurrence_memberships WHERE id = %s::uuid",
                (row["id"],),
            ).fetchone()
            return _row(fresh)
        ins = conn.execute(
            """
            INSERT INTO occurrence_memberships (
                occurrence_id, evidence_kind, evidence_key, evidence_ref,
                join_method, confidence, status, actor_key, provenance_json
            ) VALUES (
                %s::uuid, %s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb
            )
            RETURNING *
            """,
            (
                occurrence_id,
                kind,
                key,
                json.dumps(sanitize_pg(ref)),
                join_method,
                confidence,
                status,
                actor_key,
                json.dumps(sanitize_pg(provenance or {})),
            ),
        ).fetchone()
        row = _row(ins)
        _history(
            conn,
            membership_id=row["id"],
            occurrence_id=occurrence_id,
            prior=None,
            new=status,
            actor_key=actor_key,
            reason="insert",
            join_method=join_method,
        )
        return row


def list_memberships(
    occurrence_id: str,
    *,
    include_rejected: bool = False,
) -> list[dict[str, Any]]:
    sql = """
        SELECT * FROM occurrence_memberships
        WHERE occurrence_id = %s::uuid
    """
    if not include_rejected:
        sql += " AND status NOT IN ('rejected', 'withdrawn')"
    sql += " ORDER BY created_at"
    with connection() as conn:
        rows = conn.execute(sql, (occurrence_id,)).fetchall()
    return [_row(r) for r in rows]


def get_membership(membership_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM occurrence_memberships WHERE id = %s::uuid",
            (membership_id,),
        ).fetchone()
    return _row(row) if row else None


def set_membership_status(
    membership_id: str,
    status: str,
    *,
    actor_key: str = "owner",
    reason: str | None = None,
) -> dict[str, Any]:
    if status not in MEMBER_STATUSES:
        raise ValueError(f"bad membership status {status}")
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM occurrence_memberships WHERE id = %s::uuid",
            (membership_id,),
        ).fetchone()
        if not row:
            raise KeyError(membership_id)
        prior = str(row["status"])
        conn.execute(
            """
            UPDATE occurrence_memberships
            SET status = %s, actor_key = %s, updated_at = now()
            WHERE id = %s::uuid
            """,
            (status, actor_key, membership_id),
        )
        _history(
            conn,
            membership_id=membership_id,
            occurrence_id=str(row["occurrence_id"]),
            prior=prior,
            new=status,
            actor_key=actor_key,
            reason=reason,
            join_method=str(row.get("join_method") or ""),
        )
        fresh = conn.execute(
            "SELECT * FROM occurrence_memberships WHERE id = %s::uuid",
            (membership_id,),
        ).fetchone()
        return _row(fresh)


def membership_keys(occurrence_id: str, *, include_rejected: bool = True) -> set[str]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT evidence_kind, evidence_key, status
            FROM occurrence_memberships
            WHERE occurrence_id = %s::uuid
            """,
            (occurrence_id,),
        ).fetchall()
    out: set[str] = set()
    for r in rows:
        if not include_rejected and str(r["status"]) in BLOCKING:
            continue
        out.add(f"{r['evidence_kind']}|{r['evidence_key']}")
    return out


def rejected_keys(occurrence_id: str) -> set[str]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT evidence_kind, evidence_key
            FROM occurrence_memberships
            WHERE occurrence_id = %s::uuid
              AND status IN ('rejected', 'withdrawn')
            """,
            (occurrence_id,),
        ).fetchall()
    return {f"{r['evidence_kind']}|{r['evidence_key']}" for r in rows}
