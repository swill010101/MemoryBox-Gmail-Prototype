"""Durable Place / Event / correlation_link store (P2-I10)."""
from __future__ import annotations

import json
from memorybox.db import connection


def _as_id(value: Any) -> str:
    return str(value)


def upsert_place(display_name: str, *, aliases: list[str] | None = None) -> dict[str, Any]:
    name = (display_name or "").strip()
    if not name:
        raise ValueError("place display_name required")
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id::text AS id, display_name, status, aliases_json, attributes_json
            FROM places
            WHERE lower(display_name) = lower(%s) AND status <> 'removed'
            LIMIT 1
            """,
            (name,),
        ).fetchone()
        if row:
            if aliases:
                merged = list(row.get("aliases_json") or [])
                for a in aliases:
                    if a and a not in merged:
                        merged.append(a)
                conn.execute(
                    """
                    UPDATE places
                    SET aliases_json = %s::jsonb, updated_at = now()
                    WHERE id = %s::uuid
                    """,
                    (json.dumps(merged), row["id"]),
                )
                row = dict(row)
                row["aliases_json"] = merged
            return dict(row)
        row = conn.execute(
            """
            INSERT INTO places (display_name, aliases_json)
            VALUES (%s, %s::jsonb)
            RETURNING id::text AS id, display_name, status, aliases_json, attributes_json
            """,
            (name, json.dumps(aliases or [])),
        ).fetchone()
    return dict(row)


def get_place(place_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id::text AS id, display_name, status, aliases_json, attributes_json
            FROM places WHERE id = %s::uuid
            """,
            (place_id,),
        ).fetchone()
    return dict(row) if row else None


def upsert_event(
    display_name: str,
    *,
    event_kind: str = "theme",
    start_date: str | None = None,
    end_date: str | None = None,
    place_id: str | None = None,
) -> dict[str, Any]:
    name = (display_name or "").strip()
    kind = (event_kind or "theme").strip().lower()
    if kind not in {"event", "trip", "theme"}:
        raise ValueError("event_kind must be event|trip|theme")
    if not name:
        raise ValueError("event display_name required")
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id::text AS id, event_kind, display_name, start_date, end_date,
                   place_id::text AS place_id, status, attributes_json
            FROM correlatable_events
            WHERE lower(display_name) = lower(%s)
              AND event_kind = %s
              AND status <> 'removed'
            LIMIT 1
            """,
            (name, kind),
        ).fetchone()
        if row:
            return dict(row)
        row = conn.execute(
            """
            INSERT INTO correlatable_events (
                event_kind, display_name, start_date, end_date, place_id
            )
            VALUES (%s, %s, %s::date, %s::date, %s::uuid)
            RETURNING id::text AS id, event_kind, display_name, start_date, end_date,
                      place_id::text AS place_id, status, attributes_json
            """,
            (kind, name, start_date, end_date, place_id),
        ).fetchone()
    return dict(row)


def get_event(event_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id::text AS id, event_kind, display_name, start_date, end_date,
                   place_id::text AS place_id, status, attributes_json
            FROM correlatable_events WHERE id = %s::uuid
            """,
            (event_id,),
        ).fetchone()
    return dict(row) if row else None


