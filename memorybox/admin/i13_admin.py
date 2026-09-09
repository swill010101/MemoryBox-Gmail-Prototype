"""Read-only and owner Admin aggregates for I13 Jobs and Learned Evidence."""
from __future__ import annotations

import json
import os
from typing import Any
from uuid import UUID

from memorybox.db import connection


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key, value in list(out.items()):
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
    return out


def active_admission_id() -> str | None:
    raw = os.environ.get("MEMORYBOX_I13_ADMISSION_ID", "").strip()
    try:
        UUID(raw)
    except ValueError:
        return None
    return raw


def _person_display_names(conn: Any, person_ids: set[str]) -> dict[str, str]:
    ids = sorted({pid for pid in person_ids if pid})
    if not ids:
        return {}
    rows = conn.execute(
        "SELECT id::text AS id, display_name FROM people WHERE id = ANY(%s::uuid[])",
        (ids,),
    ).fetchall()
    return {str(r["id"]): (r["display_name"] or str(r["id"])) for r in rows}


def _video_source_labels(video_ids: set[str]) -> dict[str, str]:
    labels = {vid: vid for vid in video_ids if vid}
    if not video_ids:
        return labels
    try:
        from pathlib import Path

        from memorybox.app import build_video

        for video in build_video().list_videos(limit=5000) or []:
            vid = str(getattr(video, "external_id", "") or "")
            if vid not in video_ids:
                continue
            hint = getattr(video, "path_hint", None) or getattr(video, "title", None)
            if hint:
                labels[vid] = Path(str(hint)).name
    except Exception:
        pass
    return labels


def _enrich_admin_items(conn: Any, items: list[dict[str, Any]]) -> None:
    person_ids = {str(i.get("person_id") or "") for i in items if i.get("person_id")}
    source_ids: set[str] = set()
    for item in items:
        sid = str(item.get("video_external_id") or item.get("source_id") or "")
        if sid:
            source_ids.add(sid)
    names = _person_display_names(conn, person_ids)
    labels = _video_source_labels(source_ids)
    for item in items:
        pid = str(item.get("person_id") or "")
        sid = str(item.get("video_external_id") or item.get("source_id") or "")
        item["person_display_name"] = names.get(pid) or ""
        item["source_label"] = labels.get(sid) or sid


def _queue_counts_by_status(
    conn: Any, table: str, admission_id: str | None
) -> dict[str, int]:
    if admission_id:
        rows = conn.execute(
            f"""
            SELECT status, count(*) AS n
            FROM {table}
            WHERE i13_admission_id = %s::uuid
            GROUP BY status
            """,
            (admission_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT status, count(*) AS n
            FROM {table}
            WHERE i13_admission_id IS NULL
            GROUP BY status
            """,
        ).fetchall()
    return {str(r["status"]): int(r["n"]) for r in rows}


def i13_status() -> dict[str, Any]:
    admission_id = active_admission_id()
    env = {
        "MEMORYBOX_I13_ADMISSION_ID": admission_id or "",
        "MEMORYBOX_RECOGNITION_DRAIN": os.environ.get("MEMORYBOX_RECOGNITION_DRAIN", "0"),
        "MEMORYBOX_SPEECH_DRAIN": os.environ.get("MEMORYBOX_SPEECH_DRAIN", "0"),
    }
    admission = None
    events: list[dict[str, Any]] = []
    units: list[dict[str, Any]] = []
    with connection() as conn:
        if admission_id:
            row = conn.execute(
                "SELECT * FROM i13_processing_admissions WHERE id=%s::uuid",
                (admission_id,),
            ).fetchone()
            if row:
                admission = _serialize(dict(row))
                admission["plan"] = admission.pop("plan_json", {})
            events = [
                _serialize(dict(r))
                for r in conn.execute(
                    """
                    SELECT action, actor, reference, created_at
                    FROM i13_admission_events
                    WHERE admission_id=%s::uuid
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    (admission_id,),
                ).fetchall()
            ]
            units = [
                _serialize(dict(r))
                for r in conn.execute(
                    """
                    SELECT lane, provider_key, video_external_id, person_key, enqueue_reason
                    FROM i13_queue_units
                    WHERE admission_id=%s::uuid
                    ORDER BY lane, video_external_id, person_key
                    """,
                    (admission_id,),
                ).fetchall()
            ]
        recent = [
            _serialize(dict(r))
            for r in conn.execute(
                """
                SELECT id::text, state, review_ref, start_ref, created_at,
                       plan_json->>'purpose' AS purpose,
                       plan_json->>'scope_kind' AS scope_kind,
                       plan_json->'lanes' AS lanes
                FROM i13_processing_admissions
                ORDER BY created_at DESC
                LIMIT 10
                """
            ).fetchall()
        ]
        rec_q = _queue_counts_by_status(conn, "recognition_queue_items", admission_id)
        speech_q = _queue_counts_by_status(conn, "speech_queue_items", admission_id)
    learn_enabled = bool(
        admission
        and admission.get("plan", {}).get("purpose") == "acceptance_learning"
        and admission.get("plan", {}).get("scope_kind") != "archive"
        and set(admission.get("plan", {}).get("lanes") or []) & {"face", "voice"}
        and (
            (
                admission.get("state") == "started"
                and admission.get("start_ref")
            )
            or (
                admission.get("state") == "stopped"
                and admission.get("interactive_learn_enabled")
            )
        )
    )
    archive_locked = not any(
        r.get("scope_kind") == "archive" and r.get("state") in {"unlocked", "started"}
        for r in recent
    )
    return {
        "ok": True,
        "read_only": False,
        "env": env,
        "admission": admission,
        "admission_events": events,
        "queue_units": units,
        "recent_admissions": recent,
        "recognition_queue_by_status": rec_q,
        "speech_queue_by_status": speech_q,
        "interactive_learn_enabled": learn_enabled,
        "archive_processing_locked": archive_locked,
    }


