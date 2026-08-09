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
    """Used when MEMORYBOX_PHOTO_PROVIDER=unavailable or for acceptance I4-G."""

    provider_key = "unavailable_photo"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_key=self.provider_key,
            ok=False,
            detail="photo provider deliberately unavailable",
        )

    def list_people(
        self, *, query: str | None = None, limit: int = 50
    ) -> list[PhotoPersonRef]:
        raise ProviderUnavailable("photo provider unavailable")

    def search_assets(self, query: PhotoSearchQuery) -> list[PhotoAssetDto]:
        raise ProviderUnavailable("photo provider unavailable")

    def get_asset(self, external_asset_id: str) -> PhotoAssetDto | None:
        raise ProviderUnavailable("photo provider unavailable")

    def fetch_preview(self, external_asset_id: str) -> PhotoBytesDto:
        raise ProviderUnavailable("photo provider unavailable")
