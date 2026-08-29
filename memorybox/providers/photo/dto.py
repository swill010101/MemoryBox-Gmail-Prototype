"""Photo provider DTOs — Immich IDs are external_id only, never domain person_id."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class PhotoFaceAssetRef:
    """Provider face exemplar — Immich face id is external_id only."""

    provider_key: str
    external_face_id: str
    external_person_id: str
    source_asset_id: str | None = None
    bbox: dict | None = None
    confidence: float | None = None
    thumb_url: str | None = None


@dataclass(frozen=True)
class PhotoPersonRef:
    """A person identity *at the provider*. Not a MemoryBox Person PK."""

    provider_key: str
    external_id: str
    display_name: str


@dataclass(frozen=True)
class PhotoFaceRef:
    """Named face on an asset with optional normalized box (x,y,w,h in 0..1)."""

    display_name: str
    external_person_id: str | None = None
    face_box: tuple[float, float, float, float] | None = None  # x, y, w, h


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
    # Camera / capture EXIF for Source rail (empty when Immich omitted withExif)
    exif: tuple[tuple[str, str], ...] = ()
    # Named faces (+ boxes when Immich returned geometry)
    faces: tuple[PhotoFaceRef, ...] = ()


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
    time_windows: tuple[tuple[str, str], ...] = ()
    # Place-scoped person asks need GPS/reverse-geocode; cache hits re-join map pins.
    need_location: bool = False
