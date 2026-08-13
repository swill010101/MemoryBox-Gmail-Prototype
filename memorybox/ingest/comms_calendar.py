"""Calendar ICS → Source + Evidence (evidence_kind=calendar_event)."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from memorybox.ingest import store
from memorybox.providers.calendar.dto import CalendarSourceRef
from memorybox.providers.calendar.ics import IcsCalendarReadProvider

PARSER_VERSION = "i3-calendar-1"


def _payload_from_dto(ev, *, job_id: UUID) -> dict[str, Any]:
    return {
        "evidence_channel": "calendar",
        "event_uid": ev.event_uid,
        "title": ev.title,
        "summary": ev.title,
        "start": ev.start.isoformat() if ev.start else None,
        "end": ev.end.isoformat() if ev.end else None,
        "timezone": ev.timezone,
        "location": ev.location,
        "description": ev.description,
        "organizer": ev.organizer,
        "attendees": list(ev.attendees),
        "recurrence": ev.recurrence,
        "all_day": ev.all_day,
        "source_locator": ev.source_locator,
        "provenance": {
            "provider_key": ev.provider_key,
            "ingest_job_id": str(job_id),
            "parser_version": PARSER_VERSION,
            "authority": "system",
        },
        "content_hash": ev.content_hash,
    }


def ingest_ics(
    ics_uri: str,
    *,
    limit: int | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    path = Path(ics_uri)
    job_id = store.start_job(
        "ingest_calendar",
        message="ingest ics locator configured",
        payload={"source_kind": "ics_import"},
    )
    try:
        if not path.is_file():
            raise FileNotFoundError(f"ics not found: {path}")
        _size = path.stat().st_size
        source_id = store.upsert_source(
            source_kind="ics_import",
            label=label or f"ics:{path.name}",
            uri=str(path.resolve()),
            metadata={
                "fixture_or_smoke": True,
                "byte_size": _size,
                "original_untouched": True,
            },
        )
        provider = IcsCalendarReadProvider()
        inserted = 0
        skipped = 0
        evidence_ids: list[str] = []
        for ev in provider.iter_events(
            CalendarSourceRef(provider_key="ics", uri=str(path)), limit=limit
        ):
            existing = store.evidence_exists_by_hash(source_id, ev.content_hash)
            if existing:
                skipped += 1
                evidence_ids.append(str(existing))
                continue
            payload = _payload_from_dto(ev, job_id=job_id)
            eid = store.insert_evidence(
                evidence_kind="calendar_event",
                source_id=source_id,
                summary=(ev.title or ev.event_uid or "(untitled event)")[:500],
                payload=payload,
            )
            inserted += 1
            evidence_ids.append(str(eid))
        store.finish_job(
            job_id,
            status="done",
            message=f"inserted={inserted} skipped={skipped}",
        )
        return {
            "ok": True,
            "job_id": str(job_id),
            "source_id": str(source_id),
            "inserted": inserted,
            "skipped": skipped,
            "evidence_ids": evidence_ids,
            "ics_bytes": _size,
        }
    except Exception as exc:  # noqa: BLE001
        store.finish_job(
            job_id, status="error", message="ingest failed", error_message=str(exc)
        )
        return {"ok": False, "job_id": str(job_id), "error": str(exc)}
