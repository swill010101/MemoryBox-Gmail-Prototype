"""In-memory PhotoProvider for Increment 2 acceptance (no Immich required)."""
from __future__ import annotations

from datetime import datetime, timezone

from memorybox.providers.base import ProviderError, ProviderHealth
from memorybox.providers.photo.dto import (
    PhotoAssetDto,
    PhotoBytesDto,
    PhotoPersonRef,
    PhotoSearchQuery,
)


class FakePhotoProvider:
    provider_key = "fake_photo"

    def __init__(
        self,
        *,
        extra_people: list[PhotoPersonRef] | None = None,
        extra_assets: list[PhotoAssetDto] | None = None,
    ) -> None:
        # Immich-shaped UUID strings as *external* ids only
        self._people = [
            PhotoPersonRef(
                provider_key=self.provider_key,
                external_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                display_name="Grandpa",
            )
        ]
        if extra_people:
            self._people.extend(extra_people)
        self._assets = [
            PhotoAssetDto(
                provider_key=self.provider_key,
                external_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                original_filename="grandpa_christmas.jpg",
                taken_at=datetime(2019, 12, 25, 15, 0, tzinfo=timezone.utc),
                people=(self._people[0],),
            )
        ]
        if extra_assets:
            self._assets.extend(extra_assets)

    def add_named_person(
        self, *, external_id: str, display_name: str
    ) -> PhotoPersonRef:
        ref = PhotoPersonRef(
            provider_key=self.provider_key,
            external_id=external_id,
            display_name=display_name,
        )
        self._people.append(ref)
        return ref

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
        # Minimal valid 1×1 PNG so Library <img> can render in harness.
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789a63000100000500010d0a2db40000000049454e44ae426082"
        )
        return PhotoBytesDto(
            provider_key=self.provider_key,
            external_id=external_asset_id,
            content_type="image/png",
            data=png,
        )

    def list_face_assets(
        self, *, person_external_id: str, limit: int = 50
    ) -> list:
        from memorybox.providers.photo.dto import PhotoFaceAssetRef

        out = []
        for a in self._assets:
            if any(p.external_id == person_external_id for p in a.people):
                out.append(
                    PhotoFaceAssetRef(
                        provider_key=self.provider_key,
                        external_face_id=f"face-{a.external_id[:8]}",
                        external_person_id=person_external_id,
                        source_asset_id=a.external_id,
                        confidence=0.95,
                    )
                )
            if len(out) >= limit:
                break
        # Always ensure at least one synthetic face asset for named people
        if not out:
            out.append(
                PhotoFaceAssetRef(
                    provider_key=self.provider_key,
                    external_face_id=f"face-{person_external_id[:8]}",
                    external_person_id=person_external_id,
                    source_asset_id=None,
                    confidence=0.9,
                )
            )
        return out[:limit]
