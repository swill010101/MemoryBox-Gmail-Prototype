"""Historian Capture (P2-I12) — campaigns, deliveries, immutable capture, review."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from memorybox.db import connection
from memorybox.historian_capture.email_adapter import (
    FakeHistorianEmailAdapter,
    HC_OUTBOUND_MARKER,
    email_adapter_status,
    get_email_adapter,
    is_stop_message,
    new_correlation_token,
    set_email_adapter,
)

CAMPAIGN_STATUSES = frozenset(
    {"draft", "running", "paused", "stopped", "completed"}
)
DELIVERY_STATUSES = frozenset(
    {
        "pending",
        "sent",
        "waiting",
        "reminder_sent",
        "answered",
        "no_response",
        "exhausted",
        "failed",
        "cancelled",
    }
)
VERDICT_VALUES = frozenset({"retained", "rejected", "promotion_authorized"})
ASSESSMENT_CODES = frozenset(
    {
        "high_confidence",
        "moderate_confidence",
        "low_confidence",
        "uncertain",
    }
)
DEFAULT_FOLLOW_UP_SECONDS = 259200  # 72h

_ACTIVE_DELIVERY_STATUSES = frozenset(
    {"pending", "sent", "waiting", "reminder_sent"}
)
_TERMINAL_DELIVERY_STATUSES = frozenset(
    {"answered", "no_response", "exhausted", "cancelled", "failed"}
)

_THANK_YOU_TEMPLATE = (
    "Thank you — we received and preserved your reply. "
    "Your contribution helps preserve family history."
)
_FORBIDDEN_THANK_YOU_FRAGMENTS = (
    "high confidence",
    "moderate confidence",
    "low confidence",
    "uncertain",
    "high_confidence",
    "moderate_confidence",
    "low_confidence",
    "reject as evidence",
    "promotion_authorized",
    "rejected",
    "retained",
    "review draft",
    "owner assessment",
)


class HistorianCaptureError(Exception):
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
            raise HistorianCaptureError(f"{field} is required")
        return None
    try:
        return UUID(raw)
    except (ValueError, TypeError, AttributeError) as exc:
        raise HistorianCaptureError(f"{field} must be a UUID (got {raw!r})") from exc


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


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _next_cadence_time(
    *,
    after: datetime,
    cadence_config: dict[str, Any] | None,
    timezone_name: str = "UTC",
) -> datetime:
    """Return the next question-send instant after `after` (UTC-aware)."""
    cfg = dict(cadence_config or {})
    pattern = (cfg.get("pattern") or "weekly").strip().lower()
    if pattern == "seconds":
        interval = int(cfg.get("interval_seconds") or cfg.get("seconds") or 60)
        return after + timedelta(seconds=max(1, interval))

    tz = ZoneInfo(timezone_name or "UTC")
    local_after = after.astimezone(tz)
    send_time = str(cfg.get("send_time_local") or "09:00")
    parts = send_time.split(":")
    hour = int(parts[0]) if parts and parts[0].isdigit() else 9
    minute = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

    def at_local(d: date) -> datetime:
        return datetime(d.year, d.month, d.day, hour, minute, tzinfo=tz)

    if pattern == "daily":
        candidate = at_local(local_after.date())
        if candidate <= local_after:
            candidate = at_local(local_after.date() + timedelta(days=1))
        return candidate.astimezone(timezone.utc)

    if pattern == "weekly":
        target_wd = cfg.get("weekday")
        if target_wd is None:
            target_wd = local_after.weekday()
        else:
            target_wd = int(target_wd)
        d = local_after.date()
        days_ahead = (int(target_wd) - d.weekday()) % 7
        candidate = at_local(d + timedelta(days=days_ahead))
        if candidate <= local_after:
            candidate = at_local(d + timedelta(days=days_ahead + 7))
        return candidate.astimezone(timezone.utc)

    if pattern == "weekdays":
        allowed = {int(x) for x in (cfg.get("weekdays") or list(range(0, 5)))}
        d = local_after.date()
        for offset in range(1, 400):
            nd = d + timedelta(days=offset)
            if nd.weekday() in allowed:
                candidate = at_local(nd)
                if candidate > local_after:
                    return candidate.astimezone(timezone.utc)
        raise HistorianCaptureError("no weekday slot found in cadence_config")

    if pattern == "monthly":
        dom = int(cfg.get("day_of_month") or local_after.day)
        y, m = local_after.year, local_after.month

        def month_candidate(year: int, month: int) -> datetime | None:
            import calendar

            last = calendar.monthrange(year, month)[1]
            day = min(dom, last)
            return at_local(date(year, month, day))

        candidate = month_candidate(y, m)
        if candidate is None or candidate <= local_after:
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1
            candidate = month_candidate(y, m)
        if candidate is None:
            raise HistorianCaptureError("invalid monthly cadence")
        return candidate.astimezone(timezone.utc)

    # Default: weekly on current weekday
    return _next_cadence_time(
        after=after,
        cadence_config={"pattern": "weekly", "send_time_local": send_time},
        timezone_name=timezone_name,
    )


def _looks_like_outbound_echo(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return HC_OUTBOUND_MARKER in t and len(t) < 800


def _respondent_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "campaign_id": str(row["campaign_id"]),
        "people_id": str(row["people_id"]),
        "display_name_snapshot": row["display_name_snapshot"],
        "contact_route_kind": row["contact_route_kind"],
        "contact_route_value": row["contact_route_value"],
        "status": row["status"],
        "opted_out_at": _iso(row.get("opted_out_at")),
        "opt_out_source": row.get("opt_out_source"),
        "progress_json": _row_json(row.get("progress_json")) or {},
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


def _question_dict(q: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(q["id"]),
        "campaign_id": str(q["campaign_id"]),
        "body_text": q["body_text"],
        "sort_order": int(q["sort_order"]),
        "status": q["status"],
        "source": q.get("source") or "owner_authored",
    }


def _delivery_dict(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(d["id"]),
        "campaign_id": str(d["campaign_id"]),
        "question_id": str(d["question_id"]),
        "campaign_respondent_id": str(d["campaign_respondent_id"]),
        "status": d["status"],
        "scheduled_for": _iso(d["scheduled_for"]),
        "sent_at": _iso(d.get("sent_at")),
        "waiting_started_at": _iso(d.get("waiting_started_at")),
        "reminder_sent_at": _iso(d.get("reminder_sent_at")),
        "no_response_at": _iso(d.get("no_response_at")),
        "follow_up_deadline_at": _iso(d.get("follow_up_deadline_at")),
        "correlation_token": d["correlation_token"],
        "question_snapshot_text": d.get("question_snapshot_text"),
        "question_snapshot_hash": d.get("question_snapshot_hash"),
        "outbound_message_id": d.get("outbound_message_id"),
        "fail_detail": d.get("fail_detail"),
    }


def _latest_verdict(conn: Any, capture_item_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT * FROM historian_capture_verdicts
        WHERE capture_item_id = %s
        ORDER BY decided_at DESC, id DESC
        LIMIT 1
        """,
        (capture_item_id,),
    ).fetchone()


def _latest_assessment(conn: Any, capture_item_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT * FROM historian_capture_owner_assessments
        WHERE capture_item_id = %s
        ORDER BY set_at DESC, id DESC
        LIMIT 1
        """,
        (capture_item_id,),
    ).fetchone()


def _current_draft(conn: Any, capture_item_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT * FROM historian_capture_review_drafts
        WHERE capture_item_id = %s AND is_current = TRUE
        ORDER BY version DESC
        LIMIT 1
        """,
        (capture_item_id,),
    ).fetchone()


# --- Respondent options -----------------------------------------------------


def respondent_options(*, limit: int = 200) -> list[dict[str, Any]]:
    """MB People with profile email for campaign respondent picker."""
    out: list[dict[str, Any]] = []
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
            if not email:
                continue
            out.append(
                {
                    "source": "mb_person",
                    "people_id": pid,
                    "display_name": name,
                    "email": email,
                    "label": f"{name} · {email}",
                }
            )
    except Exception:
        pass
    out.sort(key=lambda r: (r.get("display_name") or "").lower())
    return out


# --- Campaign CRUD ------------------------------------------------------------


