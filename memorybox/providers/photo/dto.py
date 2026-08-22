"""Photo provider DTOs — Immich IDs are external_id only, never domain person_id."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class PhotoPersonRef:
    """A person identity *at the provider*. Not a MemoryBox Person PK."""

    provider_key: str
    external_id: str
    display_name: str


@dataclass(frozen=True)
class PhotoLocation:
    city: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class PhotoAssetDto:
    provider_key: str
    external_id: str
    taken_at: datetime | None = None
    original_filename: str | None = None
    location: PhotoLocation | None = None
    people: tuple[PhotoPersonRef, ...] = ()
    thumb_url: str | None = None
    web_url: str | None = None
    albums: tuple[str, ...] = ()


@dataclass(frozen=True)
class PhotoBytesDto:
    provider_key: str
    external_id: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class PhotoSearchQuery:
    person_external_ids: tuple[str, ...] = ()
    taken_after: datetime | None = None
    taken_before: datetime | None = None
    text: str | None = None
    limit: int = 50
