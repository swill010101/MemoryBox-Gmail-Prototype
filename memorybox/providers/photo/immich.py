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
    PhotoFaceRef,
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
                # Text-only metadata search is not a person library. Immich often
                # ignores unknown `query` and returns newest assets — never use
                # that to pad person finds. Require personIds or date bounds.
                body: dict[str, Any] = {"size": min(int(query.limit), 250)}
                if query.taken_after:
                    body["takenAfter"] = query.taken_after.isoformat()
                if query.taken_before:
                    body["takenBefore"] = query.taken_before.isoformat()
                if query.text and (query.taken_after or query.taken_before):
                    body["originalFileName"] = query.text
                elif query.text and not (query.taken_after or query.taken_before):
                    # No personIds and no date window: refuse unfiltered dump.
                    return []
                data = self._client.search_metadata(body)
                items = (data or {}).get("assets", {}).get("items", []) or []
                if isinstance(items, list) and not items and isinstance(
                    (data or {}).get("assets"), list
                ):
                    items = (data or {}).get("assets") or []
        except self._AuthError as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc)) from exc
        out: list[PhotoAssetDto] = []
        for a in items:
            if not isinstance(a, dict):
                continue
            try:
                out.append(self._map_asset(a))
            except Exception:  # noqa: BLE001 — skip corrupt Immich rows
                continue
            if len(out) >= query.limit:
                break
        return out

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

    def asset_people_faces(self, external_asset_id: str) -> list[dict[str, Any]]:
        """Named Immich people + face boxes for one asset (viewer People rail)."""
        try:
            raw = self._client.get_asset(external_asset_id)
        except self._AuthError as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc)) from exc
        if not isinstance(raw, dict):
            return []
        return [self._face_ref_to_dict(f) for f in self._faces_from_raw(raw)]

    @staticmethod
    def _face_ref_to_dict(face: PhotoFaceRef) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": face.display_name,
            "person_external_id": face.external_person_id,
        }
        if face.face_box:
            x, y, w, h = face.face_box
            out["face_box"] = {"x": x, "y": y, "w": w, "h": h}
        return out

    @staticmethod
    def _normalize_face_box(
        face: dict[str, Any],
    ) -> tuple[float, float, float, float] | None:
        try:
            x1 = float(face.get("boundingBoxX1", face.get("x1")))
            y1 = float(face.get("boundingBoxY1", face.get("y1")))
            x2 = float(face.get("boundingBoxX2", face.get("x2")))
            y2 = float(face.get("boundingBoxY2", face.get("y2")))
            iw = float(face.get("imageWidth") or face.get("image_width") or 0)
            ih = float(face.get("imageHeight") or face.get("image_height") or 0)
        except (TypeError, ValueError):
            return None
        if iw <= 0 or ih <= 0:
            return None
        w = max(0.0, (x2 - x1) / iw)
        h = max(0.0, (y2 - y1) / ih)
        x = max(0.0, min(1.0, x1 / iw))
        y = max(0.0, min(1.0, y1 / ih))
        if w <= 0 or h <= 0:
            return None
        return (x, y, min(1.0, w), min(1.0, h))

    def _faces_from_raw(self, raw: dict[str, Any]) -> tuple[PhotoFaceRef, ...]:
        out: list[PhotoFaceRef] = []
        seen: set[str] = set()

        def add(
            name: str,
            pid: str | None,
            box: tuple[float, float, float, float] | None,
        ) -> None:
            n = (name or "").strip()
            if n.lower() == "unknown":
                n = ""
            if not n and not box:
                return
            key = f"{n}|{pid or ''}|{box}"
            if key in seen:
                return
            seen.add(key)
            out.append(
                PhotoFaceRef(
                    display_name=n or "Unknown",
                    external_person_id=pid or None,
                    face_box=box,
                )
            )

        for p in raw.get("people") or []:
            if not isinstance(p, dict):
                continue
            name = str(p.get("name") or "").strip()
            pid = str(p.get("id") or "") or None
            person_faces = p.get("faces") if isinstance(p.get("faces"), list) else []
            if person_faces:
                for f in person_faces:
                    if not isinstance(f, dict):
                        continue
                    add(name, pid, self._normalize_face_box(f))
            elif name:
                add(name, pid, None)

        for f in raw.get("unassignedFaces") or raw.get("faces") or []:
            if not isinstance(f, dict):
                continue
            person = f.get("person") if isinstance(f.get("person"), dict) else {}
            name = str((person or {}).get("name") or f.get("name") or "").strip()
            pid = str((person or {}).get("id") or "") or None
            box = self._normalize_face_box(f)
            if not name and not box:
                continue
            add(name, pid, box)

        return tuple(out)

    def fetch_preview(self, external_asset_id: str) -> PhotoBytesDto:
        from memorybox.providers.photo.asset_ref import photo_proxy_asset_id

        aid = photo_proxy_asset_id(external_asset_id) or (
            str(external_asset_id or "").strip()
        )
        try:
            data, content_type, _source = self._client.fetch_preview_bytes(aid)
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

    def fetch_person_thumbnail(self, person_id: str) -> PhotoBytesDto | None:
        """Immich person feature-face thumbnail (not an asset preview)."""
        pid = (person_id or "").strip()
        if not pid:
            return None
        fetch = getattr(self._client, "fetch_person_thumbnail_bytes", None)
        if not callable(fetch):
            return None
        try:
            got = fetch(pid)
        except Exception:  # noqa: BLE001
            return None
        if not got:
            return None
        data, content_type, _src = got
        if not data:
            return None
        return PhotoBytesDto(
            provider_key=self.provider_key,
            external_id=pid,
            content_type=content_type or "image/jpeg",
            data=data,
        )

    def _map_asset(self, raw: dict[str, Any]) -> PhotoAssetDto:
        ext = str(raw.get("id") or "")
        # Prefer EXIF / Immich display date over fileCreatedAt (often the Immich
        # import time). Older scans imported in 2023+ still carry pre-2023 EXIF.
        taken_at = self._parse_taken_at(raw)
        faces = self._faces_from_raw(raw)
        people_raw = raw.get("people") or []
        people: list[PhotoPersonRef] = []
        seen_pids: set[str] = set()
        for p in people_raw:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id") or "")
            if not pid or pid in seen_pids:
                continue
            seen_pids.add(pid)
            people.append(
                PhotoPersonRef(
                    provider_key=self.provider_key,
                    external_id=pid,
                    display_name=str(p.get("name") or ""),
                )
            )
        for face in faces:
            if face.external_person_id and face.external_person_id not in seen_pids:
                seen_pids.add(face.external_person_id)
                people.append(
                    PhotoPersonRef(
                        provider_key=self.provider_key,
                        external_id=face.external_person_id,
                        display_name=face.display_name,
                    )
                )
        loc_raw = raw.get("exifInfo") if isinstance(raw.get("exifInfo"), dict) else {}
        location = None
        # Immich puts GPS + reverse-geocode city/state/country on exifInfo when
        # person search learned withExif=true (Map pins). If Immich rejected or
        # timed out withExif, location may be sparse — gallery still honest.
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
        exif_pairs = self._exif_pairs(loc_raw, raw)
        kind = str(raw.get("type") or raw.get("assetType") or "IMAGE").strip().upper()
        if kind not in {"IMAGE", "VIDEO", "AUDIO", "OTHER"}:
            kind = "IMAGE"
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
            exif=exif_pairs,
            faces=faces,
            asset_kind=kind,
        )

    def fetch_original(self, external_asset_id: str) -> PhotoBytesDto:
        try:
            data, content_type, _source = self._client.fetch_original_bytes(
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

    def fetch_original_range(
        self, external_asset_id: str, *, range_header: str | None = None
    ) -> tuple[int, bytes, str, dict[str, str]]:
        try:
            return self._client.fetch_original_range(
                external_asset_id, range_header=range_header
            )
        except self._AuthError as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc)) from exc

    @staticmethod
    def _exif_pairs(exif: dict[str, Any], raw: dict[str, Any]) -> tuple[tuple[str, str], ...]:
        """Human Source-rail rows from Immich exifInfo (omit empties)."""
        rows: list[tuple[str, str]] = []

        def add(label: str, value: Any) -> None:
            if value is None or value == "":
                return
            s = str(value).strip()
            if not s or s.lower() in ("none", "null", "undefined"):
                return
            rows.append((label, s))

        add("Camera make", exif.get("make"))
        add("Camera model", exif.get("model"))
        add("Lens", exif.get("lensModel") or exif.get("lens"))
        fnum = exif.get("fNumber")
        if fnum is not None and fnum != "":
            try:
                add("Aperture", f"f/{float(fnum):g}")
            except (TypeError, ValueError):
                add("Aperture", fnum)
        add("Exposure", exif.get("exposureTime"))
        fl = exif.get("focalLength")
        if fl is not None and fl != "":
            try:
                add("Focal length", f"{float(fl):g} mm")
            except (TypeError, ValueError):
                add("Focal length", fl)
        add("ISO", exif.get("iso") or exif.get("ISO"))
        add(
            "Date original",
            exif.get("dateTimeOriginal") or exif.get("dateTime"),
        )
        w = exif.get("exifImageWidth") or raw.get("exifImageWidth")
        h = exif.get("exifImageHeight") or raw.get("exifImageHeight")
        if w and h:
            add("Dimensions", f"{w} × {h}")
        add("Description", exif.get("description") or exif.get("imageDescription"))
        return tuple(rows)

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
        from memorybox.providers.photo.asset_ref import photo_proxy_asset_id
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
                    source_asset_id=(
                        photo_proxy_asset_id(
                            f.get("assetId") or f.get("imageId") or ""
                        )
                    ),
                    bbox=bbox,
                    confidence=f.get("confidence") or f.get("score"),
                    thumb_url=None,
                )
            )
            if len(out) >= limit:
                break
        return out
