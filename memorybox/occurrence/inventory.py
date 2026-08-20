"""Inventory FlightSim for the proof Trip/Event. Do not hard-code Alaska or Christmas."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from memorybox.db import connection
from memorybox.occurrence.discover import tokens_from_label
from memorybox.occurrence.store import list_memberships

_TOKEN = re.compile(r"[a-z0-9']{4,}")
_SKIP_TITLES = frozenset(
    {
        "busy",
        "blocked",
        "hold",
        "call",
        "meeting",
        "zoom",
        "lunch",
        "haircut",
        "pickup",
        "dropoff",
        "reminder",
    }
)


def _payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _day(value: Any) -> str:
    s = str(value or "")[:10]
    return s if len(s) == 10 else ""


def inventory_proof_candidates(*, limit: int = 12) -> list[dict[str, Any]]:
    """Score owner-named calendar/event titles by authentic cross-source overlap."""
    with connection() as conn:
        cals = conn.execute(
            """
            SELECT id, summary, payload_json
            FROM evidence
            WHERE evidence_kind = 'calendar_event'
            """
        ).fetchall()
        comms = conn.execute(
            """
            SELECT id, summary, payload_json
            FROM evidence
            WHERE evidence_kind = 'communication'
            """
        ).fetchall()
        spoken_n = conn.execute(
            """
            SELECT count(*)::int AS n
            FROM speech_spoken_moments
            WHERE COALESCE(status, 'accepted') <> 'withdrawn'
            """
        ).fetchone()
        occs = conn.execute(
            """
            SELECT id, kind, label, status, time_start, time_end
            FROM occurrences
            WHERE status NOT IN ('rejected', 'withdrawn')
            """
        ).fetchall()

    comm_index: list[tuple[str, str, str, str]] = []
    for r in comms:
        p = _payload(r["payload_json"])
        blob = " ".join(
            [
                str(r.get("summary") or ""),
                str(p.get("subject") or ""),
                str(p.get("body_text") or "")[:400],
            ]
        ).lower()
        day = _day(p.get("sent_at") or p.get("date"))
        ch = str(p.get("channel") or "email").lower()
        comm_index.append((str(r["id"]), blob, day, ch))

    scored: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    for r in cals:
        p = _payload(r["payload_json"])
        title = str(p.get("title") or r.get("summary") or "").strip()
        if not title or title.lower() in _SKIP_TITLES:
            continue
        toks = tokens_from_label(title)
        if not toks:
            continue
        day = _day(p.get("start"))
        loc = str(p.get("location") or "").strip()
        comm_hit = 0
        channels: set[str] = set()
        for _eid, blob, cday, ch in comm_index:
            if not any(t in blob for t in toks):
                continue
            if day and cday and abs(
                (int(day[:4] + day[5:7] + day[8:10]) if day else 0)
                - (int(cday[:4] + cday[5:7] + cday[8:10]) if cday else 0)
            ) > 400:  # rough YYYYMMDD distance ~ 1 year
                continue
            comm_hit += 1
            channels.add("sms" if ch in ("sms", "imessage", "mms") else "email")
        kind = "trip" if re.search(r"(?i)\b(trip|cruise|vacation|holiday)\b", title) else "event"
        modalities = {"calendar"}
        if comm_hit:
            modalities |= channels or {"email"}
        if loc:
            modalities.add("place")
        score = comm_hit * 3 + (2 if loc else 0) + len(toks)
        key = title.lower()
        if key in seen_labels:
            continue
        seen_labels.add(key)
        scored.append(
            {
                "kind": kind,
                "label": title,
                "time_start": p.get("start"),
                "place": loc or None,
                "calendar_id": str(r["id"]),
                "comm_hits": comm_hit,
                "modalities": sorted(modalities),
                "modality_n": len(modalities),
                "score": score,
            }
        )
    scored.sort(key=lambda x: (-x["score"], -x["modality_n"], x["label"]))

    existing = []
    for o in occs:
        members = list_memberships(str(o["id"]), include_rejected=False)
        kinds = sorted({str(m.get("evidence_kind")) for m in members})
        existing.append(
            {
                "kind": o["kind"],
                "label": o["label"],
                "occurrence_id": str(o["id"]),
                "status": o["status"],
                "member_n": len(members),
                "kinds": kinds,
                "modality_n": len(kinds),
                "score": 1000 + len(kinds) * 10 + len(members),
                "existing": True,
            }
        )
    existing.sort(key=lambda x: -x["score"])
    combined = existing + scored
    spoken_count = int((spoken_n or {}).get("n") or 0)
    for row in combined:
        row["archive_spoken_moments"] = spoken_count
    return combined[:limit]


def pick_proof_occurrence() -> dict[str, Any] | None:
    rows = inventory_proof_candidates(limit=12)
    if not rows:
        return None
    best = rows[0]
    if best.get("existing") and best.get("occurrence_id"):
        return {**best, "selected_from": "existing_occurrence"}
    return {**best, "selected_from": "inventory"}
