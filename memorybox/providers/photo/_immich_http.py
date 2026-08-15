"""In-package Immich HTTP client (POC earn-in for PhotoProvider).

Config-driven only — no hard-coded hosts/paths. Secrets never logged.
"""
from __future__ import annotations

import json
import threading
import time
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
        self._lock = threading.Lock()
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
        retries: int = 2,
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
        last_err: Exception | None = None
        attempts = max(1, int(retries))
        lock = getattr(self, "_lock", None)
        if lock is None:
            self._lock = threading.Lock()
            lock = self._lock
        with lock:
            for attempt in range(attempts):
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
                except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                    # FlightSim Immich often RST/times out on person library search.
                    # Retry — do not treat a dropped socket as "this person has no photos".
                    last_err = exc
                    if attempt < attempts - 1:
                        time.sleep(0.35 * (attempt + 1))
                        continue
                    raise
        if last_err is not None:
            raise last_err
        raise RuntimeError("Immich request failed")

    def ping(self) -> bool:
        status, body = self._request("GET", "/server/ping", timeout=8, retries=1)
        return status == 200 and isinstance(body, dict) and body.get("res") == "pong"

    def check_read_permissions(self) -> dict[str, bool]:
        out = {"asset.read": False, "album.read": False, "person.read": False}
        status, _ = self._request(
            "POST", "/search/metadata", body={"size": 1}, timeout=8, retries=1
        )
        out["asset.read"] = status == 200
        status, _ = self._request("GET", "/albums")
        out["album.read"] = status == 200
        status, _ = self._request("GET", "/people?withHidden=false")
        out["person.read"] = status == 200
        return out

    def search_metadata(self, body: dict[str, Any]) -> dict[str, Any]:
        req = dict(body or {})
        status, data = self._request("POST", "/search/metadata", body=req, timeout=25)
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

        Prefer ``withExif: true`` so Map gets GPS, but learn once per client:
        if Immich rejects or times out withExif, fall back to plain personIds
        pagination for the rest of the fetch. Never re-probe multi-variants on
        every page (that wiped FlightSim person libraries).

        Do not trust ``assets.total`` as an early-stop.
        """
        if not person_ids:
            return []
        target = max(1, min(int(size), 5000))
        # FlightSim /search/metadata RST on large person pages (100+withExif).
        # Smaller pages get a library instead of 0 photos / 1 video.
        page_size = 25
        max_pages = max(2, (target + page_size - 1) // page_size) + 2
        use_order = getattr(self, "_person_use_order", True)
        # None = not yet probed; True/False = learned for this client
        use_exif: bool | None = getattr(self, "_person_with_exif", None)

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

        def _once(
            payload: dict[str, Any],
            *,
            timeout: float = 25,
            retries: int = 2,
        ) -> tuple[int, Any, Exception | None]:
            try:
                status, data = self._request(
                    "POST",
                    "/search/metadata",
                    body=payload,
                    timeout=timeout,
                    retries=retries,
                )
                return status, data, None
            except Exception as exc:  # noqa: BLE001
                return 0, None, exc

        def _page(page: int) -> tuple[list[dict[str, Any]], str | None]:
            nonlocal use_order, use_exif
            base: dict[str, Any] = {
                "personIds": list(person_ids),
                "size": page_size,
                "page": max(1, int(page)),
            }
            # After flags are learned, one payload only (keeps Tom/Eugene fast).
            if use_exif is not None:
                payload = dict(base)
                if use_exif:
                    payload["withExif"] = True
                if use_order:
                    payload["order"] = "desc"
                status, data, err = _once(payload)
                if status == 200:
                    return _extract_items(data)
                if err is not None and page == 1:
                    raise err
                # Learned withExif started failing mid-pagination — drop EXIF once.
                if use_exif and (err is not None or status in (400, 422)):
                    use_exif = False
                    self._person_with_exif = False
                    payload.pop("withExif", None)
                    status, data, err = _once(payload)
                    if status == 200:
                        return _extract_items(data)
                return [], None

            # Library first (no withExif). FlightSim personIds+withExif often
            # RST for 25s × retries and never reaches the working path — that
            # was Show me Peggy George = 1 video / 0 photos / ~129s.
            last_err: Exception | None = None
            for payload in ({**base, "order": "desc"}, dict(base)):
                status, data, err = _once(payload, timeout=25, retries=1)
                if err is not None:
                    last_err = err
                    continue
                if status == 200:
                    items, nxt = _extract_items(data)
                    st_x, data_x, _err_x = _once(
                        {**base, "order": "desc", "withExif": True},
                        timeout=8,
                        retries=1,
                    )
                    if st_x == 200:
                        items_x, nxt_x = _extract_items(data_x)
                        if items_x:
                            use_exif = True
                            use_order = True
                            self._person_with_exif = True
                            self._person_use_order = True
                            return items_x, nxt_x
                    use_exif = False
                    use_order = "order" in payload
                    self._person_with_exif = False
                    self._person_use_order = use_order
                    return items, nxt
                if status in (400, 422):
                    continue
            if page == 1 and last_err is not None:
                raise last_err
            use_exif = False
            self._person_with_exif = False
            return [], None

        by_id: dict[str, dict[str, Any]] = {}
        page = 1
        for _ in range(max_pages):
            if len(by_id) >= target:
                break
            batch, next_page = _page(page)
            if not batch:
                break
            added = 0
            for it in batch:
                eid = it.get("id")
                if not eid:
                    continue
                key = str(eid)
                if key in by_id:
                    continue
                by_id[key] = it
                added += 1
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

    @staticmethod
    def _immich_asset_id(value: Any) -> str | None:
        """Immich asset UUID — not a filesystem thumbnailPath or person id."""
        s = str(value or "").strip()
        if not s or "/" in s or s.startswith("http") or len(s) < 16:
            return None
        return s

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
                status, data = self._request("GET", path, timeout=8, retries=1)
            except Exception:  # noqa: BLE001
                continue
            if status != 200:
                continue
            faces: list[dict[str, Any]] = []
            if isinstance(data, dict):
                raw_faces = data.get("faces") or data.get("items") or []
                if isinstance(raw_faces, list):
                    faces = [f for f in raw_faces if isinstance(f, dict)]
                for key in (
                    "faceAssetId",
                    "featureFaceAssetId",
                    "thumbnailAssetId",
                    "faceAssetID",
                ):
                    aid = self._immich_asset_id(data.get(key))
                    if aid and not any(
                        self._immich_asset_id(f.get("assetId") or f.get("imageId")) == aid
                        for f in faces
                    ):
                        faces.append(
                            {
                                "id": f"person-face-{aid}",
                                "personId": pid,
                                "assetId": aid,
                            }
                        )
            elif isinstance(data, list):
                faces = [f for f in data if isinstance(f, dict)]
            # Drop rows whose assetId is a path / person id (get_asset would 404).
            usable = []
            for f in faces:
                aid = self._immich_asset_id(f.get("assetId") or f.get("imageId"))
                if not aid or aid == pid:
                    continue
                row = dict(f)
                row["assetId"] = aid
                usable.append(row)
            if usable:
                return usable
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

    def fetch_person_thumbnail_bytes(
        self, person_id: str
    ) -> tuple[bytes, str, str] | None:
        """Immich preferred person thumbnail (feature face / person thumb)."""
        pid = (person_id or "").strip()
        if not pid:
            return None
        for path in (
            f"/people/{pid}/thumbnail",
            f"/people/{pid}/thumbnail?format=JPEG",
            f"/people/{pid}/thumbnail?format=WEBP",
        ):
            url = f"{self.api_base}{path}"
            got = self._fetch_api_image(url)
            if got:
                return got[0], got[1], "immich-person-thumb"
        # Person payload may expose the feature-face asset id (varies by Immich version)
        try:
            status, data = self._request("GET", f"/people/{pid}")
        except Exception:  # noqa: BLE001
            status, data = 0, None
        if status == 200 and isinstance(data, dict):
            for key in (
                "faceAssetId",
                "featureFaceAssetId",
                "thumbnailAssetId",
                "faceAssetID",
            ):
                asset_id = str(data.get(key) or "").strip()
                if not asset_id:
                    continue
                try:
                    data_b, ctype, src = self.fetch_preview_bytes(asset_id)
                    return data_b, ctype, src
                except Exception:  # noqa: BLE001
                    continue
        # Fall back: faces list → asset preview
        faces = self.list_faces_for_person(pid)
        for face in faces:
            asset_id = str(
                face.get("assetId")
                or face.get("asset_id")
                or face.get("id")
                or ""
            ).strip()
            if not asset_id or asset_id.startswith("person-thumb-"):
                continue
            try:
                data_b, ctype, src = self.fetch_preview_bytes(asset_id)
                return data_b, ctype, src
            except Exception:  # noqa: BLE001
                continue
        return None