def create_campaign(
    *,
    title: str | None = None,
    owner_person_id: str | None = None,
    cadence_config_json: dict[str, Any] | None = None,
    follow_up_interval_seconds: int = DEFAULT_FOLLOW_UP_SECONDS,
    send_thank_you_ack: bool = True,
    timezone_name: str = "UTC",
    respondents: list[dict[str, Any]] | None = None,
    questions: list[str] | None = None,
) -> dict[str, Any]:
    owner = _parse_uuid(owner_person_id, field="owner_person_id", required=False)
    if owner is None:
        try:
            from memorybox.profile.owner import get_owner_person_id

            oid = get_owner_person_id()
            if oid:
                owner = UUID(oid)
        except Exception:
            owner = None
    if follow_up_interval_seconds < 1:
        raise HistorianCaptureError("follow_up_interval_seconds must be >= 1")
    cadence = cadence_config_json or {
        "pattern": "weekly",
        "send_time_local": "09:00",
    }
    campaign_id = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO historian_capture_campaigns (
                id, owner_person_id, title, status,
                cadence_config_json, follow_up_interval_seconds,
                send_thank_you_ack, timezone_name, provenance_json
            ) VALUES (
                %s, %s, %s, 'draft', %s::jsonb, %s, %s, %s, %s::jsonb
            )
            """,
            (
                campaign_id,
                owner,
                (title or "").strip() or None,
                json.dumps(cadence),
                int(follow_up_interval_seconds),
                bool(send_thank_you_ack),
                timezone_name or "UTC",
                json.dumps({"increment": "12"}),
            ),
        )
        for body in questions or []:
            text = (body or "").strip()
            if text:
                _insert_question(conn, campaign_id, text, sort_order=None)
        for resp in respondents or []:
            _add_respondent_row(
                conn,
                campaign_id=campaign_id,
                people_id=str(resp.get("people_id") or ""),
                contact_route_value=str(
                    resp.get("contact_route_value") or resp.get("email") or ""
                ),
                display_name_snapshot=resp.get("display_name_snapshot")
                or resp.get("display_name"),
            )
    return get_campaign(str(campaign_id))


def _insert_question(
    conn: Any,
    campaign_id: UUID,
    body_text: str,
    *,
    sort_order: int | None,
) -> UUID:
    if sort_order is None:
        max_ord = conn.execute(
            """
            SELECT COALESCE(MAX(sort_order), -1) AS m
            FROM historian_capture_questions WHERE campaign_id = %s
            """,
            (campaign_id,),
        ).fetchone()["m"]
        sort_order = int(max_ord) + 1
    qid = uuid4()
    conn.execute(
        """
        INSERT INTO historian_capture_questions
            (id, campaign_id, body_text, sort_order, status, source)
        VALUES (%s, %s, %s, %s, 'active', 'owner_authored')
        """,
        (qid, campaign_id, body_text, int(sort_order)),
    )
    return qid


def _resolve_person_display(conn: Any, people_id: UUID) -> str:
    row = conn.execute(
        "SELECT display_name FROM people WHERE id = %s", (people_id,)
    ).fetchone()
    if row and row.get("display_name"):
        return str(row["display_name"]).strip()
    return "(unnamed)"


def _add_respondent_row(
    conn: Any,
    *,
    campaign_id: UUID,
    people_id: str,
    contact_route_value: str,
    display_name_snapshot: str | None = None,
) -> UUID:
    pid = _parse_uuid(people_id, field="people_id")
    email = (contact_route_value or "").strip().lower()
    if not email or "@" not in email:
        raise HistorianCaptureError("contact_route_value (email) is required")
    name = (display_name_snapshot or "").strip() or _resolve_person_display(conn, pid)
    rid = uuid4()
    conn.execute(
        """
        INSERT INTO historian_capture_campaign_respondents (
            id, campaign_id, people_id, display_name_snapshot,
            contact_route_kind, contact_route_value, status, progress_json
        ) VALUES (%s, %s, %s, %s, 'email', %s, 'active', '{}'::jsonb)
        """,
        (rid, campaign_id, pid, name, email),
    )
    return rid


def add_respondents(
    campaign_id: str,
    respondents: list[dict[str, Any]],
) -> dict[str, Any]:
    cid = _parse_uuid(campaign_id, field="campaign_id")
    with connection() as conn:
        camp = conn.execute(
            "SELECT status FROM historian_capture_campaigns WHERE id = %s", (cid,)
        ).fetchone()
        if not camp:
            raise HistorianCaptureError("campaign not found")
        if camp["status"] not in ("draft", "paused", "running"):
            raise HistorianCaptureError(
                "cannot add respondents to stopped/completed campaign"
            )
        for resp in respondents:
            _add_respondent_row(
                conn,
                campaign_id=cid,
                people_id=str(resp.get("people_id") or ""),
                contact_route_value=str(
                    resp.get("contact_route_value") or resp.get("email") or ""
                ),
                display_name_snapshot=resp.get("display_name_snapshot")
                or resp.get("display_name"),
            )
        conn.execute(
            "UPDATE historian_capture_campaigns SET updated_at = now() WHERE id = %s",
            (cid,),
        )
    return get_campaign(str(cid))


def get_campaign(campaign_id: str) -> dict[str, Any]:
    cid = _parse_uuid(campaign_id, field="campaign_id")
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM historian_capture_campaigns WHERE id = %s", (cid,)
        ).fetchone()
        if not row:
            raise HistorianCaptureError(f"campaign not found: {campaign_id}")
        respondents = conn.execute(
            """
            SELECT * FROM historian_capture_campaign_respondents
            WHERE campaign_id = %s ORDER BY created_at ASC
            """,
            (cid,),
        ).fetchall()
        questions = conn.execute(
            """
            SELECT * FROM historian_capture_questions
            WHERE campaign_id = %s
            ORDER BY sort_order ASC, created_at ASC
            """,
            (cid,),
        ).fetchall()
        deliveries = conn.execute(
            """
            SELECT * FROM historian_capture_deliveries
            WHERE campaign_id = %s ORDER BY scheduled_for ASC
            """,
            (cid,),
        ).fetchall()
        new_count = conn.execute(
            """
            SELECT COUNT(*) AS n FROM historian_capture_items i
            WHERE i.campaign_id = %s
              AND i.match_status = 'matched'
              AND NOT EXISTS (
                SELECT 1 FROM historian_capture_verdicts v
                WHERE v.capture_item_id = i.id
              )
            """,
            (cid,),
        ).fetchone()["n"]
    return {
        "id": str(row["id"]),
        "owner_person_id": str(row["owner_person_id"])
        if row["owner_person_id"]
        else None,
        "title": row["title"],
        "status": row["status"],
        "cadence_config_json": _row_json(row["cadence_config_json"]) or {},
        "follow_up_interval_seconds": int(row["follow_up_interval_seconds"]),
        "send_thank_you_ack": bool(row["send_thank_you_ack"]),
        "timezone_name": row["timezone_name"],
        "new_capture_count": int(new_count),
        "respondents": [_respondent_dict(r) for r in respondents],
        "questions": [_question_dict(q) for q in questions],
        "deliveries": [_delivery_dict(d) for d in deliveries],
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def list_campaigns(*, limit: int = 50) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*,
                   (SELECT COUNT(*) FROM historian_capture_campaign_respondents r
                    WHERE r.campaign_id = c.id AND r.status = 'active') AS respondent_count,
                   (SELECT COUNT(*) FROM historian_capture_items i
                    WHERE i.campaign_id = c.id AND i.match_status = 'matched'
                      AND NOT EXISTS (
                        SELECT 1 FROM historian_capture_verdicts v
                        WHERE v.capture_item_id = i.id
                      )) AS new_count
            FROM historian_capture_campaigns c
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
            "respondent_count": int(r["respondent_count"]),
            "new_capture_count": int(r["new_count"]),
            "follow_up_interval_seconds": int(r["follow_up_interval_seconds"]),
            "updated_at": _iso(r["updated_at"]),
        }
        for r in rows
    ]


def add_questions(campaign_id: str, bodies: list[str]) -> dict[str, Any]:
    cid = _parse_uuid(campaign_id, field="campaign_id")
    with connection() as conn:
        camp = conn.execute(
            "SELECT status FROM historian_capture_campaigns WHERE id = %s", (cid,)
        ).fetchone()
        if not camp:
            raise HistorianCaptureError("campaign not found")
        if camp["status"] in ("stopped", "completed"):
            raise HistorianCaptureError("cannot add questions after stop/completed")
        for body in bodies:
            text = (body or "").strip()
            if text:
                _insert_question(conn, cid, text, sort_order=None)
        conn.execute(
            "UPDATE historian_capture_campaigns SET updated_at = now() WHERE id = %s",
            (cid,),
        )
    return get_campaign(str(cid))


def update_question(
    question_id: str,
    *,
    body_text: str | None = None,
    sort_order: int | None = None,
) -> dict[str, Any]:
    qid = _parse_uuid(question_id, field="question_id")
    with connection() as conn:
        q = conn.execute(
            "SELECT * FROM historian_capture_questions WHERE id = %s", (qid,)
        ).fetchone()
        if not q:
            raise HistorianCaptureError("question not found")
        sent = conn.execute(
            """
            SELECT 1 FROM historian_capture_deliveries
            WHERE question_id = %s AND sent_at IS NOT NULL LIMIT 1
            """,
            (qid,),
        ).fetchone()
        if sent:
            raise HistorianCaptureError(
                "cannot edit question that was already sent"
            )
        if body_text is not None:
            text = body_text.strip()
            if not text:
                raise HistorianCaptureError("body_text required")
            conn.execute(
                """
                UPDATE historian_capture_questions
                SET body_text = %s, updated_at = now() WHERE id = %s
                """,
                (text, qid),
            )
        if sort_order is not None:
            conn.execute(
                """
                UPDATE historian_capture_questions
                SET sort_order = %s, updated_at = now() WHERE id = %s
                """,
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


# --- Lifecycle ---------------------------------------------------------------

def _respondent_has_in_flight(conn: Any, respondent_id: UUID) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM historian_capture_deliveries
        WHERE campaign_respondent_id = %s
          AND status = ANY(%s)
        LIMIT 1
        """,
        (respondent_id, list(_ACTIVE_DELIVERY_STATUSES)),
    ).fetchone()
    return bool(row)


