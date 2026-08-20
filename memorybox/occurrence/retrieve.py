"""Hydrate occurrence membership into Ask hit types. Spoken Moments keep t_start/t_end."""
from __future__ import annotations

import json
from typing import Any

from memorybox.ask import retrieve as R
from memorybox.db import connection
from memorybox.occurrence.store import list_memberships, list_places


def _payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _stamp(hit: Any, member: dict[str, Any]) -> Any:
    hit.membership_status = str(member.get("status") or "")
    hit.membership_id = str(member.get("id") or "")
    hit.occurrence_id = str(member.get("occurrence_id") or "")
    hit.join_method = str(member.get("join_method") or "")
    return hit


def _play_url(provider_key: str, video_id: str, t0: float) -> str:
    pk = str(provider_key or "")
    looks_immich = pk == "immich" or (
        len(video_id) == 36 and video_id.count("-") == 4 and not video_id.startswith("vid-")
    )
    if looks_immich:
        return f"/library/media/immich-video/{video_id}?t={t0:.3f}"
    return f"/review/media/{video_id}?t={t0:.3f}"


def hydrate_memberships(occurrence_id: str) -> dict[str, Any]:
    members = list_memberships(occurrence_id, include_rejected=False)
    photos: list[R.PhotoHit] = []
    evidence: list[R.EvidenceHit] = []
    videos: list[R.VideoHit] = []
    artifacts: list[dict[str, Any]] = []
    spoken_precise: list[dict[str, Any]] = []
    kinds: set[str] = set()

    evidence_ids = [
        str((m.get("evidence_ref") or {}).get("evidence_id") or "")
        for m in members
        if m.get("evidence_kind") in ("email", "sms", "calendar", "communication")
    ]
    evidence_ids = [x for x in evidence_ids if x]
    by_eid: dict[str, dict[str, Any]] = {}
    if evidence_ids:
        ph = ",".join(["%s::uuid"] * len(evidence_ids))
        with connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id::text AS id, evidence_kind, summary, payload_json
                FROM evidence
                WHERE id IN ({ph})
                """,
                evidence_ids,
            ).fetchall()
        for r in rows:
            by_eid[str(r["id"])] = dict(r)

    spoken_ids = [
        str((m.get("evidence_ref") or {}).get("spoken_moment_id") or "")
        for m in members
        if m.get("evidence_kind") == "spoken_moment"
    ]
    spoken_ids = [x for x in spoken_ids if x]
    by_spoken: dict[str, dict[str, Any]] = {}
    if spoken_ids:
        ph = ",".join(["%s::uuid"] * len(spoken_ids))
        with connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id::text AS id, video_provider_key, video_external_id,
                       t_start, t_end, text, person_id
                FROM speech_spoken_moments
                WHERE id IN ({ph})
                """,
                spoken_ids,
            ).fetchall()
        for r in rows:
            by_spoken[str(r["id"])] = dict(r)

    face_ids = [
        str((m.get("evidence_ref") or {}).get("appearance_moment_id") or "")
        for m in members
        if m.get("evidence_kind") == "face_range"
    ]
    face_ids = [x for x in face_ids if x]
    by_face: dict[str, dict[str, Any]] = {}
    if face_ids:
        ph = ",".join(["%s::uuid"] * len(face_ids))
        with connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id::text AS id, video_provider_key, video_external_id,
                       start_sec, end_sec, person_id, face_external_id
                FROM face_appearance_moments
                WHERE id IN ({ph})
                """,
                face_ids,
            ).fetchall()
        for r in rows:
            by_face[str(r["id"])] = dict(r)

    for m in members:
        kind = str(m.get("evidence_kind") or "")
        ref = dict(m.get("evidence_ref") or {})
        kinds.add(kind)
        st = str(m.get("status") or "candidate")
        if kind == "photo":
            hit = R.PhotoHit(
                provider_key=str(ref.get("provider_key") or "immich"),
                external_id=str(ref.get("external_id") or ""),
                taken_at=ref.get("taken_at"),
                people=list(ref.get("people") or []),
                location=ref.get("place") or ref.get("location"),
                thumb_url=None,
                web_url=None,
                attribution="occurrence_member",
                place=ref.get("place"),
                latitude=ref.get("latitude"),
                longitude=ref.get("longitude"),
                original_filename=ref.get("original_filename"),
            )
            photos.append(_stamp(hit, m))
        elif kind in ("email", "sms", "calendar", "communication"):
            eid = str(ref.get("evidence_id") or "")
            row = by_eid.get(eid)
            payload = _payload(row["payload_json"]) if row else {}
            channel = kind if kind in ("email", "sms", "calendar") else str(
                payload.get("channel") or ref.get("channel") or "email"
            )
            summary = (
                (row or {}).get("summary")
                or payload.get("subject")
                or payload.get("title")
                or ref.get("subject")
                or ref.get("title")
                or "Member"
            )
            ekind = "calendar_event" if channel == "calendar" else "communication"
            hit = R.EvidenceHit(
                evidence_id=eid,
                evidence_kind=ekind,
                summary=str(summary),
                score=1.0,
                excerpt=str(payload.get("body_text") or payload.get("description") or summary)[:280],
                source="occurrence_membership",
                sent_at=payload.get("sent_at") or payload.get("start") or ref.get("sent_at") or ref.get("start"),
                channel=channel if channel != "calendar" else "calendar",
                people=None,
                thread_id=payload.get("thread_id"),
            )
            evidence.append(_stamp(hit, m))
        elif kind == "spoken_moment":
            sid = str(ref.get("spoken_moment_id") or "")
            row = by_spoken.get(sid) or {}
            t0 = float(row.get("t_start") if row.get("t_start") is not None else ref.get("t_start") or 0)
            t1 = float(row.get("t_end") if row.get("t_end") is not None else ref.get("t_end") or t0)
            vid = str(row.get("video_external_id") or ref.get("video_external_id") or "")
            pk = str(row.get("video_provider_key") or ref.get("video_provider_key") or "hvrt")
            text = str(row.get("text") or ref.get("text") or "")
            hit = R.VideoHit(
                provider_key=pk,
                external_id=f"{vid}:{t0:.3f}",
                video_external_id=vid,
                start_sec=t0,
                end_sec=t1,
                label="Spoken Moment",
                play_url=_play_url(pk, vid, t0),
                identity_trust=st if st == "owner_confirmed" else "candidate",
                spoken_text=text,
                clip_kind="spoken_moment",
                attribution="occurrence_spoken_moment",
            )
            hit.spoken_moment_id = sid
            videos.append(_stamp(hit, m))
            spoken_precise.append(
                {
                    "spoken_moment_id": sid,
                    "video_external_id": vid,
                    "t_start": t0,
                    "t_end": t1,
                    "membership_id": m.get("id"),
                    "status": st,
                    "text": text[:240],
                }
            )
        elif kind == "face_range":
            aid = str(ref.get("appearance_moment_id") or "")
            row = by_face.get(aid) or {}
            t0 = float(row.get("start_sec") if row.get("start_sec") is not None else ref.get("start_sec") or 0)
            t1 = float(row.get("end_sec") if row.get("end_sec") is not None else ref.get("end_sec") or t0)
            vid = str(row.get("video_external_id") or ref.get("video_external_id") or "")
            pk = str(row.get("video_provider_key") or ref.get("video_provider_key") or "hvrt")
            hit = R.VideoHit(
                provider_key=pk,
                external_id=f"{vid}:{t0:.3f}",
                video_external_id=vid,
                start_sec=t0,
                end_sec=t1,
                face_external_id=row.get("face_external_id") or ref.get("face_external_id"),
                label="Face appearance",
                play_url=_play_url(pk, vid, t0),
                identity_trust=st if st == "owner_confirmed" else "candidate",
                clip_kind="face_range",
                attribution="occurrence_face_range",
            )
            videos.append(_stamp(hit, m))
        elif kind == "artifact":
            artifacts.append(
                {
                    "id": ref.get("artifact_id"),
                    "label": ref.get("label") or "Artifact",
                    "membership_status": st,
                    "membership_id": m.get("id"),
                    "occurrence_id": occurrence_id,
                }
            )

    confirmed = sum(1 for m in members if m.get("status") == "owner_confirmed")
    candidates = sum(1 for m in members if m.get("status") == "candidate")
    return {
        "photos": photos,
        "evidence": evidence,
        "videos": videos,
        "artifacts": artifacts,
        "members": members,
        "kinds": sorted(kinds),
        "confirmed_n": confirmed,
        "candidate_n": candidates,
        "spoken_precise": spoken_precise,
        "places": list_places(occurrence_id),
    }
