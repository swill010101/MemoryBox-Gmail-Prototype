"""I11 heuristic episode families — diagnostic/regression only after I11A.

I11A inference is the product semantic engine for broad synthesis. Do not tune
these families as importance rules. Keep this module for dump-i11-episodes and
prove-i11 fixtures.

Families describe what the evidence is *about*. Commerce/admin/promo are not banned;
they are supporting archive unless a life-period topic is also grounded in the text.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

LIFE_FAMILIES = frozenset(
    {
        "health",
        "family_visit",
        "social_family",
        "project",
        "religious",
        "travel",
        "hobby_learning",
        "milestone",
        "household_project",
    }
)
SUPPORTING_FAMILIES = frozenset({"commerce", "promotional", "admin_notice", "noise"})
ATTACHABLE_FAMILIES = frozenset({"other", "presence", "calendar"})

_LIFE_PRIORITY = (
    "health",
    "travel",
    "religious",
    "milestone",
    "family_visit",
    "project",
    "hobby_learning",
    "household_project",
    "social_family",
)

_HEALTH_RE = re.compile(
    r"(?i)\b("
    r"surgery|surgical|surgeon|operation|procedure|"
    r"knee|hip|shoulder|orthopedic|orthopaedic|"
    r"recovery|rehab|rehabilitation|physical therapy|\bpt\b|"
    r"hospital|doctor'?s? appointment"
    r")\b"
)
_VISIT_RE = re.compile(
    r"(?i)\b(coming to (stay|visit)|staying with|flew in|here for (a |the )?(week|visit)|"
    r"family in town|visiting us)\b"
)
_SOCIAL_RE = re.compile(
    r"(?i)\b(dinner|birthday party|get[- ]together|cookout|harbor dinner|"
    r"see you (at|on|tuesday|thursday|sunday|monday|wednesday|friday|saturday))\b"
)
_PROJECT_RE = re.compile(
    r"(?i)\b(trivia night|fundrais|re:\s*sponsors?|volunteer committee|"
    r"planning (the|our) )\b"
)
_RELIGIOUS_RE = re.compile(
    r"(?i)\b(day of reflection|mass\b|liturgy|parish|retreat|church choir|"
    r"stations of the cross)\b"
)
_TRAVEL_RE = re.compile(
    r"(?i)\b(itinerary|boarding pass|flight to|check-?in|hotel reservation|"
    r"marriott|hilton|airbnb|rental car)\b"
)
_HOBBY_RE = re.compile(
    r"(?i)\b(rehearsal|music planning|choir practice|lessons|class of|"
    r"guitar|piano practice)\b"
)
_MILESTONE_RE = re.compile(
    r"(?i)\b(graduation|wedding|born on|new baby|retirement party|anniversary dinner)\b"
)
_HOUSEHOLD_RE = re.compile(
    r"(?i)\b(wi-?fi|wifi|router|internet (service|outage)|home network)\b"
)
_PROMO_RE = re.compile(
    r"(?i)\b("
    r"unsubscribe|% off|percent off|use code|promo code|limited time|"
    r"shop now|coupon|special offer|rewards club|e-?club|"
    r"this week only|don't miss|act now"
    r")\b"
)
_COMMERCE_RE = re.compile(
    r"(?i)\b("
    r"your order|order #|order has been processed|order confirmation|"
    r"refund|tracking|shipment|shipped|out for delivery|invoice|"
    r"payment received|package delivered"
    r")\b"
)
_ADMIN_RE = re.compile(
    r"(?i)\b("
    r"1099-?r|1099|1098-?[te]?|form w-?2|tax document|irs\.gov|"
    r"account statement|privacy (policy|notice)|terms of (use|service)"
    r")\b"
)
_SURGERY_KIND_RE = re.compile(
    r"(?i)\b(knee|hip|shoulder|back|heart|cataract)\b.*\bsurgery\b|"
    r"\bsurgery\b.*\b(knee|hip|shoulder|back)\b|"
    r"\b(knee|hip|shoulder) surgery\b"
)
_SCHEDULED_RE = re.compile(
    r"(?i)\bscheduled(?:\s+for)?\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?|\w+ \d{1,2})\b"
)
_TRIVIA_RE = re.compile(r"(?i)\btrivia night\b")
_REFLECTION_RE = re.compile(r"(?i)\bday of reflection\b")
_WEAK_SUBJECT_RE = re.compile(
    r"(?i)^(re:|fwd:|fw:)?\s*("
    r"your .+ order.*|.*order #\d+.*|.*refund.*|"
    r"latest info|sponsors?|lll+|.|"
    r".{1,3}"
    r")$"
)
_SUBJECT_STRIP = re.compile(r"(?i)^(re:|fwd:|fw:)\s*")


def unit_blob(unit: dict[str, Any]) -> str:
    return " ".join(
        str(x or "")
        for x in (
            unit.get("subject"),
            unit.get("title"),
            unit.get("content"),
            unit.get("authored_text"),
            unit.get("_raw_body"),
        )
    )


def looks_supporting_subject(subject: str) -> bool:
    s = str(subject or "")
    return bool(_COMMERCE_RE.search(s) or _ADMIN_RE.search(s) or _PROMO_RE.search(s) or _is_weak_title(s))


def _is_weak_title(title: str) -> bool:
    t = _SUBJECT_STRIP.sub("", str(title or "")).strip()
    if len(t) < 4:
        return True
    if re.fullmatch(r"(?i)l{2,}", t):
        return True
    if re.fullmatch(r"(?i)(re:|fwd:|fw:)?\s*(latest info|sponsors?|info|update|fyi)", t):
        return True
    if _COMMERCE_RE.search(t) or re.search(r"(?i)order #\d+", t):
        return True
    letters = re.sub(r"[^a-z]+", "", t.lower())
    if letters and not re.search(r"[aeiouy]", letters) and len(letters) <= 6:
        return True
    return False


def _families_in_blob(blob: str, *, kind: str, source_type: str) -> set[str]:
    found: set[str] = set()
    if _HEALTH_RE.search(blob):
        found.add("health")
    if _VISIT_RE.search(blob):
        found.add("family_visit")
    if _PROJECT_RE.search(blob):
        found.add("project")
    if _RELIGIOUS_RE.search(blob):
        found.add("religious")
    if _TRAVEL_RE.search(blob) or kind == "travel":
        found.add("travel")
    if _HOBBY_RE.search(blob):
        found.add("hobby_learning")
    if _MILESTONE_RE.search(blob):
        found.add("milestone")
    if _HOUSEHOLD_RE.search(blob):
        found.add("household_project")
    if _SOCIAL_RE.search(blob) and not _PROMO_RE.search(blob):
        found.add("social_family")
    if kind in {"journal", "story"}:
        found.add("milestone")
    if kind == "calendar" and not found:
        found.add("calendar")
    if kind in {"media_observation", "spoken_moment"} and not found:
        found.add("presence")
    supporting: set[str] = set()
    if _PROMO_RE.search(blob):
        supporting.add("promotional")
    if _COMMERCE_RE.search(blob):
        supporting.add("commerce")
    if _ADMIN_RE.search(blob):
        supporting.add("admin_notice")
    life = found & LIFE_FAMILIES
    if source_type == "sms" and not life and not supporting:
        found.add("social_family")
        life = found & LIFE_FAMILIES
    if life:
        return life
    if supporting:
        return supporting
    if found:
        return found
    if _is_weak_title(blob[:80]):
        return {"noise"}
    return {"other"}


def _primary_family(families: set[str]) -> str:
    for fam in _LIFE_PRIORITY:
        if fam in families:
            return fam
    for fam in ("promotional", "commerce", "admin_notice", "noise"):
        if fam in families:
            return fam
    if families:
        return sorted(families)[0]
    return "other"


def _event_label(blob: str, family: str, fallback: str) -> str:
    if family == "health":
        kind_m = _SURGERY_KIND_RE.search(blob)
        if kind_m or re.search(r"(?i)\bsurgery\b", blob):
            part = "knee"
            if kind_m:
                raw = kind_m.group(0).lower()
                for p in ("knee", "hip", "shoulder", "back", "heart", "cataract"):
                    if p in raw:
                        part = p
                        break
            if re.search(r"(?i)\b(recovery|rehab|physical therapy|\bpt\b)\b", blob):
                return f"Preparing for {part} surgery and recovery"
            return f"Preparing for {part} surgery"
        if re.search(r"(?i)physical therapy|\bpt\b", blob):
            return "Physical therapy"
        return "Health and recovery"
    if family == "project":
        if _TRIVIA_RE.search(blob) or re.search(r"(?i)\bsponsors?\b", blob):
            return "Trivia Night planning and fundraising"
        return "A recurring project or responsibility"
    if family == "religious":
        if _REFLECTION_RE.search(blob):
            if re.search(r"(?i)\bmusic\b", blob):
                return "Day of Reflection and music planning"
            return "Day of Reflection"
        return "Religious or community activity"
    if family == "household_project":
        if _HOUSEHOLD_RE.search(blob):
            return "Home Wi-Fi and internet"
        return "A household project"
    if family == "travel":
        return fallback if fallback and not _is_weak_title(fallback) else "Travel during the period"
    if family == "social_family":
        if re.search(r"(?i)\bharbor\b", blob) and re.search(r"(?i)\bdinner\b", blob):
            return "Harbor dinner"
        if re.search(r"(?i)\blunch\b", blob):
            return "Lunch plans"
        clean = _SUBJECT_STRIP.sub("", fallback).strip()
        if re.match(r"(?i)sms\s+\d+$", clean) or _is_weak_title(clean):
            return "Family messages"
        if clean and not _COMMERCE_RE.search(clean):
            return clean[:80]
        return "A family or social gathering"
    if family == "family_visit":
        return "Family visit"
    if family == "hobby_learning":
        if re.search(r"(?i)\bmusic\b", blob):
            return "Music planning and practice"
        return "A hobby or learning activity"
    if family in SUPPORTING_FAMILIES:
        return fallback[:80] if fallback else family
    clean = _SUBJECT_STRIP.sub("", fallback).strip()
    if clean and not _is_weak_title(clean):
        return clean[:80]
    return "Untitled correspondence"


def _grounded_claims(blob: str, family: str) -> list[str]:
    claims: list[str] = []
    if family == "health":
        sched = _SCHEDULED_RE.search(blob)
        if re.search(r"(?i)\bsurgery\b", blob):
            if sched:
                claims.append(f"Surgery was scheduled for {sched.group(1)}")
            else:
                claims.append("Surgery is mentioned in the evidence")
        if re.search(r"(?i)physical therapy|\bpt\b", blob):
            claims.append("Physical therapy is part of the period")
        if re.search(r"(?i)\brecovery\b", blob):
            claims.append("Recovery is underway or planned")
    if family == "project" and (_TRIVIA_RE.search(blob) or re.search(r"(?i)\bsponsors?\b", blob)):
        claims.append("Trivia Night planning and fundraising is underway")
    if family == "religious" and _REFLECTION_RE.search(blob):
        claims.append("Day of Reflection is being planned")
        if re.search(r"(?i)\bmusic\b", blob):
            claims.append("Music planning is tied to that event")
    if family == "household_project" and _HOUSEHOLD_RE.search(blob):
        claims.append("Home Wi-Fi or internet is being handled")
    if family == "social_family":
        if re.search(r"(?i)\bharbor\b", blob) and re.search(r"(?i)\bdinner\b", blob):
            claims.append("Harbor dinner is in the evidence")
        elif re.search(r"(?i)\bdinner\b", blob):
            claims.append("A dinner gathering is in the evidence")
    if family == "travel":
        claims.append("Travel arrangements appear in the evidence")
    return claims[:6]


def annotate_unit(unit: dict[str, Any]) -> dict[str, Any]:
    blob = unit_blob(unit)
    kind = str(unit.get("kind") or "")
    source_type = str(unit.get("source_type") or "")
    families = _families_in_blob(blob, kind=kind, source_type=source_type)
    primary = _primary_family(families)
    fallback = str(unit.get("subject") or unit.get("title") or unit.get("content") or "")
    label = _event_label(blob, primary, fallback)
    extra = _grounded_claims(blob, primary)
    claims = list(unit.get("claims") or [])
    for text in extra:
        claims.append({"type": "life_period", "text": text, "family": primary, "basis": ["authored_text"]})
    unit["claims"] = claims
    unit["primary_family"] = primary
    unit["topic_families"] = sorted(families)
    unit["event_label"] = label
    unit["event_key"] = f"{primary}:{re.sub(r'[^a-z0-9]+', '_', label.lower())[:48]}"
    unit["_primary_family"] = primary
    unit["_event_key"] = unit["event_key"]
    unit["_event_label"] = label
    return unit


def episode_group_key(unit: dict[str, Any], fallback_key: tuple[Any, ...]) -> tuple[Any, ...]:
    """Split mixed threads by grounded family; do not bucket by subject or week."""
    fam = str(unit.get("_primary_family") or unit.get("primary_family") or "other")
    kind = str(unit.get("kind") or "")
    if kind == "communication":
        tid = str(unit.get("thread_id") or "").strip()
        if tid:
            return ("thread_topic", tid, fam)
        return fallback_key[:2] + (fam, unit.get("unit_id"))
    if kind == "travel":
        conf = str(unit.get("confirmation") or "")[:80]
        return ("travel_topic", fam, conf or unit.get("unit_id"))
    return fallback_key + (fam,)


def families_compatible(a: str, b: str) -> bool:
    if a == b:
        return True
    if a in LIFE_FAMILIES and b in ATTACHABLE_FAMILIES:
        return True
    if b in LIFE_FAMILIES and a in ATTACHABLE_FAMILIES:
        return True
    return False


def is_life_family(fam: str) -> bool:
    return fam in LIFE_FAMILIES


def apply_episode_meaning(episode: dict[str, Any]) -> dict[str, Any]:
    members = list(episode.get("_members") or [])
    for m in members:
        if not m.get("_primary_family"):
            annotate_unit(m)
    fams = [str(m.get("_primary_family") or "other") for m in members]
    life = [f for f in fams if f in LIFE_FAMILIES]
    if life:
        primary = Counter(life).most_common(1)[0][0]
    else:
        primary = Counter(fams).most_common(1)[0][0] if fams else "other"
    blobs = " ".join(unit_blob(m) for m in members)
    labels = [str(m.get("_event_label") or "") for m in members if m.get("_event_label")]
    fallback = str(episode.get("title") or "")
    title = Counter(labels).most_common(1)[0][0] if labels else _event_label(blobs, primary, fallback)
    episode["title"] = title[:160]
    extra = _grounded_claims(blobs, primary)
    claims = list(episode.get("claims") or [])
    seen = {str(c.get("text") if isinstance(c, dict) else c) for c in claims}
    for text in extra:
        if text not in seen:
            claims.append({"type": "life_period", "text": text, "family": primary})
            seen.add(text)
    episode["claims"] = claims
    episode["primary_family"] = primary
    episode["event_label"] = title
    episode["event_key"] = f"{primary}:{re.sub(r'[^a-z0-9]+', '_', title.lower())[:48]}"
    if len(members) >= 3 and primary in LIFE_FAMILIES:
        episode["kind"] = "theme"
    return episode


def score_reason(episode: dict[str, Any], score: float) -> str:
    fam = str(episode.get("primary_family") or "other")
    if fam in LIFE_FAMILIES:
        return f"characterizes the period ({fam.replace('_', ' ')})"
    if fam in SUPPORTING_FAMILIES:
        return f"supporting archive ({fam.replace('_', ' ')}); not a characterizing life episode"
    return "does not clearly characterize life in the period"


def public_episode_dump(pack: dict[str, Any]) -> dict[str, Any]:
    audit = pack.get("episode_audit") if isinstance(pack.get("episode_audit"), dict) else {}

    def slim(rows: list[Any]) -> list[dict[str, Any]]:
        out = []
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            out.append(
                {
                    "title": r.get("title"),
                    "score": r.get("score"),
                    "reason": r.get("reason"),
                    "claims": r.get("claims") or [],
                    "evidence_ids": r.get("evidence_ids") or [],
                }
            )
        return out

    rejected = audit.get("rejected") or []
    return {
        "narrated": False,
        "candidates": slim(audit.get("candidates") or []),
        "selected": slim(audit.get("selected") or []),
        "rejected_titles": [r.get("title") for r in rejected if isinstance(r, dict)],
        "rejected": slim(rejected),
    }


def audit_row(episode: dict[str, Any]) -> dict[str, Any]:
    claims: list[str] = []
    for c in episode.get("claims") or []:
        if isinstance(c, dict):
            t = str(c.get("text") or "").strip()
            if t:
                claims.append(t)
        else:
            claims.append(str(c))
    ids = list(episode.get("evidence_ids") or [])[:40]
    return {
        "title": episode.get("title") or episode.get("event_label"),
        "family": episode.get("primary_family"),
        "score": episode.get("significance_score") if episode.get("significance_score") is not None else episode.get("significance"),
        "reason": episode.get("significance_reason"),
        "claims": claims[:8],
        "evidence_ids": ids,
        "selected": bool(episode.get("narrator_selected")),
    }
