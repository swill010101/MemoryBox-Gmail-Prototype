"""Evidence-first Spoken Moment retrieval (SQL + optional Qdrant). Residual chat must not invent passages."""
from __future__ import annotations

from typing import Any

from memorybox.db import connection
from memorybox.planner import QueryPlan
from memorybox.recognition.process import ensure_timeslot_play_url
from memorybox.speech.index import search_similar


def _person_ids(plan: QueryPlan) -> list[str]:
    ids = [str(x) for x in (getattr(plan, "person_ids", ()) or ()) if x]
    names = [str(n).strip() for n in (plan.person_names or ()) if str(n).strip()]
    out: list[str] = list(ids)
    if not names:
        return out
    try:
        from memorybox.person import (
            AmbiguousIdentityError,
            find_ask_person_by_name,
            list_people_by_exact_name,
        )

        for name in names:
            try:
                person = find_ask_person_by_name(name, photo=None, lazy_seed=True)
            except AmbiguousIdentityError:
                person = None
                for view in list_people_by_exact_name(name):
                    if view and view.id and view.id not in out:
                        out.append(view.id)
            except Exception:
                person = None
            if person and person.id and person.id not in out:
                out.append(person.id)
            elif not person:
                for view in list_people_by_exact_name(name):
                    if view and view.id and view.id not in out:
                        out.append(view.id)
    except Exception:
        return out
    return out


def _provider_key_for_video_id(video_external_id: str) -> str:
    raw = (video_external_id or "").strip()
    if len(raw) == 36 and raw.count("-") == 4:
        return "immich"
    return "hvrt"


def list_voice_presence_videos(person_ids: list[str]) -> list[dict[str, str]]:
    """Videos where this Person's voice was Learned or assigned — one row per file."""
    pids = [str(p) for p in person_ids if str(p).strip()]
    if not pids:
        return []
    try:
        with connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT video_provider_key, video_external_id
                FROM (
                    SELECT video_provider_key, video_external_id
                    FROM speech_voice_exemplars
                    WHERE person_id::text = ANY(%s) AND withdrawn = false
                    UNION
                    SELECT video_provider_key, video_external_id
                    FROM speech_speaker_turns
                    WHERE person_id::text = ANY(%s)
                    UNION
                    SELECT video_provider_key, video_external_id
                    FROM speech_spoken_moments
                    WHERE person_id::text = ANY(%s)
                      AND COALESCE(status, 'accepted') <> 'withdrawn'
                ) voice_files
                WHERE COALESCE(video_external_id, '') <> ''
                """,
                (pids, pids, pids),
            ).fetchall()
    except Exception:
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for r in rows:
        vid = str(r.get("video_external_id") or "").strip()
        if not vid or vid in seen:
            continue
        seen.add(vid)
        out.append(
            {
                "video_provider_key": str(r.get("video_provider_key") or _provider_key_for_video_id(vid)),
                "video_external_id": vid,
            }
        )
    return out


def list_transcribed_videos(*, limit: int = 48) -> list[dict[str, str]]:
    """Every file that already has words — used when Learn/tags have not joined yet."""
    try:
        with connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT video_provider_key, video_external_id
                FROM (
                    SELECT video_provider_key, video_external_id
                    FROM speech_spoken_moments
                    WHERE COALESCE(status, 'accepted') <> 'withdrawn'
                    UNION
                    SELECT video_provider_key, video_external_id
                    FROM speech_transcript_words
                ) transcribed
                WHERE COALESCE(video_external_id, '') <> ''
                LIMIT %s
                """,
                (max(int(limit), 1),),
            ).fetchall()
    except Exception:
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for r in rows:
        vid = str(r.get("video_external_id") or "").strip()
        if not vid or vid in seen:
            continue
        seen.add(vid)
        out.append(
            {
                "video_provider_key": str(
                    r.get("video_provider_key") or _provider_key_for_video_id(vid)
                ),
                "video_external_id": vid,
            }
        )
    return out


def _moments_on_videos(video_ids: list[str], *, limit: int) -> list[dict[str, Any]]:
    vids = [str(v).strip() for v in video_ids if str(v).strip()]
    if not vids:
        return []
    with connection() as conn:
        return [
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
                (vids, int(limit)),
            ).fetchall()
        ]


def presence_hits_for_people(
    person_ids: list[str],
    *,
    phrase: str = "",
    about: str = "",
    limit: int = 48,
) -> list[dict[str, Any]]:
    """Whole-video voice presence. Does not mint start:end gallery clips."""
    presence = list_voice_presence_videos(person_ids)
    if not presence and not phrase and not about:
        presence = list_transcribed_videos(limit=int(limit))
    vids = [p["video_external_id"] for p in presence]
    rows = _moments_on_videos(vids, limit=max(int(limit) * 12, 96))
    if phrase:
        needle = phrase.lower()
        rows = [r for r in rows if needle in str(r.get("text") or "").lower()]
    elif about:
        needle = about.lower()
        matched = [r for r in rows if needle in str(r.get("text") or "").lower()]
        extra_ids = {str(r.get("id") or "") for r in matched}
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
                    if str(d.get("video_external_id") or "") not in set(vids) and vids:
                        continue
                    matched.append(d)
                    extra_ids.add(hid)
        rows = matched
    hits = _collapse_voice_to_videos(rows, phrase=phrase, about=about, limit=int(limit))
    if phrase or about:
        return hits
    have = {str(h.get("video_external_id") or "") for h in hits}
    for p in presence:
        vid = p["video_external_id"]
        if vid in have:
            continue
        if len(hits) >= int(limit):
            break
        vpk = p.get("video_provider_key") or _provider_key_for_video_id(vid)
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
                "label": "Video",
                "spoken_text": None,
                "play_url": play,
                "mb_person_id": person_ids[0] if person_ids else None,
                "identity_trust": "confirmed",
                "attribution": "voice_in_video",
                "speaker_state": "owner_confirmed",
                "clip_kind": "voice_presence",
            }
        )
        have.add(vid)
    return hits[: int(limit)]


def search_spoken_moments(plan: QueryPlan, *, limit: int = 48) -> list[dict[str, Any]]:
    if not getattr(plan, "want_spoken", False):
        return []
    try:
        pids = _person_ids(plan)
    except Exception:
        pids = []
    phrase = (getattr(plan, "spoken_phrase", None) or "").strip()
    about = (getattr(plan, "spoken_about", None) or "").strip()
    if pids:
        try:
            hits = presence_hits_for_people(
                pids, phrase=phrase, about=about, limit=int(limit)
            )
        except Exception:
            hits = []
        if hits or phrase or about:
            return hits
    if phrase or about:
        if plan.person_names and not pids:
            return []
        clauses = ["COALESCE(status, 'accepted') <> 'withdrawn'"]
        args: list[Any] = []
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
        return _collapse_voice_to_videos(rows, phrase=phrase, about=about, limit=int(limit))
    try:
        return presence_hits_for_people([], phrase="", about="", limit=int(limit))
    except Exception:
        return []


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
