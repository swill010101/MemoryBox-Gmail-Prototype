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

# P2-I1 Peggy corpus face id (mapped to MB Person in acceptance)
PEGGY_FACE_ID = "face-peggy-1"
OTHER_FACE_ID = "face-other-9"

# Orthogonal synthetic embeddings for I8B harness (no InsightFace required).
I8B_PEGGY_VEC = [1.0] + [0.0] * 15
I8B_OTHER_VEC = [0.0, 1.0] + [0.0] * 14
# Cosine vs Peggy exemplars ≈ 0.30 (uncertain band 0.28–0.38)
I8B_UNCERTAIN_PEGGY_VEC = [0.32] + [0.0] * 14 + [0.947]


class FakeVideoProvider:
    provider_key = PROVIDER_KEY

    def __init__(self, *, presence_gap_sec: float = 60.0, peggy_corpus: bool = False, i8b_corpus: bool = False) -> None:
        self.presence_gap_sec = presence_gap_sec
        self.i8b_corpus = bool(i8b_corpus)
        if peggy_corpus:
            # Enough videos to demonstrate full-library queue + §1.D corpus
            self._videos = [
                VideoAssetDto(
                    provider_key=self.provider_key,
                    external_id="video-peggy-clear",
                    title="Peggy clearly appears",
                    duration_sec=60.0,
                ),
                VideoAssetDto(
                    provider_key=self.provider_key,
                    external_id="video-peggy-absent",
                    title="Peggy does not appear",
                    duration_sec=45.0,
                ),
                VideoAssetDto(
                    provider_key=self.provider_key,
                    external_id="video-peggy-ambiguous",
                    title="Difficult/ambiguous Peggy appearance",
                    duration_sec=50.0,
                ),
                VideoAssetDto(
                    provider_key=self.provider_key,
                    external_id="video-library-01",
                    title="Library filler 01",
                    duration_sec=30.0,
                ),
                VideoAssetDto(
                    provider_key=self.provider_key,
                    external_id="video-library-02",
                    title="Library filler 02",
                    duration_sec=30.0,
                ),
                VideoAssetDto(
                    provider_key=self.provider_key,
                    external_id="video-library-03",
                    title="Library filler 03",
                    duration_sec=30.0,
                ),
                VideoAssetDto(
                    provider_key=self.provider_key,
                    external_id="video-corrupt-demo",
                    title="Corrupt/unprocessable demo",
                    duration_sec=None,
                ),
            ]
            if i8b_corpus:
                self._videos.append(
                    VideoAssetDto(
                        provider_key=self.provider_key,
                        external_id="video-both-people",
                        title="Peggy and second person both appear",
                        duration_sec=40.0,
                    )
                )
            self._raw: list[tuple[str, RawDetection]] = [
                ("video-peggy-clear", RawDetection(PEGGY_FACE_ID, 5.0, 8.0, "Peggy")),
                ("video-peggy-clear", RawDetection(PEGGY_FACE_ID, 20.0, 22.0, "Peggy")),
                # absent: only other face
                ("video-peggy-absent", RawDetection(OTHER_FACE_ID, 3.0, 4.0, "Other")),
                # ambiguous low-confidence-ish span
                ("video-peggy-ambiguous", RawDetection(PEGGY_FACE_ID, 12.0, 12.5, "Peggy?")),
                ("video-library-01", RawDetection(OTHER_FACE_ID, 1.0, 2.0, "Other")),
                ("video-library-02", RawDetection(PEGGY_FACE_ID, 7.0, 9.0, "Peggy")),
                ("video-library-03", RawDetection(OTHER_FACE_ID, 2.0, 3.0, "Other")),
            ]
            if i8b_corpus:
                self._raw.append(
                    ("video-both-people", RawDetection(PEGGY_FACE_ID, 4.0, 6.0, "Peggy"))
                )
                self._raw.append(
                    ("video-both-people", RawDetection(OTHER_FACE_ID, 18.0, 20.0, "Other"))
                )
            self._unprocessable = {"video-corrupt-demo": "unsupported_codec"}
        else:
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
            self._raw = [
                ("video-synth-alpha", RawDetection("face-alpha-1", 1.0, 1.2, "AlphaFace")),
                ("video-synth-alpha", RawDetection("face-alpha-1", 5.0, 5.5, "AlphaFace")),
                ("video-synth-alpha", RawDetection("face-alpha-1", 20.0, 21.0, "AlphaFace")),
                ("video-synth-alpha", RawDetection("face-alpha-1", 100.0, 101.0, "AlphaFace")),
                ("video-synth-beta", RawDetection("face-beta-2", 2.0, 3.0, "BetaFace")),
                ("video-synth-beta", RawDetection("face-beta-2", 10.0, 11.0, "BetaFace")),
                ("video-synth-alpha", RawDetection("face-boot-3", 40.0, 41.0, "BootFace")),
                ("video-synth-alpha", RawDetection("face-boot-3", 45.0, 46.0, "BootFace")),
            ]
            self._unprocessable = {}

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_key=self.provider_key,
            ok=True,
            detail="fake",
            meta={"presence_gap_sec": self.presence_gap_sec},
        )

    def list_videos(self, *, limit: int = 100) -> list[VideoAssetDto]:
        return list(self._videos)[:limit]

    def eligible_video_rows(self) -> list[dict]:
        """P2-I1 helper: eligible inventory with visible exclusions."""
        rows = []
        for v in self._videos:
            reason = self._unprocessable.get(v.external_id)
            rows.append(
                {
                    "video_provider_key": self.provider_key,
                    "video_external_id": v.external_id,
                    "eligible": reason is None,
                    "reason": reason,
                }
            )
        return rows

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
                    play_url=(
                        f"/review/ui?video={sp.video_external_id}&t={sp.start_sec}"
                    ),
                )
            )
        return hits[: query.limit]

    def i8b_scan_samples(self, video_external_id: str) -> list[dict]:
        """Synthetic per-frame embeddings for I8B (same vectors as seeded exemplars)."""
        out: list[dict] = []
        if video_external_id == "video-peggy-ambiguous":
            return [
                {
                    "t_sec": 12.0,
                    "embedding": list(I8B_UNCERTAIN_PEGGY_VEC),
                    "bbox": {"x1": 10, "y1": 10, "x2": 80, "y2": 80},
                }
            ]
        for vid, det in self._raw:
            if vid != video_external_id:
                continue
            if det.candidate_id == PEGGY_FACE_ID:
                vec = I8B_PEGGY_VEC
            elif det.candidate_id == OTHER_FACE_ID:
                vec = I8B_OTHER_VEC
            else:
                continue
            out.append(
                {
                    "t_sec": float(det.t_sec),
                    "embedding": list(vec),
                    "bbox": {"x1": 8, "y1": 8, "x2": 90, "y2": 90},
                    "face_external_id": det.candidate_id,
                }
            )
        return out

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
