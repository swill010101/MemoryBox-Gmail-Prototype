"""In-memory PhotoProvider for Increment 2 acceptance (no Immich required)."""
from __future__ import annotations

from memorybox.providers.base import ProviderError, ProviderHealth
from memorybox.providers.photo.dto import (
    PhotoAssetDto,
    PhotoBytesDto,
    PhotoPersonRef,
    PhotoSearchQuery,
)


class FakePhotoProvider:
    provider_key = "fake_photo"

    def __init__(self) -> None:
        # Immich-shaped UUID strings as *external* ids only
        self._people = [
            PhotoPersonRef(
                provider_key=self.provider_key,
                external_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                display_name="Grandpa",
            )
        ]
        self._assets = [
            PhotoAssetDto(
                provider_key=self.provider_key,
                external_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                original_filename="grandpa_christmas.jpg",
                people=(self._people[0],),
            )
        ]

    def health(self) -> ProviderHealth:
        return ProviderHealth(provider_key=self.provider_key, ok=True, detail="fake")

    def list_people(
        self, *, query: str | None = None, limit: int = 50
    ) -> list[PhotoPersonRef]:
        rows = self._people
        if query:
            q = query.lower()
            rows = [p for p in rows if q in p.display_name.lower()]
        return rows[:limit]

    def search_assets(self, query: PhotoSearchQuery) -> list[PhotoAssetDto]:
        rows = self._assets
        if query.person_external_ids:
            wanted = set(query.person_external_ids)
            rows = [
                a
                for a in rows
                if any(p.external_id in wanted for p in a.people)
            ]
        return rows[: query.limit]

    def get_asset(self, external_asset_id: str) -> PhotoAssetDto | None:
        for a in self._assets:
            if a.external_id == external_asset_id:
                return a
        return None

    def fetch_preview(self, external_asset_id: str) -> PhotoBytesDto:
        if not self.get_asset(external_asset_id):
            raise ProviderError(f"unknown asset {external_asset_id}")
        return PhotoBytesDto(
            provider_key=self.provider_key,
            external_id=external_asset_id,
            content_type="image/jpeg",
            data=b"\xff\xd8\xfffake",
        )
