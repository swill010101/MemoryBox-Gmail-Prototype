"""In-package Immich HTTP client (POC earn-in for PhotoProvider).

Config-driven only — no hard-coded hosts/paths. Secrets never logged.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class ImmichAuthError(RuntimeError):
    pass


class ImmichHttpClient:
    def __init__(self, env_path: Path) -> None:
        if not env_path.is_file():
            raise FileNotFoundError(
                f"Missing {env_path}. Copy config/immich.env.example and set IMMICH_API_KEY."
            )
        vals = self._load_env(env_path)
        key = vals.get("IMMICH_API_KEY") or vals.get("immich_api_key") or ""
        if not key or key.startswith("REPLACE_"):
            raise ImmichAuthError("IMMICH_API_KEY is missing or still a placeholder.")
        raw = (
            vals.get("IMMICH_BASE_URL")
            or vals.get("IMMICH_URL")
            or vals.get("immich_base_url")
            or vals.get("immich_url")
            or ""
        )
        self.ui_root, self.api_base = self._normalize_base_url(raw)
        self._key = key
        thumbs = (vals.get("IMMICH_THUMBS_PATH") or vals.get("immich_thumbs_path") or "").strip()
        self.thumbs_root = Path(thumbs) if thumbs else None

    @staticmethod
    def _load_env(path: Path) -> dict[str, str]:
        out: dict[str, str] = {}
        text = path.read_text(encoding="utf-8-sig")  # strip BOM if present
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            key = k.strip()
            val = v.strip().strip('"').strip("'")
            # Tolerate accidental KEY=KEY=value pastes
            prefix = key + "="
            while val.lower().startswith(prefix.lower()):
                val = val[len(prefix) :].strip().strip('"').strip("'")
            if key:
                out[key] = val
                out[key.upper()] = val  # case-insensitive lookup
        return out

    @staticmethod
    def _normalize_base_url(raw: str) -> tuple[str, str]:
        """Return (ui_root, api_base). Raises ImmichAuthError on bad values."""
        url = (raw or "").strip().strip('"').strip("'")
        # Common paste mistakes
        for junk in (
            "IMMICH_BASE_URL=",
            "IMMICH_URL=",
            "immich_base_url=",
            "immich_url=",
        ):
            if url.lower().startswith(junk.lower()):
                url = url[len(junk) :].strip()
        url = url.rstrip("/")
        if not url:
            raise ImmichAuthError("IMMICH_BASE_URL / IMMICH_URL is empty.")
        lower = url.lower()
        if not (lower.startswith("http://") or lower.startswith("https://")):
            raise ImmichAuthError(
                "IMMICH_BASE_URL must start with http:// or https:// "
                f"(got {url[:48]!r}). Check config/immich.env formatting."
            )
        if url.endswith("/api"):
            return url[:-4], url
        return url, url + "/api"

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        timeout: float = 60,
    ) -> tuple[int, Any]:
        url = self.api_base + (path if path.startswith("/") else "/" + path)
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "x-api-key": self._key,
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace") if e.fp else ""
            try:
                parsed = json.loads(raw) if raw else None
            except Exception:  # noqa: BLE001
                parsed = raw
            return e.code, parsed

    def ping(self) -> bool:
        status, body = self._request("GET", "/server/ping")
        return status == 200 and isinstance(body, dict) and body.get("res") == "pong"

    def check_read_permissions(self) -> dict[str, bool]:
        out = {"asset.read": False, "album.read": False, "person.read": False}
        status, _ = self._request("POST", "/search/metadata", body={"size": 1})
        out["asset.read"] = status == 200
        status, _ = self._request("GET", "/albums")
        out["album.read"] = status == 200
        status, _ = self._request("GET", "/people?withHidden=false")
        out["person.read"] = status == 200
        return out

    def search_metadata(self, body: dict[str, Any]) -> dict[str, Any]:
        req = dict(body or {})
        # Always request EXIF so city/GPS are available for Explore Map / place filter.
        req.setdefault("withExif", True)
        status, data = self._request("POST", "/search/metadata", body=req)
        if status == 403:
            raise ImmichAuthError(
                "Immich API key lacks asset.read (needed for /search/metadata)."
            )
        if status != 200 or not isinstance(data, dict):
            raise RuntimeError(f"Immich search/metadata failed HTTP {status}")
        return data

    def list_people(self) -> list[dict[str, Any]]:
        status, data = self._request("GET", "/people?withHidden=false")
        if status != 200:
            return []
        if isinstance(data, dict):
            return list(data.get("people") or [])
        return data if isinstance(data, list) else []

    def search_by_person_ids(
        self, person_ids: list[str], *, size: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch Immich assets for person id(s).

        Immich metadata search is paginated. Do **not** trust ``assets.total`` to
        stop early — on many Immich builds it mirrors the page count (~100–250).

        Compatibility (FlightSim Immich variants):
        - Prefer ``withExif`` for Map GPS; fall back if rejected.
        - Prefer page size 100 (widely accepted); shrink from 250 if needed.
        - ``order`` is optional — omit on retry if rejected.
        - Never discard already-fetched pages on a later request failure.
        """
        if not person_ids:
            return []
        target = max(1, min(int(size), 5000))
        page_size = int(getattr(self, "_person_page_size", 100) or 100)
        use_exif = getattr(self, "_person_with_exif", True)
        use_order = getattr(self, "_person_use_order", True)
        max_calls = max(40, (target // max(page_size, 1)) + 15)
        calls = 0

        def _extract_items(data: Any) -> tuple[list[dict[str, Any]], str | None]:
            if not isinstance(data, dict):
                return [], None
            assets = data.get("assets")
            items: list[Any] = []
            next_page = None
            if isinstance(assets, dict):
                raw_items = assets.get("items")
                if isinstance(raw_items, list):
                    items = raw_items
                next_page = assets.get("nextPage")
            elif isinstance(assets, list):
                items = assets
            elif isinstance(data.get("items"), list):
                items = list(data.get("items") or [])
                next_page = data.get("nextPage")
            next_s = (
                str(next_page).strip()
                if next_page not in (None, "", 0, "0")
                else None
            )
            return ([it for it in items if isinstance(it, dict)], next_s)

        def _once(payload: dict[str, Any]) -> tuple[int, Any]:
            nonlocal calls
            if calls >= max_calls:
                return 0, None
            calls += 1
            try:
                return self._request("POST", "/search/metadata", body=payload)
            except Exception:  # noqa: BLE001
                return 0, None

        def _search(page: int) -> tuple[list[dict[str, Any]], str | None]:
            nonlocal page_size, use_exif, use_order
            base: dict[str, Any] = {
                "personIds": list(person_ids),
                "size": page_size,
                "page": max(1, int(page)),
            }
            variants: list[dict[str, Any]] = []
            if use_exif and use_order:
                variants.append({**base, "order": "desc", "withExif": True})
            if use_exif:
                variants.append({**base, "withExif": True})
            if use_order:
                variants.append({**base, "order": "desc"})
            variants.append(dict(base))
            seen_v: set[str] = set()
            uniq: list[dict[str, Any]] = []
            for v in variants:
                key = json.dumps(v, sort_keys=True)
                if key in seen_v:
                    continue
                seen_v.add(key)
                uniq.append(v)

            last_status = 0
            for payload in uniq:
                status, data = _once(payload)
                last_status = status
                if status == 200:
                    use_exif = bool(payload.get("withExif"))
                    use_order = "order" in payload
                    self._person_with_exif = use_exif
                    self._person_use_order = use_order
                    self._person_page_size = page_size
                    return _extract_items(data)
                if status in (400, 422) and page_size > 100:
                    page_size = 100
                    self._person_page_size = 100
                    base["size"] = 100
            if last_status != 200:
                status, data = _once(
                    {
                        "personIds": list(person_ids),
                        "size": min(page_size, 100),
                        "page": max(1, int(page)),
                    }
                )
                if status == 200:
                    use_exif = False
                    use_order = False
                    self._person_with_exif = False
                    self._person_use_order = False
                    self._person_page_size = min(page_size, 100)
                    return _extract_items(data)
            return [], None

        def _ingest(batch: list[dict[str, Any]], into: dict[str, dict[str, Any]]) -> int:
            added = 0
            for it in batch:
                eid = it.get("id")
                if not eid:
                    continue
                key = str(eid)
                if key in into:
                    continue
                into[key] = it
                added += 1
            return added

        by_id: dict[str, dict[str, Any]] = {}
        page = 1
        for _ in range((target // max(page_size, 1)) + 8):
            if len(by_id) >= target or calls >= max_calls:
                break
            batch, next_page = _search(page)
            if not batch:
                break
            added = _ingest(batch, by_id)
            if added == 0:
                break
            if len(by_id) >= target:
                break
            if next_page and str(next_page).isdigit():
                page = int(next_page)
            elif len(batch) < page_size:
                break
            else:
                page += 1

        return list(by_id.values())[:target]

    def find_people_by_name(self, name_query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        q = (name_query or "").strip().lower()
        if len(q) < 2:
            return []
        hits = []
        for p in self.list_people():
            name = str(p.get("name") or "").strip()
            if not name:
                continue
            nl = name.lower()
            if q == nl or q in nl or nl.startswith(q):
                hits.append(p)
        hits.sort(
            key=lambda p: (
                0 if str(p.get("name") or "").lower() == q else 1,
                str(p.get("name") or ""),
            )
        )
        return hits[:limit]

    def list_faces_for_person(self, person_id: str) -> list[dict[str, Any]]:
        """Best-effort Immich face exemplars for a person (P2-I1)."""
        pid = (person_id or "").strip()
        if not pid:
            return []
        # Immich variants across versions
        for path in (
            f"/people/{pid}?withFaces=true",
            f"/faces?id={pid}",
            f"/people/{pid}",
        ):
            try:
                status, data = self._request("GET", path)
            except Exception:  # noqa: BLE001
                continue
            if status != 200:
                continue
            faces: list[dict[str, Any]] = []
            if isinstance(data, dict):
                raw_faces = data.get("faces") or data.get("items") or []
                if isinstance(raw_faces, list):
                    faces = [f for f in raw_faces if isinstance(f, dict)]
                # Some payloads embed thumbnail as person-level only
                if not faces and data.get("id"):
                    faces = [
                        {
                            "id": f"person-thumb-{pid}",
                            "personId": pid,
                            "assetId": data.get("thumbnailPath") or data.get("id"),
                            "boundingBoxX1": None,
                        }
                    ]
            elif isinstance(data, list):
                faces = [f for f in data if isinstance(f, dict)]
            if faces:
                return faces
        return []

    def thumb_url(self, asset_id: str, *, size: str = "preview") -> str:
        return f"{self.api_base}/assets/{asset_id}/thumbnail?size={size}"

    def web_url(self, asset_id: str) -> str:
        return f"{self.ui_root}/photos/{asset_id}"

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        status, data = self._request("GET", f"/assets/{asset_id}")
        if status == 200 and isinstance(data, dict):
            return data
        return None

    def _fetch_api_image(self, url: str, timeout: float = 30) -> tuple[bytes, str] | None:
        req = urllib.request.Request(
            url,
            headers={"x-api-key": self._key, "Accept": "image/*,*/*"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                if not data or len(data) < 24:
                    return None
                ctype = resp.headers.get("Content-Type") or "image/jpeg"
                if "json" in ctype or data[:1] in (b"{", b"["):
                    return None
                return data, ctype
        except Exception:  # noqa: BLE001
            return None

    def fetch_preview_bytes(self, asset_id: str) -> tuple[bytes, str, str]:
        for size in ("preview", "thumbnail"):
            got = self._fetch_api_image(self.thumb_url(asset_id, size=size))
            if got:
                return got[0], got[1], "immich-api"
        raise FileNotFoundError(
            "No thumbnail available via Immich API (needs asset.view on API key)"
        )
