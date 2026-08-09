"""Immich PhotoProvider adapter — in-package HTTP client behind DTOs."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from memorybox.providers.base import ProviderError, ProviderHealth, ProviderUnavailable
from memorybox.providers.photo._immich_http import ImmichAuthError, ImmichHttpClient
from memorybox.providers.photo.dto import (
    PhotoAssetDto,
    PhotoBytesDto,
    PhotoLocation,
    PhotoPersonRef,
    PhotoSearchQuery,
)


class ImmichPhotoProvider:
    """Immich via config-driven HTTP client; Immich ids are external_id only."""

    provider_key = "immich"

    def __init__(self, env_path: Path | None = None) -> None:
        self._AuthError = ImmichAuthError
        if env_path is None:
            raise ProviderUnavailable("Immich env_path is required via configuration")
        try:
            self._client = ImmichHttpClient(env_path)
        except FileNotFoundError as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except ImmichAuthError as exc:
            raise ProviderUnavailable(str(exc)) from exc

    def health(self) -> ProviderHealth:
        try:
            ok = bool(self._client.ping())
            meta: dict[str, Any] = {}
            if ok:
                meta["permissions"] = self._client.check_read_permissions()
            return ProviderHealth(
                provider_key=self.provider_key,
                ok=ok,
                detail="pong" if ok else "ping failed",
                meta=meta,
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderHealth(
                provider_key=self.provider_key, ok=False, detail=str(exc)
            )

    def list_people(
        self, *, query: str | None = None, limit: int = 50
    ) -> list[PhotoPersonRef]:
        try:
            if query:
                raw = self._client.find_people_by_name(query)
            else:
                raw = self._client.list_people()
        except self._AuthError as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc)) from exc
        out: list[PhotoPersonRef] = []
        for row in raw or []:
            if not isinstance(row, dict):
                continue
            ext = str(row.get("id") or "")
            if not ext:
                continue
            out.append(
                PhotoPersonRef(
                    provider_key=self.provider_key,
                    external_id=ext,
                    display_name=str(row.get("name") or ""),
                )
            )
            if len(out) >= limit:
                break
        return out

    def search_assets(self, query: PhotoSearchQuery) -> list[PhotoAssetDto]:
        try:
            if query.person_external_ids:
                raw = self._client.search_by_person_ids(
                    list(query.person_external_ids), size=query.limit
                )
                items = raw if isinstance(raw, list) else []
            else:
                body: dict[str, Any] = {"size": query.limit}
                if query.taken_after:
                    body["takenAfter"] = query.taken_after.isoformat()
                if query.taken_before:
                    body["takenBefore"] = query.taken_before.isoformat()
                if query.text:
                    body["query"] = query.text
                data = self._client.search_metadata(body)
                items = (data or {}).get("assets", {}).get("items", []) or []
        except self._AuthError as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc)) from exc
        return [self._map_asset(a) for a in items if isinstance(a, dict)][: query.limit]

    def get_asset(self, external_asset_id: str) -> PhotoAssetDto | None:
        try:
            raw = self._client.get_asset(external_asset_id)
        except self._AuthError as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc)) from exc
        if not isinstance(raw, dict):
            return None
        return self._map_asset(raw)

    def fetch_preview(self, external_asset_id: str) -> PhotoBytesDto:
        try:
            data, content_type, _source = self._client.fetch_preview_bytes(
                external_asset_id
            )
        except self._AuthError as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc)) from exc
        return PhotoBytesDto(
            provider_key=self.provider_key,
            external_id=external_asset_id,
            content_type=content_type or "application/octet-stream",
            data=data,
        )

    def _map_asset(self, raw: dict[str, Any]) -> PhotoAssetDto:
        ext = str(raw.get("id") or "")
        taken = raw.get("fileCreatedAt") or raw.get("takenAt") or raw.get("localDateTime")
        taken_at: datetime | None = None
        if isinstance(taken, str):
            try:
                taken_at = datetime.fromisoformat(taken.replace("Z", "+00:00"))
            except ValueError:
                taken_at = None
        people_raw = raw.get("people") or []
        people: list[PhotoPersonRef] = []
        for p in people_raw:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id") or "")
            if not pid:
                continue
            people.append(
                PhotoPersonRef(
                    provider_key=self.provider_key,
                    external_id=pid,
                    display_name=str(p.get("name") or ""),
                )
            )
        loc_raw = raw.get("exifInfo") or {}
        location = None
        if isinstance(loc_raw, dict) and any(
            loc_raw.get(k) for k in ("city", "state", "country", "latitude", "longitude")
        ):
            location = PhotoLocation(
                city=loc_raw.get("city"),
                state=loc_raw.get("state"),
                country=loc_raw.get("country"),
                latitude=loc_raw.get("latitude"),
                longitude=loc_raw.get("longitude"),
            )
        albums = tuple(
            str(a.get("albumName") or a.get("name") or "")
            for a in (raw.get("albums") or [])
            if isinstance(a, dict)
        )
        return PhotoAssetDto(
            provider_key=self.provider_key,
            external_id=ext,
            taken_at=taken_at,
            original_filename=raw.get("originalFileName") or raw.get("originalPath"),
            location=location,
            people=tuple(people),
            thumb_url=self._client.thumb_url(ext) if ext else None,
            web_url=self._client.web_url(ext) if ext else None,
            albums=albums,
        )
