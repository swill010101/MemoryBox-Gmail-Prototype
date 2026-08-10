"""Presence span merging — configurable gap tolerance (I7)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RawDetection:
    """Short-interval / frame detection (derived evidence)."""

    candidate_id: str
    t_sec: float
    end_sec: float | None = None
    label: str | None = None


@dataclass(frozen=True)
class MergedSpan:
    candidate_id: str
    start_sec: float
    end_sec: float
    label: str | None = None
    detection_count: int = 1


DEFAULT_PRESENCE_GAP_SEC = 60.0


def merge_presence_spans(
    detections: list[RawDetection],
    *,
    gap_sec: float = DEFAULT_PRESENCE_GAP_SEC,
) -> list[MergedSpan]:
    """Merge nearby same-candidate detections into continuous presence spans.

    Adjacent detections of the same candidate_id merge when the gap between the
    previous span end and the next detection start is <= gap_sec.
    Gaps larger than gap_sec start a new span.
    """
    if gap_sec < 0:
        raise ValueError("gap_sec must be >= 0")
    by_cand: dict[str, list[RawDetection]] = {}
    for d in detections:
        cid = (d.candidate_id or "").strip()
        if not cid:
            continue
        by_cand.setdefault(cid, []).append(d)

    out: list[MergedSpan] = []
    for cid, rows in by_cand.items():
        ordered = sorted(
            rows,
            key=lambda r: (r.t_sec, r.end_sec if r.end_sec is not None else r.t_sec),
        )
        cur_start: float | None = None
        cur_end: float | None = None
        cur_label: str | None = None
        count = 0
        for r in ordered:
            start = float(r.t_sec)
            end = float(r.end_sec) if r.end_sec is not None else start
            if end < start:
                start, end = end, start
            if cur_start is None:
                cur_start, cur_end, cur_label, count = start, end, r.label, 1
                continue
            assert cur_end is not None
            if start - cur_end <= gap_sec:
                cur_end = max(cur_end, end)
                count += 1
                if r.label and not cur_label:
                    cur_label = r.label
            else:
                out.append(
                    MergedSpan(
                        candidate_id=cid,
                        start_sec=cur_start,
                        end_sec=cur_end,
                        label=cur_label,
                        detection_count=count,
                    )
                )
                cur_start, cur_end, cur_label, count = start, end, r.label, 1
        if cur_start is not None and cur_end is not None:
            out.append(
                MergedSpan(
                    candidate_id=cid,
                    start_sec=cur_start,
                    end_sec=cur_end,
                    label=cur_label,
                    detection_count=count,
                )
            )
    out.sort(key=lambda s: (s.candidate_id, s.start_sec, s.end_sec))
    return out
