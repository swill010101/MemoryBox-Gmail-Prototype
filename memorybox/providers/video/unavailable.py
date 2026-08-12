"""Unavailable VideoIntelligenceProvider — visible failure, never empty success."""
from __future__ import annotations

from memorybox.providers.base import ProviderHealth, ProviderUnavailable
from memorybox.providers.video.dto import (
    VideoAssetDto,
    VideoFaceCandidate,
    VideoPresenceSpan,
    VideoSearchQuery,
    VideoSegmentHit,
)


class UnavailableVideoProvider:
    provider_key = "unavailable_video"

    def __init__(self, detail: str = "video intelligence unavailable") -> None:
        self._detail = detail

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_key=self.provider_key, ok=False, detail=self._detail
        )

    def list_videos(self, *, limit: int = 100) -> list[VideoAssetDto]:
        raise ProviderUnavailable(self._detail)

    def list_face_candidates(
        self, *, video_external_id: str | None = None, limit: int = 100
    ) -> list[VideoFaceCandidate]:
        raise ProviderUnavailable(self._detail)

    def list_presence_spans(
        self,
        *,
        video_external_id: str | None = None,
        face_external_id: str | None = None,
        limit: int = 200,
    ) -> list[VideoPresenceSpan]:
        raise ProviderUnavailable(self._detail)

    def search_segments(self, query: VideoSearchQuery) -> list[VideoSegmentHit]:
        raise ProviderUnavailable(self._detail)

    def get_segment(self, external_id: str) -> VideoSegmentHit | None:
        raise ProviderUnavailable(self._detail)
