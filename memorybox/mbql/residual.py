"""Residual model fill — Q1 leftover slots only. Q4 fail back. I7A traces chat."""
from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any

from memorybox.planner import QueryPlan
from memorybox.providers.llm.dto import ChatMessage

_PRONOUN_SAY = re.compile(
    r"(?i)\bwhat\s+did\s+(she|he|they|her|him)\s+say\b|\bwhat\s+did\s+they\s+say\b"
)
_OTHER_TRIP = re.compile(
    r"(?i)\b((?:the\s+)?other\s+trip|(?:a\s+)?different\s+trip|that\s+trip)\b"
)

_RESIDUAL_SLOTS = (
    "person_names",
    "place_names",
    "event_labels",
    "trip_labels",
    "time_start",
    "time_end",
)
_PRONOUN_PEOPLE = frozenset({"she", "he", "they", "her", "him", "his", "their"})


def real_person_names(plan: QueryPlan) -> tuple[str, ...]:
    return tuple(n for n in (plan.person_names or ()) if str(n).strip().lower() not in _PRONOUN_PEOPLE)


def needs_residual(plan: QueryPlan, text: str) -> bool:
    if getattr(plan, "act", "find") in ("refine", "navigate"):
        return False
    q = text or plan.original_ask or ""
    if plan.requires_clarification:
        return True
    if _PRONOUN_SAY.search(q) and not real_person_names(plan):
        return True
    if _OTHER_TRIP.search(q) and not plan.trip_labels and not plan.reference_resolved:
        return True
    return False


def residual_slots(plan: QueryPlan, text: str) -> list[str]:
    q = text or plan.original_ask or ""
    out: list[str] = []
    if _PRONOUN_SAY.search(q) and not real_person_names(plan):
        out.append("person_names")
    if _OTHER_TRIP.search(q) and not plan.trip_labels:
        out.append("trip_labels")
    if plan.requires_clarification:
        for slot in _RESIDUAL_SLOTS:
            val = getattr(plan, slot, None)
            if not val:
                out.append(slot)
    # unique preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def _parse_json(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw or "")
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


def _clean_names(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    out: list[str] = []
    for item in value:
        t = str(item or "").strip()
        if t and t not in out:
            out.append(t)
    return tuple(out)


def try_residual_fill(plan: QueryPlan, text: str, llm: Any) -> QueryPlan | None:
    """Fill only residual slots. Extra slots / bad JSON → None (fail back)."""
    slots = residual_slots(plan, text)
    if not slots:
        return None
    payload = {
        "task": "mbql_residual_slot_fill",
        "ask": text,
        "allowed_slots": slots,
        "deterministic": {
            "person_names": list(plan.person_names),
            "place_names": list(plan.place_names),
            "event_labels": list(plan.event_labels),
            "trip_labels": list(plan.trip_labels),
            "time_start": plan.time_start,
            "time_end": plan.time_end,
            "ambiguity_message": plan.ambiguity_message,
        },
        "rules": [
            "Fill only allowed_slots.",
            "Do not invent extra people, dates, or modalities.",
            "If still ambiguous, set clarify=true and ambiguity_message.",
            "Return JSON only.",
        ],
    }
    token = None
    try:
        from memorybox.ai_trace import context as ai_ctx

        token = ai_ctx.set_assembled_context(
            {
                "task": "mbql_residual_slot_fill",
                "allowed_slots": slots,
                "deterministic": payload["deterministic"],
            }
        )
        result = llm.chat(
            [
                ChatMessage(
                    role="system",
                    content="Fill missing MemoryBox Ask slots. JSON only. No narrative.",
                ),
                ChatMessage(role="user", content=json.dumps(payload)),
            ],
            json_mode=True,
        )
        data = _parse_json(getattr(result, "content", "") or "")
    except Exception:  # noqa: BLE001
        return None
    finally:
        if token is not None:
            try:
                from memorybox.ai_trace import context as ai_ctx

                ai_ctx.reset_assembled_context(token)
            except Exception:  # noqa: BLE001
                pass
    if not data:
        return None

    extra = [k for k in data.keys() if k not in set(slots) | {"clarify", "ambiguity_message", "ok"}]
    if extra:
        # Extra slots are not applied (locked rule). Still may use allowed ones.
        pass

    updates: dict[str, Any] = {
        "compile_provenance": "mixed" if any(getattr(plan, s, None) for s in _RESIDUAL_SLOTS) else "model_fill",
        "notes": tuple(list(plan.notes) + ["mbql_residual_fill"]),
    }
    if data.get("clarify") is True:
        updates["requires_clarification"] = True
        updates["act"] = "clarify"
        msg = str(data.get("ambiguity_message") or plan.ambiguity_message or "Which person or trip?").strip()
        updates["ambiguity_message"] = msg
        return replace(plan, **updates)

    filled_any = False
    if "person_names" in slots:
        names = _clean_names(data.get("person_names"))
        if names:
            updates["person_names"] = names[:1]  # one referent; no extra people
            filled_any = True
    if "place_names" in slots:
        places = _clean_names(data.get("place_names"))
        if places:
            updates["place_names"] = places[:1]
            filled_any = True
    if "event_labels" in slots:
        events = _clean_names(data.get("event_labels"))
        if events:
            updates["event_labels"] = events
            filled_any = True
    if "trip_labels" in slots:
        trips = _clean_names(data.get("trip_labels"))
        if trips:
            updates["trip_labels"] = trips[:1]
            filled_any = True
    if "time_start" in slots and data.get("time_start"):
        updates["time_start"] = str(data.get("time_start"))[:10]
        filled_any = True
    if "time_end" in slots and data.get("time_end"):
        updates["time_end"] = str(data.get("time_end"))[:10]
        filled_any = True

    if not filled_any:
        return None
    if updates.get("person_names") or updates.get("trip_labels"):
        updates["requires_clarification"] = False
        updates["act"] = "find"
        updates["ambiguity_message"] = None
    return replace(plan, **updates)
