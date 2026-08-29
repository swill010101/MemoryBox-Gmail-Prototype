"""Grounded communication-pattern observations — not personality psychology."""
from __future__ import annotations

import re
from typing import Any

from memorybox.ask.i11a.windows import _day

_LOVE = re.compile(r"(?i)\blove\s+you\b|\blove\s+ya\b|\bly\b")
_HEART = re.compile(
    r"[\U0001F495\U0001F496\U0001F497\U0001F498\U0001F49A\U0001F49B"
    r"\U0001F49C\U0001F49D\U0001F49E\U0001F49F\u2764\u2665\U0001F60D\U0001F618]"
    r"|(?<![a-z])<3(?![a-z])",
)
_DINNER = re.compile(r"(?i)\b(dinner|supper|come\s+over\s+to\s+eat|let'?s\s+eat)\b")
_GIFT = re.compile(
    r"(?i)\b(gift|present|sent\s+you|baked|brought\s+over|dropped\s+off|"
    r"care\s+package|meal\s+for\s+you)\b"
)
_INVITE = re.compile(r"(?i)\b(come\s+over|join\s+us|invitation|rsvp|are\s+you\s+free)\b")
_TRAVEL = re.compile(
    r"(?i)\b(flight|airport|hotel|itinerary|packing|visit\s+you|coming\s+to)\b"
)


def _text(unit: dict[str, Any]) -> str:
    return " ".join(
        str(x or "")
        for x in (
            unit.get("content"),
            unit.get("authored_text"),
            unit.get("subject"),
            unit.get("title"),
        )
    )


def _ids(unit: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in (unit.get("evidence_id"), unit.get("unit_id"), unit.get("source_id")):
        s = str(key or "").strip()
        if s and s not in out:
            out.append(s)
    for extra in unit.get("extra_ids") or []:
        s = str(extra or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _people(unit: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for p in unit.get("people") or []:
        if isinstance(p, dict):
            n = str(p.get("name") or "").strip()
        else:
            n = str(p).strip()
        if n and n not in names:
            names.append(n)
    for n in unit.get("participants") or []:
        s = str(n).strip()
        if s and s not in names:
            names.append(s)
    return names


def _pattern_unit(
    *,
    pattern_type: str,
    label: str,
    rows: list[dict[str, Any]],
    claim: str,
) -> dict[str, Any]:
    days = sorted(d for d in (_day(u.get("time") or u.get("timestamp")) for u in rows) if d)
    eids: list[str] = []
    people: list[str] = []
    for u in rows:
        for i in _ids(u):
            if i not in eids:
                eids.append(i)
        for n in _people(u):
            if n not in people:
                people.append(n)
    reps = eids[:8]
    return {
        "unit_id": f"pat-{pattern_type}-{eids[0] if eids else 'x'}",
        "evidence_id": reps[0] if reps else f"pat-{pattern_type}",
        "kind": "comm_pattern",
        "source_type": "pattern",
        "pattern_type": pattern_type,
        "time": days[0] if days else None,
        "date_span": {"start": days[0] if days else None, "end": days[-1] if days else None},
        "people": [{"name": n, "role": "participant"} for n in people[:12]],
        "place": None,
        "content": claim[:400],
        "occurrence_count": len(rows),
        "extra_ids": eids,
        "source_evidence_ids": eids,
        "representative_evidence_ids": reps,
        "asset_ref": None,
        "claim_type": "observed",
    }


def communication_pattern_units(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recurring message patterns with full provenance. Not trait psychology."""
    comms = [
        u
        for u in units
        if str(u.get("kind") or "") == "communication"
        or str(u.get("source_type") or "") in {"sms", "email", "imessage"}
    ]
    if not comms:
        return []
    buckets: dict[str, list[dict[str, Any]]] = {
        "affectionate_signoff": [],
        "heart_emoji": [],
        "dinner_planning": [],
        "gifts_or_meals": [],
        "invitations": [],
        "travel_planning": [],
    }
    by_people: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for u in comms:
        text = _text(u)
        if _LOVE.search(text):
            buckets["affectionate_signoff"].append(u)
        if _HEART.search(text):
            buckets["heart_emoji"].append(u)
        if _DINNER.search(text):
            buckets["dinner_planning"].append(u)
        if _GIFT.search(text):
            buckets["gifts_or_meals"].append(u)
        if _INVITE.search(text):
            buckets["invitations"].append(u)
        if _TRAVEL.search(text):
            buckets["travel_planning"].append(u)
        key = tuple(sorted(_people(u))[:6])
        if key:
            by_people.setdefault(key, []).append(u)

    out: list[dict[str, Any]] = []
    specs = (
        (
            "affectionate_signoff",
            "Messages repeatedly included affectionate sign-offs such as “love you”.",
        ),
        (
            "heart_emoji",
            "Messages repeatedly used heart emojis.",
        ),
        (
            "dinner_planning",
            "Messages repeatedly planned dinners or meals together.",
        ),
        (
            "gifts_or_meals",
            "Messages repeatedly mentioned gifts, meals, or support sent or offered.",
        ),
        (
            "invitations",
            "Messages repeatedly included invitations to get together.",
        ),
        (
            "travel_planning",
            "Messages repeatedly discussed travel plans together.",
        ),
    )
    for ptype, claim in specs:
        rows = buckets[ptype]
        if len(rows) < 2:
            continue
        out.append(_pattern_unit(pattern_type=ptype, label=claim, rows=rows, claim=claim))

    for people_key, rows in by_people.items():
        if len(rows) < 4:
            continue
        names = ", ".join(people_key[:4])
        out.append(
            _pattern_unit(
                pattern_type="repeated_contact",
                label="repeated contact",
                rows=rows,
                claim=f"Repeated contact among {names} across {len(rows)} messages.",
            )
        )
    return out
