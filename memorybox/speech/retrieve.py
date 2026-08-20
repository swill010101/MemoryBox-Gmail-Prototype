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


def _exemplar_video_ids(person_ids: list[str]) -> list[str]:
    if not person_ids:
        return []
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT video_external_id
            FROM speech_voice_exemplars
            WHERE person_id = ANY(%s::uuid[]) AND withdrawn = false
            """,
            (person_ids,),
        ).fetchall()
    return [str(r["video_external_id"]) for r in rows if r.get("video_external_id")]


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
    args.append(max(int(limit) * 12, 96))
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
    if pids and not rows and not phrase and not about:
        # Owner Learn may have an exemplar before every overlapping moment is tagged.
        vids = _exemplar_video_ids(pids)
        if vids:
            with connection() as conn:
                rows = [
                    dict(r)
                    for r in conn.execute(
                        """
                        SELECT id::text, video_provider_key, video_external_id, t_start, t_end,
                               text, person_id::text, speaker_state, confidence, status
                        FROM speech_spoken_moments
                        WHERE COALESCE(status, 'accepted') <> 'withdrawn'
                          AND video_external_id = ANY(%s)
                        ORDER BY t_start ASC
                        LIMIT %s
                        """,
                        (vids, max(int(limit) * 12, 96)),
                    ).fetchall()
                ]
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
    return _collapse_voice_to_videos(rows, phrase=phrase, about=about, limit=int(limit))


def _collapse_voice_to_videos(
    rows: list[dict[str, Any]],
    *,
    phrase: str,
    about: str,
    limit: int,
) -> list[dict[str, Any]]:
    """One gallery card per source video. Voice does not mint start:end clips (face does)."""
    by_vid: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for r in rows:
        vid = str(r.get("video_external_id") or "")
        if not vid:
            continue
        if vid not in by_vid:
            order.append(vid)
            by_vid[vid] = []
        by_vid[vid].append(r)
    hits: list[dict[str, Any]] = []
    want_phrase = (phrase or "").strip().lower()
    want_about = (about or "").strip().lower()
    for vid in order:
        if len(hits) >= limit:
            break
        group = by_vid[vid]
        snippet = ""
        if want_phrase:
            for r in group:
                text = str(r.get("text") or "")
                if want_phrase in text.lower():
                    snippet = text.strip()
                    break
        if not snippet and want_about:
            for r in group:
                text = str(r.get("text") or "")
                if want_about in text.lower():
                    snippet = text.strip()
                    break
        if not snippet:
            parts: list[str] = []
            seen: set[str] = set()
            for r in group:
                text = str(r.get("text") or "").strip()
                if not text or text.lower() in seen:
                    continue
                seen.add(text.lower())
                parts.append(text)
                if len(" ".join(parts)) >= 160:
                    break
            snippet = " ".join(parts).strip()[:160]
        person_id = next((r.get("person_id") for r in group if r.get("person_id")), None)
        confirmed = any(str(r.get("speaker_state") or "") == "owner_confirmed" for r in group)
        vpk = str(group[0].get("video_provider_key") or "hvrt")
        play = ensure_timeslot_play_url(
            video_external_id=vid,
            start_sec=0.0,
            video_provider_key=vpk,
        )
        hits.append(
            {
                "id": f"voice-video:{vid}",
                "provider_key": vpk,
                "video_external_id": vid,
                "external_id": vid,
                "start_sec": 0.0,
                "end_sec": None,
                "label": snippet or "Video",
                "spoken_text": snippet or None,
                "play_url": play,
                "mb_person_id": person_id,
                "identity_trust": "confirmed" if confirmed else "candidate",
                "attribution": "voice_in_video",
                "speaker_state": "owner_confirmed" if confirmed else "identified",
                "clip_kind": "voice_presence",
            }
        )
    return hits