def _next_unsent_question(
    conn: Any, *, campaign_id: UUID, respondent_id: UUID
) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT q.* FROM historian_capture_questions q
        WHERE q.campaign_id = %s AND q.status = 'active'
          AND NOT EXISTS (
            SELECT 1 FROM historian_capture_deliveries d
            WHERE d.question_id = q.id
              AND d.campaign_respondent_id = %s
              AND d.status NOT IN ('cancelled', 'failed')
          )
        ORDER BY q.sort_order ASC, q.created_at ASC
        LIMIT 1
        """,
        (campaign_id, respondent_id),
    ).fetchone()


def _schedule_delivery(
    conn: Any,
    *,
    campaign_id: UUID,
    question: dict[str, Any],
    respondent_id: UUID,
    scheduled_for: datetime,
) -> UUID:
    did = uuid4()
    token = new_correlation_token()
    conn.execute(
        """
        INSERT INTO historian_capture_deliveries (
            id, campaign_id, question_id, campaign_respondent_id,
            channel, scheduled_for, status, correlation_token, provenance_json
        ) VALUES (%s, %s, %s, %s, 'email', %s, 'pending', %s, %s::jsonb)
        """,
        (
            did,
            campaign_id,
            question["id"],
            respondent_id,
            scheduled_for,
            token,
            json.dumps({"increment": "12"}),
        ),
    )
    return did


def _maybe_complete_campaign(conn: Any, campaign_id: UUID) -> None:
    camp = conn.execute(
        "SELECT status FROM historian_capture_campaigns WHERE id = %s",
        (campaign_id,),
    ).fetchone()
    if not camp or camp["status"] != "running":
        return
    pending = conn.execute(
        """
        SELECT COUNT(*) AS n FROM historian_capture_deliveries
        WHERE campaign_id = %s AND status = ANY(%s)
        """,
        (campaign_id, list(_ACTIVE_DELIVERY_STATUSES)),
    ).fetchone()["n"]
    if int(pending) > 0:
        return
    active_respondents = conn.execute(
        """
        SELECT id FROM historian_capture_campaign_respondents
        WHERE campaign_id = %s AND status = 'active'
        """,
        (campaign_id,),
    ).fetchall()
    for r in active_respondents:
        nxt = _next_unsent_question(
            conn, campaign_id=campaign_id, respondent_id=r["id"]
        )
        if nxt:
            return
    conn.execute(
        """
        UPDATE historian_capture_campaigns
        SET status = 'completed', updated_at = now()
        WHERE id = %s AND status = 'running'
        """,
        (campaign_id,),
    )


def _schedule_next_for_respondent(
    conn: Any,
    *,
    campaign_id: UUID,
    respondent_id: UUID,
    after: datetime,
    cadence_config: dict[str, Any],
    timezone_name: str,
) -> UUID | None:
    respondent = conn.execute(
        "SELECT status FROM historian_capture_campaign_respondents WHERE id = %s",
        (respondent_id,),
    ).fetchone()
    if not respondent or respondent["status"] != "active":
        return None
    if _respondent_has_in_flight(conn, respondent_id):
        return None
    nxt_q = _next_unsent_question(
        conn, campaign_id=campaign_id, respondent_id=respondent_id
    )
    if not nxt_q:
        return None
    when = _next_cadence_time(
        after=after,
        cadence_config=cadence_config,
        timezone_name=timezone_name,
    )
    return _schedule_delivery(
        conn,
        campaign_id=campaign_id,
        question=nxt_q,
        respondent_id=respondent_id,
        scheduled_for=when,
    )


def _bootstrap_pending_deliveries(
    conn: Any, *, campaign_id: UUID, when: datetime
) -> None:
    respondents = conn.execute(
        """
        SELECT id FROM historian_capture_campaign_respondents
        WHERE campaign_id = %s AND status = 'active'
        """,
        (campaign_id,),
    ).fetchall()
    for r in respondents:
        if _respondent_has_in_flight(conn, r["id"]):
            continue
        nxt = _next_unsent_question(
            conn, campaign_id=campaign_id, respondent_id=r["id"]
        )
        if nxt:
            _schedule_delivery(
                conn,
                campaign_id=campaign_id,
                question=nxt,
                respondent_id=r["id"],
                scheduled_for=when,
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
            "SELECT * FROM historian_capture_campaigns WHERE id = %s", (cid,)
        ).fetchone()
        if not camp:
            raise HistorianCaptureError("campaign not found")
        if camp["status"] not in ("draft", "paused"):
            raise HistorianCaptureError(f"cannot start from status={camp['status']}")
        qcount = conn.execute(
            """
            SELECT COUNT(*) AS n FROM historian_capture_questions
            WHERE campaign_id = %s AND status = 'active'
            """,
            (cid,),
        ).fetchone()["n"]
        if int(qcount) < 1:
            raise HistorianCaptureError("campaign needs at least one active question")
        rcount = conn.execute(
            """
            SELECT COUNT(*) AS n FROM historian_capture_campaign_respondents
            WHERE campaign_id = %s AND status = 'active'
            """,
            (cid,),
        ).fetchone()["n"]
        if int(rcount) < 1:
            raise HistorianCaptureError("campaign needs at least one active respondent")
        pending = conn.execute(
            """
            SELECT COUNT(*) AS n FROM historian_capture_deliveries
            WHERE campaign_id = %s AND status = 'pending'
            """,
            (cid,),
        ).fetchone()["n"]
        if int(pending) == 0:
            _bootstrap_pending_deliveries(conn, campaign_id=cid, when=now)
        conn.execute(
            """
            UPDATE historian_capture_campaigns
            SET status = 'running', updated_at = now()
            WHERE id = %s
            """,
            (cid,),
        )
    if auto_tick:
        tick_scheduler(now=now)
    return get_campaign(str(cid))


def pause_campaign(campaign_id: str) -> dict[str, Any]:
    cid = _parse_uuid(campaign_id, field="campaign_id")
    with connection() as conn:
        camp = conn.execute(
            "SELECT status FROM historian_capture_campaigns WHERE id = %s", (cid,)
        ).fetchone()
        if not camp or camp["status"] != "running":
            raise HistorianCaptureError("only running campaigns can pause")
        conn.execute(
            """
            UPDATE historian_capture_campaigns
            SET status = 'paused', updated_at = now() WHERE id = %s
            """,
            (cid,),
        )
    return get_campaign(str(cid))


def resume_campaign(
    campaign_id: str, *, now: datetime | None = None, auto_tick: bool = True
) -> dict[str, Any]:
    return start_campaign(campaign_id, now=now, auto_tick=auto_tick)


def stop_campaign(campaign_id: str) -> dict[str, Any]:
    cid = _parse_uuid(campaign_id, field="campaign_id")
    with connection() as conn:
        camp = conn.execute(
            "SELECT status FROM historian_capture_campaigns WHERE id = %s", (cid,)
        ).fetchone()
        if not camp:
            raise HistorianCaptureError("campaign not found")
        conn.execute(
            """
            UPDATE historian_capture_deliveries
            SET status = 'cancelled', updated_at = now()
            WHERE campaign_id = %s AND status = ANY(%s)
            """,
            (cid, list(_ACTIVE_DELIVERY_STATUSES)),
        )
        conn.execute(
            """
            UPDATE historian_capture_campaigns
            SET status = 'stopped', updated_at = now() WHERE id = %s
            """,
            (cid,),
        )
    return get_campaign(str(cid))


def skip_question(question_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    qid = _parse_uuid(question_id, field="question_id")
    now = now or _now()
    with connection() as conn:
        q = conn.execute(
            "SELECT * FROM historian_capture_questions WHERE id = %s", (qid,)
        ).fetchone()
        if not q:
            raise HistorianCaptureError("question not found")
        sent = conn.execute(
            """
            SELECT 1 FROM historian_capture_deliveries
            WHERE question_id = %s AND sent_at IS NOT NULL LIMIT 1
            """,
            (qid,),
        ).fetchone()
        if sent:
            raise HistorianCaptureError("cannot skip a question that was already sent")
        conn.execute(
            """
            UPDATE historian_capture_questions
            SET status = 'skipped', updated_at = now() WHERE id = %s
            """,
            (qid,),
        )
        conn.execute(
            """
            UPDATE historian_capture_deliveries
            SET status = 'cancelled', updated_at = now()
            WHERE question_id = %s AND status = 'pending'
            """,
            (qid,),
        )
        camp = conn.execute(
            "SELECT * FROM historian_capture_campaigns WHERE id = %s",
            (q["campaign_id"],),
        ).fetchone()
        if camp and camp["status"] == "running":
            cadence = _row_json(camp["cadence_config_json"]) or {}
            respondents = conn.execute(
                """
                SELECT id FROM historian_capture_campaign_respondents
                WHERE campaign_id = %s AND status = 'active'
                """,
                (camp["id"],),
            ).fetchall()
            for r in respondents:
                if not _respondent_has_in_flight(conn, r["id"]):
                    _schedule_next_for_respondent(
                        conn,
                        campaign_id=camp["id"],
                        respondent_id=r["id"],
                        after=now,
                        cadence_config=cadence,
                        timezone_name=camp["timezone_name"],
                    )
            _maybe_complete_campaign(conn, camp["id"])
        camp_id = q["campaign_id"]
    tick_scheduler(now=now)
    return get_campaign(str(camp_id))


# --- Scheduler / send --------------------------------------------------------


def _mark_delivery_answered(
    conn: Any,
    *,
    delivery_id: UUID,
    now: datetime,
) -> dict[str, Any]:
    d = conn.execute(
        "SELECT * FROM historian_capture_deliveries WHERE id = %s", (delivery_id,)
    ).fetchone()
    if not d:
        raise HistorianCaptureError("delivery not found")
    if d["status"] in _TERMINAL_DELIVERY_STATUSES:
        return d
    conn.execute(
        """
        UPDATE historian_capture_deliveries
        SET status = 'answered',
            follow_up_deadline_at = NULL,
            updated_at = now()
        WHERE id = %s
        """,
        (delivery_id,),
    )
    camp = conn.execute(
        "SELECT * FROM historian_capture_campaigns WHERE id = %s",
        (d["campaign_id"],),
    ).fetchone()
    if camp and camp["status"] == "running":
        cadence = _row_json(camp["cadence_config_json"]) or {}
        _schedule_next_for_respondent(
            conn,
            campaign_id=d["campaign_id"],
            respondent_id=d["campaign_respondent_id"],
            after=now,
            cadence_config=cadence,
            timezone_name=camp["timezone_name"],
        )
        _maybe_complete_campaign(conn, d["campaign_id"])
    return conn.execute(
        "SELECT * FROM historian_capture_deliveries WHERE id = %s", (delivery_id,)
    ).fetchone()


def _mark_delivery_no_response(
    conn: Any,
    *,
    delivery_id: UUID,
    now: datetime,
) -> None:
    d = conn.execute(
        "SELECT * FROM historian_capture_deliveries WHERE id = %s", (delivery_id,)
    ).fetchone()
    if not d or d["status"] in _TERMINAL_DELIVERY_STATUSES:
        return
    conn.execute(
        """
        UPDATE historian_capture_deliveries
        SET status = 'no_response',
            no_response_at = %s,
            follow_up_deadline_at = NULL,
            updated_at = now()
        WHERE id = %s
        """,
        (now, delivery_id),
    )
    camp = conn.execute(
        "SELECT * FROM historian_capture_campaigns WHERE id = %s",
        (d["campaign_id"],),
    ).fetchone()
    if camp and camp["status"] == "running":
        cadence = _row_json(camp["cadence_config_json"]) or {}
        _schedule_next_for_respondent(
            conn,
            campaign_id=d["campaign_id"],
            respondent_id=d["campaign_respondent_id"],
            after=now,
            cadence_config=cadence,
            timezone_name=camp["timezone_name"],
        )
        _maybe_complete_campaign(conn, d["campaign_id"])


def _process_respondent_opt_out(
    conn: Any,
    *,
    respondent_id: UUID,
    source: str,
    capture_item_id: UUID | None = None,
    inbound_message_id: str | None = None,
    keyword: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE historian_capture_campaign_respondents
        SET status = 'opted_out',
            opted_out_at = now(),
            opt_out_inbound_message_id = COALESCE(%s, opt_out_inbound_message_id),
            opt_out_source = %s,
            updated_at = now()
        WHERE id = %s AND status <> 'opted_out'
        """,
        (inbound_message_id, source, respondent_id),
    )
    conn.execute(
        """
        UPDATE historian_capture_deliveries
        SET status = 'cancelled', updated_at = now()
        WHERE campaign_respondent_id = %s AND status = ANY(%s)
        """,
        (respondent_id, list(_ACTIVE_DELIVERY_STATUSES)),
    )
    conn.execute(
        """
        INSERT INTO historian_capture_respondent_opt_outs (
            id, campaign_respondent_id, capture_item_id,
            keyword_matched, source, provenance_json
        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            uuid4(),
            respondent_id,
            capture_item_id,
            keyword,
            source,
            json.dumps(
                {
                    "inbound_message_id": inbound_message_id,
                    "keyword": keyword,
                }
            ),
        ),
    )


def tick_scheduler(
    *, now: datetime | None = None, adapter: Any | None = None
) -> dict[str, Any]:
    """Send pending deliveries; process follow-up deadlines; schedule next questions."""
    now = now or _now()
    adapter = adapter or get_email_adapter()
    sent_ids: list[str] = []
    failed_ids: list[str] = []
    reminders: list[str] = []
    no_responses: list[str] = []

    with connection() as conn:
        due_followups = conn.execute(
            """
            SELECT d.*, c.follow_up_interval_seconds, c.title AS campaign_title,
                   c.status AS campaign_status, c.timezone_name,
                   c.cadence_config_json,
                   r.display_name_snapshot AS respondent_name,
                   r.contact_route_value AS respondent_email,
                   r.status AS respondent_status,
                   COALESCE(d.question_snapshot_text, q.body_text) AS question_body
            FROM historian_capture_deliveries d
            JOIN historian_capture_campaigns c ON c.id = d.campaign_id
            JOIN historian_capture_campaign_respondents r
                ON r.id = d.campaign_respondent_id
            JOIN historian_capture_questions q ON q.id = d.question_id
            WHERE c.status = 'running'
              AND d.follow_up_deadline_at IS NOT NULL
              AND d.follow_up_deadline_at <= %s
              AND d.status = 'waiting'
            ORDER BY d.follow_up_deadline_at ASC
            """,
            (now,),
        ).fetchall()

    for d in due_followups:
        if d["respondent_status"] != "active":
            continue
        interval = timedelta(seconds=int(d["follow_up_interval_seconds"]))
        with connection() as conn:
            fresh = conn.execute(
                "SELECT * FROM historian_capture_deliveries WHERE id = %s", (d["id"],)
            ).fetchone()
            if not fresh or fresh["status"] != "waiting":
                continue
            if fresh["reminder_sent_at"] is None:
                result = adapter.send_question(
                    to_email=d["respondent_email"],
                    respondent_name=d["respondent_name"],
                    question_body=d["question_body"],
                    correlation_token=d["correlation_token"],
                    campaign_title=d["campaign_title"],
                    is_reminder=True,
                )
                if not result.ok:
                    conn.execute(
                        """
                        UPDATE historian_capture_deliveries
                        SET fail_detail = %s, retry_count = retry_count + 1,
                            updated_at = now()
                        WHERE id = %s
                        """,
                        (result.fail_detail or "reminder_send_failed", d["id"]),
                    )
                    continue
                conn.execute(
                    """
                    UPDATE historian_capture_deliveries
                    SET reminder_sent_at = %s,
                        reminder_outbound_message_id = %s,
                        follow_up_deadline_at = %s,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (now, result.outbound_message_id, now + interval, d["id"]),
                )
                reminders.append(str(d["id"]))
            else:
                _mark_delivery_no_response(conn, delivery_id=d["id"], now=now)
                no_responses.append(str(d["id"]))

    with connection() as conn:
        due = conn.execute(
            """
            SELECT d.*, c.follow_up_interval_seconds, c.title AS campaign_title,
                   c.status AS campaign_status, c.timezone_name,
                   c.cadence_config_json,
                   r.display_name_snapshot AS respondent_name,
                   r.contact_route_value AS respondent_email,
                   r.status AS respondent_status,
                   q.body_text AS question_body
            FROM historian_capture_deliveries d
            JOIN historian_capture_campaigns c ON c.id = d.campaign_id
            JOIN historian_capture_campaign_respondents r
                ON r.id = d.campaign_respondent_id
            JOIN historian_capture_questions q ON q.id = d.question_id
            WHERE d.status = 'pending'
              AND d.scheduled_for <= %s
              AND c.status = 'running'
              AND r.status = 'active'
            ORDER BY d.scheduled_for ASC
            """,
            (now,),
        ).fetchall()

    for d in due:
        if d["respondent_status"] != "active":
            continue
        snapshot = d["question_body"]
        result = adapter.send_question(
            to_email=d["respondent_email"],
            respondent_name=d["respondent_name"],
            question_body=snapshot,
            correlation_token=d["correlation_token"],
            campaign_title=d["campaign_title"],
        )
        with connection() as conn:
            if not result.ok:
                conn.execute(
                    """
                    UPDATE historian_capture_deliveries
                    SET status = 'failed', fail_detail = %s,
                        retry_count = retry_count + 1, updated_at = now()
                    WHERE id = %s
                    """,
                    (result.fail_detail or "send_failed", d["id"]),
                )
                failed_ids.append(str(d["id"]))
                continue
            interval = timedelta(seconds=int(d["follow_up_interval_seconds"]))
            snap_hash = _sha256_text(snapshot)
            conn.execute(
                """
                UPDATE historian_capture_deliveries
                SET status = 'waiting',
                    sent_at = %s,
                    waiting_started_at = %s,
                    follow_up_deadline_at = %s,
                    question_snapshot_text = %s,
                    question_snapshot_hash = %s,
                    outbound_message_id = %s,
                    thread_id = %s,
                    preserved_outbound_raw_uri = %s,
                    fail_detail = NULL,
                    updated_at = now()
                WHERE id = %s
                """,
                (
                    now,
                    now,
                    now + interval,
                    snapshot,
                    snap_hash,
                    result.outbound_message_id,
                    result.thread_id,
                    result.preserved_raw_uri,
                    d["id"],
                ),
            )
            sent_ids.append(str(d["id"]))

    return {
        "ok": True,
        "sent": sent_ids,
        "failed": failed_ids,
        "reminders": reminders,
        "no_responses": no_responses,
        "at": _iso(now),
        "email_provider": email_adapter_status(),
    }


