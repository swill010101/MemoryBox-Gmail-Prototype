"""Calendar event DTOs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CalendarSourceRef:
    provider_key: str
    uri: str


@dataclass(frozen=True)
class CalendarEventDto:
    provider_key: str
    event_uid: str | None
    title: str | None
    start: datetime | None
    end: datetime | None
    timezone: str | None
    location: str | None
    description: str | None
    organizer: str | None
    attendees: tuple[str, ...]
    recurrence: str | None
    content_hash: str
    source_locator: str
    all_day: bool = False
