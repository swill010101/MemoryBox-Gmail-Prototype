"""P2-I11 tell synthesis: prepared pack + provider-neutral LLM. Fail closed if down."""
from __future__ import annotations

import json
import re
from typing import Any

from memorybox.ask.evidence_prep import prepare_narrative_pack
from memorybox.ask.narrative_ground import ground_narrative
from memorybox.providers.base import ProviderError, ProviderUnavailable
from memorybox.providers.llm.dto import ChatMessage

LIVING_VIEW_SCHEMA = 1
NARRATION_UNAVAILABLE = (
    "Narration unavailable. Family evidence and coverage are still shown. "
    "MemoryBox will not substitute a stitched essay for the narrator."
)

SYSTEM_PROMPT = """NARRATIVE_SYNTHESIS
Write like a careful family documentarian or historian, not a novelist.
The user JSON is a semantic life-period outline produced before narration. It is not an archive dump.
You receive: Person/relationship/background context; chronological episodes with grounded claims and evidence IDs; explicit scheduled_window, observed_window, and derived_window on episodes and the pack; story-claim uncertainty.
You do not receive, and must not invent, archive-count summaries, week-count summaries, or implementation diagnostics.

The narrator never renders system truth fields. Python, the UI, and AI Trace render retrieve/process completeness, evidence-considered counts, volume, missing-modality notices, eligible/processed totals, model name, and diagnostics.

Write a factual chronological account in natural prose. Connect grounded facts. Do not dramatize, embellish, or add scene-setting that is not directly supported.

Rules:
- Documentary, not literary. Precise, restrained wording. No colorful scene-setting.
- Narrate only the episodes and themes in this outline. Do not mention every week. Do not iterate dates that have no characterizing episode.
- Continuous prose (about 2–8 short paragraphs). Chronological. Begin with the account.
- Write from grounded claims and evidence IDs. Do not paste bodies, headers, quoted replies, addresses, or "On … wrote:" chains.
- Do not introduce geographic details (for example “Bering Sea”) unless a supporting evidence ID / listed place or claim establishes that location.
- Do not describe weather, emotional reactions, motives, atmosphere, excitement, concern, disappointment, beauty, or other experiential details unless those words appear in the grounded claims.
- Distinguish planned/scheduled from observed/actual. A calendar range is not proof of travel across that entire range.
- Prefer observed_window when photos, GPS, or other observations corroborate an actual span. Keep scheduled_window as planning evidence if useful. derived_window is inferred (for example travel extracted from mail) — not narrative fact of presence.
- When evidence type affects certainty, use phrasing such as “the calendar showed…,” “travel records indicate…,” “photos place…,” or “messages suggest…”.
- Do not convert plausible inference into narrative fact.
- Do not write how much mail, how many texts, how many weeks, or how MemoryBox processed the archive.
- Do not write retrieve/process completeness, evidence-considered counts, archive or week counts, missing-modality notices, eligible/processed totals, model name, or AI Trace diagnostics.
- Do not list shipping notices, receipts, surveys, or ordinary order confirmations unless they are a listed characterizing claim.
- Presence is not photographer, purpose, emotion, companions, or extra significance.
- Do not treat filename, folder, or camera owner as photographer.
- SMS timestamp is not location.
- Do not invent people, places, or dates.
- If episodes is empty, say the period was examined and nothing standout emerged. Do not dump ordinary correspondence.
"""


