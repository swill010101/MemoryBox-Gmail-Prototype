"""VideoIntelligenceProvider protocol."""
from __future__ import annotations

from typing import Protocol

from memorybox.providers.base import ProviderHealth
from memorybox.providers.video.dto import (
    VideoAssetDto,
    VideoFaceCandidate,
    VideoPresenceSpan,
    VideoSearchQuery,
    VideoSegmentHit,
)


class VideoIntelligenceProvider(Protocol):
    provider_key: str

    def health(self) -> ProviderHealth: ...

    def list_videos(self, *, limit: int = 100) -> list[VideoAssetDto]: ...

    def list_face_candidates(
        self, *, video_external_id: str | None = None, limit: int = 100
    ) -> list[VideoFaceCandidate]: ...

    def list_presence_spans(
        self,
        *,
        video_external_id: str | None = None,
        face_external_id: str | None = None,
        limit: int = 200,
    ) -> list[VideoPresenceSpan]: ...

    def search_segments(self, query: VideoSearchQuery) -> list[VideoSegmentHit]: ...

    def get_segment(self, external_id: str) -> VideoSegmentHit | None: ...