def retry_delivery(delivery_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    did = _parse_uuid(delivery_id, field="delivery_id")
    now = now or _now()
    with connection() as conn:
        d = conn.execute(
            "SELECT * FROM historian_capture_deliveries WHERE id = %s", (did,)
        ).fetchone()
        if not d:
            raise HistorianCaptureError("delivery not found")
        if d["status"] != "failed":
            raise HistorianCaptureError("only failed deliveries can retry")
        conn.execute(
            """
            UPDATE historian_capture_deliveries
            SET status = 'pending', scheduled_for = %s,
                fail_detail = NULL, updated_at = now()
            WHERE id = %s
            """,
            (now, did),
        )
        camp_id = d["campaign_id"]
    tick_scheduler(now=now)
    return get_campaign(str(camp_id))


# --- Inbound / capture items -------------------------------------------------


def _capture_item_dict(
    row: dict[str, Any],
    *,
    conn: Any | None = None,
    include_review: bool = True,
) -> dict[str, Any]:
    item_id = row["id"]
    verdict = None
    assessment = None
    draft = None
    if include_review and conn is not None:
        verdict = _latest_verdict(conn, item_id)
        assessment = _latest_assessment(conn, item_id)
        draft = _current_draft(conn, item_id)
    return {
        "id": str(row["id"]),
        "campaign_id": str(row["campaign_id"]) if row.get("campaign_id") else None,
        "question_id": str(row["question_id"]) if row.get("question_id") else None,
        "delivery_id": str(row["delivery_id"]) if row.get("delivery_id") else None,
        "campaign_respondent_id": str(row["campaign_respondent_id"])
        if row.get("campaign_respondent_id")
        else None,
        "channel": row["channel"],
        "received_at": _iso(row.get("received_at")),
        "inbound_message_id": row.get("inbound_message_id"),
        "from_address": row.get("from_address"),
        "subject": row.get("subject"),
        "preserved_raw_uri": row.get("preserved_raw_uri"),
        "content_hash": row.get("content_hash"),
        "header_json": _row_json(row.get("header_json")) or {},
        "extracted_text": row.get("extracted_text"),
        "match_status": row.get("match_status"),
        "provenance_json": _row_json(row.get("provenance_json")) or {},
        "current_draft": (
            {
                "id": str(draft["id"]),
                "version": int(draft["version"]),
                "body_text": draft["body_text"],
                "notes_private": draft.get("notes_private"),
            }
            if draft
            else None
        ),
        "latest_verdict": (
            {
                "id": str(verdict["id"]),
                "verdict": verdict["verdict"],
                "decided_at": _iso(verdict["decided_at"]),
            }
            if verdict
            else None
        ),
        "latest_assessment": (
            {
                "id": str(assessment["id"]),
                "assessment_code": assessment["assessment_code"],
                "set_at": _iso(assessment["set_at"]),
            }
            if assessment
            else None
        ),
    }


def record_capture_item(
    *,
    campaign_id: str | None = None,
    question_id: str | None = None,
    delivery_id: str | None = None,
    campaign_respondent_id: str | None = None,
    channel: str = "email_text",
    extracted_text: str | None = None,
    inbound_message_id: str | None = None,
    from_address: str = "",
    subject: str = "",
    preserved_raw_uri: str = "",
    raw_bytes: bytes | None = None,
    header_json: dict[str, Any] | None = None,
    match_status: str = "matched",
    auto_draft: bool = True,
) -> dict[str, Any]:
    if channel not in ("email_text", "other"):
        raise HistorianCaptureError(f"invalid channel: {channel}")
    if inbound_message_id:
        with connection() as conn:
            existing = conn.execute(
                "SELECT id FROM historian_capture_items WHERE inbound_message_id = %s",
                (inbound_message_id,),
            ).fetchone()
            if existing:
                return get_capture_item(str(existing["id"]))

    content_hash = ""
    if raw_bytes is not None:
        content_hash = _sha256_bytes(raw_bytes)
    elif preserved_raw_uri or extracted_text:
        content_hash = _sha256_text(extracted_text or "")

    cid = _parse_uuid(campaign_id, field="campaign_id", required=False)
    qid = _parse_uuid(question_id, field="question_id", required=False)
    did = _parse_uuid(delivery_id, field="delivery_id", required=False)
    rid = _parse_uuid(campaign_respondent_id, field="campaign_respondent_id", required=False)
    item_id = uuid4()
    now = _now()
    with connection() as conn:
        if content_hash:
            dup = conn.execute(
                """
                SELECT id FROM historian_capture_items
                WHERE content_hash = %s AND content_hash <> ''
                LIMIT 1
                """,
                (content_hash,),
            ).fetchone()
            if dup:
                return get_capture_item(str(dup["id"]))
        conn.execute(
            """
            INSERT INTO historian_capture_items (
                id, campaign_id, question_id, delivery_id, campaign_respondent_id,
                channel, received_at, inbound_message_id, from_address, subject,
                preserved_raw_uri, content_hash, header_json, extracted_text,
                match_status, provenance_json
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s::jsonb, %s,
                %s, %s::jsonb
            )
            """,
            (
                item_id,
                cid,
                qid,
                did,
                rid,
                channel,
                now,
                inbound_message_id,
                from_address or "",
                subject or "",
                preserved_raw_uri or "",
                content_hash,
                json.dumps(header_json or {}),
                extracted_text or "",
                match_status,
                json.dumps({"increment": "12", "testimony_immutable": True}),
            ),
        )
        if did and match_status == "matched":
            _mark_delivery_answered(conn, delivery_id=did, now=now)
        if auto_draft and (extracted_text or "").strip():
            conn.execute(
                """
                INSERT INTO historian_capture_review_drafts (
                    id, capture_item_id, version, is_current, body_text,
                    created_by, supersedes_draft_id
                ) VALUES (%s, %s, 1, TRUE, %s, 'owner', NULL)
                """,
                (uuid4(), item_id, (extracted_text or "").strip()),
            )
        if cid:
            conn.execute(
                "UPDATE historian_capture_campaigns SET updated_at = now() WHERE id = %s",
                (cid,),
            )
    return get_capture_item(str(item_id))


def poll_and_ingest(*, adapter: Any | None = None) -> dict[str, Any]:
    """Poll email adapter; correlate by token; quarantine unmatched/ambiguous."""
    adapter = adapter or get_email_adapter()
    items = adapter.poll_inbound()
    created: list[str] = []
    quarantined: list[dict[str, Any]] = []
    duplicates: list[str] = []
    skipped: list[dict[str, Any]] = []
    opt_outs: list[str] = []

    known_outbound: set[str] = set()
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT outbound_message_id, reminder_outbound_message_id
            FROM historian_capture_deliveries
            WHERE outbound_message_id IS NOT NULL
               OR reminder_outbound_message_id IS NOT NULL
            """
        ).fetchall()
        for r in rows:
            if r.get("outbound_message_id"):
                known_outbound.add(str(r["outbound_message_id"]))
            if r.get("reminder_outbound_message_id"):
                known_outbound.add(str(r["reminder_outbound_message_id"]))

    for item in items:
        mid = item.inbound_message_id
        text = (item.extracted_text or "").strip()
        if mid and mid in known_outbound:
            skipped.append({"inbound_message_id": mid, "reason": "known_outbound_id"})
            adapter.mark_processed(mid)
            continue
        if _looks_like_outbound_echo(text):
            skipped.append(
                {
                    "inbound_message_id": mid,
                    "reason": "outbound_echo_body",
                    "subject": item.subject,
                }
            )
            continue
        if getattr(item, "skip_reason", None):
            skipped.append(
                {
                    "inbound_message_id": mid,
                    "reason": item.skip_reason,
                    "subject": item.subject,
                }
            )
            adapter.mark_processed(mid)
            continue

        raw_bytes = getattr(item, "raw_bytes", None)
        content_hash = _sha256_bytes(raw_bytes) if raw_bytes else _sha256_text(text)

        if item.ambiguous or not item.correlation_token:
            with connection() as conn:
                if mid:
                    existing = conn.execute(
                        "SELECT id FROM historian_capture_items WHERE inbound_message_id = %s",
                        (mid,),
                    ).fetchone()
                    if existing:
                        duplicates.append(str(existing["id"]))
                        adapter.mark_processed(mid)
                        continue
                qid = uuid4()
                conn.execute(
                    """
                    INSERT INTO historian_capture_items (
                        id, channel, received_at, inbound_message_id, from_address,
                        subject, preserved_raw_uri, content_hash, header_json,
                        extracted_text, match_status, provenance_json
                    ) VALUES (
                        %s, 'email_text', now(), %s, %s,
                        %s, %s, %s, %s::jsonb,
                        %s, %s, %s::jsonb
                    )
                    """,
                    (
                        qid,
                        mid,
                        item.from_addr,
                        item.subject,
                        item.preserved_raw_uri,
                        content_hash,
                        json.dumps(getattr(item, "raw_headers", {}) or {}),
                        text,
                        "ambiguous" if item.ambiguous else "unmatched",
                        json.dumps({"reason": "ambiguous_correlation"}),
                    ),
                )
            quarantined.append(
                {
                    "capture_item_id": str(qid),
                    "inbound_message_id": mid,
                    "subject": item.subject,
                    "reason": "ambiguous_correlation"
                    if item.ambiguous
                    else "missing_token",
                }
            )
            adapter.mark_processed(mid)
            continue

        with connection() as conn:
            if mid:
                existing = conn.execute(
                    "SELECT id FROM historian_capture_items WHERE inbound_message_id = %s",
                    (mid,),
                ).fetchone()
                if existing:
                    duplicates.append(str(existing["id"]))
                    adapter.mark_processed(mid)
                    continue
            d = conn.execute(
                """
                SELECT d.*, r.status AS respondent_status
                FROM historian_capture_deliveries d
                JOIN historian_capture_campaign_respondents r
                    ON r.id = d.campaign_respondent_id
                WHERE d.correlation_token = %s
                """,
                (item.correlation_token.lower(),),
            ).fetchone()
            if not d:
                qid = uuid4()
                conn.execute(
                    """
                    INSERT INTO historian_capture_items (
                        id, channel, received_at, inbound_message_id, from_address,
                        subject, preserved_raw_uri, content_hash, header_json,
                        extracted_text, match_status, provenance_json
                    ) VALUES (
                        %s, 'email_text', now(), %s, %s,
                        %s, %s, %s, %s::jsonb,
                        %s, 'unmatched', %s::jsonb
                    )
                    """,
                    (
                        qid,
                        mid,
                        item.from_addr,
                        item.subject,
                        item.preserved_raw_uri,
                        content_hash,
                        json.dumps(getattr(item, "raw_headers", {}) or {}),
                        text,
                        json.dumps(
                            {"token": item.correlation_token, "reason": "unknown_token"}
                        ),
                    ),
                )
                quarantined.append(
                    {
                        "capture_item_id": str(qid),
                        "inbound_message_id": mid,
                        "token": item.correlation_token,
                        "reason": "unknown_token",
                    }
                )
                adapter.mark_processed(mid)
                continue

            if is_stop_message(text):
                stop_id = uuid4()
                conn.execute(
                    """
                    INSERT INTO historian_capture_items (
                        id, campaign_id, question_id, delivery_id,
                        campaign_respondent_id, channel, received_at,
                        inbound_message_id, from_address, subject,
                        preserved_raw_uri, content_hash, header_json,
                        extracted_text, match_status, provenance_json
                    ) VALUES (
                        %s, %s, %s, %s, %s, 'email_text', now(),
                        %s, %s, %s, %s, %s, %s::jsonb, %s, 'matched', %s::jsonb
                    )
                    """,
                    (
                        stop_id,
                        d["campaign_id"],
                        d["question_id"],
                        d["id"],
                        d["campaign_respondent_id"],
                        mid,
                        item.from_addr,
                        item.subject,
                        item.preserved_raw_uri,
                        content_hash,
                        json.dumps(getattr(item, "raw_headers", {}) or {}),
                        text,
                        json.dumps({"stop": True}),
                    ),
                )
                _process_respondent_opt_out(
                    conn,
                    respondent_id=d["campaign_respondent_id"],
                    source="respondent_stop",
                    capture_item_id=stop_id,
                    inbound_message_id=mid,
                    keyword=(text.split() or ["STOP"])[0],
                )
                opt_outs.append(str(d["campaign_respondent_id"]))
                adapter.mark_processed(mid)
                continue

            camp_id = str(d["campaign_id"])
            q_id = str(d["question_id"])
            did = str(d["id"])
            resp_id = str(d["campaign_respondent_id"])

        cap = record_capture_item(
            campaign_id=camp_id,
            question_id=q_id,
            delivery_id=did,
            campaign_respondent_id=resp_id,
            channel="email_text",
            extracted_text=item.extracted_text,
            inbound_message_id=mid,
            from_address=item.from_addr,
            subject=item.subject,
            preserved_raw_uri=item.preserved_raw_uri,
            raw_bytes=raw_bytes,
            header_json=getattr(item, "raw_headers", {}) or {},
            match_status="matched",
        )
        created.append(cap["id"])
        adapter.mark_processed(mid)

    return {
        "ok": True,
        "created": created,
        "quarantined": quarantined,
        "duplicates": duplicates,
        "skipped": skipped,
        "opt_outs": opt_outs,
        "examined": len(items),
    }


def get_capture_item(capture_item_id: str) -> dict[str, Any]:
    iid = _parse_uuid(capture_item_id, field="capture_item_id")
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM historian_capture_items WHERE id = %s", (iid,)
        ).fetchone()
        if not row:
            raise HistorianCaptureError("capture item not found")
        q = None
        if row.get("question_id"):
            q = conn.execute(
                "SELECT body_text FROM historian_capture_questions WHERE id = %s",
                (row["question_id"],),
            ).fetchone()
        resp = None
        if row.get("campaign_respondent_id"):
            resp = conn.execute(
                """
                SELECT display_name_snapshot, contact_route_value, people_id, status,
                       opted_out_at, opt_out_source
                FROM historian_capture_campaign_respondents WHERE id = %s
                """,
                (row["campaign_respondent_id"],),
            ).fetchone()
        camp = None
        if row.get("campaign_id"):
            camp = conn.execute(
                "SELECT title, status FROM historian_capture_campaigns WHERE id = %s",
                (row["campaign_id"],),
            ).fetchone()
        out = _capture_item_dict(row, conn=conn)
    out["question_body"] = q["body_text"] if q else None
    out["respondent_name"] = resp["display_name_snapshot"] if resp else None
    out["respondent_email"] = resp["contact_route_value"] if resp else None
    out["respondent_people_id"] = (
        str(resp["people_id"]) if resp and resp.get("people_id") else None
    )
    out["respondent_status"] = resp["status"] if resp else None
    out["respondent_opted_out_at"] = _iso(resp.get("opted_out_at")) if resp else None
    out["respondent_opt_out_source"] = resp.get("opt_out_source") if resp else None
    out["campaign_title"] = camp["title"] if camp else None
    out["campaign_status"] = camp["status"] if camp else None
    return out


def list_capture_items(
    *,
    campaign_id: str | None = None,
    match_status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if campaign_id:
        clauses.append("campaign_id = %s")
        params.append(_parse_uuid(campaign_id, field="campaign_id"))
    if match_status:
        clauses.append("match_status = %s")
        params.append(match_status)
    params.append(limit)
    where = " AND ".join(clauses)
    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id FROM historian_capture_items
            WHERE {where}
            ORDER BY received_at DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
    return [get_capture_item(str(r["id"])) for r in rows]


def list_unmatched_items(*, limit: int = 100) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id FROM historian_capture_items
            WHERE match_status IN ('unmatched', 'ambiguous')
            ORDER BY received_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [get_capture_item(str(r["id"])) for r in rows]


def new_capture_count() -> int:
    with connection() as conn:
        n = conn.execute(
            """
            SELECT COUNT(*) AS n FROM historian_capture_items i
            WHERE i.match_status = 'matched'
              AND NOT EXISTS (
                SELECT 1 FROM historian_capture_verdicts v
                WHERE v.capture_item_id = i.id
              )
            """
        ).fetchone()["n"]
    return int(n)


# --- Review drafts -----------------------------------------------------------


def create_draft(
    capture_item_id: str,
    *,
    body_text: str | None = None,
    notes_private: str | None = None,
    proposed_links_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    iid = _parse_uuid(capture_item_id, field="capture_item_id")
    with connection() as conn:
        item = conn.execute(
            "SELECT * FROM historian_capture_items WHERE id = %s", (iid,)
        ).fetchone()
        if not item:
            raise HistorianCaptureError("capture item not found")
        current = _current_draft(conn, iid)
        if current:
            raise HistorianCaptureError("draft already exists; use update_current_draft")
        text = (body_text if body_text is not None else item.get("extracted_text") or "").strip()
        draft_id = uuid4()
        conn.execute(
            """
            INSERT INTO historian_capture_review_drafts (
                id, capture_item_id, version, is_current, body_text,
                notes_private, proposed_links_json, created_by
            ) VALUES (%s, %s, 1, TRUE, %s, %s, %s::jsonb, 'owner')
            """,
            (
                draft_id,
                iid,
                text,
                notes_private,
                json.dumps(proposed_links_json or {}),
            ),
        )
    return get_capture_item(str(iid))


def update_current_draft(
    capture_item_id: str,
    *,
    body_text: str | None = None,
    notes_private: str | None = None,
    proposed_links_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    iid = _parse_uuid(capture_item_id, field="capture_item_id")
    with connection() as conn:
        item = conn.execute(
            "SELECT * FROM historian_capture_items WHERE id = %s", (iid,)
        ).fetchone()
        if not item:
            raise HistorianCaptureError("capture item not found")
        current = _current_draft(conn, iid)
        if not current:
            raise HistorianCaptureError("no current draft; use create_draft first")
        max_ver = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS m FROM historian_capture_review_drafts WHERE capture_item_id = %s",
            (iid,),
        ).fetchone()["m"]
        new_version = int(max_ver) + 1
        new_text = (
            body_text if body_text is not None else current["body_text"]
        ).strip()
        if not new_text:
            raise HistorianCaptureError("body_text required")
        new_id = uuid4()
        conn.execute(
            "UPDATE historian_capture_review_drafts SET is_current = FALSE WHERE capture_item_id = %s",
            (iid,),
        )
        conn.execute(
            """
            INSERT INTO historian_capture_review_drafts (
                id, capture_item_id, version, is_current, body_text,
                notes_private, proposed_links_json, created_by, supersedes_draft_id
            ) VALUES (%s, %s, %s, TRUE, %s, %s, %s::jsonb, 'owner', %s)
            """,
            (
                new_id,
                iid,
                new_version,
                new_text,
                notes_private if notes_private is not None else current.get("notes_private"),
                json.dumps(
                    proposed_links_json
                    if proposed_links_json is not None
                    else (_row_json(current.get("proposed_links_json")) or {})
                ),
                current["id"],
            ),
        )
    return get_capture_item(str(iid))


# --- Assessment & verdict ----------------------------------------------------


def set_owner_assessment(
    capture_item_id: str,
    assessment_code: str,
    *,
    note_private: str | None = None,
    actor_key: str = "owner",
) -> dict[str, Any]:
    if assessment_code not in ASSESSMENT_CODES:
        raise HistorianCaptureError(f"invalid assessment_code: {assessment_code}")
    iid = _parse_uuid(capture_item_id, field="capture_item_id")
    with connection() as conn:
        item = conn.execute(
            "SELECT id FROM historian_capture_items WHERE id = %s", (iid,)
        ).fetchone()
        if not item:
            raise HistorianCaptureError("capture item not found")
        prior = _latest_assessment(conn, iid)
        aid = uuid4()
        conn.execute(
            """
            INSERT INTO historian_capture_owner_assessments (
                id, capture_item_id, assessment_code, note_private,
                set_by, supersedes_assessment_id
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                aid,
                iid,
                assessment_code,
                note_private,
                actor_key,
                prior["id"] if prior else None,
            ),
        )
    return get_capture_item(str(iid))


