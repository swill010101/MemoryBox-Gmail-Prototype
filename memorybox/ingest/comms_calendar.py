"""Calendar ICS → Source + Evidence (evidence_kind=calendar_event)."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from memorybox.ingest import store
from memorybox.providers.calendar.dto import CalendarSourceRef
from memorybox.providers.calendar.ics import IcsCalendarReadProvider

_ICS_SUFFIXES = {".ics", ".ical"}
_MAX_ICS_SCAN = 400
_MAX_ICS_SAMPLE = 12

PARSER_VERSION = "i3-calendar-1"


def _count_row(row: Any) -> int:
    if not row:
        return 0
    if isinstance(row, dict):
        return int(next(iter(row.values())))
    return int(row[0])


def _list_ics(root: Path) -> tuple[list[dict[str, Any]], int]:
    sample: list[dict[str, Any]] = []
    found = 0
    stack: list[tuple[Path, int]] = [(root, 0)]
    scanned = 0
    while stack and scanned < _MAX_ICS_SCAN:
        cur, level = stack.pop()
        try:
            children = list(cur.iterdir())
        except OSError:
            continue
        for child in children:
            scanned += 1
            if scanned > _MAX_ICS_SCAN:
                break
            try:
                if child.is_file() and child.suffix.lower() in _ICS_SUFFIXES:
                    found += 1
                    if len(sample) < _MAX_ICS_SAMPLE:
                        sample.append(
                            {
                                "path": str(child),
                                "bytes": child.stat().st_size,
                            }
                        )
                elif child.is_dir() and level < 4:
                    stack.append((child, level + 1))
            except OSError:
                continue
    return sample, found


def inspect_calendar_state(*, uri: str | None = None) -> dict[str, Any]:
    """Read-only: staged ICS vs PG calendar_event. No ingest. Archive Health calendar slice."""
    from memorybox.ingest.sources_paths import calendar_dir_candidates, default_sources_root

    sources_root = default_sources_root()
    staged_root: Path | None = None
    if uri:
        staged_root = Path(uri)
    else:
        for cand in calendar_dir_candidates():
            try:
                if cand.is_dir():
                    staged_root = cand
                    break
                if cand.is_file() and cand.suffix.lower() in _ICS_SUFFIXES:
                    staged_root = cand.parent
                    break
            except OSError:
                continue

    ics_sample: list[dict[str, Any]] = []
    ics_count = 0
    staged_exists = False
    if staged_root is not None:
        try:
            staged_exists = staged_root.is_dir() or staged_root.is_file()
        except OSError:
            staged_exists = False
        if staged_root.is_file() and staged_root.suffix.lower() in _ICS_SUFFIXES:
            ics_count = 1
            ics_sample = [{"path": str(staged_root), "bytes": staged_root.stat().st_size}]
        elif staged_root.is_dir():
            ics_sample, ics_count = _list_ics(staged_root)

    pg_ok = False
    calendar_event_count: int | None = None
    pg_error: str | None = None
    try:
        from memorybox.db import connection

        with connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM evidence WHERE evidence_kind = 'calendar_event'"
            ).fetchone()
            calendar_event_count = _count_row(row)
            pg_ok = True
    except Exception as exc:  # noqa: BLE001
        pg_error = f"{type(exc).__name__}: {exc}"

    n = calendar_event_count if calendar_event_count is not None else 0
    needs_ingest = bool(pg_ok and n == 0 and ics_count > 0)
    first_ics = (ics_sample[0]["path"] if ics_sample else None)
    ingest_hint = (
        f'python -m memorybox ingest-calendar --uri "{first_ics}"' if first_ics else None
    )

    archive_health = {
        "product": "archive_health",
        "ui": "/status/ui",
        "note": (
            "Archive Health tab (Settings → Archive Health /status/ui). "
            "Staged ICS is not the same as ingested calendar_event rows."
        ),
        "metrics": {
            "calendar": {
                "key": "calendar",
                "label": "Calendar events",
                "value": calendar_event_count,
                "source": "pg:evidence",
                "state": "available" if pg_ok else "unavailable",
            },
            "calendar_source": {
                "key": "calendar_source",
                "label": "Calendar (ICS evidence)",
                "value": calendar_event_count,
                "source": "pg:evidence.calendar_event",
                "note": "Indexed calendar_event evidence rows",
                "state": "available" if pg_ok else "unavailable",
            },
            "staged_calendar": {
                "key": "staged_calendar",
                "label": "Staged calendar Takeout / ICS",
                "display": str(staged_root) if staged_root else "calendar/",
                "ics_files": ics_count,
                "state": "available" if staged_exists else "unavailable",
                "source": str(staged_root) if staged_root else None,
                "note": "Calendar originals staged; PG calendar_event count is separate (ingest result)",
            },
        },
    }

    return {
        "ok": True,
        "calendar_event": calendar_event_count,
        "calendar_event_kind": "calendar_event",
        "pg_ok": pg_ok,
        "pg_error": pg_error,
        "sources_root": str(sources_root) if sources_root else None,
        "staged_calendar_dir": str(staged_root) if staged_root else None,
        "staged_ics_files": ics_count,
        "staged_ics_sample": ics_sample,
        "needs_ingest": needs_ingest,
        "ingest_hint": ingest_hint,
        "archive_health": archive_health,
    }


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
