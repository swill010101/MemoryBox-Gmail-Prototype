"""P2-I11 — deterministic tell stitch + persistable Ask/view JSON."""
from __future__ import annotations

from typing import Any

LIVING_VIEW_SCHEMA = 1


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


def _subject(plan: Any) -> str:
    people = [str(n).strip() for n in (getattr(plan, "person_names", None) or ()) if str(n).strip()]
    places = [str(n).strip() for n in (getattr(plan, "place_names", None) or ()) if str(n).strip()]
    trips = [str(n).strip() for n in (getattr(plan, "trip_labels", None) or ()) if str(n).strip()]
    events = [
        str(n).strip()
        for n in (getattr(plan, "event_labels", None) or ())
        if str(n).strip() and not str(n).startswith("trip:")
    ]
    bits = people or trips or places or events
    if bits:
        return ", ".join(bits[:3])
    ask = str(getattr(plan, "original_ask", "") or "").strip()
    return ask[:80] if ask else "this ask"


def _clip(text: str, n: int = 280) -> str:
    t = " ".join((text or "").split())
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def synthesize_tell(
    plan: Any,
    statements: list[dict[str, Any]] | None,
    citations: list[dict[str, Any]] | None,
    coverage: dict[str, Any] | None = None,
    *,
    fallback: str | None = None,
) -> str:
    """Evidence-backed prose. Not family truth. No model call."""
    subject = _subject(plan)
    groups: dict[str, list[str]] = {
        "journal": [],
        "recollection": [],
        "communication": [],
        "photo": [],
        "video": [],
        "artifact": [],
        "other": [],
    }
    for s in statements or []:
        text = _clip(str(s.get("text") or ""))
        if not text:
            continue
        pk = str(s.get("provenance_kind") or "")
        label = str(s.get("label") or "").lower()
        if s.get("journal_ids") or label == "journal" or "journal" in pk:
            bucket = "journal"
        elif s.get("story_ids") or label == "recollection" or "narrator" in pk or "story" in pk:
            bucket = "recollection"
        elif s.get("evidence_ids") or label == "fact" and not s.get("photo_external_ids"):
            if s.get("photo_external_ids"):
                bucket = "photo"
            else:
                bucket = "communication"
        elif s.get("photo_external_ids") or "photo" in pk:
            bucket = "photo"
        elif s.get("video_external_ids") or "spoken" in text.lower() or "video" in pk:
            bucket = "video"
        elif s.get("artifact_ids") or "artifact" in pk:
            bucket = "artifact"
        else:
            bucket = "other"
        if len(groups[bucket]) < 4:
            groups[bucket].append(text)

    paras: list[str] = [
        f"From what MemoryBox has, here is an evidence-backed account of {subject}. "
        "This is synthesis from retrieved sources, not family truth until you Save Story."
    ]
    if groups["journal"]:
        paras.append("Owner journal: " + " ".join(groups["journal"]))
    if groups["recollection"]:
        paras.append("Owner recollection (Story): " + " ".join(groups["recollection"]))
    if groups["communication"]:
        paras.append(
            "Communications in the archive (may be hidden in Gallery until you add Email/SMS): "
            + " ".join(groups["communication"])
        )
    if groups["photo"]:
        paras.append("Photos: " + " ".join(groups["photo"]))
    if groups["video"]:
        paras.append("Video / spoken moments: " + " ".join(groups["video"]))
    if groups["artifact"]:
        paras.append("Artifacts: " + " ".join(groups["artifact"]))
    if groups["other"]:
        paras.append("Also cited: " + " ".join(groups["other"]))

    sourced = sum(len(v) for v in groups.values())
    if sourced == 0:
        if fallback and fallback.strip():
            paras.append(fallback.strip())
        else:
            paras.append(
                "No citable excerpts were available for a longer account. "
                "MemoryBox will not invent family facts."
            )
    n_cite = len(citations or [])
    cov = ""
    if isinstance(coverage, dict) and coverage.get("summary"):
        cov = str(coverage.get("summary") or "").strip()
    footer = f"From {n_cite} cited source(s)."
    if cov:
        footer = f"{cov} {footer}"
    paras.append(footer + " Use the gallery and coverage strip to inspect originals.")
    return "\n\n".join(paras)
