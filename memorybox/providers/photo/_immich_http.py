"""In-package Immich HTTP client (POC earn-in for PhotoProvider).

Config-driven only — no hard-coded hosts/paths. Secrets never logged.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("memorybox.immich")
_CIRCUIT_COOLDOWN_SEC = 300
_PERSON_LIB_MEM_TTL_SEC = 6 * 3600
_PERSON_LIB_DISK_TTL_SEC = 24 * 3600
_PERSON_TIMELINE_YEAR_BUDGET = 24
_PERSON_TIMELINE_MONTH_BUDGET = 18


class ImmichAuthError(RuntimeError):
    pass


def immich_activity_path() -> Path:
    """Ask-side Immich call log (not Immich's own server log). No API keys."""
    import os

    raw = (os.environ.get("MEMORYBOX_IMMICH_ACTIVITY_PATH") or "").strip()
    if raw:
        return Path(raw)
    home = (
        os.environ.get("MEMORYBOX_HOME")
        or os.environ.get("MEMORYBOX_DATA_DIR")
        or ""
    ).strip()
    if home:
        return Path(home) / "immich-activity.jsonl"
    return Path(__file__).resolve().parents[2] / "immich-activity.jsonl"


def _append_immich_activity(rec: dict[str, Any]) -> None:
    try:
        path = immich_activity_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
    except Exception:  # noqa: BLE001 — never fail a photo ask because the log disk hiccuped
        return


def read_immich_activity(*, limit: int = 200) -> list[dict[str, Any]]:
    path = immich_activity_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-max(1, int(limit)) :]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


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
        if getattr(self, "_circuit_open", False) and not self._circuit_allows(path):
            self._record_call(method, path, status=0, ms=0, err="circuit_open")
            raise TimeoutError("immich circuit open")
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
                t0 = time.monotonic()
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        raw = resp.read().decode("utf-8", "replace")
                        ms = (time.monotonic() - t0) * 1000
                        self._record_call(method, path, status=int(resp.status), ms=ms)
                        return resp.status, (json.loads(raw) if raw else None)
                except urllib.error.HTTPError as e:
                    ms = (time.monotonic() - t0) * 1000
                    raw = e.read().decode("utf-8", "replace") if e.fp else ""
                    try:
                        parsed = json.loads(raw) if raw else None
                    except Exception:  # noqa: BLE001
                        parsed = raw
                    self._record_call(method, path, status=int(e.code), ms=ms)
                    return e.code, parsed
                except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                    # FlightSim Immich often RST/times out on person library search.
                    ms = (time.monotonic() - t0) * 1000
                    last_err = exc
                    self._record_call(method, path, status=0, ms=ms, err=str(exc)[:160])
                    self._note_transport_fail(exc)
                    if attempt < attempts - 1 and not getattr(self, "_circuit_open", False):
                        time.sleep(0.35 * (attempt + 1))
                        continue
                    raise
        if last_err is not None:
            raise last_err
        raise RuntimeError("Immich request failed")

    def _record_call(
        self,
        method: str,
        path: str,
        *,
        status: int,
        ms: float,
        err: str | None = None,
    ) -> None:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "method": str(method or "GET"),
            "path": str(path or "")[:160],
            "status": int(status or 0),
            "ms": int(ms),
            "err": (err or "")[:160] or None,
            "circuit": self._circuit(),
        }
        log = getattr(self, "_call_log", None)
        if log is None:
            self._call_log = []
            log = self._call_log
        log.append(rec)
        if len(log) > 48:
            del log[:-48]
        _LOG.info(
            "immich %s %s status=%s ms=%s err=%s circuit=%s",
            rec["method"],
            rec["path"],
            rec["status"],
            rec["ms"],
            rec["err"],
            rec["circuit"],
        )
        _append_immich_activity(rec)

    def diag_snapshot(self) -> dict[str, Any]:
        """Last Immich HTTP calls for curator / /dev/ai-trace (no secrets)."""
        rows = list(getattr(self, "_call_log", None) or [])
        fails = [
            r
            for r in rows
            if r.get("err") or int(r.get("status") or 0) in (0, 500, 502, 503, 504)
        ]
        return {
            "calls": len(rows),
            "fails": len(fails),
            "circuit": self._circuit(),
            "source": getattr(self, "_last_person_source", None),
            "incomplete": bool(getattr(self, "_person_lib_incomplete", False)),
            "total_ms": int(sum(int(r.get("ms") or 0) for r in rows)),
            "last": rows[-8:],
        }

    def _reset_call_log(self) -> None:
        self._call_log = []

    def _reset_person_circuit(self) -> None:
        """No-op while cooldown is live. Name search is already allowlisted."""
        until = float(getattr(self, "_circuit_until", 0) or 0)
        if getattr(self, "_circuit_open", False) and until and time.time() < until:
            return
        if getattr(self, "_circuit_open", False):
            return
        self._transport_fails = 0

    def _note_transport_fail(self, exc: BaseException | None = None) -> None:
        """Two RST/timeouts → stay off Immich for five minutes."""
        msg = str(exc or "").lower()
        if exc is not None and not isinstance(
            exc, (TimeoutError, ConnectionError, OSError, urllib.error.URLError)
        ):
            if "timed out" not in msg and "circuit" not in msg and "rst" not in msg:
                return
        self._transport_fails = int(getattr(self, "_transport_fails", 0) or 0) + 1
        if self._transport_fails >= 2:
            self._circuit_open = True
            self._circuit_until = time.time() + _CIRCUIT_COOLDOWN_SEC

    def _circuit(self) -> bool:
        return bool(getattr(self, "_circuit_open", False))

    def _maybe_half_open(self) -> None:
        """After cooldown, one ping. Failure keeps the circuit shut."""
        if not getattr(self, "_circuit_open", False):
            return
        until = float(getattr(self, "_circuit_until", 0) or 0)
        if until and time.time() < until:
            return
        try:
            if self.ping():
                self._circuit_open = False
                self._circuit_until = 0
                self._transport_fails = 0
                return
        except Exception:  # noqa: BLE001
            pass
        self._circuit_until = time.time() + _CIRCUIT_COOLDOWN_SEC

    def _person_lib_disk_dir(self) -> Path | None:
        import os

        home = (
            os.environ.get("MEMORYBOX_HOME")
            or os.environ.get("MEMORYBOX_DATA_DIR")
            or ""
        ).strip()
        if not home:
            return None
        return Path(home) / "immich-person-lib"

    def _read_person_lib_cache(
        self, cache_key: str, *, allow_stale: bool
    ) -> list[dict[str, Any]] | None:
        mem = getattr(self, "_person_lib_cache", None)
        if isinstance(mem, dict) and cache_key in mem:
            rows, ts = mem[cache_key]
            age = time.time() - float(ts)
            if isinstance(rows, list) and rows:
                if allow_stale or age < _PERSON_LIB_MEM_TTL_SEC:
                    return list(rows)
        disk = self._person_lib_disk_dir()
        if disk is None:
            return None
        path = disk / f"{cache_key.replace('/', '_')[:80]}.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        rows = raw.get("assets")
        ts = float(raw.get("ts") or 0)
        if not isinstance(rows, list) or not rows:
            return None
        age = time.time() - ts
        if allow_stale or age < _PERSON_LIB_DISK_TTL_SEC:
            return [r for r in rows if isinstance(r, dict)]
        return None

    def _write_person_lib_cache(
        self, cache_key: str, rows: list[dict[str, Any]]
    ) -> None:
        store = getattr(self, "_person_lib_cache", None)
        if store is None:
            self._person_lib_cache = {}
            store = self._person_lib_cache
        store[cache_key] = (list(rows), time.time())
        disk = self._person_lib_disk_dir()
        if disk is None:
            return
        try:
            disk.mkdir(parents=True, exist_ok=True)
            path = disk / f"{cache_key.replace('/', '_')[:80]}.json"
            path.write_text(
                json.dumps({"ts": time.time(), "assets": rows}, default=str),
                encoding="utf-8",
            )
        except OSError:
            return

    @staticmethod
    def _circuit_allows(path: str) -> bool:
        """Name lookup stays open after a mapped-id RST (stale Immich UUID)."""
        p = path or ""
        return (
            p == "/server/ping"
            or p == "/search/person"
            or p.startswith("/people?name=")
        )

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
        try:
            status, data = self._request(
                "GET", "/people?withHidden=false", timeout=8, retries=1
            )
        except Exception as exc:  # noqa: BLE001
            self._note_transport_fail(exc)
            return []
        if status != 200:
            return []
        if isinstance(data, dict):
            return list(data.get("people") or [])
        return data if isinstance(data, list) else []

    def search_by_person_ids(
        self, person_ids: list[str], *, size: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch Immich assets for person id(s).

        FlightSim POST /search/metadata often RST on personIds (Show me Peggy
        George = 0 photos / 1 video). Prefer GET paths the Immich UI uses:

        1. ``GET /people/{id}`` faces — often a subset (feature faces), not
           the person library (Peggy: 131 faces vs 598 Immich assets)
        2. ``GET /timeline/buckets`` + ``/timeline/bucket`` with personId —
           the Immich person-page source; always union with faces
        3. POST /search/metadata last, short timeout, never the first probe

        Prefer ``withExif: true`` on the metadata path so Map gets GPS, but
        learn once per client. Do not trust ``assets.total`` as an early-stop.
        Do not treat a non-empty face list as a complete library.
        """
        if not person_ids:
            return []
        self._maybe_half_open()
        self._reset_call_log()
        self._person_lib_incomplete = False
        target = max(1, min(int(size), 5000))
        cache_key = ",".join(sorted(str(p).strip() for p in person_ids if str(p).strip()))
        cached = self._read_person_lib_cache(
            cache_key, allow_stale=self._circuit()
        )
        if cached:
            self._last_person_source = "cache"
            return list(cached)[:target]
        if self._circuit():
            self._last_person_source = "timeout"
            return []
        by_id: dict[str, dict[str, Any]] = {}

        def _add(rows: list[dict[str, Any]]) -> None:
            for it in rows:
                if not isinstance(it, dict):
                    continue
                eid = str(it.get("id") or "").strip()
                if not eid or eid in by_id:
                    continue
                by_id[eid] = it

        _add(self._assets_from_person_faces(person_ids, target))
        if not self._circuit():
            _add(self._assets_from_person_timeline(person_ids, target))
        # Any GET hit is enough to skip /search/metadata RST (0 photos / 1 video).
        if by_id:
            self._last_person_source = "faces_or_timeline"
            out = list(by_id.values())[:target]
            # Cache newest-year walks even when the year budget truncated older
            # decades. Re-walking a recovering NAS is how Immich bounces again.
            if not self._circuit():
                self._write_person_lib_cache(cache_key, out)
            return out
        if self._circuit():
            self._last_person_source = "timeout"
            return []

        try:
            _add(self._assets_from_person_metadata(person_ids, target))
            if by_id:
                self._last_person_source = "metadata"
        except Exception as exc:  # noqa: BLE001
            self._note_transport_fail(exc)
        if by_id:
            out = list(by_id.values())[:target]
            if not self._circuit():
                self._write_person_lib_cache(cache_key, out)
            return out
        self._last_person_source = "timeout" if self._circuit() else "empty"
        return []

    def _assets_from_person_faces(
        self, person_ids: list[str], target: int
    ) -> list[dict[str, Any]]:
        """Stub assets from face records. GET /people works on FlightSim."""
        by_id: dict[str, dict[str, Any]] = {}
        for pid in person_ids:
            pid = str(pid or "").strip()
            if not pid:
                continue
            if self._circuit():
                break
            try:
                faces = self.list_faces_for_person(pid)
            except Exception as exc:  # noqa: BLE001
                self._note_transport_fail(exc)
                faces = []
            for face in faces or []:
                if not isinstance(face, dict):
                    continue
                aid = self._immich_asset_id(
                    face.get("assetId") or face.get("imageId")
                )
                if not aid or aid == pid or aid in by_id:
                    continue
                by_id[aid] = {
                    "id": aid,
                    "people": [{"id": pid, "name": face.get("personName") or ""}],
                }
                if len(by_id) >= target:
                    return list(by_id.values())
        return list(by_id.values())

    def _assets_from_person_timeline(
        self, person_ids: list[str], target: int
    ) -> list[dict[str, Any]]:
        """Immich UI person library: time buckets, then bucket asset ids."""
        by_id: dict[str, dict[str, Any]] = {}
        for pid in person_ids:
            pid = str(pid or "").strip()
            if not pid:
                continue
            if self._circuit():
                break
            buckets = self._list_person_time_buckets(pid)
            # Newest years first so a budget stop cannot drop 1984–now.
            # YEAR = one GET/year (allow a lifetime). MONTH is the RST risk.
            year_mode = "size=YEAR" in str(getattr(self, "_person_buckets_tmpl", "") or "")
            budget = (
                _PERSON_TIMELINE_YEAR_BUDGET
                if year_mode
                else _PERSON_TIMELINE_MONTH_BUDGET
            )
            self._timeline_http = 0
            self._person_lib_incomplete = False
            if len(buckets) > budget:
                self._person_lib_incomplete = True
            for bucket in buckets[:budget]:
                if self._circuit() or int(getattr(self, "_timeline_http", 0) or 0) >= budget:
                    self._person_lib_incomplete = True
                    break
                if len(by_id) >= target:
                    return list(by_id.values())[:target]
                for it in self._list_person_bucket_assets(pid, bucket):
                    eid = str(it.get("id") or "").strip()
                    if not eid or eid in by_id:
                        continue
                    people = it.get("people")
                    if not isinstance(people, list) or not people:
                        it = dict(it)
                        it["people"] = [{"id": pid}]
                    by_id[eid] = it
                    if len(by_id) >= target:
                        return list(by_id.values())[:target]
        return list(by_id.values())[:target]

    def _list_person_time_buckets(self, person_id: str) -> list[str]:
        pid = (person_id or "").strip()
        if not pid:
            return []
        tmpls = (
            "/timeline/buckets?personId={pid}&size=YEAR",
            "/timeline/buckets?personId={pid}&size=MONTH",
            "/timeline/buckets?personIds={pid}&size=MONTH",
            "/assets/time-buckets?personId={pid}&size=MONTH",
            "/asset/time-buckets?personId={pid}&size=MONTH",
            "/timeline/buckets?personId={pid}",
        )
        sticky = getattr(self, "_person_buckets_tmpl", None)
        use = (sticky,) if sticky in tmpls else tmpls
        for tmpl in use:
            path = tmpl.format(pid=pid)
            if self._circuit():
                break
            try:
                status, data = self._request("GET", path, timeout=6, retries=1)
            except Exception as exc:  # noqa: BLE001
                self._note_transport_fail(exc)
                if self._circuit():
                    break
                continue
            if status != 200:
                continue
            rows = data if isinstance(data, list) else (
                data.get("buckets") if isinstance(data, dict) else None
            )
            if not isinstance(rows, list) or not rows:
                continue
            out: list[str] = []
            for row in rows:
                if isinstance(row, str) and row.strip():
                    out.append(row.strip())
                    continue
                if not isinstance(row, dict):
                    continue
                tb = (
                    row.get("timeBucket")
                    or row.get("timeBucketId")
                    or row.get("id")
                    or row.get("date")
                )
                if tb:
                    out.append(str(tb).strip())
            if out:
                self._person_buckets_tmpl = tmpl
                return self._sort_time_buckets_newest_first(out)
        return []

    @staticmethod
    def _sort_time_buckets_newest_first(buckets: list[str]) -> list[str]:
        """Newest year/month first. Never walk 1900→1983 and drop the rest."""

        def _key(raw: str) -> str:
            s = str(raw or "").strip()
            return s[:10] if len(s) >= 4 else s

        return sorted((b for b in buckets if str(b).strip()), key=_key, reverse=True)

    def _list_person_bucket_assets(
        self, person_id: str, time_bucket: str
    ) -> list[dict[str, Any]]:
        pid = (person_id or "").strip()
        tb = (time_bucket or "").strip()
        if not pid or not tb:
            return []
        from urllib.parse import quote

        qtb = quote(tb, safe=":-T.Z")
        tmpls = (
            "/timeline/bucket?timeBucket={qtb}&personId={pid}",
            "/timeline/bucket?timeBucket={qtb}&personIds={pid}",
            "/assets/time-bucket?timeBucket={qtb}&personId={pid}",
            "/asset/time-bucket?timeBucket={qtb}&personId={pid}",
        )
        sticky = getattr(self, "_person_bucket_tmpl", None)
        use = (sticky,) if sticky in tmpls else tmpls
        for tmpl in use:
            path = tmpl.format(qtb=qtb, pid=pid)
            if self._circuit():
                break
            try:
                self._timeline_http = int(getattr(self, "_timeline_http", 0) or 0) + 1
                status, data = self._request("GET", path, timeout=6, retries=1)
            except Exception as exc:  # noqa: BLE001
                self._note_transport_fail(exc)
                if self._circuit():
                    break
                continue
            if status != 200:
                continue
            items = self._normalize_timeline_assets(data)
            if items:
                self._person_bucket_tmpl = tmpl
                return items
        return []

    def _normalize_timeline_assets(self, data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            out: list[dict[str, Any]] = []
            for it in data:
                if isinstance(it, dict) and it.get("id"):
                    out.append(it)
                elif isinstance(it, str) and self._immich_asset_id(it):
                    out.append({"id": str(it)})
            return out
        if not isinstance(data, dict):
            return []
        raw_items = data.get("items") or data.get("assets")
        if isinstance(raw_items, list) and raw_items:
            return [it for it in raw_items if isinstance(it, dict) and it.get("id")]
        ids = data.get("id") or data.get("ids")
        if not isinstance(ids, list) or not ids:
            return []

        def _col(name: str) -> list[Any]:
            v = data.get(name)
            return v if isinstance(v, list) else []

        created = _col("fileCreatedAt") or _col("createdAt")
        cities = _col("city")
        countries = _col("country")
        is_image = _col("isImage")
        out: list[dict[str, Any]] = []
        for i, aid in enumerate(ids):
            key = str(aid or "").strip()
            if not key:
                continue
            row: dict[str, Any] = {"id": key}
            if i < len(is_image) and is_image[i] is False:
                row["type"] = "video"
                row["isVideo"] = True
            if i < len(created) and created[i]:
                row["localDateTime"] = created[i]
                row["fileCreatedAt"] = created[i]
            city = cities[i] if i < len(cities) else None
            country = countries[i] if i < len(countries) else None
            if city or country:
                row["exifInfo"] = {
                    "city": city or None,
                    "country": country or None,
                }
            out.append(row)
        return out

    def _assets_from_person_metadata(
        self, person_ids: list[str], target: int
    ) -> list[dict[str, Any]]:
        """Last-resort POST /search/metadata. Short timeouts — FlightSim RST."""
        # FlightSim /search/metadata RST on large person pages (100+withExif).
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
            timeout: float = 8,
            retries: int = 1,
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
                status, data, err = _once(payload, timeout=8, retries=1)
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

    @staticmethod
    def _name_matches_person(query: str, person_name: str) -> bool:
        """Match Immich 'Peggy' to Ask 'Peggy George' without substring traps."""
        q = (query or "").strip().lower()
        n = (person_name or "").strip().lower()
        if len(q) < 2 or not n:
            return False
        if q == n:
            return True
        if n.startswith(q + " ") or q.startswith(n + " "):
            return True
        q0 = q.split()[0]
        n0 = n.split()[0]
        return bool(q0 and n0 and q0 == n0 and (n.startswith(q) or q.startswith(n)))

    def find_people_by_name(self, name_query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        q = (name_query or "").strip()
        if len(q) < 2:
            return []
        tokens = [q]
        first = q.split()[0]
        if first.lower() != q.lower():
            tokens.append(first)
        hits: list[dict[str, Any]] = []
        seen: set[str] = set()

        def _add(rows: Any) -> None:
            if isinstance(rows, dict):
                rows = rows.get("people") or rows.get("items") or []
            if not isinstance(rows, list):
                return
            for p in rows:
                if not isinstance(p, dict):
                    continue
                pid = str(p.get("id") or "").strip()
                name = str(p.get("name") or "").strip()
                if not pid or pid in seen or not name:
                    continue
                if self._name_matches_person(q, name):
                    seen.add(pid)
                    hits.append(p)

        from urllib.parse import quote

        for token in tokens:
            try:
                status, data = self._request(
                    "POST",
                    "/search/person",
                    body={"name": token},
                    timeout=6,
                    retries=1,
                )
                if status == 200:
                    _add(data)
            except Exception as exc:  # noqa: BLE001
                self._note_transport_fail(exc)
            if hits:
                break
            try:
                status, data = self._request(
                    "GET",
                    f"/people?name={quote(token)}&withHidden=false",
                    timeout=6,
                    retries=1,
                )
                if status == 200:
                    _add(data)
            except Exception as exc:  # noqa: BLE001
                self._note_transport_fail(exc)
            if hits:
                break
        if hits:
            ql = q.lower()
            hits.sort(
                key=lambda p: (
                    0 if str(p.get("name") or "").strip().lower() == ql else 1,
                    str(p.get("name") or ""),
                )
            )
            return hits[:limit]
        # Do not dump GET /people (60s+ on FlightSim) after search/person missed.
        return []

    @staticmethod
    def _immich_asset_id(value: Any) -> str | None:
        """Immich asset UUID — not a filesystem thumbnailPath or person id."""
        s = str(value or "").strip()
        if not s or "/" in s or s.startswith("http") or len(s) < 16:
            return None
        return s

    def list_faces_for_person(self, person_id: str) -> list[dict[str, Any]]:
        """Best-effort Immich face exemplars for a person (P2-I1).

        ``withFaces=true`` is the person-library path when /search/metadata RST:
        each face carries a real asset UUID (not thumbnailPath).
        """
        pid = (person_id or "").strip()
        if not pid:
            return []
        # Cheap person record first (feature face). withFaces can RST when
        # the person has hundreds of faces — that was 187s / 0 photos.
        for path in (
            f"/people/{pid}",
            f"/people/{pid}?withFaces=true",
            f"/people/{pid}/faces",
            f"/faces?id={pid}",
        ):
            if self._circuit():
                break
            try:
                status, data = self._request("GET", path, timeout=6, retries=1)
            except Exception as exc:  # noqa: BLE001
                self._note_transport_fail(exc)
                if self._circuit():
                    break
                continue
            if status != 200:
                continue
            usable = self._faces_from_people_payload(pid, data)
            if usable:
                return usable
        return []

    def _faces_from_people_payload(
        self, pid: str, data: Any
    ) -> list[dict[str, Any]]:
        faces: list[dict[str, Any]] = []
        if isinstance(data, dict):
            for key in ("faces", "items", "assets"):
                raw = data.get(key)
                if isinstance(raw, list):
                    faces.extend(f for f in raw if isinstance(f, dict))
            for key in (
                "faceAssetId",
                "featureFaceAssetId",
                "thumbnailAssetId",
                "faceAssetID",
            ):
                aid = self._immich_asset_id(data.get(key))
                if aid:
                    faces.append(
                        {
                            "id": f"person-face-{aid}",
                            "personId": pid,
                            "assetId": aid,
                        }
                    )
        elif isinstance(data, list):
            faces = [f for f in data if isinstance(f, dict)]
        usable: list[dict[str, Any]] = []
        seen: set[str] = set()
        for f in faces:
            nested = f.get("asset") if isinstance(f.get("asset"), dict) else {}
            aid = self._immich_asset_id(
                f.get("assetId")
                or f.get("imageId")
                or f.get("sourceAssetId")
                or nested.get("id")
            )
            if not aid or aid == pid or aid in seen:
                continue
            seen.add(aid)
            row = dict(f)
            row["assetId"] = aid
            if not row.get("id"):
                row["id"] = f"person-face-{aid}"
            usable.append(row)
        return usable

    def thumb_url(self, asset_id: str, *, size: str = "preview") -> str:
        return f"{self.api_base}/assets/{asset_id}/thumbnail?size={size}"

    def web_url(self, asset_id: str) -> str:
        return f"{self.ui_root}/photos/{asset_id}"

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        status, data = self._request("GET", f"/assets/{asset_id}")
        if status == 200 and isinstance(data, dict):
            return data
        return None

    def _fetch_api_image(self, url: str, timeout: float = 3) -> tuple[bytes, str] | None:
        if self._circuit():
            return None
        req = urllib.request.Request(
            url,
            headers={"x-api-key": self._key, "Accept": "image/*,*/*"},
            method="GET",
        )
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                ms = (time.monotonic() - t0) * 1000
                if not data or len(data) < 24:
                    return None
                ctype = resp.headers.get("Content-Type") or "image/jpeg"
                if "json" in ctype or data[:1] in (b"{", b"["):
                    return None
                self._record_call("GET", url.split("/api", 1)[-1][:160], status=200, ms=ms)
                return data, ctype
        except Exception as exc:  # noqa: BLE001
            ms = (time.monotonic() - t0) * 1000
            self._record_call(
                "GET",
                url.split("/api", 1)[-1][:160],
                status=0,
                ms=ms,
                err=str(exc)[:160],
            )
            self._note_transport_fail(exc)
            return None

    def fetch_preview_bytes(self, asset_id: str) -> tuple[bytes, str, str]:
        if self._circuit():
            raise FileNotFoundError("immich circuit open")
        sem = getattr(self, "_thumb_sema", None)
        if sem is None:
            self._thumb_sema = threading.Semaphore(2)
            sem = self._thumb_sema
        if not sem.acquire(timeout=1.0):
            raise FileNotFoundError("immich thumb backlog")
        try:
            got = self._fetch_api_image(
                self.thumb_url(asset_id, size="thumbnail"), timeout=3
            )
            if got:
                return got[0], got[1], "immich-api"
        finally:
            sem.release()
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
