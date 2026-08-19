"""Scan one video against MemoryBox exemplars; write observations + ranges."""
from __future__ import annotations

from typing import Any, Callable

from memorybox.recognition.constants import (
    FACE_SIM_THRESHOLD,
    LINEAGE_NATIVE,
    MODEL_ID,
    UNCERTAIN_FLOOR,
)
from memorybox.recognition.embeddings import cosine
from memorybox.recognition.exemplars import list_active_exemplars
from memorybox.recognition.observations import (
    delete_native_observations_for_video,
    finish_processing_run,
    group_assigned_into_ranges,
    insert_observation,
    list_withdrawals,
    overlaps_withdrawal,
    persist_native_range,
    start_processing_run,
)

ScanFn = Callable[[str], list[dict[str, Any]]]


def match_embedding(
    embedding: list[float],
    exemplars: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, float]:
    best: dict[str, Any] | None = None
    best_score = -1.0
    for ex in exemplars:
        s = cosine(embedding, ex.get("embedding") or [])
        if s > best_score:
            best_score = s
            best = ex
    return best, best_score


def collect_scan_samples(video_provider: Any, video_external_id: str) -> list[dict[str, Any]]:
    """Prefer provider-injected samples (harness); else empty (InsightFace path later)."""
    fn = getattr(video_provider, "i8b_scan_samples", None)
    if callable(fn):
        return list(fn(video_external_id) or [])
    return []


def scan_video_for_person(
    *,
    person_id: str,
    video_provider: Any,
    video_external_id: str,
    video_provider_key: str | None = None,
    run_kind: str = "provider_seeded",
    trigger: str | None = None,
) -> dict[str, Any]:
    vpk = video_provider_key or getattr(video_provider, "provider_key", None) or "hvrt"
    exemplars = list_active_exemplars(person_id)
    if not exemplars:
        return {
            "ok": False,
            "reason": "no_active_exemplars",
            "person_id": person_id,
            "video_external_id": video_external_id,
            "ranges": [],
        }
    samples = collect_scan_samples(video_provider, video_external_id)
    withdrawals = list_withdrawals(
        person_id=person_id,
        video_provider_key=vpk,
        video_external_id=video_external_id,
    )
    run_id = start_processing_run(
        person_id=person_id,
        run_kind=run_kind,
        trigger=trigger,
        meta={"video_external_id": video_external_id, "exemplar_count": len(exemplars)},
    )
    delete_native_observations_for_video(
        person_id=person_id,
        video_provider_key=vpk,
        video_external_id=video_external_id,
    )
    observations: list[dict[str, Any]] = []
    accepted = 0
    uncertain = 0
    for sample in samples:
        emb = sample.get("embedding")
        if not emb:
            continue
        t_sec = float(sample.get("t_sec") or 0)
        best, score = match_embedding(emb, exemplars)
        if overlaps_withdrawal(t_sec, withdrawals):
            state = "withdrawn"
            pid: str | None = None
        elif score >= FACE_SIM_THRESHOLD and best:
            state = "assigned"
            pid = str(best.get("person_id") or person_id)
            accepted += 1
        elif score >= UNCERTAIN_FLOOR:
            state = "uncertain"
            pid = None
            uncertain += 1
        else:
            continue
        oid = insert_observation(
            video_provider_key=vpk,
            video_external_id=video_external_id,
            t_sec=t_sec,
            bbox=sample.get("bbox"),
            person_id=pid,
            confidence=score if state == "assigned" else None,
            match_score=score,
            review_state=state,
            embedding_model=MODEL_ID,
            exemplar_id=best.get("id") if best else None,
            processing_run_id=run_id,
            meta={"lineage": LINEAGE_NATIVE},
        )
        observations.append(
            {
                "id": oid,
                "t_sec": t_sec,
                "person_id": pid,
                "review_state": state,
                "match_score": score,
            }
        )
    ranges = group_assigned_into_ranges(observations)
    range_ids = []
    for r in ranges:
        mid = persist_native_range(
            person_id=person_id,
            video_provider_key=vpk,
            video_external_id=video_external_id,
            start_sec=float(r["start_sec"]),
            end_sec=float(r["end_sec"]),
            observation_ids=list(r["observation_ids"]),
            confidence=float(r["confidence"]),
            processing_run_id=run_id,
            model_version=MODEL_ID,
        )
        range_ids.append(mid)
    finish_processing_run(
        run_id,
        candidate_count=len(samples),
        accepted_count=accepted,
        uncertain_count=uncertain,
        range_count=len(range_ids),
    )
    return {
        "ok": True,
        "person_id": person_id,
        "video_external_id": video_external_id,
        "run_id": run_id,
        "run_kind": run_kind,
        "lineage": LINEAGE_NATIVE,
        "candidate_count": len(samples),
        "accepted_count": accepted,
        "uncertain_count": uncertain,
        "ranges": range_ids,
        "observation_count": len(observations),
    }
