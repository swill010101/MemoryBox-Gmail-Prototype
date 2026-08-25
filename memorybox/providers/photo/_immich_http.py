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
_PERSON_TIMELINE_YEAR_BUDGET = 80
_PERSON_TIMELINE_MONTH_BUDGET = 18
_PERSON_TIMELINE_MONTH_WALK = 720
_PERSON_LIB_CACHE_VER = "v10"


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
        if self.thumbs_root is None:
            _LOG.warning("IMMICH_THUMBS_PATH unset; /library/media/photo will 204")
        elif not self.thumbs_root.is_dir():
            _LOG.warning("IMMICH_THUMBS_PATH is not a directory: %s", self.thumbs_root)

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
            "person_library_unwindowed_n": getattr(self, "_person_library_unwindowed_n", None),
            "person_assets_in_window_n": getattr(self, "_person_assets_in_window_n", None),
            "person_stills_in_window_n": getattr(self, "_person_stills_in_window_n", None),
            "person_videos_in_window_n": getattr(self, "_person_videos_in_window_n", None),
            "year_fair_applied": getattr(self, "_year_fair_applied", None),
            "immich_person_asset_count": getattr(self, "_immich_person_asset_count", None),
            "query_time_windows": [
                list(w) for w in (getattr(self, "_timeline_windows", ()) or ())
            ],
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
        """Do not ping a restarting NAS. Serve cache or empty until Ask restarts."""
        return

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
        path = disk / f"{_PERSON_LIB_CACHE_VER}-{cache_key.replace('/', '_')[:80]}.json"
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
            path = disk / f"{_PERSON_LIB_CACHE_VER}-{cache_key.replace('/', '_')[:80]}.json"
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
            or (
                p.startswith("/people/")
                and "?" not in p
                and "/thumbnail" not in p
                and "/faces" not in p
            )
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

    def get_person(self, person_id: str) -> dict[str, Any] | None:
        """Cheap Immich person record (name + id). Used to reject stale mappings."""
        pid = (person_id or "").strip()
        if not pid:
            return None
        cached = getattr(self, "_person_rec", None)
        if isinstance(cached, dict) and pid in cached:
            return cached[pid]
        try:
            status, data = self._request("GET", f"/people/{pid}", timeout=6, retries=1)
        except Exception as exc:  # noqa: BLE001
            self._note_transport_fail(exc)
            return None
        if status == 200 and isinstance(data, dict) and data.get("id"):
            store = getattr(self, "_person_rec", None)
            if store is None:
                self._person_rec = {}
                store = self._person_rec
            store[pid] = data
            return data
        return None

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
        self,
        person_ids: list[str],
        *,
        size: int = 50,
        time_windows: tuple[tuple[str, str], ...] | list[tuple[str, str]] | None = None,
        need_location: bool = False,
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
        self._timeline_windows = tuple(time_windows or ())
        self._reset_call_log()
        self._person_lib_incomplete = False
        target = max(1, min(int(size), 5000))
        reported = self._reported_person_asset_count(person_ids)
        self._immich_person_asset_count = reported
        cache_key = (
            f"{_PERSON_LIB_CACHE_VER}:"
            + ",".join(sorted(str(p).strip() for p in person_ids if str(p).strip()))
        )
        cached = self._read_person_lib_cache(cache_key, allow_stale=True)
        if cached and reported and len(cached) < max(40, int(reported * 0.4)):
            cached = None
            self._last_person_source = "cache_skipped_truncated"
        if cached:
            self._last_person_source = "cache"
            rows: list[dict[str, Any]] = [
                dict(it) if isinstance(it, dict) else it for it in cached
            ]
            if need_location:
                by_cached: dict[str, dict[str, Any]] = {}
                for it in rows:
                    if not isinstance(it, dict):
                        continue
                    eid = str(it.get("id") or "").strip()
                    if eid:
                        by_cached[eid] = it
                self._merge_map_marker_gps(by_cached)
                rows = list(by_cached.values()) or rows
            windowed = self._filter_assets_to_windows(
                rows, getattr(self, "_timeline_windows", ()) or ()
            )
            return self._finalize_person_library(rows, windowed, target)
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
            self._merge_map_marker_gps(by_id)
            self._last_person_source = "faces_or_timeline"
            full = list(by_id.values())
            # Never cache a truncated walk — FlightSim re-asks kept 2015-only Peggy.
            # Cache the unwindowed library so Christmas / year asks reuse it.
            if full and not self._circuit() and not getattr(self, "_person_lib_incomplete", False):
                self._write_person_lib_cache(cache_key, full)
            windowed = self._filter_assets_to_windows(
                full, getattr(self, "_timeline_windows", ()) or ()
            )
            return self._finalize_person_library(full, windowed, target)
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
            full = list(by_id.values())
            if not self._circuit() and not getattr(self, "_person_lib_incomplete", False):
                self._write_person_lib_cache(cache_key, full)
            windowed = self._filter_assets_to_windows(
                full, getattr(self, "_timeline_windows", ()) or ()
            )
            return self._finalize_person_library(full, windowed, target)
        self._last_person_source = "timeout" if self._circuit() else "empty"
        return []

    def _reported_person_asset_count(self, person_ids: list[str]) -> int | None:
        """Immich person record totals — compare with what this walk actually kept."""
        total = 0
        saw = False
        for pid in person_ids:
            rec = self.get_person(str(pid or "").strip()) or {}
            for key in ("assetCount", "assetsCount", "assets"):
                raw = rec.get(key)
                if isinstance(raw, bool):
                    continue
                if isinstance(raw, (int, float)) and int(raw) > 0:
                    total += int(raw)
                    saw = True
                    break
                if isinstance(raw, dict):
                    n = raw.get("total") or raw.get("count")
                    if n not in (None, ""):
                        try:
                            total += int(n)
                            saw = True
                            break
                        except (TypeError, ValueError):
                            pass
        return total if saw else None

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
            # Walk the full person timeline. Ask windows filter assets after
            # cache — never cache a January walk as the unwindowed library.
            raw_buckets = self._list_person_time_buckets(pid)
            by_year = self._group_buckets_by_year(raw_buckets)
            years = sorted(by_year.keys(), reverse=True)
            month_mode = any(len(v) > 1 for v in by_year.values()) or any(
                self._stamp_is_month(s) for s in raw_buckets
            )
            budget = _PERSON_TIMELINE_YEAR_BUDGET
            self._timeline_http = 0
            self._person_lib_incomplete = False
            if month_mode:
                stamps = raw_buckets[:_PERSON_TIMELINE_MONTH_WALK]
                if len(raw_buckets) > _PERSON_TIMELINE_MONTH_WALK:
                    self._person_lib_incomplete = True
                for tb in stamps:
                    if self._circuit():
                        self._person_lib_incomplete = True
                        break
                    for it in self._list_person_bucket_assets(pid, tb, size="MONTH"):
                        eid = str(it.get("id") or "").strip()
                        if not eid or eid in by_id:
                            continue
                        people = it.get("people")
                        if not isinstance(people, list) or not people:
                            it = dict(it)
                            it["people"] = [{"id": pid}]
                        by_id[eid] = it
                continue
            if len(years) > budget:
                self._person_lib_incomplete = True
            years_walked = 0
            for year in years[:budget]:
                if self._circuit():
                    self._person_lib_incomplete = True
                    break
                years_walked += 1
                rows = self._list_person_year_assets(pid, year, by_year.get(year) or [])
                for it in rows:
                    eid = str(it.get("id") or "").strip()
                    if not eid or eid in by_id:
                        continue
                    people = it.get("people")
                    if not isinstance(people, list) or not people:
                        it = dict(it)
                        it["people"] = [{"id": pid}]
                    by_id[eid] = it
            if years_walked < min(len(years), budget):
                self._person_lib_incomplete = True
        return list(by_id.values())

    def _list_person_time_buckets(self, person_id: str) -> list[str]:
        pid = (person_id or "").strip()
        if not pid:
            return []
        tmpls = (
            "/timeline/buckets?personId={pid}&size=MONTH",
            "/timeline/buckets?personId={pid}&size=YEAR",
            "/timeline/buckets?personIds={pid}&size=MONTH",
            "/assets/time-buckets?personId={pid}&size=MONTH",
            "/asset/time-buckets?personId={pid}&size=MONTH",
            "/timeline/buckets?personId={pid}",
        )
        sticky = getattr(self, "_person_buckets_tmpl", None)
        if sticky and "MONTH" not in str(sticky):
            sticky = None
        use = (sticky,) if sticky in tmpls else tmpls
        year_only: list[str] | None = None
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
                # Never sticky a YEAR bucket list — it hides months (Tom/Sue holes).
                if "MONTH" in tmpl:
                    self._person_buckets_tmpl = tmpl
                    return self._sort_time_buckets_newest_first(out)
                if getattr(self, "_person_buckets_tmpl", None) and "MONTH" in str(
                    getattr(self, "_person_buckets_tmpl")
                ):
                    continue
                year_only = out
                continue
        if year_only:
            return self._sort_time_buckets_newest_first(year_only)
        return []

    @staticmethod
    def _sort_time_buckets_newest_first(buckets: list[str]) -> list[str]:
        """Newest year/month first. Never walk 1900→1983 and drop the rest."""

        def _key(raw: str) -> str:
            s = str(raw or "").strip()
            return s[:10] if len(s) >= 4 else s

        return sorted((b for b in buckets if str(b).strip()), key=_key, reverse=True)

    @staticmethod
    def _collapse_buckets_to_years(buckets: list[str]) -> list[str]:
        """One Immich timeBucket string per year (keep the real stamp).

        Rewriting to YYYY-01-01 makes GET /timeline/bucket miss recent years
        when Immich only knows 2025-12-01 (FlightSim: latest looked like 2015).
        """
        years: list[str] = []
        seen: set[str] = set()
        for raw in ImmichHttpClient._sort_time_buckets_newest_first(buckets):
            s = str(raw or "").strip()
            y = s[:4]
            if len(y) != 4 or not y.isdigit() or y in seen:
                continue
            seen.add(y)
            years.append(s)
        return years

    @staticmethod
    def _group_buckets_by_year(buckets: list[str]) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for raw in ImmichHttpClient._sort_time_buckets_newest_first(buckets):
            s = str(raw or "").strip()
            y = s[:4]
            if len(y) != 4 or not y.isdigit():
                continue
            grouped.setdefault(y, []).append(s)
        return grouped

    @staticmethod
    def _stamp_is_month(raw: str) -> bool:
        s = str(raw or "").strip()
        if len(s) < 7 or s[4] != "-":
            return False
        mm = s[5:7]
        return mm.isdigit() and mm != "01"

    def _list_person_year_assets(
        self, person_id: str, year: str, month_stamps: list[str]
    ) -> list[dict[str, Any]]:
        """Full year first (ISO YEAR bucket). Month stamps only if YEAR is empty.

        A December stamp + size=YEAR does not match Immich date_trunc('year'),
        so Tom/Sue looked like 2026 / 2023 / 2022 holes with a few hundred photos.
        """
        y = str(year or "").strip()[:4]
        if len(y) != 4 or not y.isdigit():
            return []
        year_stamps = (
            f"{y}-01-01T00:00:00.000Z",
            f"{y}-01-01",
        )
        for tb in year_stamps:
            items = self._list_person_bucket_assets(person_id, tb, size="YEAR")
            if items:
                return items
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tb in month_stamps:
            for it in self._list_person_bucket_assets(person_id, tb, size="MONTH"):
                eid = str(it.get("id") or "").strip()
                if not eid or eid in seen:
                    continue
                seen.add(eid)
                out.append(it)
        return out

    @staticmethod
    def _filter_years_to_windows(
        years: list[str],
        windows: tuple[tuple[str, str], ...] | list[tuple[str, str]] | None,
    ) -> list[str]:
        """Keep year buckets that overlap Ask time windows (Christmas / a year)."""
        if not windows:
            return list(years)
        keep: list[str] = []
        for yb in years:
            y = str(yb or "")[:4]
            if not y.isdigit():
                continue
            yi = int(y)
            for start, end in windows:
                try:
                    a = int(str(start)[:4])
                    b = int(str(end)[:4])
                except (TypeError, ValueError):
                    continue
                if a <= yi <= b:
                    keep.append(yb)
                    break
        return keep

    def _filter_assets_to_windows(
        self,
        rows: list[dict[str, Any]],
        windows: tuple[tuple[str, str], ...] | list[tuple[str, str]] | None,
    ) -> list[dict[str, Any]]:
        """Keep assets whose taken date falls in Ask windows (after cache)."""
        if not windows:
            return list(rows)
        from memorybox.planner.temporal import date_in_windows

        out: list[dict[str, Any]] = []
        for it in rows:
            iso = self._asset_taken_iso(it)
            if not iso:
                # Face stubs without EXIF stay (Explore undated gallery).
                out.append(it)
                continue
            if date_in_windows(iso, windows):
                out.append(it)
        return out

    @staticmethod
    def _asset_taken_iso(raw: dict[str, Any] | None) -> str | None:
        if not isinstance(raw, dict):
            return None
        exif = raw.get("exifInfo") if isinstance(raw.get("exifInfo"), dict) else {}
        for taken in (
            exif.get("dateTimeOriginal"),
            exif.get("dateTime"),
            raw.get("localDateTime"),
            raw.get("takenAt"),
            raw.get("fileCreatedAt"),
        ):
            if isinstance(taken, str) and len(taken.strip()) >= 8:
                return taken.strip()
        return None

    def _list_person_bucket_assets(
        self, person_id: str, time_bucket: str, *, size: str = "YEAR"
    ) -> list[dict[str, Any]]:
        pid = (person_id or "").strip()
        tb = (time_bucket or "").strip()
        if not pid or not tb:
            return []
        from urllib.parse import quote

        qtb = quote(tb, safe=":-T.Z")
        year_tmpls = (
            "/timeline/bucket?timeBucket={qtb}&personId={pid}&size=YEAR&withCoordinates=true",
            "/timeline/bucket?timeBucket={qtb}&personIds={pid}&size=YEAR&withCoordinates=true",
            "/timeline/bucket?timeBucket={qtb}&personId={pid}&size=YEAR",
            "/timeline/bucket?timeBucket={qtb}&personIds={pid}&size=YEAR",
        )
        month_tmpls = (
            "/timeline/bucket?timeBucket={qtb}&personId={pid}&size=MONTH&withCoordinates=true",
            "/timeline/bucket?timeBucket={qtb}&personIds={pid}&size=MONTH&withCoordinates=true",
            "/timeline/bucket?timeBucket={qtb}&personId={pid}&withCoordinates=true",
            "/timeline/bucket?timeBucket={qtb}&personIds={pid}&withCoordinates=true",
            "/timeline/bucket?timeBucket={qtb}&personId={pid}&size=MONTH",
            "/timeline/bucket?timeBucket={qtb}&personIds={pid}&size=MONTH",
            "/timeline/bucket?timeBucket={qtb}&personId={pid}",
            "/timeline/bucket?timeBucket={qtb}&personIds={pid}",
        )
        tmpls = year_tmpls if str(size).upper() == "YEAR" else month_tmpls
        attr = "_person_year_tmpl" if str(size).upper() == "YEAR" else "_person_month_tmpl"
        sticky = getattr(self, attr, None)
        use = (sticky,) if sticky in tmpls else tmpls
        for tmpl in use:
            path = tmpl.format(qtb=qtb, pid=pid)
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
            items = self._normalize_timeline_assets(data)
            if items:
                self._timeline_http = int(getattr(self, "_timeline_http", 0) or 0) + 1
                setattr(self, attr, tmpl)
                return self._coerce_asset_dates_to_bucket_year(items, tb)
        return []

    @staticmethod
    def _row_is_video(raw: Any) -> bool:
        if not isinstance(raw, dict):
            return False
        if raw.get("isVideo") is True:
            return True
        return str(raw.get("type") or "").lower() == "video"

    @staticmethod
    def year_fair_should_apply(time_windows: Any, n: int, target: int) -> bool:
        """Year-fair subsample is for uncapped libraries, not dated Ask windows.

        A January Ask showing initial_candidate_count=9 was membership after the
        window filter (and sometimes a year-fair subsample of that month), not a
        Person-library cap of 9. Cache stays unwindowed; windowed Asks return
        every in-window asset.
        """
        if time_windows:
            return False
        return int(n) > int(target)

    def _finalize_person_library(
        self,
        full: list[dict[str, Any]],
        windowed: list[dict[str, Any]],
        target: int,
    ) -> list[dict[str, Any]]:
        windows = getattr(self, "_timeline_windows", ()) or ()
        self._person_library_unwindowed_n = len(full)
        self._person_assets_in_window_n = len(windowed)
        stills = sum(1 for it in windowed if not self._row_is_video(it))
        vids = len(windowed) - stills
        self._person_stills_in_window_n = stills
        self._person_videos_in_window_n = vids
        reported = getattr(self, "_immich_person_asset_count", None)
        if reported and len(full) < max(40, int(reported * 0.4)):
            self._person_lib_incomplete = True
        if not self.year_fair_should_apply(windows, len(windowed), target):
            self._year_fair_applied = False
            return windowed
        out = self._year_fair_assets(windowed, target)
        self._year_fair_applied = len(out) < len(windowed)
        return out

    @staticmethod
    def _year_fair_assets(
        rows: list[dict[str, Any]], target: int
    ) -> list[dict[str, Any]]:
        """Keep every year when the person library is larger than the Ask cap."""
        if len(rows) <= target:
            return rows
        by_y: dict[int, list[dict[str, Any]]] = {}
        for it in rows:
            y = ImmichHttpClient._asset_year(it) or 0
            by_y.setdefault(y, []).append(it)
        years = sorted(by_y.keys(), reverse=True)
        out: list[dict[str, Any]] = []
        seen: set[int] = set()
        idxs = {y: 0 for y in years}
        while len(out) < target:
            progressed = False
            for y in years:
                i = idxs[y]
                bucket = by_y[y]
                if i >= len(bucket):
                    continue
                aid = id(bucket[i])
                if aid in seen:
                    idxs[y] = i + 1
                    continue
                seen.add(aid)
                out.append(bucket[i])
                idxs[y] = i + 1
                progressed = True
                if len(out) >= target:
                    break
            if not progressed:
                break
        return out

    @staticmethod
    def _asset_year(raw: Any) -> int | None:
        if isinstance(raw, dict):
            exif = raw.get("exifInfo") if isinstance(raw.get("exifInfo"), dict) else {}
            candidates = (
                exif.get("dateTimeOriginal"),
                exif.get("dateTime"),
                raw.get("localDateTime"),
                raw.get("takenAt"),
                raw.get("fileCreatedAt"),
            )
        else:
            candidates = (raw,)
        for taken in candidates:
            if not isinstance(taken, str) or len(taken.strip()) < 4:
                continue
            y = taken.strip()[:4]
            if y.isdigit():
                yi = int(y)
                if 1800 <= yi <= 2100:
                    return yi
        return None

    @staticmethod
    def _coerce_asset_dates_to_bucket_year(
        items: list[dict[str, Any]], time_bucket: str
    ) -> list[dict[str, Any]]:
        """YEAR buckets often stamp fileCreatedAt as Immich import day (2023).

        Keep EXIF when it matches the bucket year. Otherwise pin localDateTime
        to mid-year so Explore timeline density follows the walk, not import.
        """
        y = str(time_bucket or "").strip()[:4]
        if not (len(y) == 4 and y.isdigit()):
            return items
        year = int(y)
        out: list[dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            row = dict(it)
            exif = row.get("exifInfo") if isinstance(row.get("exifInfo"), dict) else {}
            exif_year = ImmichHttpClient._asset_year(
                {
                    "exifInfo": exif,
                    "localDateTime": None,
                    "takenAt": None,
                    "fileCreatedAt": None,
                }
            )
            if exif_year == year:
                out.append(row)
                continue
            if ImmichHttpClient._asset_year(row) == year:
                out.append(row)
                continue
            row["localDateTime"] = f"{year}-07-01T12:00:00"
            out.append(row)
        return out

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
        states = _col("state")
        countries = _col("country")
        lats = _col("latitude") or _col("lat")
        lons = _col("longitude") or _col("lng") or _col("lon")
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
            state = states[i] if i < len(states) else None
            country = countries[i] if i < len(countries) else None
            lat = ImmichHttpClient._float_or_none(lats[i] if i < len(lats) else None)
            lon = ImmichHttpClient._float_or_none(lons[i] if i < len(lons) else None)
            ImmichHttpClient._stamp_gps(
                row,
                lat=lat,
                lon=lon,
                city=city,
                state=state,
                country=country,
            )
            out.append(row)
        return out

    @staticmethod
    def _float_or_none(v: Any) -> float | None:
        if v is None or isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            fv = float(v)
            if fv != fv:  # NaN
                return None
            return fv
        s = str(v).strip()
        if not s or s.lower() in ("none", "null"):
            return None
        try:
            fv = float(s)
        except ValueError:
            return None
        if fv != fv:
            return None
        return fv

    @staticmethod
    def _stamp_gps(
        row: dict[str, Any],
        *,
        lat: float | None,
        lon: float | None,
        city: Any = None,
        state: Any = None,
        country: Any = None,
    ) -> None:
        if lat is not None:
            row["latitude"] = lat
        if lon is not None:
            row["longitude"] = lon
        city_s = str(city).strip() if city not in (None, "") else ""
        state_s = str(state).strip() if state not in (None, "") else ""
        country_s = str(country).strip() if country not in (None, "") else ""
        if not any((lat is not None, lon is not None, city_s, state_s, country_s)):
            return
        exif = row.get("exifInfo") if isinstance(row.get("exifInfo"), dict) else {}
        exif = dict(exif)
        if lat is not None:
            exif["latitude"] = lat
        if lon is not None:
            exif["longitude"] = lon
        if city_s:
            exif["city"] = city_s
        if state_s:
            exif["state"] = state_s
        if country_s:
            exif["country"] = country_s
        row["exifInfo"] = exif

    def _merge_map_marker_gps(self, by_id: dict[str, dict[str, Any]]) -> None:
        """Join Immich map markers onto the person library (pins without metadata RST)."""
        if not by_id:
            return
        try:
            status, data = self._request("GET", "/map/markers", timeout=8, retries=1)
        except Exception:  # noqa: BLE001
            return
        if status != 200:
            return
        rows = data if isinstance(data, list) else (
            (data.get("markers") or data.get("items")) if isinstance(data, dict) else None
        )
        if not isinstance(rows, list):
            return
        for m in rows:
            if not isinstance(m, dict):
                continue
            aid = str(m.get("id") or m.get("assetId") or m.get("asset_id") or "").strip()
            if not aid or aid not in by_id:
                continue
            lat = self._float_or_none(
                m.get("lat") if m.get("lat") is not None else m.get("latitude")
            )
            lon = self._float_or_none(
                m.get("lon")
                if m.get("lon") is not None
                else (m.get("lng") if m.get("lng") is not None else m.get("longitude"))
            )
            if lat is None or lon is None:
                continue
            self._stamp_gps(
                by_id[aid],
                lat=lat,
                lon=lon,
                city=m.get("city"),
                state=m.get("state"),
                country=m.get("country"),
            )

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
        memo = getattr(self, "_name_hits", None)
        if memo is None:
            self._name_hits = {}
            memo = self._name_hits
        ck = q.lower()
        if ck in memo:
            return list(memo[ck])[:limit]
        tokens = [q]
        first = q.split()[0]
        if first.lower() != q.lower() and first.lower() not in memo:
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
            memo[ck] = list(hits)
            if first.lower() != q.lower():
                memo[first.lower()] = list(hits)
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
        # One GET. withFaces / /faces 404s were extra Immich hits before timeline.
        rec = self.get_person(pid)
        if rec:
            usable = self._faces_from_people_payload(pid, rec)
            if usable:
                return usable
        for path in (
            f"/people/{pid}?withFaces=true",
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

    def list_faces_for_asset(self, asset_id: str) -> list[dict[str, Any]]:
        """GET /faces?id={assetId} — complete boxes + imageWidth/imageHeight.

        Required for I8B crops. GET /people/{id} feature faces are not a catalog.
        """
        from urllib.parse import quote

        aid = self._immich_asset_id(asset_id)
        if not aid or self._circuit():
            return []
        try:
            status, data = self._request(
                "GET",
                f"/faces?id={quote(aid)}",
                timeout=8,
                retries=1,
            )
        except Exception as exc:  # noqa: BLE001
            self._note_transport_fail(exc)
            return []
        if status != 200:
            return []
        if isinstance(data, list):
            rows = [f for f in data if isinstance(f, dict)]
        elif isinstance(data, dict):
            raw = data.get("faces") or data.get("items") or data.get("data") or []
            rows = [f for f in raw if isinstance(f, dict)]
        else:
            rows = []
        for f in rows:
            if not f.get("assetId"):
                f["assetId"] = aid
        return rows

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

    def _thumb_paths(self, asset_id: str) -> tuple[str, ...]:
        aid = (asset_id or "").strip()
        sticky = getattr(self, "_thumb_tmpl", None)
        tmpls = (
            "/assets/{id}/thumbnail?size=thumbnail",
            "/assets/{id}/thumbnail?size=preview",
            "/assets/{id}/thumbnail?size=WEB",
            "/asset/thumbnail/{id}",
        )
        if sticky in tmpls:
            return (sticky.format(id=aid),)
        return tuple(t.format(id=aid) for t in tmpls)

    @staticmethod
    def _thumb_search_roots(root: Path) -> list[Path]:
        """IMMICH_THUMBS_PATH may be thumbs/ or the Immich library/upload parent."""
        roots: list[Path] = []
        if root.is_dir():
            roots.append(root)
            nested = root / "thumbs"
            if nested.is_dir() and nested.resolve() != root.resolve():
                roots.append(nested)
        return roots

    @staticmethod
    def _thumb_path_candidates(root: Path, aid: str) -> list[Path]:
        """Immich on-disk layouts (old prefix + current owner/aa/bb nest)."""
        prefix = aid[:2]
        nest = aid[2:4] if len(aid) >= 4 else ""
        names = (
            f"{aid}-thumbnail.webp",
            f"{aid}-preview.webp",
            f"{aid}-thumbnail.jpeg",
            f"{aid}-preview.jpeg",
            f"{aid}_thumbnail.webp",
            f"{aid}_preview.webp",
            f"{aid}.webp",
            f"{aid}.jpeg",
            f"{aid}.jpg",
        )
        out: list[Path] = []

        def _add(base: Path) -> None:
            for name in names:
                out.append(base / prefix / name)
                out.append(base / prefix / aid / name)
                if nest:
                    out.append(base / prefix / nest / name)
                    out.append(base / prefix / nest / aid / name)

        _add(root)
        try:
            users = [p for p in root.iterdir() if p.is_dir()][:16]
        except OSError:
            users = []
        for user in users:
            # Skip the 2-char hex shard dirs so we do not recurse the same tree.
            if len(user.name) == 2:
                continue
            _add(user)
        return out

    def _read_local_thumb(self, asset_id: str) -> tuple[bytes, str] | None:
        """Immich thumbs on disk — no HTTP, no NAS API bounce."""
        root = self.thumbs_root
        aid = (asset_id or "").strip()
        if root is None or not aid:
            return None
        seen: set[str] = set()
        paths: list[Path] = []
        for search in self._thumb_search_roots(root):
            paths.extend(self._thumb_path_candidates(search, aid))
            prefix = aid[:2]
            nest = aid[2:4] if len(aid) >= 4 else ""
            globs = (
                f"{prefix}/{aid}-thumbnail.webp",
                f"{prefix}/{nest}/{aid}-thumbnail.webp" if nest else "",
                f"*/{prefix}/{aid}-thumbnail.webp",
                f"*/{prefix}/{nest}/{aid}-thumbnail.webp" if nest else "",
                f"*/{prefix}/{nest}/{aid}-preview.webp" if nest else "",
            )
            for pattern in globs:
                if not pattern:
                    continue
                try:
                    paths.extend(search.glob(pattern))
                except OSError:
                    continue
        for path in paths:
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            try:
                if not path.is_file() or path.stat().st_size < 24:
                    continue
                data = path.read_bytes()
            except OSError:
                continue
            if not data or data[:1] in (b"{", b"["):
                continue
            suf = path.suffix.lower()
            ctype = "image/webp" if suf == ".webp" else "image/jpeg"
            return data, ctype
        return None

    def _encoded_video_roots(self) -> list[Path]:
        root = self.thumbs_root
        if root is None:
            return []
        out: list[Path] = []
        seen: set[str] = set()

        def _add(p: Path) -> None:
            try:
                key = str(p.resolve())
            except OSError:
                key = str(p)
            if key in seen or not p.is_dir():
                return
            seen.add(key)
            out.append(p)

        for base in (root, root.parent):
            _add(base / "encoded-video")
            if base.name.lower() in {"encoded-video", "encoded_video"}:
                _add(base)
        return out

    def find_local_encoded_video(self, asset_id: str) -> Path | None:
        """Immich transcoded MP4 on disk (sibling of thumbs/)."""
        aid = (asset_id or "").strip()
        if not aid:
            return None
        prefix = aid[:2]
        nest = aid[2:4] if len(aid) >= 4 else ""
        names = (f"{aid}.mp4", f"{aid}.webm", f"{aid}.m4v")
        paths: list[Path] = []
        for search in self._encoded_video_roots():
            for name in names:
                paths.append(search / prefix / name)
                if nest:
                    paths.append(search / prefix / nest / name)
            try:
                users = [p for p in search.iterdir() if p.is_dir()][:16]
            except OSError:
                users = []
            for user in users:
                if len(user.name) == 2:
                    continue
                for name in names:
                    paths.append(user / prefix / name)
                    if nest:
                        paths.append(user / prefix / nest / name)
            globs = [
                f"{prefix}/{aid}.mp4",
                f"*/{prefix}/{aid}.mp4",
            ]
            if nest:
                globs.extend(
                    (
                        f"{prefix}/{nest}/{aid}.mp4",
                        f"*/{prefix}/{nest}/{aid}.mp4",
                    )
                )
            for pattern in globs:
                try:
                    paths.extend(search.glob(pattern))
                except OSError:
                    continue
        seen: set[str] = set()
        for path in paths:
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            try:
                if path.is_file() and path.stat().st_size > 64:
                    return path
            except OSError:
                continue
        return None

    def open_video_playback(self, asset_id: str, range_header: str | None):
        """Immich transcoded playback stream (API key + Range)."""
        aid = (asset_id or "").strip()
        if not aid:
            raise FileNotFoundError("missing asset id")
        headers = {"x-api-key": self._key, "Accept": "video/*,*/*"}
        if range_header:
            headers["Range"] = range_header
        last_err: Exception | None = None
        for path in (
            f"/assets/{aid}/video/playback",
            f"/assets/{aid}/original",
        ):
            url = f"{self.api_base}{path}"
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                return urllib.request.urlopen(req, timeout=120)
            except urllib.error.HTTPError as exc:
                last_err = exc
                if exc.code in {401, 403, 404}:
                    continue
                raise
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                continue
        raise FileNotFoundError(str(last_err or "immich video playback missing"))

    def _thumb_missed(self, asset_id: str) -> bool:
        store = getattr(self, "_thumb_miss", None)
        if not isinstance(store, dict):
            return False
        ts = store.get(asset_id)
        if ts is None:
            return False
        if time.time() - float(ts) > 300:
            store.pop(asset_id, None)
            return False
        return True

    def _mark_thumb_miss(self, asset_id: str) -> None:
        store = getattr(self, "_thumb_miss", None)
        if store is None:
            self._thumb_miss = {}
            store = self._thumb_miss
        store[asset_id] = time.time()
        if len(store) > 4000:
            oldest = sorted(store.items(), key=lambda kv: kv[1])[:2000]
            for key, _ in oldest:
                store.pop(key, None)

    def _fetch_api_image(self, url: str, timeout: float = 3) -> tuple[bytes, str] | None:
        if self._circuit():
            return None
        req = urllib.request.Request(
            url,
            headers={"x-api-key": self._key, "Accept": "image/*,*/*"},
            method="GET",
        )
        t0 = time.monotonic()
        path = url.split("/api", 1)[-1][:160]
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                ms = (time.monotonic() - t0) * 1000
                if not data or len(data) < 24:
                    return None
                ctype = resp.headers.get("Content-Type") or "image/jpeg"
                if "json" in ctype or data[:1] in (b"{", b"["):
                    return None
                self._record_call("GET", path, status=200, ms=ms)
                return data, ctype
        except urllib.error.HTTPError as exc:
            ms = (time.monotonic() - t0) * 1000
            self._record_call("GET", path, status=int(exc.code), ms=ms, err=str(exc)[:160])
            if int(exc.code) in (401, 403):
                self._thumb_forbidden = True
            # 4xx means Immich answered. Do not open the transport circuit.
            return None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            ms = (time.monotonic() - t0) * 1000
            self._record_call("GET", path, status=0, ms=ms, err=str(exc)[:160])
            self._note_transport_fail(exc)
            return None

    def fetch_preview_bytes(self, asset_id: str) -> tuple[bytes, str, str]:
        aid = (asset_id or "").strip()
        if not aid:
            raise FileNotFoundError("missing asset id")
        local = self._read_local_thumb(aid)
        if local:
            return local[0], local[1], "immich-thumbs-path"
        if self._thumb_missed(aid):
            raise FileNotFoundError("immich thumb miss cached")
        import os

        api_on = (
            os.environ.get("IMMICH_THUMBS_API")
            or os.environ.get("MEMORYBOX_IMMICH_THUMBS_API")
            or ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        if not api_on:
            self._mark_thumb_miss(aid)
            raise FileNotFoundError("immich thumb API disabled; set IMMICH_THUMBS_PATH")
        if getattr(self, "_thumb_forbidden", False):
            raise FileNotFoundError("immich API key lacks asset.view")
        if self._circuit():
            raise FileNotFoundError("immich circuit open")
        sem = getattr(self, "_thumb_sema", None)
        if sem is None:
            self._thumb_sema = threading.Semaphore(2)
            sem = self._thumb_sema
        if not sem.acquire(timeout=1.0):
            raise FileNotFoundError("immich thumb backlog")
        try:
            for path in self._thumb_paths(aid):
                if self._circuit() or getattr(self, "_thumb_forbidden", False):
                    break
                got = self._fetch_api_image(self.api_base + path, timeout=3)
                if got:
                    raw_tmpl = path.replace(aid, "{id}")
                    self._thumb_tmpl = raw_tmpl
                    return got[0], got[1], "immich-api"
        finally:
            sem.release()
        self._mark_thumb_miss(aid)
        raise FileNotFoundError(
            "No thumbnail available via Immich API (needs asset.view on API key)"
        )

    def fetch_person_thumbnail_bytes(
        self, person_id: str
    ) -> tuple[bytes, str, str] | None:
        """Immich preferred person thumbnail (feature face / person thumb).

        Does not fall through to a random face-list still — that is not the
        Immich UI preferred crop.
        """
        pid = (person_id or "").strip()
        if not pid:
            return None
        disk = self._read_local_person_thumb(pid)
        if disk:
            return disk[0], disk[1], "immich-person-disk"
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
                local = self._read_local_thumb(asset_id)
                if local:
                    return local[0], local[1], "immich-feature-face-disk"
                try:
                    data_b, ctype, src = self.fetch_preview_bytes(asset_id)
                    return data_b, ctype, src
                except Exception:  # noqa: BLE001
                    continue
        return None

    def _read_local_person_thumb(self, person_id: str) -> tuple[bytes, str] | None:
        """On-disk Immich person preferred thumb (`{personId}.jpeg` nest)."""
        root = self.thumbs_root
        pid = (person_id or "").strip()
        if root is None or not pid:
            return None
        names = (
            f"{pid}.jpeg",
            f"{pid}.jpg",
            f"{pid}.webp",
            f"{pid}-preview.jpeg",
            f"{pid}-thumbnail.webp",
        )
        paths: list[Path] = []
        for search in self._thumb_search_roots(root):
            paths.extend(self._thumb_path_candidates(search, pid))
            prefix = pid[:2]
            nest = pid[2:4] if len(pid) >= 4 else ""
            for pattern in (
                f"{prefix}/{nest}/{pid}.jpeg" if nest else "",
                f"*/{prefix}/{nest}/{pid}.jpeg" if nest else "",
                f"*/{prefix}/{nest}/{pid}.webp" if nest else "",
            ):
                if not pattern:
                    continue
                try:
                    paths.extend(search.glob(pattern))
                except OSError:
                    continue
            try:
                users = [p for p in search.iterdir() if p.is_dir()][:16]
            except OSError:
                users = []
            for user in users:
                if len(user.name) == 2:
                    continue
                base = user / prefix / nest if nest else user / prefix
                for name in names:
                    paths.append(base / name)
        seen: set[str] = set()
        for path in paths:
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            try:
                if not path.is_file() or path.stat().st_size < 24:
                    continue
                data = path.read_bytes()
            except OSError:
                continue
            if not data or data[:1] in (b"{", b"["):
                continue
            suf = path.suffix.lower()
            ctype = "image/webp" if suf == ".webp" else "image/jpeg"
            return data, ctype
        return None
