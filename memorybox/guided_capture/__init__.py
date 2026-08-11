"""Guided Capture (EF-11) — campaigns, time-driven cadence, responses, review."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from memorybox.db import connection
from memorybox.guided_capture.email_adapter import (
    FakeGuidedEmailAdapter,
    get_email_adapter,
    new_correlation_token,
    set_email_adapter,
)
from memorybox.providers.capture import build_capture_stt

CREDIBILITY_VALUES = frozenset(
    {
        "not_rated",
        "trust_strongly",
        "generally_trust",
        "uncertain",
        "doubt",
        "believe_incorrect",
    }
)

CAMPAIGN_STATUSES = frozenset(
    {"draft", "running", "paused", "stopped", "outbound_complete"}
)


class GuidedCaptureError(Exception):
    pass


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_uuid(value: str | None, *, field: str, required: bool = True) -> UUID | None:
    raw = (value or "").strip()
    if not raw:
        if required:
            raise GuidedCaptureError(f"{field} is required")
        return None
    try:
        return UUID(raw)
    except (ValueError, TypeError, AttributeError) as exc:
        raise GuidedCaptureError(f"{field} must be a UUID (got {raw!r})") from exc


def _row_json(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return v
    return v


# --- Contacts -----------------------------------------------------------------


def upsert_contact(
    *,
    display_name: str,
    email: str,
    people_id: str | None = None,
) -> dict[str, Any]:
    name = (display_name or "").strip()
    addr = (email or "").strip().lower()
    if not name:
        raise GuidedCaptureError("display_name is required")
    if not addr or "@" not in addr:
        raise GuidedCaptureError("email is required")
    pid = _parse_uuid(people_id, field="people_id", required=False)
    with connection() as conn:
        existing = conn.execute(
            """
            SELECT id FROM guided_capture_contacts
            WHERE lower(email) = lower(%s)
            ORDER BY created_at ASC LIMIT 1
            """,
            (addr,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE guided_capture_contacts
                SET display_name = %s,
                    people_id = COALESCE(%s, people_id),
                    updated_at = now()
                WHERE id = %s
                """,
                (name, pid, existing["id"]),
            )
            cid = existing["id"]
        else:
            cid = uuid4()
            conn.execute(
                """
                INSERT INTO guided_capture_contacts
                    (id, display_name, email, people_id, provenance_json)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (
                    cid,
                    name,
                    addr,
                    pid,
                    json.dumps({"source": "guided_capture", "auto_person": False}),
                ),
            )
    return get_contact(str(cid))


def get_contact(contact_id: str) -> dict[str, Any]:
    cid = _parse_uuid(contact_id, field="contact_id")
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM guided_capture_contacts WHERE id = %s", (cid,)
        ).fetchone()
    if not row:
        raise GuidedCaptureError(f"contact not found: {contact_id}")
    return {
        "id": str(row["id"]),
        "display_name": row["display_name"],
        "email": row["email"],
        "people_id": str(row["people_id"]) if row["people_id"] else None,
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def link_contact_person(contact_id: str, people_id: str | None) -> dict[str, Any]:
    """Explicit link only — never auto-mint Person from campaign email."""
    cid = _parse_uuid(contact_id, field="contact_id")
    pid = _parse_uuid(people_id, field="people_id", required=False)
    with connection() as conn:
        conn.execute(
            """
            UPDATE guided_capture_contacts
            SET people_id = %s, updated_at = now()
            WHERE id = %s
            """,
            (pid, cid),
        )
    return get_contact(str(cid))


def list_contacts(*, limit: int = 100) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM guided_capture_contacts
            ORDER BY updated_at DESC LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": str(r["id"]),
            "display_name": r["display_name"],
            "email": r["email"],
            "people_id": str(r["people_id"]) if r["people_id"] else None,
        }
        for r in rows
    ]


def respondent_options(*, limit: int = 200) -> list[dict[str, Any]]:
    """MB People (with email if on profile) + prior GC contacts for campaign picker.

    MB Person is optional — free-typed name+email always works. When an MB Person
    is chosen and has a profile email, that email is preferred.
    """
    out: list[dict[str, Any]] = []
    seen_email: set[str] = set()
    try:
        from memorybox.person import list_people
        from memorybox.profile.facts import list_contacts as list_person_contacts

        for p in list_people(limit=limit):
            pid = str(p.get("id") or "")
            name = (p.get("display_name") or "").strip() or "(unnamed)"
            email = None
            try:
                for c in list_person_contacts(pid):
                    if (c.contact_kind or "").lower() == "email" and c.value_text:
                        email = c.value_text.strip()
                        break
            except Exception:
                email = None
            key = (email or "").lower()
            out.append(
                {
                    "source": "mb_person",
                    "people_id": pid,
                    "display_name": name,
                    "email": email,
                    "label": f"{name}" + (f" · {email}" if email else " · (no email on profile)"),
                }
            )
            if key:
                seen_email.add(key)
    except Exception:
        pass
    for c in list_contacts(limit=limit):
        key = (c.get("email") or "").lower()
        if key and key in seen_email:
            continue
        out.append(
            {
                "source": "gc_contact",
                "people_id": c.get("people_id"),
                "display_name": c.get("display_name"),
                "email": c.get("email"),
                "label": f"{c.get('display_name')} · {c.get('email')} (prior campaign)",
            }
        )
        if key:
            seen_email.add(key)
    out.sort(key=lambda r: (r.get("display_name") or "").lower())
    return out


def create_campaign(
    *,
    respondent_contact_id: str,
    title: str | None = None,
    owner_person_id: str | None = None,
    cadence_seconds: int = 86400,
    start_at: datetime | str | None = None,
    timezone_name: str = "UTC",
    questions: list[str] | None = None,
) -> dict[str, Any]:
    contact_id = _parse_uuid(respondent_contact_id, field="respondent_contact_id")
    owner = _parse_uuid(owner_person_id, field="owner_person_id", required=False)
    if owner is None:
        try:
            from memorybox.profile.owner import get_owner_person_id

            oid = get_owner_person_id()
            if oid:
                owner = UUID(oid)
        except Exception:
            owner = None
    if cadence_seconds < 1:
        raise GuidedCaptureError("cadence_seconds must be >= 1")
    start = start_at
    if isinstance(start, str) and start.strip():
        start = datetime.fromisoformat(start.strip().replace("Z", "+00:00"))
    if start is None:
        start = _now()
    if getattr(start, "tzinfo", None) is None:
        start = start.replace(tzinfo=timezone.utc)

    campaign_id = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO guided_capture_campaigns (
                id, owner_person_id, respondent_contact_id, title, status,
                send_mode, start_at, cadence_seconds, timezone_name, provenance_json
            ) VALUES (
                %s, %s, %s, %s, 'draft', 'time_driven', %s, %s, %s, %s::jsonb
            )
            """,
            (
                campaign_id,
                owner,
                contact_id,
                (title or "").strip() or None,
                start,
                int(cadence_seconds),
                timezone_name or "UTC",
                json.dumps({"increment": "11"}),
            ),
        )
        for i, body in enumerate(questions or []):
            text = (body or "").strip()
            if not text:
                continue
            conn.execute(
                """
                INSERT INTO guided_capture_questions
                    (id, campaign_id, body_text, sort_order, status)
                VALUES (%s, %s, %s, %s, 'active')
                """,
                (uuid4(), campaign_id, text, i),
            )
    return get_campaign(str(campaign_id))


