"""P2-I11 tell synthesis: prepared pack + provider-neutral LLM. Fail closed if down."""
from __future__ import annotations

import json
from typing import Any

from memorybox.ask.evidence_prep import prepare_narrative_pack
from memorybox.providers.base import ProviderError, ProviderUnavailable
from memorybox.providers.llm.dto import ChatMessage

LIVING_VIEW_SCHEMA = 1
NARRATION_UNAVAILABLE = (
    "Narration unavailable. Family evidence and coverage are still shown. "
    "MemoryBox will not substitute a stitched essay for the narrator."
)

SYSTEM_PROMPT = """NARRATIVE_SYNTHESIS
You are MemoryBox's narrator. Write readable prose ONLY from the prepared evidence pack JSON.
Rules:
- A source supports only the claim listed on that unit. Presence is not photographer, purpose, emotion, companions, or significance.
- Do not treat filename, folder, or camera owner as photographer.
- SMS timestamp is not location. Use location_assertions.basis only.
- Calendar rows are scheduled/recorded, not proof the event occurred unless corroborating units exist.
- Travel units are derived; the original communication remains the authentic source. Never ignore that provenance.
- Derived summaries are not family truth.
- Do not invent people, places, dates, or motives.
- End with a short "Family evidence used" line using evidence_used counts of supplied units.
- If the pack is empty, say you do not have enough family evidence. Do not guess.
"""


def persistable_view(
    *,
    original_ask: str,
    plan: dict[str, Any] | None,
    presentation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    p = dict(plan or {})
    return {
        "schema_version": LIVING_VIEW_SCHEMA,
        "original_ask": original_ask or p.get("original_ask") or "",
        "output_mode": p.get("output_mode") or "show",
        "plan": p,
        "presentation": dict(presentation or {}),
    }


def memories_from_citations(citations: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for c in citations or []:
        kind = str(c.get("kind") or "")
        source_kind = ""
        source_id = ""
        if kind == "photo":
            source_kind, source_id = "photo", str(c.get("external_id") or "")
        elif kind == "video":
            source_kind, source_id = "video", str(c.get("video_external_id") or c.get("external_id") or "")
        elif kind == "story":
            continue
        elif kind == "journal":
            source_kind, source_id = "journal", str(c.get("journal_id") or "")
        elif kind == "artifact":
            source_kind, source_id = "artifact", str(c.get("artifact_id") or "")
        elif kind == "evidence":
            ek = str(c.get("evidence_kind") or c.get("source") or "").lower()
            eid = str(c.get("evidence_id") or "")
            if "sms" in ek or ek in {"text", "imessage", "mms"}:
                source_kind = "sms_conversation"
            elif "calendar" in ek:
                source_kind = "calendar_event"
            elif "email" in ek or "mail" in ek:
                source_kind = "email_thread"
            else:
                source_kind = "evidence"
            source_id = eid
        if not source_kind or not source_id:
            continue
        key = (source_kind, source_id)
        if key in seen:
            continue
        seen.add(key)
        label = str(c.get("label") or c.get("title") or c.get("summary") or "").strip() or None
        out.append({"source_kind": source_kind, "source_id": source_id, "label_snapshot": label})
    return out[:24]


def evidence_used_footer(pack: dict[str, Any] | None) -> str:
    used = (pack or {}).get("evidence_used") or {}
    bits = []
    labels = (
        ("photos", "photos"),
        ("video_moments", "video moments"),
        ("spoken_moments", "spoken moments"),
        ("emails", "emails"),
        ("sms", "texts"),
        ("calendar_events", "calendar events"),
        ("journal_entries", "journal entries"),
        ("stories", "stories"),
        ("artifacts", "artifacts"),
        ("travel", "travel records"),
        ("place_event", "places/events"),
    )
    for key, label in labels:
        n = int(used.get(key) or 0)
        if n:
            bits.append(f"{n} {label}")
    if not bits:
        return "Family evidence used: none supplied for synthesis."
    return "Family evidence used: " + ", ".join(bits) + "."


def _fail_closed(pack: dict[str, Any] | None, *, reason: str) -> str:
    cov = ""
    if isinstance(pack, dict):
        cov = str((pack.get("coverage") or {}).get("summary") or "").strip()
    parts = [p for p in (cov, NARRATION_UNAVAILABLE, evidence_used_footer(pack)) if p]
    if reason:
        parts.insert(1, reason)
    return "\n\n".join(parts)


def synthesize_tell(
    plan: Any,
    pack: dict[str, Any],
    llm: Any,
) -> tuple[str, dict[str, Any]]:
    """LLM synthesis from the prepared pack. Never returns stitch-as-essay."""
    meta: dict[str, Any] = {"ok": False, "fail_closed": False}
    if llm is None:
        meta["fail_closed"] = True
        return _fail_closed(pack, reason="No language model is configured."), meta
    payload = json.dumps(pack, default=str)
    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=payload,
        ),
    ]
    try:
        result = llm.chat(messages, json_mode=False)
        text = str(getattr(result, "content", "") or "").strip()
        if not text:
            meta["fail_closed"] = True
            return _fail_closed(pack, reason="The model returned no narration."), meta
        footer = evidence_used_footer(pack)
        if "Family evidence used" not in text:
            text = text.rstrip() + "\n\n" + footer
        meta["ok"] = True
        meta["model"] = getattr(result, "model", None)
        return text, meta
    except (ProviderUnavailable, ProviderError) as exc:
        meta["fail_closed"] = True
        meta["error"] = str(exc)
        return _fail_closed(pack, reason="The narrator model is unavailable."), meta
    except Exception as exc:  # noqa: BLE001
        meta["fail_closed"] = True
        meta["error"] = str(exc)
        return _fail_closed(pack, reason="The narrator model is unavailable."), meta


def tell_from_hits(
    plan: Any,
    *,
    llm: Any,
    evidence: list[Any] | None = None,
    photos: list[Any] | None = None,
    videos: list[Any] | None = None,
    stories: list[Any] | None = None,
    journals: list[Any] | None = None,
    artifacts: list[Any] | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    pack = prepare_narrative_pack(
        plan,
        evidence=evidence,
        photos=photos,
        videos=videos,
        stories=stories,
        journals=journals,
        artifacts=artifacts,
    )
    text, meta = synthesize_tell(plan, pack, llm)
    return text, pack, meta