def upsert_link(
    *,
    subject_type: str,
    subject_id: str,
    object_type: str,
    object_id: str,
    predicate: str,
    evidence_id: str | None = None,
    authority: str = "system",
    status: str = "candidate",
    observed_date: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    st = (subject_type or "").strip()
    sid = (subject_id or "").strip()
    ot = (object_type or "").strip()
    oid = (object_id or "").strip()
    pred = (predicate or "about").strip()
    auth = (authority or "system").strip()
    stat = (status or "candidate").strip()
    if not (st and sid and ot and oid and pred):
        raise ValueError("correlation link requires subject, object, predicate")
    if stat not in {"candidate", "confirmed", "rejected", "superseded"}:
        raise ValueError("invalid link status")
    with connection() as conn:
        existing = conn.execute(
            """
            SELECT id::text AS id, status, authority, observed_date, provenance_json
            FROM correlation_links
            WHERE subject_type = %s AND subject_id = %s
              AND object_type = %s AND object_id = %s::uuid
              AND predicate = %s
              AND status <> 'superseded'
            LIMIT 1
            """,
            (st, sid, ot, oid, pred),
        ).fetchone()
        if existing:
            # GRAPH-03: never restore a rejected assignment from the same evidence.
            if str(existing["status"]) == "rejected":
                return {"ok": True, "id": existing["id"], "status": "rejected", "restored": False}
            if str(existing["status"]) == "confirmed" and stat == "candidate":
                return {"ok": True, "id": existing["id"], "status": "confirmed", "restored": False}
            conn.execute(
                """
                UPDATE correlation_links
                SET status = %s, authority = %s, observed_date = COALESCE(%s::date, observed_date),
                    evidence_id = COALESCE(%s::uuid, evidence_id),
                    provenance_json = %s::jsonb, updated_at = now()
                WHERE id = %s::uuid
                """,
                (
                    stat,
                    auth,
                    observed_date,
                    evidence_id,
                    json.dumps(provenance or {}),
                    existing["id"],
                ),
            )
            return {"ok": True, "id": existing["id"], "status": stat, "updated": True}
        row = conn.execute(
            """
            INSERT INTO correlation_links (
                subject_type, subject_id, object_type, object_id, predicate,
                evidence_id, authority, status, observed_date, provenance_json
            )
            VALUES (%s, %s, %s, %s::uuid, %s, %s::uuid, %s, %s, %s::date, %s::jsonb)
            RETURNING id::text AS id, status
            """,
            (
                st,
                sid,
                ot,
                oid,
                pred,
                evidence_id,
                auth,
                stat,
                observed_date,
                json.dumps(provenance or {}),
            ),
        ).fetchone()
    return {"ok": True, "id": row["id"], "status": row["status"], "created": True}


def _set_link_status(link_id: str, status: str, *, actor: str = "owner") -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute(
            """
            UPDATE correlation_links
            SET status = %s, authority = %s, updated_at = now(),
                provenance_json = COALESCE(provenance_json, '{}'::jsonb)
                    || jsonb_build_object('last_actor', %s::text, 'last_status', %s::text)
            WHERE id = %s::uuid
            RETURNING id::text AS id, status, subject_type, subject_id,
                      object_type, object_id::text AS object_id, predicate
            """,
            (status, actor, actor, status, link_id),
        ).fetchone()
    if not row:
        raise ValueError(f"correlation link not found: {link_id}")
    return dict(row)


def confirm_link(link_id: str, *, actor: str = "owner") -> dict[str, Any]:
    return _set_link_status(link_id, "confirmed", actor=actor)


def reject_link(link_id: str, *, actor: str = "owner") -> dict[str, Any]:
    return _set_link_status(link_id, "rejected", actor=actor)


def list_links(
    *,
    object_type: str | None = None,
    object_id: str | None = None,
    subject_type: str | None = None,
    subject_id: str | None = None,
    statuses: tuple[str, ...] = ("candidate", "confirmed"),
    limit: int = 500,
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    args: list[Any] = []
    if object_type and object_id:
        clauses.append("object_type = %s AND object_id = %s::uuid")
        args.extend([object_type, object_id])
    if subject_type and subject_id:
        clauses.append("subject_type = %s AND subject_id = %s")
        args.extend([subject_type, subject_id])
    if statuses:
        clauses.append("status = ANY(%s)")
        args.append(list(statuses))
    args.append(int(limit))
    sql = f"""
        SELECT id::text AS id, subject_type, subject_id, object_type,
               object_id::text AS object_id, predicate, evidence_id::text AS evidence_id,
               authority, status, observed_date::text AS observed_date, provenance_json
        FROM correlation_links
        WHERE {' AND '.join(clauses)}
        ORDER BY updated_at DESC
        LIMIT %s
    """
    with connection() as conn:
        rows = conn.execute(sql, tuple(args)).fetchall()
    return [dict(r) for r in rows]


def rejected_subject_keys(object_type: str, object_id: str) -> set[tuple[str, str]]:
    rows = list_links(
        object_type=object_type,
        object_id=object_id,
        statuses=("rejected",),
        limit=2000,
    )
    return {(str(r["subject_type"]), str(r["subject_id"])) for r in rows}


def date_conflicts(event_id: str) -> list[dict[str, Any]]:
    """EVS-167: show disagreeing observed_dates; do not elect a winner."""
    rows = list_links(
        object_type="event",
        object_id=event_id,
        statuses=("candidate", "confirmed"),
        limit=2000,
    )
    by_date: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        d = str(r.get("observed_date") or "").strip()
        if not d:
            continue
        by_date.setdefault(d, []).append(r)
    if len(by_date) < 2:
        return []
    return [
        {"observed_date": d, "count": len(items), "link_ids": [i["id"] for i in items]}
        for d, items in sorted(by_date.items())
    ]
