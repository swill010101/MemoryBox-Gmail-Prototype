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


def _list_ics(root: Path) -> tuple[list[dict[str, Any]], int, int]:
    found_files: list[dict[str, Any]] = []
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
                    found_files.append(
                        {
                            "path": str(child),
                            "bytes": child.stat().st_size,
                        }
                    )
                elif child.is_dir() and level < 4:
                    stack.append((child, level + 1))
            except OSError:
                continue
    found_files.sort(key=lambda row: int(row["bytes"]), reverse=True)
    total_bytes = sum(int(row["bytes"]) for row in found_files)
    return found_files, len(found_files), total_bytes


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

    ics_files: list[dict[str, Any]] = []
    ics_count = 0
    staged_bytes = 0
    staged_exists = False
    if staged_root is not None:
        try:
            staged_exists = staged_root.is_dir() or staged_root.is_file()
        except OSError:
            staged_exists = False
        if staged_root.is_file() and staged_root.suffix.lower() in _ICS_SUFFIXES:
            staged_bytes = staged_root.stat().st_size
            ics_count = 1
            ics_files = [{"path": str(staged_root), "bytes": staged_bytes}]
        elif staged_root.is_dir():
            ics_files, ics_count, staged_bytes = _list_ics(staged_root)

    ics_sample = ics_files[:_MAX_ICS_SAMPLE]
    largest = int(ics_files[0]["bytes"]) if ics_files else 0

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
    # i3 smoke used --limit 5. A 2MB+ Takeout ICS with a handful of PG rows is not the archive.
    coverage_gap = bool(
        pg_ok and ics_count > 0 and n > 0 and largest >= 100_000 and n < 100
    )
    coverage = (
        "empty"
        if n == 0
        else ("smoke_or_partial" if coverage_gap else "ingested")
    )
    tree_uri = None
    if staged_root is not None:
        tree_uri = str(staged_root if staged_root.is_dir() else staged_root.parent)
    ingest_recommended = needs_ingest or coverage_gap
    ingest_hint = (
        f'python -m memorybox ingest-calendar --uri "{tree_uri}"'
        if ingest_recommended and tree_uri
        else None
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
                "ics_bytes": staged_bytes,
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
        "staged_ics_bytes": staged_bytes,
        "staged_ics_sample": ics_sample,
        "coverage": coverage,
        "coverage_gap": coverage_gap,
        "needs_ingest": needs_ingest,
        "ingest_recommended": ingest_recommended,
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
                "fixture_or_smoke": limit is not None,
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


def compact_calendar_cli_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep counts; do not print thousands of evidence UUIDs."""
    out = dict(payload)
    ids = out.get("evidence_ids")
    if isinstance(ids, list) and len(ids) > 12:
        out["evidence_id_count"] = len(ids)
        out["evidence_ids_sample"] = ids[:8]
        del out["evidence_ids"]
    files = out.get("files")
    if isinstance(files, list):
        compact_files = []
        for row in files:
            if not isinstance(row, dict):
                compact_files.append(row)
                continue
            compact_files.append(compact_calendar_cli_payload(row))
        out["files"] = compact_files
    return out


def ingest_calendar_uri(
    uri: str,
    *,
    limit: int | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Ingest one ICS file or every .ics under a staged calendar folder. Originals untouched."""
    path = Path(uri)
    if path.is_file():
        return ingest_ics(str(path), limit=limit, label=label)
    if not path.is_dir():
        return {"ok": False, "error": f"ics not found: {path}"}
    files, count, total_bytes = _list_ics(path)
    if count == 0:
        return {
            "ok": False,
            "error": "no .ics files in folder",
            "uri": str(path),
        }
    file_results: list[dict[str, Any]] = []
    inserted = 0
    skipped = 0
    all_ok = True
    for row in files:
        one = ingest_ics(str(row["path"]), limit=limit, label=label)
        file_results.append(
            {
                "path": row["path"],
                "bytes": row["bytes"],
                "ok": bool(one.get("ok")),
                "inserted": one.get("inserted"),
                "skipped": one.get("skipped"),
                "error": one.get("error"),
                "job_id": one.get("job_id"),
                "source_id": one.get("source_id"),
            }
        )
        if not one.get("ok"):
            all_ok = False
        inserted += int(one.get("inserted") or 0)
        skipped += int(one.get("skipped") or 0)
    return {
        "ok": all_ok,
        "uri": str(path),
        "ics_files": count,
        "ics_bytes": total_bytes,
        "inserted": inserted,
        "skipped": skipped,
        "original_untouched": True,
        "files": file_results,
    }
