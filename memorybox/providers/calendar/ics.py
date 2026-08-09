"""ICS CalendarReadProvider — files only; originals untouched."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from memorybox.providers.base import ProviderError, ProviderHealth, ProviderUnavailable
from memorybox.providers.calendar.dto import CalendarEventDto, CalendarSourceRef
from memorybox.providers.calendar import ics_parse


class IcsCalendarReadProvider:
    provider_key = "ics"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_key=self.provider_key, ok=True, detail="filesystem ics reader"
        )

    def iter_events(
        self, source: CalendarSourceRef, *, limit: int | None = None
    ) -> Iterator[CalendarEventDto]:
        if source.provider_key not in (self.provider_key, "filesystem"):
            raise ProviderError(
                f"IcsCalendarReadProvider cannot read provider_key={source.provider_key}"
            )
        path = Path(source.uri)
        if not path.is_file():
            raise ProviderUnavailable(f"ics not found: {path}")
        yielded = 0
        for component, ics_path in ics_parse.iter_vevents(path):
            if limit is not None and yielded >= limit:
                break
            uid = ics_parse._text(component.get("uid")) or None
            summary = ics_parse._text(component.get("summary")) or None
            description = ics_parse._text(component.get("description")) or None
            location = ics_parse._text(component.get("location")) or None
            organizer = ics_parse._text(component.get("organizer")) or None
            start_prop = component.get("dtstart")
            end_prop = component.get("dtend")
            start, all_day, tz_start = ics_parse._to_dt(start_prop)
            end, _, tz_end = ics_parse._to_dt(end_prop)
            attendees: list[str] = []
            raw_att = component.get("attendee")
            if raw_att is None:
                pass
            elif isinstance(raw_att, list):
                attendees = [ics_parse._text(a) for a in raw_att]
            else:
                attendees = [ics_parse._text(raw_att)]
            rrule = component.get("rrule")
            recurrence = ics_parse._text(rrule) if rrule else None
            start_s = start.isoformat() if start else ""
            ch = ics_parse.event_hash(
                uid or "",
                start_s,
                summary or "",
                location or "",
                description or "",
            )
            locator = f"{ics_path.resolve().as_uri()}#uid={uid or ch}"
            yield CalendarEventDto(
                provider_key=self.provider_key,
                event_uid=uid,
                title=summary,
                start=start,
                end=end,
                timezone=tz_start or tz_end,
                location=location,
                description=description,
                organizer=organizer,
                attendees=tuple(a for a in attendees if a),
                recurrence=recurrence,
                content_hash=ch,
                source_locator=locator,
                all_day=all_day,
            )
            yielded += 1
