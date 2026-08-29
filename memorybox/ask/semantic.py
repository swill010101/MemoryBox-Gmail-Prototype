"""Generalized semantic constraints — relative language, not phrase-specific fields."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

INTERPRETATION_KIND_YOUTH = "relative_youth"

# Versioned interpretations. Empty until the owner (or a test) registers one.
# Do not encode a universal numeric youth range in the planner.
_INTERPRETATIONS: dict[str, dict[str, Any]] = {}

RELATIVE_AGE_RE = re.compile(
    r"(?i)\bwhen\s+"
    r"(?P<who>dad|daddy|father|mom|mommy|mother|he|she|i|me|"
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
    r"\s+(?:was|were|is)\s+"
    r"(?P<phrase>young|younger|little|a\s+kid|a\s+child)"
)


@dataclass(frozen=True)
class SemanticConstraint:
    person_name: str | None
    person_id: str | None
    constraint_kind: str
    age_band: tuple[int, int] | None
    interpretation_id: str
    interpretation_version: str
    time_start: str | None
    time_end: str | None
    resolved: bool
    unresolved_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.age_band:
            d["age_band"] = [int(self.age_band[0]), int(self.age_band[1])]
        return d


def reset_interpretations() -> None:
    _INTERPRETATIONS.clear()


def register_interpretation(
    interpretation_id: str,
    *,
    version: str,
    age_band: tuple[int, int],
) -> None:
    lo, hi = int(age_band[0]), int(age_band[1])
    if lo < 0 or hi < lo:
        raise ValueError("age_band must be a non-negative inclusive range")
    _INTERPRETATIONS[interpretation_id] = {
        "interpretation_id": interpretation_id,
        "version": version,
        "age_band": (lo, hi),
    }


def get_interpretation(interpretation_id: str) -> dict[str, Any] | None:
    row = _INTERPRETATIONS.get(interpretation_id)
    return dict(row) if row else None


def _who_label(raw: str) -> str:
    w = (raw or "").strip()
    low = w.lower()
    if low in {"i", "me"}:
        return "self"
    if low in {"he", "she"}:
        return "context_person"
    if low in {"dad", "daddy", "father"}:
        return "Dad"
    if low in {"mom", "mommy", "mother"}:
        return "Mom"
    return w


def detect_relative_age(ask: str) -> dict[str, str] | None:
    m = RELATIVE_AGE_RE.search(ask or "")
    if not m:
        return None
    phrase = re.sub(r"\s+", " ", (m.group("phrase") or "").strip().lower())
    interp = INTERPRETATION_KIND_YOUTH
    if phrase in {"little", "a kid", "a child"}:
        interp = "relative_childhood"
    return {"who": _who_label(m.group("who") or ""), "interpretation_id": interp}


def _birth_year(person_id: str | None) -> int | None:
    if not person_id:
        return None
    try:
        from memorybox.profile.facts import get_current_fact

        fact = get_current_fact(person_id, "birth_date")
    except Exception:
        return None
    if not fact or not getattr(fact, "value_date", None):
        return None
    try:
        return int(str(fact.value_date)[:4])
    except (TypeError, ValueError):
        return None


def resolve_semantic_constraints(
    ask: str,
    *,
    person_names: tuple[str, ...] = (),
    person_ids: tuple[str, ...] = (),
    owner_person_id: str | None = None,
) -> list[SemanticConstraint]:
    hit = detect_relative_age(ask)
    if not hit:
        return []
    who = hit["who"]
    interp_id = hit["interpretation_id"]
    name = None
    pid = person_ids[0] if person_ids else None
    if who == "self":
        name = "self"
        pid = owner_person_id or pid
    elif who == "context_person":
        name = person_names[0] if person_names else None
    else:
        name = who if who not in person_names else (person_names[0] if person_names else who)
        if person_names and who.lower() == str(person_names[0]).lower():
            name = person_names[0]
        elif person_names and who in {"Dad", "Mom"}:
            name = person_names[0]
        elif person_names:
            name = person_names[0]
    interp = get_interpretation(interp_id)
    if not interp:
        return [
            SemanticConstraint(
                person_name=name,
                person_id=pid,
                constraint_kind="age_band",
                age_band=None,
                interpretation_id=interp_id,
                interpretation_version="unresolved",
                time_start=None,
                time_end=None,
                resolved=False,
                unresolved_reason=(
                    f"No stored interpretation for {interp_id}. "
                    "Ask what ages that phrase means rather than guessing."
                ),
            )
        ]
    band = interp["age_band"]
    by = _birth_year(pid)
    t0 = t1 = None
    resolved = False
    reason = None
    if by:
        t0 = f"{by + band[0]:04d}-01-01"
        t1 = f"{by + band[1]:04d}-12-31"
        # Do not project into the future as if it were lived years.
        today = date.today().isoformat()
        if t1 > today:
            t1 = today
        resolved = True
    else:
        reason = (
            "Birth date missing and no other reliable age/date evidence; "
            "will not guess calendar years."
        )
    return [
        SemanticConstraint(
            person_name=name,
            person_id=pid,
            constraint_kind="age_band",
            age_band=band,
            interpretation_id=interp_id,
            interpretation_version=str(interp["version"]),
            time_start=t0,
            time_end=t1,
            resolved=resolved,
            unresolved_reason=reason,
        )
    ]


def apply_constraints_to_plan(plan: Any) -> Any:
    from dataclasses import replace

    owner_id = None
    try:
        from memorybox.profile.owner import get_owner_person_id

        owner_id = get_owner_person_id()
    except Exception:
        owner_id = None
    constraints = resolve_semantic_constraints(
        str(getattr(plan, "original_ask", "") or ""),
        person_names=tuple(getattr(plan, "person_names", ()) or ()),
        person_ids=tuple(getattr(plan, "person_ids", ()) or ()),
        owner_person_id=owner_id,
    )
    if not constraints:
        return plan
    payload = tuple(c.to_dict() for c in constraints)
    notes = list(getattr(plan, "notes", ()) or [])
    notes.append("semantic_constraints")
    first = constraints[0]
    kwargs: dict[str, Any] = {
        "semantic_constraints": payload,
        "notes": tuple(notes),
    }
    if first.resolved and first.time_start and first.time_end:
        kwargs["time_start"] = first.time_start
        kwargs["time_end"] = first.time_end
        kwargs["temporal_windows"] = ((first.time_start, first.time_end),)
        kwargs["temporal_label"] = (
            f"{first.person_name or 'person'} age {first.age_band[0]}–{first.age_band[1]}"
            if first.age_band
            else None
        )
        notes.append("semantic_age_band_dates")
        kwargs["notes"] = tuple(notes)
    elif not first.resolved:
        kwargs["requires_clarification"] = True
        kwargs["ambiguity_message"] = (
            first.unresolved_reason
            or "Relative age language is unresolved. What ages do you mean?"
        )
        kwargs["act"] = "clarify"
        notes.append("semantic_age_band_ask")
        kwargs["notes"] = tuple(notes)
    return replace(plan, **kwargs)
