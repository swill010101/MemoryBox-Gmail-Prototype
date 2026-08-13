"""Photo provider that always reports unavailable (I4-G deliberate degradation)."""
from __future__ import annotations

from memorybox.providers.base import ProviderHealth, ProviderUnavailable
from memorybox.providers.photo.dto import (
    PhotoAssetDto,
    PhotoBytesDto,
    PhotoPersonRef,
    PhotoSearchQuery,
)


class UnavailablePhotoProvider:
    """Used when MEMORYBOX_PHOTO_PROVIDER=unavailable or Immich cannot be configured."""

    provider_key = "unavailable_photo"

    def __init__(self, detail: str = "photo provider deliberately unavailable") -> None:
        self._detail = detail

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_key=self.provider_key,
            ok=False,
            detail=self._detail,
        )

    def list_people(
        self, *, query: str | None = None, limit: int = 50
    ) -> list[PhotoPersonRef]:
        raise ProviderUnavailable(self._detail)

    def search_assets(self, query: PhotoSearchQuery) -> list[PhotoAssetDto]:
        raise ProviderUnavailable(self._detail)

    def get_asset(self, external_asset_id: str) -> PhotoAssetDto | None:
        raise ProviderUnavailable(self._detail)

    def fetch_preview(self, external_asset_id: str) -> PhotoBytesDto:
        raise ProviderUnavailable(self._detail)

    def list_face_assets(self, *, person_external_id: str, limit: int = 50) -> list:
        raise ProviderUnavailable(self._detail)