def get_campaign(campaign_id: str) -> dict[str, Any]:
    cid = _parse_uuid(campaign_id, field="campaign_id")
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM guided_capture_campaigns WHERE id = %s", (cid,)
        ).fetchone()
        if not row:
            raise GuidedCaptureError(f"campaign not found: {campaign_id}")
        contact = conn.execute(
            "SELECT * FROM guided_capture_contacts WHERE id = %s",
            (row["respondent_contact_id"],),
        ).fetchone()
        questions = conn.execute(
            """
            SELECT * FROM guided_capture_questions
            WHERE campaign_id = %s
            ORDER BY sort_order ASC, created_at ASC
            """,
            (cid,),
        ).fetchall()
        deliveries = conn.execute(
            """
            SELECT * FROM guided_capture_deliveries
            WHERE campaign_id = %s
            ORDER BY scheduled_for ASC
            """,
            (cid,),
        ).fetchall()
        new_count = conn.execute(
            """
            SELECT COUNT(*) AS n FROM guided_capture_responses
            WHERE campaign_id = %s AND review_status = 'new'
            """,
            (cid,),
        ).fetchone()["n"]
    return {
        "id": str(row["id"]),
        "owner_person_id": str(row["owner_person_id"]) if row["owner_person_id"] else None,
        "respondent_contact_id": str(row["respondent_contact_id"]),
        "respondent": {
            "id": str(contact["id"]),
            "display_name": contact["display_name"],
            "email": contact["email"],
            "people_id": str(contact["people_id"]) if contact["people_id"] else None,
        }
        if contact
        else None,
        "title": row["title"],
        "status": row["status"],
        "send_mode": row["send_mode"],
        "start_at": _iso(row["start_at"]),
        "cadence_seconds": int(row["cadence_seconds"]),
        "timezone_name": row["timezone_name"],
        "new_response_count": int(new_count),
        "questions": [_question_dict(q) for q in questions],
        "deliveries": [_delivery_dict(d) for d in deliveries],
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def _question_dict(q: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(q["id"]),
        "campaign_id": str(q["campaign_id"]),
        "body_text": q["body_text"],
        "sort_order": int(q["sort_order"]),
        "status": q["status"],
        "category": q.get("category"),
    }


def _delivery_dict(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(d["id"]),
        "campaign_id": str(d["campaign_id"]),
        "question_id": str(d["question_id"]),
        "status": d["status"],
        "scheduled_for": _iso(d["scheduled_for"]),
        "sent_at": _iso(d["sent_at"]),
        "correlation_token": d["correlation_token"],
        "outbound_message_id": d.get("outbound_message_id"),
        "fail_detail": d.get("fail_detail"),
    }


def list_campaigns(*, limit: int = 50) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*, ct.display_name AS respondent_name, ct.email AS respondent_email,
                   (SELECT COUNT(*) FROM guided_capture_responses r
                    WHERE r.campaign_id = c.id AND r.review_status = 'new') AS new_count
            FROM guided_capture_campaigns c
            JOIN guided_capture_contacts ct ON ct.id = c.respondent_contact_id
            ORDER BY c.updated_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": str(r["id"]),
            "title": r["title"],
            "status": r["status"],
            "respondent_name": r["respondent_name"],
            "respondent_email": r["respondent_email"],
            "cadence_seconds": int(r["cadence_seconds"]),
            "new_response_count": int(r["new_count"]),
            "start_at": _iso(r["start_at"]),
            "updated_at": _iso(r["updated_at"]),
        }
        for r in rows
    ]


