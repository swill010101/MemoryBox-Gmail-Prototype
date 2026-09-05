"""Persist I9 words, anonymous turns, Spoken Moments."""
from __future__ import annotations

import json
from typing import Any

from memorybox.db import connection
from memorybox.speech.constants import LINEAGE, TRANSCRIBE_MODEL


def start_run(
    *,
    video_provider_key: str,
    video_external_id: str,
    run_kind: str,
    trigger: str | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO speech_processing_runs (
                video_provider_key, video_external_id, run_kind, trigger, meta_json
            ) VALUES (%s, %s, %s, %s, %s::jsonb)
            RETURNING id::text
            """,
            (
                video_provider_key,
                video_external_id,
                run_kind,
                trigger,
                json.dumps(meta or {}),
            ),
        ).fetchone()
    return str(row["id"])


def finish_run(
    run_id: str,
    *,
    word_count: int = 0,
    turn_count: int = 0,
    moment_count: int = 0,
    status: str = "completed",
    detail: str | None = None,
) -> None:
    with connection() as conn:
        conn.execute(
            """
            UPDATE speech_processing_runs
            SET status = %s, word_count = %s, turn_count = %s, moment_count = %s,
                detail = %s, finished_at = now()
            WHERE id = %s::uuid
            """,
            (status, word_count, turn_count, moment_count, detail, run_id),
        )


def replace_video_transcript(
    *,
    video_provider_key: str,
    video_external_id: str,
    words: list[dict[str, Any]],
    turns: list[dict[str, Any]],
    moments: list[dict[str, Any]],
    run_id: str,
    model_version: str = TRANSCRIBE_MODEL,
) -> dict[str, Any]:
    vpk, veid = video_provider_key, video_external_id
    with connection() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(vpk+':'+veid,))
        if conn.execute('SELECT 1 FROM i13_transcript_versions WHERE provider_key=%s AND source_id=%s AND run_id=%s::uuid',(vpk,veid,run_id)).fetchone():
            raise ValueError('transcript_run_already_persisted')
        for w in words:
            conn.execute(
                """
                INSERT INTO speech_transcript_words (
                    video_provider_key, video_external_id, t_start, t_end, token,
                    confidence, model_version, processing_run_id, meta_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::uuid, '{}'::jsonb)
                """,
                (
                    vpk,
                    veid,
                    float(w["t_start"]),
                    float(w["t_end"]),
                    str(w["token"]),
                    w.get("confidence"),
                    model_version,
                    run_id,
                ),
            )
        turn_ids: list[str] = []
        for t in turns:
            row = conn.execute(
                """
                INSERT INTO speech_speaker_turns (
                    video_provider_key, video_external_id, t_start, t_end,
                    anonymous_speaker_key, person_id, status, confidence,
                    diarization_model, processing_run_id, meta_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid, %s::jsonb)
                RETURNING id::text
                """,
                (
                    vpk,
                    veid,
                    float(t["t_start"]),
                    float(t["t_end"]),
                    str(t["anonymous_speaker_key"]),
                    t.get("person_id"),
                    str(t.get("status") or "anonymous"),
                    t.get("confidence"),
                    str(t.get("diarization_model") or "pause_gap_local"),
                    run_id,
                    json.dumps({"lineage": LINEAGE}),
                ),
            ).fetchone()
            turn_ids.append(str(row["id"]))
        moment_ids: list[str] = []
        for i, m in enumerate(moments):
            tid = m.get("turn_id") or (turn_ids[i] if i < len(turn_ids) else None)
            row = conn.execute(
                """
                INSERT INTO speech_spoken_moments (
                    video_provider_key, video_external_id, t_start, t_end, text,
                    text_original, turn_id, person_id, speaker_state, confidence,
                    model_version, status, processing_run_id, meta_json
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s::uuid, %s, %s, %s, %s, 'accepted',
                    %s::uuid, %s::jsonb
                )
                RETURNING id::text
                """,
                (
                    vpk,
                    veid,
                    float(m["t_start"]),
                    float(m["t_end"]),
                    str(m["text"]),
                    str(m.get("text_original") or m["text"]),
                    tid,
                    m.get("person_id"),
                    str(m.get("speaker_state") or "anonymous"),
                    m.get("confidence"),
                    model_version,
                    run_id,
                    json.dumps({"lineage": LINEAGE}),
                ),
            ).fetchone()
            moment_ids.append(str(row["id"]))
        snapshot = {'provenance':'machine_run'}
        for key, table in [('words','speech_transcript_words'),('turns','speech_speaker_turns'),('moments','speech_spoken_moments')]:
            snapshot[key] = [dict(r) for r in conn.execute(
                f'SELECT * FROM {table} WHERE video_provider_key=%s AND video_external_id=%s AND processing_run_id=%s::uuid ORDER BY t_start,t_end,id',
                (vpk,veid,run_id)).fetchall()]
        conn.execute('INSERT INTO i13_transcript_versions(provider_key,source_id,run_id,machine) VALUES (%s,%s,%s::uuid,%s::jsonb)',
            (vpk,veid,run_id,json.dumps(snapshot,default=str)))
    return {"word_count": len(words), "turn_count": len(turns), "moment_ids": moment_ids}


def _speech_api_row(row: Any) -> dict[str, Any]:
    d = dict(row)
    for k in ("t_start", "t_end", "confidence"):
        if d.get(k) is not None:
            d[k] = float(d[k])
    return d


def list_transcript(video_external_id: str, video_provider_key: str | None = None) -> dict[str, Any]:
    from memorybox.speech.annotations import transcript
    return transcript(video_provider_key, (video_external_id or '').strip())


def persist_voice_exemplar(
    *,
    person_id: str,
    video_provider_key: str,
    video_external_id: str,
    t_start: float,
    t_end: float,
    embedding: list[float],
    embedding_model: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO speech_voice_exemplars (
                person_id, video_provider_key, video_external_id,
                t_start, t_end, embedding_json, embedding_model, meta_json
            ) VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)
            RETURNING id::text, person_id::text
            """,
            (
                person_id,
                video_provider_key,
                video_external_id,
                float(t_start),
                float(t_end),
                json.dumps(embedding),
                embedding_model,
                json.dumps(meta or {"provenance": "owner_review_learn"}),
            ),
        ).fetchone()
    return dict(row)