_DEBUG_LEAK = re.compile(
    r"(?is)\s*(year-fair sample[^.]*\.?|showing \d+ of \d+[^.]*\.?|"
    r"ingested (?:SMS|email|calendar)[^.]*\.?|bounded_tell_[a-z]+;[^.\n]*|"
    r"tell pack; email_n=\d+[^.]*\.?|"
    r"\d{4}-W\d{2}:[^.]*evidence item\(s\)[^.]*\.?|"
    r"Around \d{4}-\d{2}-\d{2}, \d+ (?:email|sms|calendar)[^.]*\.?|"
    r"Across the weeks that have evidence,[^.]*\.?|"
    r"coverage is incomplete[^.]*\.?|"
    r"coverage of the archive[^.]*\.?|"
    r"family evidence considered:[^\n]*|"
    r"family evidence used:[^\n]*|"
    r"processed \d+ of \d+ eligible[^.]*\.?|"
    r"considered \d+ eligible item[^.]*\.?|"
    r"no photos found[^.]*\.?)"
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


def default_modality_state(plan: Any, pack: dict[str, Any] | None = None) -> dict[str, str]:
    """queried vs not_requested for footer zeros. Caller may overlay failed/skipped."""
    used = (pack or {}).get("evidence_used") or {}
    want_photo = bool(getattr(plan, "want_photo", False) or getattr(plan, "want_still", False))
    want_video = bool(getattr(plan, "want_video", False))
    want_spoken = bool(getattr(plan, "want_spoken", False))
    return {
        "photos": "queried" if want_photo else "not_requested",
        "video_moments": "queried" if want_video else "not_requested",
        "spoken_moments": "queried" if want_spoken else "not_requested",
        "emails": "queried" if getattr(plan, "want_communication", False) or getattr(plan, "output_mode", "") == "tell" else "not_requested",
        "sms": "queried" if getattr(plan, "want_communication", False) or getattr(plan, "output_mode", "") == "tell" else "not_requested",
        "calendar_events": "queried" if getattr(plan, "want_calendar", False) or getattr(plan, "output_mode", "") == "tell" else "not_requested",
        "journal_entries": "queried" if getattr(plan, "want_journal", False) or getattr(plan, "output_mode", "") == "tell" else "not_requested",
        "stories": "queried" if getattr(plan, "want_story", False) or getattr(plan, "output_mode", "") == "tell" else "not_requested",
        "artifacts": "queried" if getattr(plan, "want_artifact", False) else "not_requested",
        "travel": "queried" if used.get("travel") or getattr(plan, "output_mode", "") == "tell" else "not_requested",
        "place_event": "not_requested",
    }


def evidence_used_footer(pack: dict[str, Any] | None) -> str:
    used = (pack or {}).get("evidence_considered") or (pack or {}).get("evidence_used") or {}
    state = (pack or {}).get("modality_state") if isinstance((pack or {}).get("modality_state"), dict) else {}
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
        st = str(state.get(key) or "")
        if st in {"unavailable", "failed"}:
            bits.append(f"{label} unavailable")
            continue
        if st in {"skipped", "not_requested"}:
            continue
        n = int(used.get(key) or 0)
        if n or st == "queried":
            bits.append(f"{n} {label}")
        elif n:
            bits.append(f"{n} {label}")
    if not bits:
        return "Family evidence considered: none processed for this Ask."
    return "Family evidence considered: " + " · ".join(bits) + "."


def coverage_incomplete_line(pack: dict[str, Any] | None) -> str:
    """Family-facing retrieve/process completeness — Python/UI only, never the model."""
    if not isinstance(pack, dict):
        return ""
    cov = pack.get("coverage") if isinstance(pack.get("coverage"), dict) else {}
    if not cov.get("incomplete"):
        return ""
    note = str(cov.get("truncation_disclosure") or "").strip()
    if note:
        if note.lower().startswith("coverage is incomplete"):
            return note
        return "Coverage is incomplete. " + note
    return "Coverage is incomplete."


def missing_modality_lines(pack: dict[str, Any] | None) -> str:
    """Family-facing missing-modality notice — Python/UI only, never the model."""
    if not isinstance(pack, dict):
        return ""
    cov = pack.get("coverage") if isinstance(pack.get("coverage"), dict) else {}
    scope = pack.get("scope") if isinstance(pack.get("scope"), dict) else {}
    missing = cov.get("missing") or []
    # Requestor-library period tells searched the owner's photos; zero hits
    # must not look like "photos were never searched."
    if "photos" in missing and scope.get("requestor_library"):
        return "No photos were found for this period."
    return ""


def _story_uncertainty(episodes: list[Any]) -> dict[str, Any]:
    flags: dict[str, Any] = {
        "provenance": (
            "Claims are grounded in the evidence IDs on each episode. "
            "Do not invent facts. Calendar scheduled is not proof the event occurred. "
            "A calendar range is not proof of travel across that entire range. "
            "Prefer the strongest corroborated actual window; keep broader scheduled windows as planning. "
            "Travel facts may be derived from communication. "
            "Do not add places, weather, emotions, companions, or transitions unless an evidence ID supports them."
        ),
    }
    for ep in episodes:
        if not isinstance(ep, dict):
            continue
        u = ep.get("uncertainty")
        if not isinstance(u, dict):
            continue
        if u.get("calendar_scheduled_not_occurred"):
            flags["calendar_scheduled_not_occurred"] = True
        if u.get("travel_derived_from_communication"):
            flags["travel_derived_from_communication"] = True
    return flags


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
    episodes = list(outline.get("episodes") or [])
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
        "scheduled_window": outline.get("scheduled_window"),
        "observed_window": outline.get("observed_window"),
        "derived_window": outline.get("derived_window"),
        "episodes": episodes,
        "uncertainty": _story_uncertainty(episodes),
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
    narrator.pop("coverage", None)
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
        text = _strip_debug_leak(text)
        grounded, rejected_adds = ground_narrative(text, pack)
        if rejected_adds:
            meta["narrative_rejected"] = rejected_adds
            pack["narrative_validation"] = {
                "rejected": rejected_adds,
                "ok": bool(grounded),
            }
        if not grounded:
            meta["fail_closed"] = True
            return _fail_closed(
                pack,
                reason="Narration added unsupported detail and was rejected.",
            ), meta
        text = grounded
        cov_line = coverage_incomplete_line(pack)
        if cov_line:
            text = text.rstrip() + "\n\n" + cov_line
        miss_line = missing_modality_lines(pack)
        if miss_line:
            text = text.rstrip() + "\n\n" + miss_line
        footer = evidence_used_footer(pack)
        if "Family evidence considered" not in text and "Family evidence used" not in text:
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
    modality_state: dict[str, Any] | None = None,
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
    from memorybox.ask.i11a import needs_semantic_inference
    from memorybox.ask.i11a.infer import apply_inference_to_pack

    pack["modality_state"] = {
        **default_modality_state(plan, pack),
        **(modality_state or {}),
    }
    if needs_semantic_inference(plan):
        pack = apply_inference_to_pack(plan, pack, llm, modality_state=pack.get("modality_state"))
        if pack.get("inference", {}).get("fail_closed"):
            meta = {"ok": False, "fail_closed": True, "i11a": True}
            reason = str(pack.get("inference", {}).get("reason") or "Semantic inference is unavailable.")
            return _fail_closed(pack, reason=reason), pack, meta
    text, meta = synthesize_tell(plan, pack, llm)
    return text, pack, meta