def add_questions(campaign_id: str, bodies: list[str]) -> dict[str, Any]:
    cid = _parse_uuid(campaign_id, field="campaign_id")
    with connection() as conn:
        camp = conn.execute(
            "SELECT status FROM guided_capture_campaigns WHERE id = %s", (cid,)
        ).fetchone()
        if not camp:
            raise GuidedCaptureError("campaign not found")
        if camp["status"] in ("stopped", "outbound_complete"):
            raise GuidedCaptureError("cannot add questions after stop/outbound_complete")
        max_ord = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) AS m FROM guided_capture_questions WHERE campaign_id = %s",
            (cid,),
        ).fetchone()["m"]
        n = int(max_ord) + 1
        for body in bodies:
            text = (body or "").strip()
            if not text:
                continue
            conn.execute(
                """
                INSERT INTO guided_capture_questions
                    (id, campaign_id, body_text, sort_order, status)
                VALUES (%s, %s, %s, %s, 'active')
                """,
                (uuid4(), cid, text, n),
            )
            n += 1
        conn.execute(
            "UPDATE guided_capture_campaigns SET updated_at = now() WHERE id = %s",
            (cid,),
        )
    return get_campaign(str(cid))


def update_question(
    question_id: str,
    *,
    body_text: str | None = None,
    sort_order: int | None = None,
) -> dict[str, Any]:
    """Edit/reorder only if question has no sent delivery and no response."""
    qid = _parse_uuid(question_id, field="question_id")
    with connection() as conn:
        q = conn.execute(
            "SELECT * FROM guided_capture_questions WHERE id = %s", (qid,)
        ).fetchone()
        if not q:
            raise GuidedCaptureError("question not found")
        sent = conn.execute(
            """
            SELECT 1 FROM guided_capture_deliveries
            WHERE question_id = %s AND status = 'sent' LIMIT 1
            """,
            (qid,),
        ).fetchone()
        answered = conn.execute(
            "SELECT 1 FROM guided_capture_responses WHERE question_id = %s LIMIT 1",
            (qid,),
        ).fetchone()
        if sent or answered:
            raise GuidedCaptureError(
                "cannot edit/reorder question that was already sent or answered"
            )
        if body_text is not None:
            text = body_text.strip()
            if not text:
                raise GuidedCaptureError("body_text required")
            conn.execute(
                "UPDATE guided_capture_questions SET body_text = %s, updated_at = now() WHERE id = %s",
                (text, qid),
            )
        if sort_order is not None:
            conn.execute(
                "UPDATE guided_capture_questions SET sort_order = %s, updated_at = now() WHERE id = %s",
                (int(sort_order), qid),
            )
        camp_id = q["campaign_id"]
    return get_campaign(str(camp_id))


def starter_questions(*, limit: int = 12) -> list[str]:
    path = Path(__file__).resolve().parents[2] / "config" / "mem_questions.json"
    if not path.is_file():
        return [
            "What is your earliest childhood memory?",
            "Who influenced you most growing up, and why?",
            "What family tradition means the most to you?",
        ]
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for q in data.get("questions") or []:
        text = (q.get("text") or "").strip()
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


# --- Lifecycle: start / pause / resume / stop / skip --------------------------


