"""HTTP client for sibling Video Intelligence / HVRT worker (config URL only)."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from memorybox.providers.base import ProviderError, ProviderHealth, ProviderUnavailable
from memorybox.providers.video.dto import (
    VideoAssetDto,
    VideoFaceCandidate,
    VideoPresenceSpan,
    VideoSearchQuery,
    VideoSegmentHit,
)

PROVIDER_KEY = "hvrt"


class HvrtHttpVideoProvider:
    """Talks to sibling worker over configured base URL — never hard-codes hosts."""

    provider_key = PROVIDER_KEY

    def __init__(self, *, base_url: str, timeout_sec: float = 30.0) -> None:
        raw = (base_url or "").strip().rstrip("/")
        if not raw:
            raise ProviderUnavailable("MEMORYBOX_VIDEO_WORKER_URL is empty")
        self.base_url = raw
        self.timeout_sec = timeout_sec

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"video worker HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ProviderUnavailable(f"video worker unreachable: {exc}") from exc
        except TimeoutError as exc:
            raise ProviderUnavailable("video worker timeout") from exc

    def health(self) -> ProviderHealth:
        try:
            data = self._request("GET", "/health")
            ok = bool(data.get("ok"))
            return ProviderHealth(
                provider_key=self.provider_key,
                ok=ok,
                detail=str(data.get("detail") or ("ok" if ok else "unhealthy")),
                meta={k: v for k, v in data.items() if k not in {"ok", "detail"}},
            )
        except ProviderUnavailable as exc:
            return ProviderHealth(
                provider_key=self.provider_key, ok=False, detail=str(exc)
            )
        except ProviderError as exc:
            return ProviderHealth(
                provider_key=self.provider_key, ok=False, detail=str(exc)
            )

    def list_videos(self, *, limit: int = 100) -> list[VideoAssetDto]:
        data = self._request("GET", f"/videos?limit={int(limit)}")
        out: list[VideoAssetDto] = []
        for row in data.get("videos") or []:
            out.append(
                VideoAssetDto(
                    provider_key=self.provider_key,
                    external_id=str(row["external_id"]),
                    title=row.get("title"),
                    path_hint=row.get("path_hint"),
                    duration_sec=row.get("duration_sec"),
                )
            )
        return out

    def list_face_candidates(
        self, *, video_external_id: str | None = None, limit: int = 100
    ) -> list[VideoFaceCandidate]:
        q = f"limit={int(limit)}"
        if video_external_id:
            q += f"&video_external_id={urllib.parse.quote(video_external_id)}"
        data = self._request("GET", f"/faces?{q}")
        out: list[VideoFaceCandidate] = []
        for row in data.get("faces") or []:
            out.append(
                VideoFaceCandidate(
                    provider_key=self.provider_key,
                    external_id=str(row["external_id"]),
                    label=row.get("label"),
                    video_external_id=row.get("video_external_id"),
                )
            )
        return out

    def list_presence_spans(
        self,
        *,
        video_external_id: str | None = None,
        face_external_id: str | None = None,
        limit: int = 200,
    ) -> list[VideoPresenceSpan]:
        parts = [f"limit={int(limit)}"]
        if video_external_id:
            parts.append(
                f"video_external_id={urllib.parse.quote(video_external_id)}"
            )
        if face_external_id:
            parts.append(f"face_external_id={urllib.parse.quote(face_external_id)}")
        data = self._request("GET", "/spans?" + "&".join(parts))
        out: list[VideoPresenceSpan] = []
        for row in data.get("spans") or []:
            out.append(
                VideoPresenceSpan(
                    provider_key=self.provider_key,
                    external_id=str(row["external_id"]),
                    video_external_id=str(row["video_external_id"]),
                    face_external_id=str(row["face_external_id"]),
                    start_sec=float(row["start_sec"]),
                    end_sec=float(row["end_sec"]),
                    label=row.get("label"),
                )
            )
        return out

    def search_segments(self, query: VideoSearchQuery) -> list[VideoSegmentHit]:
        body = {
            "person_external_ids": list(query.person_external_ids or ()),
            "text": query.text,
            "video_external_id": query.video_external_id,
            "limit": query.limit,
        }
        data = self._request("POST", "/search", body)
        out: list[VideoSegmentHit] = []
        for row in data.get("hits") or []:
            out.append(
                VideoSegmentHit(
                    provider_key=self.provider_key,
                    external_id=str(row["external_id"]),
                    video_external_id=str(row["video_external_id"]),
                    start_sec=float(row["start_sec"]),
                    end_sec=float(row["end_sec"]),
                    face_external_id=row.get("face_external_id"),
                    label=row.get("label"),
                    play_url=row.get("play_url"),
                )
            )
        return out

    def get_segment(self, external_id: str) -> VideoSegmentHit | None:
        try:
            data = self._request(
                "GET", f"/segments/{urllib.parse.quote(external_id)}"
            )
        except ProviderError:
            return None
        row = data.get("hit")
        if not row:
            return None
        return VideoSegmentHit(
            provider_key=self.provider_key,
            external_id=str(row["external_id"]),
            video_external_id=str(row["video_external_id"]),
            start_sec=float(row["start_sec"]),
            end_sec=float(row["end_sec"]),
            face_external_id=row.get("face_external_id"),
            label=row.get("label"),
            play_url=row.get("play_url"),
        )

    def create_face_candidate(
        self,
        *,
        video_external_id: str,
        t_sec: float,
        label: str | None = None,
    ) -> VideoFaceCandidate:
        """Thin Review: create a face candidate at playhead (derived evidence)."""
        data = self._request(
            "POST",
            "/faces",
            {
                "video_external_id": video_external_id,
                "t_sec": t_sec,
                "label": label,
            },
        )
        row = data.get("face") or {}
        return VideoFaceCandidate(
            provider_key=self.provider_key,
            external_id=str(row["external_id"]),
            label=row.get("label"),
            video_external_id=row.get("video_external_id"),
        )
