"""Evidence-first Spoken Moment retrieval (SQL + optional Qdrant). Residual chat must not invent passages."""
from __future__ import annotations

from typing import Any

from memorybox.db import connection
from memorybox.planner import QueryPlan
from memorybox.recognition.process import ensure_timeslot_play_url
from memorybox.speech.index import search_similar


def _person_ids(plan: QueryPlan) -> list[str]:
    ids = [str(x) for x in (getattr(plan, "person_ids", ()) or ()) if x]
    if ids:
        return ids
    names = [str(n).strip() for n in (plan.person_names or ()) if str(n).strip()]
    if not names:
        return []
    out: list[str] = []
    try:
        from memorybox.person import find_ask_person_by_name

        for name in names:
            person = find_ask_person_by_name(name, photo=None, lazy_seed=False)
            if person and person.id:
                out.append(person.id)
    except Exception:
        return out
    return out


def search_spoken_moments(plan: QueryPlan, *, limit: int = 48) -> list[dict[str, Any]]:
    if not getattr(plan, "want_spoken", False):
        return []
    pids = _person_ids(plan)
    phrase = (getattr(plan, "spoken_phrase", None) or "").strip()
    about = (getattr(plan, "spoken_about", None) or "").strip()
    clauses = ["COALESCE(status, 'accepted') <> 'withdrawn'"]
    args: list[Any] = []
    if pids:
        clauses.append("person_id = ANY(%s::uuid[])")
        args.append(pids)
    elif plan.person_names:
        # Person asked but unresolved — do not return anonymous everyone-talking.
        return []
    if phrase:
        clauses.append("text ILIKE %s")
        args.append("%" + phrase + "%")
    if about and not phrase:
        clauses.append(
            "(to_tsvector('simple', text) @@ plainto_tsquery('simple', %s) OR text ILIKE %s)"
        )
        args.extend([about, "%" + about + "%"])
    args.append(int(limit))
    sql = f"""
        SELECT id::text, video_provider_key, video_external_id, t_start, t_end,
               text, person_id::text, speaker_state, confidence, status
        FROM speech_spoken_moments
        WHERE {' AND '.join(clauses)}
        ORDER BY t_start ASC
        LIMIT %s
    """
    with connection() as conn:
        rows = [dict(r) for r in conn.execute(sql, tuple(args)).fetchall()]
    if about and not phrase:
        extra_ids = {str(r["id"]) for r in rows}
        for h in search_similar(about, limit=limit):
            hid = str(h.get("id") or "")
            if hid and hid not in extra_ids:
                with connection() as conn:
                    row = conn.execute(
                        """
                        SELECT id::text, video_provider_key, video_external_id, t_start, t_end,
                               text, person_id::text, speaker_state, confidence, status
                        FROM speech_spoken_moments
                        WHERE id = %s::uuid AND COALESCE(status, 'accepted') <> 'withdrawn'
                        """,
                        (hid,),
                    ).fetchone()
                if row:
                    d = dict(row)
                    if pids and str(d.get("person_id") or "") not in pids:
                        continue
                    rows.append(d)
                    extra_ids.add(hid)
    hits = []
    for r in rows[:limit]:
        vid = str(r["video_external_id"])
        t0 = float(r["t_start"])
        play = ensure_timeslot_play_url(
            video_external_id=vid,
            start_sec=t0,
            video_provider_key=str(r.get("video_provider_key") or ""),
        )
        hits.append(
            {
                "id": r["id"],
                "provider_key": r["video_provider_key"],
                "video_external_id": vid,
                "external_id": r["id"],
                "start_sec": t0,
                "end_sec": float(r["t_end"]),
                "label": r.get("text") or "Spoken moment",
                "spoken_text": r.get("text"),
                "play_url": play,
                "mb_person_id": r.get("person_id"),
                "identity_trust": (
                    "confirmed" if r.get("speaker_state") == "owner_confirmed" else "candidate"
                ),
                "attribution": f"spoken_moment ({r.get('speaker_state')})",
                "speaker_state": r.get("speaker_state"),
            }
        )
    return hits
