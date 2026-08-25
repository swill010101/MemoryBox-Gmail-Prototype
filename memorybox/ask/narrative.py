"""P2-I11 tell synthesis: prepared pack + provider-neutral LLM. Fail closed if down."""
from __future__ import annotations

import json
import re
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
You write a family story of life during the requested period.
The user JSON is a semantic life-period outline produced before narration. It is not an archive dump.
You receive: relevant Person/relationship/background context; significant chronological episodes/themes; grounded claim summaries; limited exemplars only where useful for human detail; uncertainty/provenance.
You do not receive, and must not invent, archive-count summaries, week-count summaries, raw date buckets, or implementation diagnostics.

Rules:
- Understand that the pipeline already considered the whole period. Narrate only the episodes and themes in this outline — the ones that meaningfully characterize the period. Do not mention every week. Do not iterate dates that have no characterizing episode.
- Continuous prose (about 2–8 short paragraphs). Chronological. Natural language. Begin with the story.
- Each episode lists grounded claims, supporting evidence IDs, a date span, people, and why it is significant. Write from the claims. Use an exemplar only when a human detail helps; do not paste bodies, headers, quoted replies, addresses, or "On … wrote:" chains.
- Do not write about how much mail, how many texts, how many weeks, or how MemoryBox processed the archive.
- Routine transactional material is not in this outline unless it belongs to a characterizing episode. Do not list shipping notices, receipts, surveys, or ordinary order confirmations.
- A source supports only the listed claim. Presence is not photographer, purpose, emotion, companions, or extra significance. Do not invent motives or feelings.
- Do not treat filename, folder, or camera owner as photographer.
- SMS timestamp is not location.
- Calendar rows are scheduled/recorded, not proof the event occurred unless corroborating claims exist.
- Travel facts may be derived; do not treat derivation as the original source.
- Do not invent people, places, or dates.
- If uncertainty.incomplete_coverage is true, say coverage is incomplete after the story. Never silently sample.
- If episodes is empty, say the period was examined and nothing standout emerged. Do not dump ordinary correspondence.
"""


_DEBUG_LEAK = re.compile(
    r"(?is)\s*(year-fair sample[^.]*\.?|showing \d+ of \d+[^.]*\.?|"
    r"ingested (?:SMS|email|calendar)[^.]*\.?|bounded_tell_[a-z]+;[^.\n]*|"
    r"tell pack; email_n=\d+[^.]*\.?|"
    r"\d{4}-W\d{2}:[^.]*evidence item\(s\)[^.]*\.?|"
    r"Around \d{4}-\d{2}-\d{2}, \d+ (?:email|sms|calendar)[^.]*\.?|"
    r"Across the weeks that have evidence,[^.]*\.?)"
)


def _strip_debug_leak(text: str) -> str:
    cleaned = _DEBUG_LEAK.sub(" ", text or "")
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


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
    used = (pack or {}).get("evidence_considered") or (pack or {}).get("evidence_used") or {}
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
        return "Family evidence considered: none processed for this Ask."
    return "Family evidence considered: " + " · ".join(bits) + "."


def _fail_closed(pack: dict[str, Any] | None, *, reason: str) -> str:
    cov = ""
    if isinstance(pack, dict):
        cov = str((pack.get("coverage") or {}).get("summary") or "").strip()
    parts = [p for p in (cov, NARRATION_UNAVAILABLE, evidence_used_footer(pack)) if p]
    if reason:
        parts.insert(1, reason)
    return "\n\n".join(parts)


def pack_for_narrator(pack: dict[str, Any]) -> dict[str, Any]:
    """Semantic life-period outline for the model — never week/count diagnostics."""
    outline = pack.get("life_period_outline") if isinstance(pack.get("life_period_outline"), dict) else {}
    ask = pack.get("ask") or {}
    scope = pack.get("scope") if isinstance(pack.get("scope"), dict) else {}
    time_scope = scope.get("time") if isinstance(scope.get("time"), dict) else {}
    cov = pack.get("coverage") if isinstance(pack.get("coverage"), dict) else {}
    outline_cov = outline.get("coverage") if isinstance(outline.get("coverage"), dict) else {}
    incomplete = bool(cov.get("incomplete") or outline_cov.get("incomplete"))
    note = None
    if incomplete:
        note = outline_cov.get("note") or cov.get("truncation_disclosure")
    return {
        "original_ask": ask.get("original_ask") if isinstance(ask, dict) else "",
        "background": pack.get("background") or {
            "people": scope.get("people") or [],
            "places": scope.get("places") or [],
            "trips": scope.get("events_trips") or [],
        },
        "period": outline.get("period") or time_scope.get("label") or "this period",
        "windows": outline.get("windows") or [
            {"start": w[0], "end": w[1]}
            for w in (time_scope.get("windows") or [])
            if isinstance(w, (list, tuple)) and len(w) >= 2
        ],
        "episodes": list(outline.get("episodes") or []),
        "uncertainty": {
            "incomplete_coverage": incomplete,
            "note": note,
            "provenance": (
                "Claims are grounded in the evidence IDs on each episode. "
                "Do not invent facts. Do not write archive counts or week summaries."
            ),
        },
    }


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
    narrator = pack_for_narrator(pack)
    payload = json.dumps(narrator, default=str)
    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=payload,
        ),
    ]
    from memorybox.ai_trace.context import reset_assembled_context, set_assembled_context

    vol = pack.get("volume") if isinstance(pack.get("volume"), dict) else {}
    assembled_tok = set_assembled_context(
        {
            "layer": "evidence",
            "eligible_n": vol.get("eligible_n"),
            "processed_n": vol.get("processed_n"),
            "narrator_input_n": vol.get("narrator_input_n"),
            "episode_n": vol.get("episode_n"),
            "significant_episode_n": vol.get("significant_episode_n"),
            "evidence_considered": pack.get("evidence_considered") or pack.get("evidence_used"),
            "derived_summaries": pack.get("derived_summaries"),
            "coverage": pack.get("coverage"),
            "narrator_keys": sorted(narrator.keys()),
        }
    )
    try:
        try:
            result = llm.chat(messages, json_mode=False)
        finally:
            reset_assembled_context(assembled_tok)
        text = str(getattr(result, "content", "") or "").strip()
        if not text:
            meta["fail_closed"] = True
            return _fail_closed(pack, reason="The model returned no narration."), meta
        footer = evidence_used_footer(pack)
        if "Family evidence considered" not in text and "Family evidence used" not in text:
            text = text.rstrip() + "\n\n" + footer
        text = _strip_debug_leak(text)
        if isinstance(pack.get("coverage"), dict) and pack["coverage"].get("incomplete"):
            note = str(pack["coverage"].get("truncation_disclosure") or "").strip()
            if note and "incomplete" not in text.lower():
                text = (
                    "Coverage is incomplete. "
                    + note
                    + "\n\n"
                    + text
                )
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