def set_verdict(
    capture_item_id: str,
    verdict: str,
    *,
    review_draft_id: str | None = None,
    actor_key: str = "owner",
) -> dict[str, Any]:
    if verdict not in VERDICT_VALUES:
        raise HistorianCaptureError(f"invalid verdict: {verdict}")
    iid = _parse_uuid(capture_item_id, field="capture_item_id")
    with connection() as conn:
        item = conn.execute(
            "SELECT * FROM historian_capture_items WHERE id = %s", (iid,)
        ).fetchone()
        if not item:
            raise HistorianCaptureError("capture item not found")
        draft = None
        if review_draft_id:
            draft = conn.execute(
                """
                SELECT * FROM historian_capture_review_drafts
                WHERE id = %s AND capture_item_id = %s
                """,
                (_parse_uuid(review_draft_id, field="review_draft_id"), iid),
            ).fetchone()
        else:
            draft = _current_draft(conn, iid)
        if not draft:
            raise HistorianCaptureError("review draft required for verdict")
        prior = _latest_verdict(conn, iid)
        vid = uuid4()
        conn.execute(
            """
            INSERT INTO historian_capture_verdicts (
                id, capture_item_id, review_draft_id, verdict,
                decided_by, supersedes_verdict_id
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                vid,
                iid,
                draft["id"],
                verdict,
                actor_key,
                prior["id"] if prior else None,
            ),
        )
    return get_capture_item(str(iid))


# --- Promotion & thank-you ---------------------------------------------------


def promote_to_story(
    capture_item_id: str,
    *,
    title: str | None = None,
    story_id: str | None = None,
    actor_key: str = "owner",
) -> dict[str, Any]:
    from memorybox.story import create_story

    iid = _parse_uuid(capture_item_id, field="capture_item_id")
    with connection() as conn:
        item = conn.execute(
            "SELECT * FROM historian_capture_items WHERE id = %s", (iid,)
        ).fetchone()
        if not item:
            raise HistorianCaptureError("capture item not found")
        verdict = _latest_verdict(conn, iid)
        if not verdict or verdict["verdict"] != "promotion_authorized":
            raise HistorianCaptureError(
                "promotion requires verdict=promotion_authorized"
            )
        draft = _current_draft(conn, iid)
        if not draft:
            raise HistorianCaptureError("current review draft required for promotion")
        existing_promo = conn.execute(
            """
            SELECT id FROM historian_capture_promotions
            WHERE capture_item_id = %s AND promoted_type = 'story'
            """,
            (iid,),
        ).fetchone()
        if existing_promo:
            raise HistorianCaptureError("capture item already promoted to Story")
        narrator_person_id = None
        narrator_name = None
        if item.get("campaign_respondent_id"):
            resp = conn.execute(
                "SELECT people_id, display_name_snapshot FROM historian_capture_campaign_respondents WHERE id = %s",
                (item["campaign_respondent_id"],),
            ).fetchone()
            if resp:
                narrator_person_id = str(resp["people_id"]) if resp.get("people_id") else None
                narrator_name = resp.get("display_name_snapshot")
        body = (draft["body_text"] or "").strip()
        if not body:
            raise HistorianCaptureError("review draft body required for promotion")

    story = create_story(
        title=title or "Historian testimony",
        body_text=body,
        narrator_display_name=narrator_name,
        narrator_person_id=narrator_person_id,
        actor_key=actor_key,
        story_id=story_id,
    )
    promo_id = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO historian_capture_promotions (
                id, capture_item_id, review_draft_id, verdict_id,
                promoted_type, promoted_id, promoted_by, provenance_json
            ) VALUES (%s, %s, %s, %s, 'story', %s, %s, %s::jsonb)
            """,
            (
                promo_id,
                iid,
                draft["id"],
                verdict["id"],
                UUID(str(story.id)),
                actor_key,
                json.dumps(
                    {
                        "capture_item_id": str(iid),
                        "review_draft_id": str(draft["id"]),
                        "verdict_id": str(verdict["id"]),
                    }
                ),
            ),
        )
    return {
        "promotion_id": str(promo_id),
        "promoted_type": "story",
        "promoted_id": str(story.id),
        "capture_item_id": str(iid),
        "story": {
            "story_id": str(story.id),
            "title": story.title,
        },
    }


