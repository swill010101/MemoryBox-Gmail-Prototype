"""Video Intelligence provider DTOs — HVRT IDs are external_id only."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VideoFaceCandidate:
    """A face identity *at the video provider*. Not a MemoryBox Person PK."""

    provider_key: str
    external_id: str
    label: str | None = None
    video_external_id: str | None = None


@dataclass(frozen=True)
class VideoPresenceSpan:
    """Merged continuous presence of a face candidate on a video."""

    provider_key: str
    external_id: str
    video_external_id: str
    face_external_id: str
    start_sec: float
    end_sec: float
    label: str | None = None


@dataclass(frozen=True)
class VideoAssetDto:
    provider_key: str
    external_id: str
    title: str | None = None
    path_hint: str | None = None  # opaque/relative hint — never required as SoT path in reports
    duration_sec: float | None = None


@dataclass(frozen=True)
class VideoSegmentHit:
    provider_key: str
    external_id: str
    video_external_id: str
    start_sec: float
    end_sec: float
    face_external_id: str | None = None
    label: str | None = None
    play_url: str | None = None


@dataclass(frozen=True)
class VideoSearchQuery:
    person_external_ids: tuple[str, ...] = ()
    text: str | None = None
    video_external_id: str | None = None
    limit: int = 50