def _active_unsent_questions(conn: Any, campaign_id: UUID) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT q.* FROM guided_capture_questions q
        WHERE q.campaign_id = %s AND q.status = 'active'
          AND NOT EXISTS (
            SELECT 1 FROM guided_capture_deliveries d
            WHERE d.question_id = q.id AND d.status IN ('sent', 'pending')
          )
        ORDER BY q.sort_order ASC, q.created_at ASC
        """,
        (campaign_id,),
    ).fetchall()
    return list(rows)


def _schedule_delivery(
    conn: Any,
    *,
    campaign_id: UUID,
    question: dict[str, Any],
    contact_id: UUID,
    scheduled_for: datetime,
) -> UUID:
    did = uuid4()
    token = new_correlation_token()
    conn.execute(
        """
        INSERT INTO guided_capture_deliveries (
            id, campaign_id, question_id, respondent_contact_id,
            channel, scheduled_for, status, correlation_token, provenance_json
        ) VALUES (%s, %s, %s, %s, 'email', %s, 'pending', %s, %s::jsonb)
        """,
        (
            did,
            campaign_id,
            question["id"],
            contact_id,
            scheduled_for,
            token,
            json.dumps({"send_mode": "time_driven"}),
        ),
    )
    return did


def _maybe_outbound_complete(conn: Any, campaign_id: UUID) -> None:
    remaining = conn.execute(
        """
        SELECT COUNT(*) AS n FROM guided_capture_questions q
        WHERE q.campaign_id = %s AND q.status = 'active'
          AND NOT EXISTS (
            SELECT 1 FROM guided_capture_deliveries d
            WHERE d.question_id = q.id AND d.status = 'sent'
          )
        """,
        (campaign_id,),
    ).fetchone()["n"]
    pending = conn.execute(
        """
        SELECT COUNT(*) AS n FROM guided_capture_deliveries
        WHERE campaign_id = %s AND status = 'pending'
        """,
        (campaign_id,),
    ).fetchone()["n"]
    if int(remaining) == 0 and int(pending) == 0:
        camp = conn.execute(
            "SELECT status FROM guided_capture_campaigns WHERE id = %s",
            (campaign_id,),
        ).fetchone()
        if camp and camp["status"] == "running":
            conn.execute(
                """
                UPDATE guided_capture_campaigns
                SET status = 'outbound_complete', updated_at = now()
                WHERE id = %s
                """,
                (campaign_id,),
            )


def start_campaign(
    campaign_id: str,
    *,
    now: datetime | None = None,
    auto_tick: bool = True,
) -> dict[str, Any]:
    cid = _parse_uuid(campaign_id, field="campaign_id")
    now = now or _now()
    with connection() as conn:
        camp = conn.execute(
            "SELECT * FROM guided_capture_campaigns WHERE id = %s", (cid,)
        ).fetchone()
        if not camp:
            raise GuidedCaptureError("campaign not found")
        if camp["status"] not in ("draft", "paused"):
            raise GuidedCaptureError(f"cannot start from status={camp['status']}")
        qcount = conn.execute(
            """
            SELECT COUNT(*) AS n FROM guided_capture_questions
            WHERE campaign_id = %s AND status = 'active'
            """,
            (cid,),
        ).fetchone()["n"]
        if int(qcount) < 1:
            raise GuidedCaptureError("campaign needs at least one active question")
        # Schedule first unsent if none pending
        pending = conn.execute(
            """
            SELECT COUNT(*) AS n FROM guided_capture_deliveries
            WHERE campaign_id = %s AND status = 'pending'
            """,
            (cid,),
        ).fetchone()["n"]
        if int(pending) == 0:
            unsent = _active_unsent_questions(conn, cid)
            if unsent:
                start = camp["start_at"] or now
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                when = start if start > now else now
                _schedule_delivery(
                    conn,
                    campaign_id=cid,
                    question=unsent[0],
                    contact_id=camp["respondent_contact_id"],
                    scheduled_for=when,
                )
        conn.execute(
            """
            UPDATE guided_capture_campaigns
            SET status = 'running', updated_at = now()
            WHERE id = %s
            """,
            (cid,),
        )
    # Attempt immediate due sends (owner start expects Q1 out; harness may disable)
    if auto_tick:
        tick_scheduler(now=now)
    return get_campaign(str(cid))


def pause_campaign(campaign_id: str) -> dict[str, Any]:
    cid = _parse_uuid(campaign_id, field="campaign_id")
    with connection() as conn:
        camp = conn.execute(
            "SELECT status FROM guided_capture_campaigns WHERE id = %s", (cid,)
        ).fetchone()
        if not camp or camp["status"] != "running":
            raise GuidedCaptureError("only running campaigns can pause")
        conn.execute(
            """
            UPDATE guided_capture_campaigns
            SET status = 'paused', updated_at = now() WHERE id = %s
            """,
            (cid,),
        )
    return get_campaign(str(cid))


def resume_campaign(campaign_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    return start_campaign(campaign_id, now=now)


def stop_campaign(campaign_id: str) -> dict[str, Any]:
    cid = _parse_uuid(campaign_id, field="campaign_id")
    with connection() as conn:
        camp = conn.execute(
            "SELECT status FROM guided_capture_campaigns WHERE id = %s", (cid,)
        ).fetchone()
        if not camp:
            raise GuidedCaptureError("campaign not found")
        conn.execute(
            """
            UPDATE guided_capture_deliveries
            SET status = 'cancelled', updated_at = now()
            WHERE campaign_id = %s AND status = 'pending'
            """,
            (cid,),
        )
        conn.execute(
            """
            UPDATE guided_capture_campaigns
            SET status = 'stopped', updated_at = now() WHERE id = %s
            """,
            (cid,),
        )
    return get_campaign(str(cid))


def skip_question(question_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Skip unsent question; preserve row; advance cadence to next active."""
    qid = _parse_uuid(question_id, field="question_id")
    now = now or _now()
    with connection() as conn:
        q = conn.execute(
            "SELECT * FROM guided_capture_questions WHERE id = %s", (qid,)
        ).fetchone()
        if not q:
            raise GuidedCaptureError("question not found")
        sent = conn.execute(
            """
            SELECT 1 FROM guided_capture_deliveries
            WHERE question_id = %s AND status = 'sent' LIMIT 1
            """,
            (qid,),
        ).fetchone()
        if sent:
            raise GuidedCaptureError("cannot skip a question that was already sent")
        conn.execute(
            """
            UPDATE guided_capture_questions
            SET status = 'skipped', updated_at = now() WHERE id = %s
            """,
            (qid,),
        )
        conn.execute(
            """
            UPDATE guided_capture_deliveries
            SET status = 'cancelled', updated_at = now()
            WHERE question_id = %s AND status = 'pending'
            """,
            (qid,),
        )
        camp = conn.execute(
            "SELECT * FROM guided_capture_campaigns WHERE id = %s",
            (q["campaign_id"],),
        ).fetchone()
        if camp and camp["status"] == "running":
            # Schedule next active if no pending
            pending = conn.execute(
                """
                SELECT COUNT(*) AS n FROM guided_capture_deliveries
                WHERE campaign_id = %s AND status = 'pending'
                """,
                (camp["id"],),
            ).fetchone()["n"]
            if int(pending) == 0:
                unsent = _active_unsent_questions(conn, camp["id"])
                if unsent:
                    _schedule_delivery(
                        conn,
                        campaign_id=camp["id"],
                        question=unsent[0],
                        contact_id=camp["respondent_contact_id"],
                        scheduled_for=now,
                    )
                else:
                    _maybe_outbound_complete(conn, camp["id"])
            else:
                _maybe_outbound_complete(conn, camp["id"])
        camp_id = q["campaign_id"]
    tick_scheduler(now=now)
    return get_campaign(str(camp_id))