def list_jobs(*, limit: int = 200) -> dict[str, Any]:
    admission_id = active_admission_id()
    items: list[dict[str, Any]] = []
    job_cols = """
            SELECT id::text, person_id::text, video_provider_key, video_external_id,
                   status, enqueue_reason, attempt_count, priority, reason,
                   i13_admission_id::text, created_at, updated_at
    """
    with connection() as conn:
        if admission_id:
            rec_rows = conn.execute(
                f"""
                {job_cols}
                FROM recognition_queue_items
                WHERE i13_admission_id = %s::uuid
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT %s
                """,
                (admission_id, int(limit)),
            ).fetchall()
            speech_rows = conn.execute(
                f"""
                {job_cols}
                FROM speech_queue_items
                WHERE i13_admission_id = %s::uuid
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT %s
                """,
                (admission_id, int(limit)),
            ).fetchall()
        else:
            rec_rows = conn.execute(
                f"""
                {job_cols}
                FROM recognition_queue_items
                WHERE i13_admission_id IS NOT NULL
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT %s
                """,
                (int(limit),),
            ).fetchall()
            speech_rows = conn.execute(
                f"""
                {job_cols}
                FROM speech_queue_items
                WHERE i13_admission_id IS NOT NULL
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT %s
                """,
                (int(limit),),
            ).fetchall()
    for row in rec_rows:
        item = _serialize(dict(row))
        item["lane"] = "face"
        items.append(item)
    for row in speech_rows:
        item = _serialize(dict(row))
        item["lane"] = "voice" if item.get("person_id") else "transcribe"
        items.append(item)
    items.sort(key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    with connection() as conn:
        _enrich_admin_items(conn, items[:limit])
    status = i13_status()
    learn_enabled = status["interactive_learn_enabled"]
    archive_locked = status["archive_processing_locked"]
    return {
        "ok": True,
        "admission_id": admission_id,
        "interactive_learn_enabled": learn_enabled,
        "archive_processing_locked": archive_locked,
        "scope_lock": {
            "interactive_learn_enabled": learn_enabled,
            "archive_processing_locked": archive_locked,
        },
        "items": items[:limit],
        "counts": {
            "face_queue": len(rec_rows),
            "speech_queue": len(speech_rows),
        },
    }


def list_learned_evidence(*, limit: int = 300) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    with connection() as conn:
        face_rows = conn.execute(
            """
            SELECT id::text, person_id::text, method, authority, confirmation_state,
                   source_asset_id, provider_key, withdrawn, created_at,
                   exemplar_meta_json, quality_json
            FROM face_evidence
            WHERE withdrawn IS NOT TRUE
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (int(limit),),
        ).fetchall()
        voice_rows = conn.execute(
            """
            SELECT id::text, person_id::text, video_provider_key, video_external_id,
                   t_start, t_end, embedding_model, meta_json, withdrawn, created_at
            FROM speech_voice_exemplars
            WHERE withdrawn IS NOT TRUE
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (int(limit),),
        ).fetchall()
        appearance_rows = conn.execute(
            """
            SELECT id::text, person_id::text, video_provider_key, video_external_id,
                   start_sec, end_sec, method, confidence, authority,
                   confirmation_state, COALESCE(status, 'accepted') AS status
            FROM face_appearance_moments
            WHERE COALESCE(status, 'accepted') <> 'withdrawn'
            ORDER BY start_sec DESC
            LIMIT %s
            """,
            (int(limit),),
        ).fetchall()
        moment_rows = conn.execute(
            """
            SELECT id::text, person_id::text, video_provider_key, video_external_id,
                   t_start, t_end, speaker_state, confidence,
                   COALESCE(status, 'accepted') AS status
            FROM speech_spoken_moments
            WHERE COALESCE(status, 'accepted') <> 'withdrawn'
            ORDER BY t_start DESC
            LIMIT %s
            """,
            (int(limit),),
        ).fetchall()
    for row in face_rows:
        meta = row.get("exemplar_meta_json")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        items.append(
            {
                "kind": "face_exemplar",
                "id": row["id"],
                "person_id": row["person_id"],
                "method": row["method"],
                "authority": row["authority"],
                "confirmation_state": row["confirmation_state"],
                "source_id": row.get("source_asset_id"),
                "provider_key": row.get("provider_key"),
                "created_at": row["created_at"],
                "meta": meta or {},
            }
        )
    for row in voice_rows:
        meta = row.get("meta_json")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        items.append(
            {
                "kind": "voice_exemplar",
                "id": row["id"],
                "person_id": row["person_id"],
                "source_id": row["video_external_id"],
                "provider_key": row["video_provider_key"],
                "start_sec": row["t_start"],
                "end_sec": row["t_end"],
                "embedding_model": row["embedding_model"],
                "created_at": row["created_at"],
                "meta": meta or {},
            }
        )
    for row in appearance_rows:
        items.append(
            {
                "kind": "face_appearance",
                "id": row["id"],
                "person_id": row["person_id"],
                "source_id": row["video_external_id"],
                "provider_key": row["video_provider_key"],
                "start_sec": row["start_sec"],
                "end_sec": row["end_sec"],
                "method": row["method"],
                "confidence": row["confidence"],
                "authority": row["authority"],
                "confirmation_state": row["confirmation_state"],
                "status": row["status"],
            }
        )
    for row in moment_rows:
        items.append(
            {
                "kind": "spoken_moment",
                "id": row["id"],
                "person_id": row["person_id"],
                "source_id": row["video_external_id"],
                "provider_key": row["video_provider_key"],
                "start_sec": row["t_start"],
                "end_sec": row["t_end"],
                "speaker_state": row["speaker_state"],
                "confidence": row["confidence"],
                "status": row["status"],
            }
        )
    items.sort(
        key=lambda x: str(
            x.get("created_at") or x.get("start_sec") or x.get("end_sec") or ""
        ),
        reverse=True,
    )
    slice_items = items[:limit]
    with connection() as conn:
        _enrich_admin_items(conn, slice_items)
    return {"ok": True, "items": slice_items, "count": len(slice_items)}


def withdraw_face_exemplar(exemplar_id: str, *, reason: str) -> dict[str, Any]:
    from memorybox.recognition.exemplars import withdraw_exemplar

    withdraw_exemplar(exemplar_id)
    return {"ok": True, "id": exemplar_id, "withdrawn": True, "reason": reason}


def withdraw_voice_exemplar(exemplar_id: str, *, reason: str) -> dict[str, Any]:
    from memorybox.speech.store import withdraw_voice_exemplar as _withdraw

    _withdraw(exemplar_id, reason=reason)
    return {"ok": True, "id": exemplar_id, "withdrawn": True, "reason": reason}
