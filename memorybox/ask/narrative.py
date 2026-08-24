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
You are MemoryBox's narrator. Write a chronological story of the requested period as a whole, ONLY from the prepared outline JSON.
The outline's week summaries and episode structures already represent the complete processed evidence set. They are a hierarchical reduction, not a sample of "the first N records."
Rules:
- Write continuous prose (about 2–8 short paragraphs). Synthesize episodes in time order. Do not list records, dump JSON, or paste email/SMS/MIME bodies, headers, quoted replies, addresses, or "On … wrote:" chains.
- Do not mention debug strings, year-fair sampling, retrieve caps, n= counts, or implementation notes.
- A source supports only the claim listed. Presence is not photographer, purpose, emotion, companions, or significance. Do not invent motives or feelings.
- Do not treat filename, folder, or camera owner as photographer.
- SMS timestamp is not location. Use location_assertions.basis only.
- Calendar rows are scheduled/recorded, not proof the event occurred unless corroborating units exist.
- Travel units are derived; the original communication remains the authentic source.
- Derived week summaries are coverage context, not family truth. Use them so no week with evidence is ignored.
- Do not invent people, places, or dates.
- End with a short "Family evidence considered" line using evidence_considered counts of everything processed, not narrator seat counts.
- If coverage.incomplete is true, say coverage is incomplete and why from the pack. Never silently sample.
- If the pack is empty, say you do not have enough family evidence. Do not guess.
"""


_DEBUG_LEAK = re.compile(
    r"(?is)\s*(year-fair sample[^.]*\.?|showing \d+ of \d+[^.]*\.?|"
    r"ingested (?:SMS|email|calendar)[^.]*\.?|bounded_tell_[a-z]+;[^.\n]*|"
    r"tell pack; email_n=\d+[^.]*\.?)"
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
    """Outline for the model: complete period structure, not a raw-record dump."""
    episodes = []
    src = pack.get("narrator_episodes") or pack.get("episodes") or []
    for u in src:
        people = []
        for p in u.get("people") or []:
            if isinstance(p, dict):
                n = str(p.get("name") or "").strip()
            else:
                n = str(p or "").strip()
            if n:
                people.append(n)
        episodes.append(
            {
                "time": (u.get("time") or {}).get("value") if isinstance(u.get("time"), dict) else u.get("time"),
                "week": u.get("week"),
                "place": u.get("place"),
                "people": people[:8],
                "member_n": u.get("member_n"),
                "source_kinds": u.get("source_kinds"),
                "content": str(u.get("content") or "")[:400],
            }
        )
    derived = []
    for s in pack.get("derived_summaries") or []:
        if isinstance(s, dict):
            derived.append(
                {
                    "period": s.get("period"),
                    "text": s.get("text"),
                    "unit_n": s.get("unit_n"),
                    "episode_n": s.get("episode_n"),
                    "not_family_truth": True,
                }
            )
    ask = pack.get("ask") or {}
    plan = ask.get("plan") if isinstance(ask, dict) else {}
    cov = pack.get("coverage") or {}
    vol = pack.get("volume") or {}
    return {
        "schema_version": pack.get("schema_version"),
        "original_ask": ask.get("original_ask") if isinstance(ask, dict) else "",
        "output_mode": ask.get("output_mode") if isinstance(ask, dict) else "tell",
        "temporal_label": (pack.get("scope") or {}).get("time", {}).get("label")
        if isinstance(pack.get("scope"), dict)
        else (plan.get("temporal_label") if isinstance(plan, dict) else None),
        "outline": derived,
        "episodes": episodes,
        "derived_summaries": derived,
        "coverage": {
            "summary": cov.get("summary") if isinstance(cov, dict) else cov,
            "incomplete": bool(isinstance(cov, dict) and cov.get("incomplete")),
            "truncation_disclosure": cov.get("truncation_disclosure") if isinstance(cov, dict) else None,
        },
        "volume": {
            "eligible_n": vol.get("eligible_n"),
            "processed_n": vol.get("processed_n"),
            "narrator_input_n": vol.get("narrator_input_n") or vol.get("supplied_to_model_n"),
            "episode_n": vol.get("episode_n"),
        },
        "evidence_considered": pack.get("evidence_considered") or pack.get("evidence_used"),
        "evidence_used": pack.get("evidence_considered") or pack.get("evidence_used"),
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
    payload = json.dumps(pack_for_narrator(pack), default=str)
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
