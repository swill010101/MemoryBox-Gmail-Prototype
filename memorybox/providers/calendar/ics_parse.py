"""ICS parse helpers (no SQLite)."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

from icalendar import Calendar


def _text(val) -> str:
    if val is None:
        return ""
    if hasattr(val, "to_ical"):
        try:
            return val.to_ical().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    return str(val)


def _to_dt(val) -> tuple[datetime | None, bool, str | None]:
    """Return (datetime_utc_or_naive_date_as_utc_midnight, all_day, tzname)."""
    if val is None:
        return None, False, None
    raw = getattr(val, "dt", val)
    tzname = None
    if hasattr(val, "params"):
        tzname = val.params.get("TZID")
        if isinstance(tzname, bytes):
            tzname = tzname.decode("utf-8", "replace")
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc), False, tzname or "UTC"
        return raw.astimezone(timezone.utc), False, tzname or str(raw.tzinfo)
    if isinstance(raw, date):
        return datetime(raw.year, raw.month, raw.day, tzinfo=timezone.utc), True, tzname
    return None, False, tzname


def event_hash(
    uid: str,
    start: str,
    summary: str,
    location: str,
    description: str,
) -> str:
    raw = f"{uid}|{start}|{summary}|{location}|{description[:2000]}"
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def iter_vevents(ics_path: Path):
    raw = ics_path.read_bytes()
    cal = Calendar.from_ical(raw)
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        yield component, ics_path
