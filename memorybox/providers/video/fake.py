"""In-memory VideoIntelligenceProvider for Increment 7 acceptance."""
from __future__ import annotations

from memorybox.providers.base import ProviderHealth
from memorybox.providers.video.dto import (
    VideoAssetDto,
    VideoFaceCandidate,
    VideoPresenceSpan,
    VideoSearchQuery,
    VideoSegmentHit,
)
from memorybox.providers.video.merge import RawDetection, merge_presence_spans


PROVIDER_KEY = "fake_video"


class FakeVideoProvider:
    provider_key = PROVIDER_KEY

    def __init__(self, *, presence_gap_sec: float = 60.0) -> None:
        self.presence_gap_sec = presence_gap_sec
        self._videos = [
            VideoAssetDto(
                provider_key=self.provider_key,
                external_id="video-synth-alpha",
                title="Synthetic Alpha Reel",
                duration_sec=120.0,
            ),
            VideoAssetDto(
                provider_key=self.provider_key,
                external_id="video-synth-beta",
                title="Synthetic Beta Reel",
                duration_sec=90.0,
            ),
        ]
        # Face A: detections that should merge within 60s gap
        # Face B: second person for harness (EVS-007-class synthetic)
        self._raw: list[tuple[str, RawDetection]] = [
            ("video-synth-alpha", RawDetection("face-alpha-1", 1.0, 1.2, "AlphaFace")),
            ("video-synth-alpha", RawDetection("face-alpha-1", 5.0, 5.5, "AlphaFace")),
            ("video-synth-alpha", RawDetection("face-alpha-1", 20.0, 21.0, "AlphaFace")),
            # Gap > 60s → new span
            ("video-synth-alpha", RawDetection("face-alpha-1", 100.0, 101.0, "AlphaFace")),
            ("video-synth-beta", RawDetection("face-beta-2", 2.0, 3.0, "BetaFace")),
            ("video-synth-beta", RawDetection("face-beta-2", 10.0, 11.0, "BetaFace")),
        ]

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_key=self.provider_key,
            ok=True,
            detail="fake",
            meta={"presence_gap_sec": self.presence_gap_sec},
        )

    def list_videos(self, *, limit: int = 100) -> list[VideoAssetDto]:
        return list(self._videos)[:limit]

    def list_face_candidates(
        self, *, video_external_id: str | None = None, limit: int = 100
    ) -> list[VideoFaceCandidate]:
        seen: dict[str, VideoFaceCandidate] = {}
        for vid, det in self._raw:
            if video_external_id and vid != video_external_id:
                continue
            seen[det.candidate_id] = VideoFaceCandidate(
                provider_key=self.provider_key,
                external_id=det.candidate_id,
                label=det.label,
                video_external_id=vid,
            )
        return list(seen.values())[:limit]

    def _merged_for_video(self, video_external_id: str) -> list[VideoPresenceSpan]:
        dets = [d for vid, d in self._raw if vid == video_external_id]
        spans = merge_presence_spans(dets, gap_sec=self.presence_gap_sec)
        out: list[VideoPresenceSpan] = []
        for i, s in enumerate(spans):
            out.append(
                VideoPresenceSpan(
                    provider_key=self.provider_key,
                    external_id=f"{video_external_id}:{s.candidate_id}:{i}",
                    video_external_id=video_external_id,
                    face_external_id=s.candidate_id,
                    start_sec=s.start_sec,
                    end_sec=s.end_sec,
                    label=s.label,
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
        vids = (
            [video_external_id]
            if video_external_id
            else [v.external_id for v in self._videos]
        )
        out: list[VideoPresenceSpan] = []
        for vid in vids:
            if not vid:
                continue
            for sp in self._merged_for_video(vid):
                if face_external_id and sp.face_external_id != face_external_id:
                    continue
                out.append(sp)
        return out[:limit]

    def search_segments(self, query: VideoSearchQuery) -> list[VideoSegmentHit]:
        wanted = set(query.person_external_ids or ())
        spans = self.list_presence_spans(
            video_external_id=query.video_external_id, limit=500
        )
        hits: list[VideoSegmentHit] = []
        for sp in spans:
            if wanted and sp.face_external_id not in wanted:
                continue
            if query.text and query.text.lower() not in (sp.label or "").lower():
                if not wanted:
                    continue
            hits.append(
                VideoSegmentHit(
                    provider_key=self.provider_key,
                    external_id=sp.external_id,
                    video_external_id=sp.video_external_id,
                    start_sec=sp.start_sec,
                    end_sec=sp.end_sec,
                    face_external_id=sp.face_external_id,
                    label=sp.label,
                )
            )
        return hits[: query.limit]

    def get_segment(self, external_id: str) -> VideoSegmentHit | None:
        for h in self.search_segments(VideoSearchQuery(limit=500)):
            if h.external_id == external_id:
                return h
        return None

    def reprocess_with_extra_detection(self) -> None:
        """Harness helper: mutate derived detections without touching MB identity."""
        self._raw.append(
            (
                "video-synth-alpha",
                RawDetection("face-alpha-1", 22.0, 22.5, "AlphaFace"),
            )
        )

    def create_face_candidate(
        self,
        *,
        video_external_id: str,
        t_sec: float,
        label: str | None = None,
    ) -> VideoFaceCandidate:
        from uuid import uuid4

        fid = f"face-{uuid4().hex[:12]}"
        self._raw.append(
            (
                video_external_id,
                RawDetection(fid, float(t_sec), float(t_sec) + 1.0, label),
            )
        )
        return VideoFaceCandidate(
            provider_key=self.provider_key,
            external_id=fid,
            label=label,
            video_external_id=video_external_id,
        )