def list_voice_exemplars(person_id: str) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id::text, person_id::text, embedding_json, embedding_model,
                   t_start, t_end, video_external_id
            FROM speech_voice_exemplars
            WHERE person_id = %s::uuid AND withdrawn = false
            """,
            (person_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        emb = d.get("embedding_json")
        if isinstance(emb, str):
            d["embedding"] = json.loads(emb)
        else:
            d["embedding"] = emb
        out.append(d)
    return out


def assign_turn_person(turn_id: str, person_id: str | None, *, status: str, confidence: float | None) -> None:
    with connection() as conn:
        conn.execute(
            """
            UPDATE speech_speaker_turns
            SET person_id = %s, status = %s, confidence = %s
            WHERE id = %s::uuid
            """,
            (person_id, status, confidence, turn_id),
        )
        conn.execute(
            """
            UPDATE speech_spoken_moments
            SET person_id = %s, speaker_state = %s, confidence = %s
            WHERE turn_id = %s::uuid
              AND COALESCE(status, 'accepted') <> 'withdrawn'
            """,
            (person_id, status, confidence, turn_id),
        )


def record_withdrawal(
    *,
    person_id: str,
    video_provider_key: str,
    video_external_id: str,
    t_start: float,
    t_end: float | None = None,
    reason: str = "owner_withdraw",
) -> str:
    from memorybox.processing.scope import require_source
    require_source("voice", video_provider_key, video_external_id, person_id)
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO speech_identity_withdrawals (
                person_id, video_provider_key, video_external_id, t_start, t_end, reason
            ) VALUES (%s::uuid, %s, %s, %s, %s, %s)
            RETURNING id::text
            """,
            (person_id, video_provider_key, video_external_id, t_start, t_end, reason),
        ).fetchone()
        conn.execute(
            """
            UPDATE speech_spoken_moments
            SET status = 'withdrawn', person_id = NULL, speaker_state = 'withdrawn'
            WHERE video_external_id = %s
              AND person_id = %s::uuid
              AND t_start >= %s - 0.25
              AND t_start <= %s + 0.25
            """,
            (video_external_id, person_id, t_start, t_end if t_end is not None else t_start),
        )
    return str(row["id"])


def list_withdrawals(person_id: str, video_external_id: str) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT t_start, t_end FROM speech_identity_withdrawals
            WHERE person_id = %s::uuid AND video_external_id = %s
            """,
            (person_id, video_external_id),
        ).fetchall()
    return [dict(r) for r in rows]


def has_transcript(video_external_id: str) -> bool:
    with connection() as conn:
        return bool(conn.execute("SELECT 1 FROM i13_current_transcripts WHERE source_id=%s AND jsonb_array_length(machine->'words')>0 LIMIT 1",(video_external_id,)).fetchone())


def list_videos_with_word_counts(*, limit: int = 12) -> list[dict[str, Any]]:
    with connection() as conn:
        rows=conn.execute("SELECT source_id AS video_external_id,jsonb_array_length(machine->'words') AS word_count FROM i13_current_transcripts WHERE jsonb_array_length(machine->'words')>0 ORDER BY word_count DESC LIMIT %s",(int(limit),)).fetchall()
    return [dict(r) for r in rows]


def set_moment_qdrant_id(moment_id: str, point_id: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE speech_spoken_moments SET qdrant_point_id = %s WHERE id = %s::uuid",
            (point_id, moment_id),
        )


def overlaps_withdrawal(t_sec: float, withdrawals: list[dict[str, Any]]) -> bool:
    for w in withdrawals:
        a = float(w.get("t_start") or 0)
        b = float(w.get("t_end") if w.get("t_end") is not None else a)
        if a - 0.25 <= t_sec <= b + 0.25:
            return True
    return False
