"""Process one speech_queue_items row: transcribe per video, or voice-score for one Person."""
from __future__ import annotations

import json
from typing import Any

from memorybox.speech.constants import (
    LINEAGE,
    TRANSCRIBE_MODEL,
    UNCERTAIN_FLOOR,
    VOICE_SIM_THRESHOLD,
)
from memorybox.speech.embeddings import best_voice_score
from memorybox.speech.queue import STATUS_COMPLETED, STATUS_EXCLUDED, STATUS_FAILED, claim_next_item, complete_item
from memorybox.speech.store import (
    assign_turn_person,
    finish_run,
    has_transcript,
    list_transcript,
    list_voice_exemplars,
    list_withdrawals,
    overlaps_withdrawal,
    replace_video_transcript,
    start_run,
)
from memorybox.speech.transcribe import transcribe_video_id


def _moments_from_turns(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for t in turns:
        out.append(
            {
                "t_start": t["t_start"],
                "t_end": t["t_end"],
                "text": t.get("text") or "",
                "person_id": t.get("person_id"),
                "speaker_state": t.get("status") or "anonymous",
                "confidence": t.get("confidence"),
            }
        )
    return out


def persist_transcript(
    *,
    video_provider_key: str,
    video_external_id: str,
    video_provider: Any | None = None,
    trigger: str = "transcribe",
) -> dict[str, Any]:
    raw = transcribe_video_id(video_external_id, video_provider=video_provider)
    if not raw.get("ok"):
        return {"ok": False, **raw}
    run_id = start_run(
        video_provider_key=video_provider_key,
        video_external_id=video_external_id,
        run_kind="transcribe",
        trigger=trigger,
        meta={
            "engine": raw.get("engine"),
            "diarization_provenance": raw.get("diarization_provenance"),
            "lineage": LINEAGE,
        },
    )
    words = list(raw.get("words") or [])
    turns = list(raw.get("turns") or [])
    moments = _moments_from_turns(turns)
    saved = replace_video_transcript(
        video_provider_key=video_provider_key,
        video_external_id=video_external_id,
        words=words,
        turns=turns,
        moments=moments,
        run_id=run_id,
        model_version=str(raw.get("engine") or TRANSCRIBE_MODEL),
    )
    listed = list_transcript(video_external_id)
    try:
        from memorybox.speech.index import upsert_moments

        indexed = upsert_moments(
            [
                {
                    "id": m.get("id"),
                    "text": m.get("text"),
                    "video_external_id": video_external_id,
                    "person_id": m.get("person_id"),
                    "t_start": m.get("t_start"),
                    "t_end": m.get("t_end"),
                }
                for m in listed.get("moments") or []
            ]
        )
    except Exception:
        indexed = 0
    finish_run(
        run_id,
        word_count=saved["word_count"],
        turn_count=saved["turn_count"],
        moment_count=len(saved.get("moment_ids") or []),
        status="completed",
        detail=str(raw.get("diarization_provenance") or ""),
    )
    return {
        "ok": True,
        "run_id": run_id,
        "engine": raw.get("engine"),
        "diarization_provenance": raw.get("diarization_provenance"),
        "indexed": indexed,
        **saved,
        "injected_turn_embeddings": [
            t.get("embedding") for t in turns if t.get("embedding")
        ],
        "turns_raw": turns,
    }


def recognize_person_on_video(
    *,
    person_id: str,
    video_provider_key: str,
    video_external_id: str,
    video_provider: Any | None = None,
) -> dict[str, Any]:
    """Score anonymous turns against that Person's voice exemplars. Face ranges are not proof."""
    exemplars = list_voice_exemplars(person_id)
    if not exemplars:
        return {"ok": False, "reason": "no_voice_exemplars"}
    if not has_transcript(video_external_id):
        tr = persist_transcript(
            video_provider_key=video_provider_key,
            video_external_id=video_external_id,
            video_provider=video_provider,
            trigger="owner_learn",
        )
        if not tr.get("ok"):
            return tr
    listed = list_transcript(video_external_id)
    withdrawals = list_withdrawals(person_id, video_external_id)
    injected = None
    fn = getattr(video_provider, "i9_voice_vec_for_turn", None) if video_provider is not None else None
    assigned = 0
    uncertain = 0
    skipped_face = 0
    for turn in listed.get("turns") or []:
        tid = str(turn.get("id") or "")
        t0 = float(turn.get("t_start") or 0)
        if overlaps_withdrawal(t0, withdrawals):
            continue
        if turn.get("status") == "owner_confirmed" and str(turn.get("person_id") or "") == person_id:
            continue
        probe = None
        if callable(fn):
            probe = fn(video_external_id, t0, float(turn.get("t_end") or t0))
        if not probe:
            continue
        score = best_voice_score(probe, exemplars)
        # Intentionally ignore I8B face overlap — optional context only.
        skipped_face += 1
        if score >= VOICE_SIM_THRESHOLD:
            assign_turn_person(tid, person_id, status="system_recognized", confidence=score)
            assigned += 1
        elif score >= UNCERTAIN_FLOOR:
            assign_turn_person(tid, None, status="uncertain", confidence=score)
            uncertain += 1
    return {
        "ok": True,
        "person_id": person_id,
        "video_external_id": video_external_id,
        "assigned": assigned,
        "uncertain": uncertain,
        "face_not_used_as_proof": True,
        "face_context_ignored_count": skipped_face,
    }


def process_one(*, video_provider: Any | None = None) -> dict[str, Any] | None:
    item = claim_next_item()
    if not item:
        return None
    vpk = str(item.get("video_provider_key") or "hvrt")
    veid = str(item.get("video_external_id") or "")
    reason = str(item.get("enqueue_reason") or "transcribe")
    pid = item.get("person_id")
    try:
        if reason == "owner_learn" and pid:
            rec = recognize_person_on_video(
                person_id=str(pid),
                video_provider_key=vpk,
                video_external_id=veid,
                video_provider=video_provider,
            )
            if not rec.get("ok") and rec.get("reason") == "no_voice_exemplars":
                complete_item(item["id"], status=STATUS_EXCLUDED, reason="no_voice_exemplars", result=rec)
                return {"item_id": item["id"], "status": STATUS_EXCLUDED, **rec}
            complete_item(item["id"], status=STATUS_COMPLETED, result=rec)
            return {"item_id": item["id"], "status": STATUS_COMPLETED, **rec}
        if has_transcript(veid) and reason == "transcribe":
            complete_item(item["id"], status=STATUS_COMPLETED, reason="unchanged", result={"noop": True})
            return {"item_id": item["id"], "status": STATUS_COMPLETED, "noop": True}
        saved = persist_transcript(
            video_provider_key=vpk,
            video_external_id=veid,
            video_provider=video_provider,
            trigger=reason,
        )
        if not saved.get("ok"):
            err = str(saved.get("error") or "transcribe_failed")
            st = STATUS_EXCLUDED if err == "no_local_path" else STATUS_FAILED
            complete_item(item["id"], status=st, reason=err, result=saved)
            return {"item_id": item["id"], "status": st, **saved}
        complete_item(item["id"], status=STATUS_COMPLETED, result={"engine": saved.get("engine"), "word_count": saved.get("word_count")})
        return {"item_id": item["id"], "status": STATUS_COMPLETED, **saved}
    except Exception as exc:  # noqa: BLE001
        complete_item(item["id"], status=STATUS_FAILED, reason=str(exc))
        return {"item_id": item["id"], "status": STATUS_FAILED, "error": str(exc)}


def transcribe_this_video_now(
    *,
    video_provider_key: str,
    video_external_id: str,
    video_provider: Any | None = None,
) -> dict[str, Any]:
    """Owner-open video: persist this video only, even if a prior empty pass completed."""
    from memorybox.speech.store import has_transcript, list_transcript

    if has_transcript(video_external_id):
        tr = list_transcript(video_external_id)
        return {
            "ok": True,
            "skipped": True,
            "already_transcribed": True,
            "word_count": len(tr.get("words") or []),
            "video_external_id": video_external_id,
        }
    saved = persist_transcript(
        video_provider_key=video_provider_key,
        video_external_id=video_external_id,
        video_provider=video_provider,
        trigger="transcribe_now",
    )
    from memorybox.db import connection

    status = STATUS_COMPLETED if saved.get("ok") else STATUS_FAILED
    reason = None if saved.get("ok") else str(saved.get("error") or "transcribe_failed")
    with connection() as conn:
        conn.execute(
            """
            UPDATE speech_queue_items
            SET status = %s, reason = %s, result_json = %s::jsonb,
                finished_at = now(), updated_at = now()
            WHERE video_external_id = %s
              AND enqueue_reason = 'transcribe'
              AND person_id IS NULL
            """,
            (
                status,
                reason,
                json.dumps(
                    {
                        "engine": saved.get("engine"),
                        "word_count": saved.get("word_count"),
                        "error": saved.get("error"),
                    }
                ),
                video_external_id,
            ),
        )
    return saved


def process_queue(*, video_provider: Any | None = None, max_items: int = 25) -> dict[str, Any]:
    results = []
    for _ in range(int(max_items)):
        one = process_one(video_provider=video_provider)
        if not one:
            break
        results.append(one)
    return {"ok": True, "processed": len(results), "results": results}