def _read_raw_from_uri(uri: str | None) -> bytes | None:
    if not uri:
        return None
    from urllib.parse import unquote, urlparse

    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    raw = unquote(parsed.path or "")
    if os.name == "nt" and raw.startswith("/") and len(raw) >= 3 and raw[2] == ":":
        raw = raw[1:]
    path = Path(raw)
    if path.is_file():
        return path.read_bytes()
    return None


def promote_to_artifact(
    capture_item_id: str,
    *,
    kind: str = "document",
    label: str | None = None,
    description: str | None = None,
    actor_key: str = "owner",
) -> dict[str, Any]:
    """Promote reviewed capture to I10B Artifact with .eml representation + provenance."""
    from memorybox.artifact import add_mb_managed_representation, create_artifact

    iid = _parse_uuid(capture_item_id, field="capture_item_id")
    with connection() as conn:
        item = conn.execute(
            "SELECT * FROM historian_capture_items WHERE id = %s", (iid,)
        ).fetchone()
        if not item:
            raise HistorianCaptureError("capture item not found")
        verdict = _latest_verdict(conn, iid)
        if not verdict or verdict["verdict"] != "promotion_authorized":
            raise HistorianCaptureError(
                "promotion requires verdict=promotion_authorized"
            )
        draft = _current_draft(conn, iid)
        if not draft:
            raise HistorianCaptureError("current review draft required for promotion")
        existing_promo = conn.execute(
            """
            SELECT id FROM historian_capture_promotions
            WHERE capture_item_id = %s AND promoted_type = 'artifact'
            """,
            (iid,),
        ).fetchone()
        if existing_promo:
            raise HistorianCaptureError("capture item already promoted to Artifact")
        person_ids: list[str] = []
        if item.get("campaign_respondent_id"):
            resp = conn.execute(
                "SELECT people_id FROM historian_capture_campaign_respondents WHERE id = %s",
                (item["campaign_respondent_id"],),
            ).fetchone()
            if resp and resp.get("people_id"):
                person_ids.append(str(resp["people_id"]))
        body = (draft["body_text"] or item.get("extracted_text") or "").strip()
        art_label = (label or body[:80] or "Historian capture").strip()
        art_desc = (description or body[:2000] or None)

    artifact = create_artifact(
        kind=kind,
        label=art_label,
        description=art_desc,
        person_ids=person_ids or None,
        actor_key=actor_key,
        unresolved_context={"person": not person_ids, "place": True, "event": True},
    )
    raw_bytes = _read_raw_from_uri(item.get("preserved_raw_uri"))
    if raw_bytes:
        add_mb_managed_representation(
            str(artifact.id),
            data=raw_bytes,
            filename="capture_source.txt",
            content_type="text/plain",
            label="Original email source",
            view_kind="document",
            caption="Immutable Historian Capture inbound source (RFC822 bytes preserved)",
        )
    elif body:
        add_mb_managed_representation(
            str(artifact.id),
            data=body.encode("utf-8"),
            filename="capture_text.txt",
            content_type="text/plain",
            label="Extracted text",
            view_kind="document",
        )

    promo_id = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO historian_capture_promotions (
                id, capture_item_id, review_draft_id, verdict_id,
                promoted_type, promoted_id, promoted_by, provenance_json
            ) VALUES (%s, %s, %s, %s, 'artifact', %s, %s, %s::jsonb)
            """,
            (
                promo_id,
                iid,
                draft["id"],
                verdict["id"],
                UUID(str(artifact.id)),
                actor_key,
                json.dumps(
                    {
                        "capture_item_id": str(iid),
                        "review_draft_id": str(draft["id"]),
                        "verdict_id": str(verdict["id"]),
                        "preserved_raw_uri": item.get("preserved_raw_uri"),
                    }
                ),
            ),
        )
    return {
        "promotion_id": str(promo_id),
        "promoted_type": "artifact",
        "promoted_id": str(artifact.id),
        "capture_item_id": str(iid),
        "artifact": {
            "artifact_id": str(artifact.id),
            "label": artifact.label,
        },
    }


def thank_you_preview_body() -> str:
    return _THANK_YOU_TEMPLATE


def unmatched_count() -> int:
    return len(list_unmatched_items(limit=1000))


def connection_probe() -> dict[str, Any]:
    """Stage 1 FlightSim prove — Gmail profile + label without sending."""
    adapter = get_email_adapter()
    probe = getattr(adapter, "connection_probe", None)
    if callable(probe):
        return probe()
    st = email_adapter_status()
    return {
        "ok": bool(st.get("ok")),
        "live": bool(st.get("live")),
        "detail": st.get("detail"),
        "user_email": st.get("user_email"),
    }


def _thank_you_forbidden_reason(
    body: str,
    *,
    capture_item_id: UUID,
    conn: Any,
) -> str | None:
    lower = (body or "").lower()
    for frag in _FORBIDDEN_THANK_YOU_FRAGMENTS:
        if frag in lower:
            return f"forbidden_fragment:{frag}"
    draft = _current_draft(conn, capture_item_id)
    if draft and (draft.get("body_text") or "").strip():
        snippet = (draft["body_text"] or "").strip()[:80].lower()
        if snippet and snippet in lower:
            return "forbidden_draft_text"
    assessment = _latest_assessment(conn, capture_item_id)
    if assessment and (assessment.get("note_private") or "").strip():
        note = assessment["note_private"].strip().lower()
        if note and note in lower:
            return "forbidden_assessment_note"
    promo = conn.execute(
        """
        SELECT p.promoted_id, s.title
        FROM historian_capture_promotions p
        LEFT JOIN stories s ON s.id = p.promoted_id AND p.promoted_type = 'story'
        WHERE p.capture_item_id = %s
        LIMIT 1
        """,
        (capture_item_id,),
    ).fetchone()
    if promo:
        for field in ("title",):
            val = (promo.get(field) or "").strip().lower()
            if val and len(val) > 12 and val in lower:
                return "forbidden_story_text"
    return None


def send_thank_you_if_enabled(
    capture_item_id: str,
    *,
    verdict_id: str | None = None,
    adapter: Any | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    iid = _parse_uuid(capture_item_id, field="capture_item_id")
    adapter = adapter or get_email_adapter()
    with connection() as conn:
        item = conn.execute(
            """
            SELECT i.*, c.send_thank_you_ack, c.title AS campaign_title,
                   r.id AS respondent_id, r.status AS respondent_status,
                   r.display_name_snapshot, r.contact_route_value
            FROM historian_capture_items i
            LEFT JOIN historian_capture_campaigns c ON c.id = i.campaign_id
            LEFT JOIN historian_capture_campaign_respondents r
                ON r.id = i.campaign_respondent_id
            WHERE i.id = %s
            """,
            (iid,),
        ).fetchone()
        if not item:
            raise HistorianCaptureError("capture item not found")
        verdict = None
        if verdict_id:
            verdict = conn.execute(
                """
                SELECT * FROM historian_capture_verdicts
                WHERE id = %s AND capture_item_id = %s
                """,
                (_parse_uuid(verdict_id, field="verdict_id"), iid),
            ).fetchone()
        else:
            verdict = _latest_verdict(conn, iid)
        if not verdict:
            raise HistorianCaptureError("verdict required before thank-you")
        existing = conn.execute(
            """
            SELECT id FROM historian_capture_thank_you_acknowledgments
            WHERE capture_item_id = %s AND verdict_id = %s
            """,
            (iid, verdict["id"]),
        ).fetchone()
        if existing:
            return {"ok": True, "skipped_reason": "already_sent", "ack_id": str(existing["id"])}
        ack_id = uuid4()
        if not item.get("send_thank_you_ack", True):
            conn.execute(
                """
                INSERT INTO historian_capture_thank_you_acknowledgments (
                    id, capture_item_id, verdict_id, campaign_respondent_id,
                    skipped_reason
                ) VALUES (%s, %s, %s, %s, 'disabled')
                """,
                (ack_id, iid, verdict["id"], item.get("respondent_id")),
            )
            return {"ok": True, "skipped_reason": "disabled", "ack_id": str(ack_id)}
        if item.get("respondent_status") == "opted_out":
            conn.execute(
                """
                INSERT INTO historian_capture_thank_you_acknowledgments (
                    id, capture_item_id, verdict_id, campaign_respondent_id,
                    skipped_reason
                ) VALUES (%s, %s, %s, %s, 'opted_out')
                """,
                (ack_id, iid, verdict["id"], item.get("respondent_id")),
            )
            return {"ok": True, "skipped_reason": "opted_out", "ack_id": str(ack_id)}
        send_body = (body or _THANK_YOU_TEMPLATE).strip()
        forbidden = _thank_you_forbidden_reason(send_body, capture_item_id=iid, conn=conn)
        if forbidden:
            conn.execute(
                """
                INSERT INTO historian_capture_thank_you_acknowledgments (
                    id, capture_item_id, verdict_id, campaign_respondent_id,
                    skipped_reason
                ) VALUES (%s, %s, %s, %s, 'forbidden_content')
                """,
                (ack_id, iid, verdict["id"], item.get("respondent_id")),
            )
            return {
                "ok": False,
                "skipped_reason": "forbidden_content",
                "detail": forbidden,
                "ack_id": str(ack_id),
            }
        to_email = item.get("contact_route_value") or ""
        name = item.get("display_name_snapshot") or "there"
        result = adapter.send_thank_you(
            to_email=to_email,
            respondent_name=name,
            body=send_body,
        )
        if not result.ok:
            raise HistorianCaptureError(result.fail_detail or "thank_you_send_failed")
        conn.execute(
            """
            INSERT INTO historian_capture_thank_you_acknowledgments (
                id, capture_item_id, verdict_id, campaign_respondent_id,
                sent_at, outbound_message_id, body_snapshot, preserved_outbound_raw_uri
            ) VALUES (%s, %s, %s, %s, now(), %s, %s, %s)
            """,
            (
                ack_id,
                iid,
                verdict["id"],
                item.get("respondent_id"),
                result.outbound_message_id,
                send_body,
                result.preserved_raw_uri,
            ),
        )
    return {
        "ok": True,
        "ack_id": str(ack_id),
        "outbound_message_id": result.outbound_message_id,
        "sent_at": _iso(_now()),
        "body_snapshot": send_body,
    }


# --- Ask search --------------------------------------------------------------


def re_split_tokens(q: str) -> list[str]:
    return [t for t in re.split(r"[^\w]+", q.lower()) if t]


def search_historian_capture_for_ask(
    *,
    query: str,
    person_names: tuple[str, ...] = (),
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Search promoted/retained historian testimony; exclude rejected verdicts."""
    q = (query or "").strip()
    tokens = [t for t in re_split_tokens(q) if len(t) > 2][:8]
    clauses = [
        "i.match_status = 'matched'",
        """COALESCE((
            SELECT v.verdict FROM historian_capture_verdicts v
            WHERE v.capture_item_id = i.id
            ORDER BY v.decided_at DESC, v.id DESC
            LIMIT 1
        ), '') <> 'rejected'""",
    ]
    params: list[Any] = []
    if tokens:
        like_parts = []
        for t in tokens:
            like_parts.append(
                "(COALESCE(i.extracted_text,'') ILIKE %s "
                "OR COALESCE(d.body_text,'') ILIKE %s "
                "OR COALESCE(r.display_name_snapshot,'') ILIKE %s "
                "OR COALESCE(c.title,'') ILIKE %s "
                "OR COALESCE(s.title,'') ILIKE %s)"
            )
            pat = f"%{t}%"
            params.extend([pat, pat, pat, pat, pat])
        clauses.append("(" + " OR ".join(like_parts) + ")")
    for name in person_names:
        n = (name or "").strip()
        if not n:
            continue
        clauses.append("r.display_name_snapshot ILIKE %s")
        params.append(f"%{n}%")
    params.append(limit)
    where = " AND ".join(clauses)
    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT i.id AS capture_item_id,
                   i.extracted_text,
                   i.received_at,
                   d.body_text AS draft_body,
                   r.display_name_snapshot AS respondent_name,
                   c.title AS campaign_title,
                   q.body_text AS question_body,
                   latest_v.verdict,
                   latest_a.assessment_code,
                   p.promoted_type,
                   p.promoted_id,
                   s.title AS story_title
            FROM historian_capture_items i
            LEFT JOIN historian_capture_campaign_respondents r
                ON r.id = i.campaign_respondent_id
            LEFT JOIN historian_capture_campaigns c ON c.id = i.campaign_id
            LEFT JOIN historian_capture_questions q ON q.id = i.question_id
            LEFT JOIN LATERAL (
                SELECT body_text FROM historian_capture_review_drafts rd
                WHERE rd.capture_item_id = i.id AND rd.is_current = TRUE
                ORDER BY rd.version DESC LIMIT 1
            ) d ON TRUE
            LEFT JOIN LATERAL (
                SELECT verdict FROM historian_capture_verdicts v
                WHERE v.capture_item_id = i.id
                ORDER BY v.decided_at DESC, v.id DESC LIMIT 1
            ) latest_v ON TRUE
            LEFT JOIN LATERAL (
                SELECT assessment_code FROM historian_capture_owner_assessments a
                WHERE a.capture_item_id = i.id
                ORDER BY a.set_at DESC, a.id DESC LIMIT 1
            ) latest_a ON TRUE
            LEFT JOIN historian_capture_promotions p ON p.capture_item_id = i.id
            LEFT JOIN stories s ON s.id = p.promoted_id AND p.promoted_type = 'story'
            WHERE {where}
            ORDER BY i.received_at DESC
            LIMIT %s
            """,
            params,
        ).fetchall()
    hits: list[dict[str, Any]] = []
    for r in rows:
        testimony = (r.get("draft_body") or r.get("extracted_text") or "").strip()
        if not testimony:
            continue
        assessment = r.get("assessment_code") or "not_rated"
        hits.append(
            {
                "capture_item_id": str(r["capture_item_id"]),
                "respondent_name": r.get("respondent_name"),
                "question_body": r.get("question_body"),
                "campaign_title": r.get("campaign_title"),
                "received_at": _iso(r.get("received_at")),
                "excerpt": testimony[:400],
                "verdict": r.get("verdict"),
                "assessment_code": assessment,
                "promoted_type": r.get("promoted_type"),
                "promoted_id": str(r["promoted_id"]) if r.get("promoted_id") else None,
                "story_title": r.get("story_title"),
                "provenance_kind": "historian_capture_item",
                "attribution": (
                    f"{r.get('respondent_name')} responded to historian question "
                    f"(assessment={assessment}; verdict={r.get('verdict') or 'none'})"
                ),
            }
        )
    return hits


__all__ = [
    "HistorianCaptureError",
    "CAMPAIGN_STATUSES",
    "DELIVERY_STATUSES",
    "VERDICT_VALUES",
    "ASSESSMENT_CODES",
    "DEFAULT_FOLLOW_UP_SECONDS",
    "respondent_options",
    "create_campaign",
    "get_campaign",
    "list_campaigns",
    "add_questions",
    "add_respondents",
    "update_question",
    "starter_questions",
    "start_campaign",
    "pause_campaign",
    "resume_campaign",
    "stop_campaign",
    "skip_question",
    "tick_scheduler",
    "retry_delivery",
    "record_capture_item",
    "poll_and_ingest",
    "get_capture_item",
    "list_capture_items",
    "list_unmatched_items",
    "new_capture_count",
    "create_draft",
    "update_current_draft",
    "set_owner_assessment",
    "set_verdict",
    "promote_to_story",
    "promote_to_artifact",
    "thank_you_preview_body",
    "unmatched_count",
    "connection_probe",
    "send_thank_you_if_enabled",
    "search_historian_capture_for_ask",
    "re_split_tokens",
    "get_email_adapter",
    "set_email_adapter",
    "email_adapter_status",
    "FakeHistorianEmailAdapter",
]

