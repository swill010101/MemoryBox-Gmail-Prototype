"""CalendarReadProvider protocol."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from memorybox.providers.base import ProviderHealth
from memorybox.providers.calendar.dto import CalendarEventDto, CalendarSourceRef


class CalendarReadProvider(Protocol):
    provider_key: str

    def health(self) -> ProviderHealth: ...

    def iter_events(
        self, source: CalendarSourceRef, *, limit: int | None = None
    ) -> Iterator[CalendarEventDto]: ...