# --- Scheduler / send ---------------------------------------------------------


def tick_scheduler(*, now: datetime | None = None, adapter: Any | None = None) -> dict[str, Any]:
    """Send due pending deliveries for running campaigns; schedule next on success."""
    now = now or _now()
    adapter = adapter or get_email_adapter()
    sent_ids: list[str] = []
    failed_ids: list[str] = []
    with connection() as conn:
        due = conn.execute(
            """
            SELECT d.*, c.cadence_seconds, c.title AS campaign_title,
                   c.status AS campaign_status,
                   ct.display_name AS respondent_name, ct.email AS respondent_email,
                   q.body_text AS question_body
            FROM guided_capture_deliveries d
            JOIN guided_capture_campaigns c ON c.id = d.campaign_id
            JOIN guided_capture_contacts ct ON ct.id = d.respondent_contact_id
            JOIN guided_capture_questions q ON q.id = d.question_id
            WHERE d.status = 'pending'
              AND d.scheduled_for <= %s
              AND c.status = 'running'
            ORDER BY d.scheduled_for ASC
            """,
            (now,),
        ).fetchall()

    for d in due:
        result = adapter.send_question(
            to_email=d["respondent_email"],
            respondent_name=d["respondent_name"],
            question_body=d["question_body"],
            correlation_token=d["correlation_token"],
            campaign_title=d["campaign_title"],
        )
        with connection() as conn:
            if not result.ok:
                conn.execute(
                    """
                    UPDATE guided_capture_deliveries
                    SET status = 'failed', fail_detail = %s, updated_at = now()
                    WHERE id = %s
                    """,
                    (result.fail_detail or "send_failed", d["id"]),
                )
                failed_ids.append(str(d["id"]))
                continue
            sent_at = now
            conn.execute(
                """
                UPDATE guided_capture_deliveries
                SET status = 'sent', sent_at = %s,
                    outbound_message_id = %s, thread_id = %s,
                    preserved_raw_uri = %s, fail_detail = NULL, updated_at = now()
                WHERE id = %s
                """,
                (
                    sent_at,
                    result.outbound_message_id,
                    result.thread_id,
                    result.preserved_raw_uri,
                    d["id"],
                ),
            )
            sent_ids.append(str(d["id"]))
            # Schedule next active regardless of response — time-driven
            cadence = timedelta(seconds=int(d["cadence_seconds"]))
            next_at = sent_at + cadence
            unsent = _active_unsent_questions(conn, d["campaign_id"])
            # exclude current question (now has sent delivery)
            unsent = [u for u in unsent if str(u["id"]) != str(d["question_id"])]
            pending_others = conn.execute(
                """
                SELECT COUNT(*) AS n FROM guided_capture_deliveries
                WHERE campaign_id = %s AND status = 'pending' AND id <> %s
                """,
                (d["campaign_id"], d["id"]),
            ).fetchone()["n"]
            if unsent and int(pending_others) == 0:
                _schedule_delivery(
                    conn,
                    campaign_id=d["campaign_id"],
                    question=unsent[0],
                    contact_id=d["respondent_contact_id"],
                    scheduled_for=next_at,
                )
            _maybe_outbound_complete(conn, d["campaign_id"])

    return {"ok": True, "sent": sent_ids, "failed": failed_ids, "at": _iso(now)}


