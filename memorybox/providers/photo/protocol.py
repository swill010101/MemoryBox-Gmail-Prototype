"""PhotoProvider protocol."""
from __future__ import annotations

from typing import Protocol

from memorybox.providers.base import ProviderHealth
from memorybox.providers.photo.dto import (
    PhotoAssetDto,
    PhotoBytesDto,
    PhotoPersonRef,
    PhotoSearchQuery,
)


class PhotoProvider(Protocol):
    provider_key: str

    def health(self) -> ProviderHealth: ...

    def list_people(
        self, *, query: str | None = None, limit: int = 50
    ) -> list[PhotoPersonRef]: ...

    def search_assets(self, query: PhotoSearchQuery) -> list[PhotoAssetDto]: ...

    def get_asset(self, external_asset_id: str) -> PhotoAssetDto | None: ...

    def fetch_preview(self, external_asset_id: str) -> PhotoBytesDto: ...
