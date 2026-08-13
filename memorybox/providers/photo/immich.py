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
        # Prefer EXIF / Immich display date over fileCreatedAt (often the Immich
        # import time). Older scans imported in 2023+ still carry pre-2023 EXIF.
        taken_at = self._parse_taken_at(raw)
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
        loc_raw = raw.get("exifInfo") if isinstance(raw.get("exifInfo"), dict) else {}
        location = None
        # Immich puts GPS + reverse-geocode city/state/country on exifInfo when
        # search was called with withExif=true (otherwise Map pins are empty).
        lat = self._coerce_coord(loc_raw.get("latitude"), kind="lat")
        lon = self._coerce_coord(loc_raw.get("longitude"), kind="lng")
        if lat is None:
            lat = self._coerce_coord(raw.get("latitude"), kind="lat")
        if lon is None:
            lon = self._coerce_coord(raw.get("longitude"), kind="lng")
        city = loc_raw.get("city") or raw.get("city")
        state = loc_raw.get("state") or raw.get("state")
        country = loc_raw.get("country") or raw.get("country")
        if any(v is not None and v != "" for v in (city, state, country, lat, lon)):
            location = PhotoLocation(
                city=str(city) if city else None,
                state=str(state) if state else None,
                country=str(country) if country else None,
                latitude=lat,
                longitude=lon,
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

    @staticmethod
    def _coerce_coord(value: Any, *, kind: str) -> float | None:
        if value is None or value == "":
            return None
        try:
            n = float(value)
        except (TypeError, ValueError):
            return None
        if kind == "lat" and (-90.0 <= n <= 90.0):
            return n
        if kind == "lng" and (-180.0 <= n <= 180.0):
            return n
        return None

    @staticmethod
    def _parse_taken_at(raw: dict[str, Any]) -> datetime | None:
        """Resolve capture date; never prefer Immich import time over EXIF."""
        exif = raw.get("exifInfo") if isinstance(raw.get("exifInfo"), dict) else {}
        candidates = (
            exif.get("dateTimeOriginal"),
            exif.get("dateTime"),
            raw.get("localDateTime"),
            raw.get("takenAt"),
            raw.get("fileCreatedAt"),
        )
        for taken in candidates:
            if not isinstance(taken, str) or not taken.strip():
                continue
            s = taken.strip()
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00"))
            except ValueError:
                pass
            # EXIF style "2010:05:12 14:30:00"
            if len(s) >= 10 and s[4] == ":" and s[7] == ":":
                date_part = s[:10].replace(":", "-")
                rest = s[10:].strip()
                if rest.startswith(" "):
                    rest = rest[1:]
                iso = f"{date_part}T{rest}" if rest else date_part
                try:
                    return datetime.fromisoformat(iso.replace("Z", "+00:00"))
                except ValueError:
                    continue
        return None

    def list_face_assets(
        self, *, person_external_id: str, limit: int = 50
    ) -> list:
        from memorybox.providers.photo.dto import PhotoFaceAssetRef

        try:
            raw = self._client.list_faces_for_person(person_external_id)
        except self._AuthError as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc)) from exc
        out: list[PhotoFaceAssetRef] = []
        for f in raw or []:
            fid = str(f.get("id") or f.get("faceId") or "")
            if not fid:
                continue
            bbox = None
            if any(k in f for k in ("boundingBoxX1", "x1", "bbox")):
                bbox = {
                    "x1": f.get("boundingBoxX1", f.get("x1")),
                    "y1": f.get("boundingBoxY1", f.get("y1")),
                    "x2": f.get("boundingBoxX2", f.get("x2")),
                    "y2": f.get("boundingBoxY2", f.get("y2")),
                }
            out.append(
                PhotoFaceAssetRef(
                    provider_key=self.provider_key,
                    external_face_id=fid,
                    external_person_id=person_external_id,
                    source_asset_id=str(f.get("assetId") or f.get("imageId") or "") or None,
                    bbox=bbox,
                    confidence=f.get("confidence") or f.get("score"),
                    thumb_url=None,
                )
            )
            if len(out) >= limit:
                break
        return out