def retry_delivery(delivery_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    did = _parse_uuid(delivery_id, field="delivery_id")
    now = now or _now()
    with connection() as conn:
        d = conn.execute(
            "SELECT * FROM guided_capture_deliveries WHERE id = %s", (did,)
        ).fetchone()
        if not d:
            raise GuidedCaptureError("delivery not found")
        if d["status"] != "failed":
            raise GuidedCaptureError("only failed deliveries can retry")
        conn.execute(
            """
            UPDATE guided_capture_deliveries
            SET status = 'pending', scheduled_for = %s,
                fail_detail = NULL, updated_at = now()
            WHERE id = %s
            """,
            (now, did),
        )
        camp_id = d["campaign_id"]
    tick_scheduler(now=now)
    return get_campaign(str(camp_id))


# --- Inbound / responses ------------------------------------------------------


def _preserve_audio(data: bytes, *, filename: str | None = None) -> tuple[str, str]:
    """Preserve via I5A Capture/STT provider; return (audio_uri, audio_id)."""
    stt = build_capture_stt()
    handle = stt.preserve_audio(data, filename=filename or "voice.webm")
    return handle.audio_uri, handle.audio_id


def record_inbound_response(
    *,
    campaign_id: str,
    question_id: str,
    delivery_id: str | None = None,
    channel: str = "email_text",
    extracted_text: str | None = None,
    inbound_message_id: str | None = None,
    preserved_raw_uri: str | None = None,
    audio_bytes: bytes | None = None,
    audio_filename: str | None = None,
    run_stt: bool = True,
    force_stt_fail: bool = False,
) -> dict[str, Any]:
    cid = _parse_uuid(campaign_id, field="campaign_id")
    qid = _parse_uuid(question_id, field="question_id")
    did = _parse_uuid(delivery_id, field="delivery_id", required=False)
    if channel not in ("email_text", "voice", "other"):
        raise GuidedCaptureError(f"invalid channel: {channel}")

    # Idempotent on inbound_message_id
    if inbound_message_id:
        with connection() as conn:
            existing = conn.execute(
                """
                SELECT id FROM guided_capture_responses
                WHERE inbound_message_id = %s
                """,
                (inbound_message_id,),
            ).fetchone()
            if existing:
                return get_response(str(existing["id"]))

    with connection() as conn:
        camp = conn.execute(
            "SELECT * FROM guided_capture_campaigns WHERE id = %s", (cid,)
        ).fetchone()
        if not camp:
            raise GuidedCaptureError("campaign not found")
        # Late replies OK after outbound_complete / stopped
        q = conn.execute(
            "SELECT * FROM guided_capture_questions WHERE id = %s AND campaign_id = %s",
            (qid, cid),
        ).fetchone()
        if not q:
            raise GuidedCaptureError("question not in campaign")
        respondent_contact_id = camp["respondent_contact_id"]

    audio_uri = None
    transcript_text = None
    transcript_versions: list[dict[str, Any]] = []
    stt_status = "none"
    text = (extracted_text or "").strip() or None

    if audio_bytes:
        channel = "voice"
        try:
            audio_uri, audio_id = _preserve_audio(audio_bytes, filename=audio_filename)
            if force_stt_fail:
                stt_status = "failed"
            elif run_stt:
                stt = build_capture_stt()
                draft = stt.transcribe(audio_id)
                transcript_text = draft.text
                stt_status = "ok"
                transcript_versions.append(
                    {
                        "version": 1,
                        "text": transcript_text,
                        "source": "stt",
                        "provider_key": draft.provider_key,
                        "at": _iso(_now()),
                    }
                )
            else:
                stt_status = "pending"
        except Exception as exc:  # noqa: BLE001
            stt_status = "failed"
            if audio_uri is None:
                # last-resort preserve
                root = Path(
                    os.environ.get(
                        "MEMORYBOX_GC_AUDIO_DIR",
                        str(Path.cwd() / ".memorybox_gc_audio"),
                    )
                )
                root.mkdir(parents=True, exist_ok=True)
                p = root / f"{uuid4()}.bin"
                p.write_bytes(audio_bytes)
                audio_uri = p.resolve().as_uri()
            provenance_fail = str(exc)
        else:
            provenance_fail = None
    else:
        provenance_fail = None

    rid = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO guided_capture_responses (
                id, campaign_id, question_id, delivery_id, respondent_contact_id,
                channel, received_at, review_status, credibility,
                inbound_message_id, preserved_raw_uri, audio_uri,
                extracted_text, transcript_text, transcript_versions, stt_status,
                provenance_json
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, now(), 'new', 'not_rated',
                %s, %s, %s,
                %s, %s, %s::jsonb, %s,
                %s::jsonb
            )
            """,
            (
                rid,
                cid,
                qid,
                did,
                respondent_contact_id,
                channel,
                inbound_message_id,
                preserved_raw_uri,
                audio_uri,
                text,
                transcript_text,
                json.dumps(transcript_versions),
                stt_status,
                json.dumps(
                    {
                        "increment": "11",
                        "stt_error": provenance_fail,
                        "testimony_immutable": True,
                    }
                ),
            ),
        )
        conn.execute(
            "UPDATE guided_capture_campaigns SET updated_at = now() WHERE id = %s",
            (cid,),
        )
    return get_response(str(rid))


def poll_and_ingest(*, adapter: Any | None = None) -> dict[str, Any]:
    """Poll email adapter; correlate by token; quarantine ambiguous."""
    adapter = adapter or get_email_adapter()
    items = adapter.poll_inbound()
    created: list[str] = []
    quarantined: list[dict[str, Any]] = []
    duplicates: list[str] = []
    for item in items:
        if item.ambiguous or not item.correlation_token:
            quarantined.append(
                {
                    "inbound_message_id": item.inbound_message_id,
                    "subject": item.subject,
                    "reason": "ambiguous_correlation",
                }
            )
            adapter.mark_processed(item.inbound_message_id)
            continue
        with connection() as conn:
            existing = None
            if item.inbound_message_id:
                existing = conn.execute(
                    """
                    SELECT id FROM guided_capture_responses
                    WHERE inbound_message_id = %s
                    """,
                    (item.inbound_message_id,),
                ).fetchone()
            if existing:
                duplicates.append(str(existing["id"]))
                adapter.mark_processed(item.inbound_message_id)
                continue
            d = conn.execute(
                """
                SELECT * FROM guided_capture_deliveries
                WHERE correlation_token = %s
                """,
                (item.correlation_token.lower(),),
            ).fetchone()
            if not d:
                quarantined.append(
                    {
                        "inbound_message_id": item.inbound_message_id,
                        "token": item.correlation_token,
                        "reason": "unknown_token",
                    }
                )
                adapter.mark_processed(item.inbound_message_id)
                continue
            camp_id = str(d["campaign_id"])
            q_id = str(d["question_id"])
            did = str(d["id"])
        channel = "voice" if item.has_audio else "email_text"
        resp = record_inbound_response(
            campaign_id=camp_id,
            question_id=q_id,
            delivery_id=did,
            channel=channel,
            extracted_text=item.extracted_text,
            inbound_message_id=item.inbound_message_id,
            preserved_raw_uri=item.preserved_raw_uri,
            audio_bytes=item.audio_bytes,
            audio_filename=item.audio_filename,
        )
        created.append(resp["id"])
        adapter.mark_processed(item.inbound_message_id)
    return {
        "ok": True,
        "created": created,
        "quarantined": quarantined,
        "duplicates": duplicates,
    }


def get_response(response_id: str) -> dict[str, Any]:
    rid = _parse_uuid(response_id, field="response_id")
    with connection() as conn:
        r = conn.execute(
            "SELECT * FROM guided_capture_responses WHERE id = %s", (rid,)
        ).fetchone()
        if not r:
            raise GuidedCaptureError("response not found")
        q = conn.execute(
            "SELECT body_text FROM guided_capture_questions WHERE id = %s",
            (r["question_id"],),
        ).fetchone()
        ct = conn.execute(
            "SELECT display_name, email, people_id FROM guided_capture_contacts WHERE id = %s",
            (r["respondent_contact_id"],),
        ).fetchone()
        camp = conn.execute(
            "SELECT title, status FROM guided_capture_campaigns WHERE id = %s",
            (r["campaign_id"],),
        ).fetchone()
    testimony = r["extracted_text"] or r["transcript_text"] or ""
    return {
        "id": str(r["id"]),
        "campaign_id": str(r["campaign_id"]),
        "campaign_title": camp["title"] if camp else None,
        "campaign_status": camp["status"] if camp else None,
        "question_id": str(r["question_id"]),
        "question_body": q["body_text"] if q else None,
        "delivery_id": str(r["delivery_id"]) if r["delivery_id"] else None,
        "respondent_contact_id": str(r["respondent_contact_id"]),
        "respondent_name": ct["display_name"] if ct else None,
        "respondent_email": ct["email"] if ct else None,
        "respondent_people_id": str(ct["people_id"]) if ct and ct["people_id"] else None,
        "channel": r["channel"],
        "received_at": _iso(r["received_at"]),
        "review_status": r["review_status"],
        "credibility": r["credibility"],
        "credibility_set_at": _iso(r["credibility_set_at"]),
        "credibility_set_by": r["credibility_set_by"],
        "credibility_history": _row_json(r["credibility_history"]) or [],
        "extracted_text": r["extracted_text"],
        "transcript_text": r["transcript_text"],
        "transcript_versions": _row_json(r["transcript_versions"]) or [],
        "stt_status": r["stt_status"],
        "audio_uri": r["audio_uri"],
        "preserved_raw_uri": r["preserved_raw_uri"],
        "inbound_message_id": r["inbound_message_id"],
        "testimony_text": testimony,
        "resulting_knowledge_json": _row_json(r["resulting_knowledge_json"]) or [],
        "provenance_json": _row_json(r["provenance_json"]) or {},
    }


def list_responses(
    *,
    review_status: str | None = None,
    campaign_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if review_status:
        clauses.append("r.review_status = %s")
        params.append(review_status)
    if campaign_id:
        clauses.append("r.campaign_id = %s")
        params.append(_parse_uuid(campaign_id, field="campaign_id"))
    params.append(limit)
    where = " AND ".join(clauses)
    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT r.id FROM guided_capture_responses r
            WHERE {where}
            ORDER BY r.received_at DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
    return [get_response(str(r["id"])) for r in rows]


def new_response_count() -> int:
    with connection() as conn:
        n = conn.execute(
            """
            SELECT COUNT(*) AS n FROM guided_capture_responses
            WHERE review_status = 'new'
            """
        ).fetchone()["n"]
    return int(n)


def set_credibility(
    response_id: str,
    credibility: str,
    *,
    actor_key: str = "owner",
) -> dict[str, Any]:
    if credibility not in CREDIBILITY_VALUES:
        raise GuidedCaptureError(f"invalid credibility: {credibility}")
    rid = _parse_uuid(response_id, field="response_id")
    with connection() as conn:
        r = conn.execute(
            "SELECT credibility, credibility_history, extracted_text, transcript_text FROM guided_capture_responses WHERE id = %s",
            (rid,),
        ).fetchone()
        if not r:
            raise GuidedCaptureError("response not found")
        history = _row_json(r["credibility_history"]) or []
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "from": r["credibility"],
                "to": credibility,
                "by": actor_key,
                "at": _iso(_now()),
            }
        )
        # Never rewrite testimony when setting credibility
        conn.execute(
            """
            UPDATE guided_capture_responses
            SET credibility = %s,
                credibility_set_at = now(),
                credibility_set_by = %s,
                credibility_history = %s::jsonb,
                updated_at = now()
            WHERE id = %s
              AND extracted_text IS NOT DISTINCT FROM %s
              AND transcript_text IS NOT DISTINCT FROM %s
            """,
            (
                credibility,
                actor_key,
                json.dumps(history),
                rid,
                r["extracted_text"],
                r["transcript_text"],
            ),
        )
    return get_response(str(rid))


def mark_reviewed(response_id: str) -> dict[str, Any]:
    rid = _parse_uuid(response_id, field="response_id")
    with connection() as conn:
        conn.execute(
            """
            UPDATE guided_capture_responses
            SET review_status = 'reviewed', updated_at = now()
            WHERE id = %s
            """,
            (rid,),
        )
    return get_response(str(rid))


def correct_transcript(
    response_id: str,
    new_text: str,
    *,
    actor_key: str = "owner",
) -> dict[str, Any]:
    """Append transcript version; audio_uri immutable."""
    rid = _parse_uuid(response_id, field="response_id")
    text = (new_text or "").strip()
    if not text:
        raise GuidedCaptureError("transcript text required")
    with connection() as conn:
        r = conn.execute(
            "SELECT * FROM guided_capture_responses WHERE id = %s", (rid,)
        ).fetchone()
        if not r:
            raise GuidedCaptureError("response not found")
        audio_before = r["audio_uri"]
        versions = _row_json(r["transcript_versions"]) or []
        if not isinstance(versions, list):
            versions = []
        versions.append(
            {
                "version": len(versions) + 1,
                "text": text,
                "source": "owner_correction",
                "actor_key": actor_key,
                "at": _iso(_now()),
            }
        )
        conn.execute(
            """
            UPDATE guided_capture_responses
            SET transcript_text = %s,
                transcript_versions = %s::jsonb,
                updated_at = now()
            WHERE id = %s
            """,
            (text, json.dumps(versions), rid),
        )
        after = conn.execute(
            "SELECT audio_uri FROM guided_capture_responses WHERE id = %s", (rid,)
        ).fetchone()
        if after["audio_uri"] != audio_before:
            raise GuidedCaptureError("audio_uri must remain immutable")
    return get_response(str(rid))


def search_responses_for_ask(
    *,
    query: str,
    person_names: tuple[str, ...] = (),
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Direct PG search of Guided Capture Responses — citable without Story promotion."""
    q = (query or "").strip()
    tokens = [t for t in re_split_tokens(q) if len(t) > 2][:8]
    clauses = ["1=1"]
    params: list[Any] = []
    if tokens:
        like_parts = []
        for t in tokens:
            like_parts.append(
                "(COALESCE(r.extracted_text,'') ILIKE %s OR COALESCE(r.transcript_text,'') ILIKE %s "
                "OR COALESCE(q.body_text,'') ILIKE %s OR COALESCE(ct.display_name,'') ILIKE %s)"
            )
            pat = f"%{t}%"
            params.extend([pat, pat, pat, pat])
        clauses.append("(" + " OR ".join(like_parts) + ")")
    for name in person_names:
        n = (name or "").strip()
        if not n:
            continue
        clauses.append("ct.display_name ILIKE %s")
        params.append(f"%{n}%")
    params.append(limit)
    where = " AND ".join(clauses)
    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT r.id,
                   r.extracted_text, r.transcript_text, r.credibility, r.channel,
                   r.received_at, r.audio_uri, r.stt_status,
                   q.body_text AS question_body,
                   ct.display_name AS respondent_name,
                   c.title AS campaign_title
            FROM guided_capture_responses r
            JOIN guided_capture_questions q ON q.id = r.question_id
            JOIN guided_capture_contacts ct ON ct.id = r.respondent_contact_id
            JOIN guided_capture_campaigns c ON c.id = r.campaign_id
            WHERE {where}
            ORDER BY r.received_at DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
    hits: list[dict[str, Any]] = []
    for r in rows:
        testimony = (r["extracted_text"] or r["transcript_text"] or "").strip()
        if not testimony:
            continue
        hits.append(
            {
                "response_id": str(r["id"]),
                "respondent_name": r["respondent_name"],
                "question_body": r["question_body"],
                "campaign_title": r["campaign_title"],
                "channel": r["channel"],
                "credibility": r["credibility"],
                "received_at": _iso(r["received_at"]),
                "excerpt": testimony[:400],
                "stt_status": r["stt_status"],
                "audio_uri": r["audio_uri"],
                "provenance_kind": "guided_capture_response",
                "attribution": (
                    f"{r['respondent_name']} answered Guided Capture "
                    f"({r['channel']}; credibility={r['credibility']})"
                ),
            }
        )
    return hits


def re_split_tokens(q: str) -> list[str]:
    import re

    return [t for t in re.split(r"[^\w]+", q.lower()) if t]


__all__ = [
    "GuidedCaptureError",
    "CREDIBILITY_VALUES",
    "upsert_contact",
    "get_contact",
    "link_contact_person",
    "list_contacts",
    "respondent_options",
    "create_campaign",
    "get_campaign",
    "list_campaigns",
    "add_questions",
    "update_question",
    "starter_questions",
    "start_campaign",
    "pause_campaign",
    "resume_campaign",
    "stop_campaign",
    "skip_question",
    "tick_scheduler",
    "retry_delivery",
    "record_inbound_response",
    "poll_and_ingest",
    "get_response",
    "list_responses",
    "new_response_count",
    "set_credibility",
    "mark_reviewed",
    "correct_transcript",
    "search_responses_for_ask",
    "get_email_adapter",
    "set_email_adapter",
    "FakeGuidedEmailAdapter",
]
