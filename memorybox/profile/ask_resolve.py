"""Ask relational resolve — owner → Relationship service → MB Person id."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from memorybox.person import get_person, resolve_person_by_name
from memorybox.profile.facts import get_current_fact
from memorybox.profile.life_events import list_life_events_for_person
from memorybox.profile.owner import (
    INVERSE_ROLE,
    AmbiguousRelationshipError,
    ProfileServiceError,
    owner_config_status,
    require_owner_person_id,
)
from memorybox.profile.relationships import (
    list_relationship_assertions,
    project_derived_edges,
    resolve_one_relative,
)

_MY_ROLE_RE = re.compile(
    r"(?i)\bmy\s+(father|dad|mother|mom|son|daughter|grandfather|grandmother|"
    r"grandparent|uncle|aunt|spouse|partner|sibling|brother|sister|"
    r"grandson|granddaughter|grandchild|parent|child)\b"
)
_PICTURES_OF_ME_RE = re.compile(
    r"(?i)\b(pictures?|photos?|images?)\s+of\s+(me|myself)\b|\bof\s+myself\b"
)
_WHO_AM_I_RE = re.compile(r"(?i)\bwho\s+am\s+i\b")
_WHO_IS_RE = re.compile(r"(?i)\bwho\s+is\b")
_WHEN_BORN_RE = re.compile(r"(?i)\bwhen\s+was\b.+\bborn\b|\bbirth\s*date\b")
_ANNIVERSARY_RE = re.compile(r"(?i)\b(my\s+)?anniversary\b|\bwhen\s+did\b.+\bmarry\b")


@dataclass
class RelationalAskResolve:
    ok: bool
    intent: str
    role_phrase: str | None = None
    person_id: str | None = None
    display_name: str | None = None
    fact: dict[str, Any] | None = None
    life_event: dict[str, Any] | None = None
    ambiguity: str | None = None
    disclosure: str | None = None
    assertion_id: str | None = None
    derived_inverse_role: str | None = None
    inferred: bool = False
    inference_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def ensure_person_named(display_name: str) -> str:
    r = resolve_person_by_name(display_name, create_if_missing=True, confirm=True)
    return r.person_id


def get_person_profile(person_id: str) -> dict[str, Any]:
    from memorybox.profile.facts import list_aliases, list_contacts, list_facts

    view = get_person(person_id)
    if not view:
        raise ProfileServiceError(f"person not found: {person_id}")
    owner = owner_config_status()
    return {
        "identity": view.to_dict(),
        "is_canonical_owner": owner.get("owner_person_id") == view.id,
        "owner": owner,
        "aliases": [a.to_dict() for a in list_aliases(person_id)],
        "facts": [f.to_dict() for f in list_facts(person_id)],
        "contacts": [c.to_dict() for c in list_contacts(person_id)],
        "relationships": {
            "assertions_sot": [
                r.to_dict() for r in list_relationship_assertions(person_id)
            ],
            "derived_edges": [e.to_dict() for e in project_derived_edges(person_id)],
        },
        "life_events": [
            e.to_dict() for e in list_life_events_for_person(person_id)
        ],
    }


def resolve_relational_ask(ask_text: str) -> RelationalAskResolve:
    """Resolve owner-relative language via Relationship service — no string hacks."""
    q = (ask_text or "").strip()
    if not q:
        return RelationalAskResolve(ok=False, intent="none", disclosure="empty ask")

    who_am_i = bool(_WHO_AM_I_RE.search(q))
    pictures_me = bool(_PICTURES_OF_ME_RE.search(q))
    anniversary_me = bool(_ANNIVERSARY_RE.search(q) and re.search(r"(?i)\bmy\b", q))
    my_role = _MY_ROLE_RE.search(q)

    # Non-relational asks must not touch owner config (leave planner / retrieve alone).
    if not (who_am_i or pictures_me or anniversary_me or my_role):
        return RelationalAskResolve(ok=False, intent="none")

    try:
        owner_id = require_owner_person_id()
    except ProfileServiceError as exc:
        # Owner missing: stop keyword/evidence fall-through (see Ask “who am i?” email hit).
        if who_am_i or (my_role and _WHO_IS_RE.search(q)):
            intent = "who"
        elif pictures_me:
            intent = "self"
        elif anniversary_me:
            intent = "anniversary"
        else:
            intent = "who"
        return RelationalAskResolve(
            ok=False,
            intent=intent,
            role_phrase=my_role.group(1).lower() if my_role else ("self" if who_am_i else None),
            disclosure=str(exc),
        )

    owner = get_person(owner_id)
    owner_name = owner.display_name if owner else None

    if who_am_i:
        return RelationalAskResolve(
            ok=True,
            intent="who",
            role_phrase="self",
            person_id=owner_id,
            display_name=owner_name,
        )

    if pictures_me:
        return RelationalAskResolve(
            ok=True,
            intent="self",
            person_id=owner_id,
            display_name=owner_name,
        )

    if anniversary_me:
        events = list_life_events_for_person(owner_id)
        marriages = [e for e in events if e.event_kind == "marriage"]
        if not marriages:
            return RelationalAskResolve(
                ok=False,
                intent="anniversary",
                disclosure="No marriage/anniversary life event recorded for the owner.",
            )
        if len(marriages) > 1:
            msg = "Multiple marriage events for owner; clarify which anniversary."
            return RelationalAskResolve(
                ok=False,
                intent="anniversary",
                ambiguity=msg,
                disclosure=msg,
            )
        return RelationalAskResolve(
            ok=True,
            intent="anniversary",
            person_id=owner_id,
            display_name=owner_name,
            life_event=marriages[0].to_dict(),
        )

    assert my_role is not None
    phrase = my_role.group(1).lower()
    try:
        edge = resolve_one_relative(owner_id, role_phrase=phrase)
    except AmbiguousRelationshipError as exc:
        return RelationalAskResolve(
            ok=False,
            intent="who" if _WHO_IS_RE.search(q) else "pictures",
            role_phrase=phrase,
            ambiguity=str(exc),
            disclosure=str(exc),
        )
    except ProfileServiceError as exc:
        return RelationalAskResolve(
            ok=False,
            intent="who" if _WHO_IS_RE.search(q) else "pictures",
            role_phrase=phrase,
            disclosure=str(exc),
        )

    rel_id = edge.from_person_id
    rel = get_person(rel_id)
    rel_name = rel.display_name if rel else edge.from_display_name

    intent = "pictures"
    if _WHO_IS_RE.search(q):
        intent = "who"
    elif _WHEN_BORN_RE.search(q):
        intent = "birth"

    fact_d = None
    if intent == "birth":
        fact = get_current_fact(rel_id, "birth_date")
        if not fact:
            return RelationalAskResolve(
                ok=False,
                intent="birth",
                role_phrase=phrase,
                person_id=rel_id,
                display_name=rel_name,
                assertion_id=edge.assertion_id,
                disclosure=f"No birth_date fact recorded for {rel_name or rel_id}.",
            )
        fact_d = fact.to_dict()

    return RelationalAskResolve(
        ok=True,
        intent=intent,
        role_phrase=phrase,
        person_id=rel_id,
        display_name=rel_name,
        fact=fact_d,
        assertion_id=edge.assertion_id,
        derived_inverse_role=INVERSE_ROLE.get(edge.sot_role_kind),
        inferred=bool(getattr(edge, "inferred", False)),
        inference_note=getattr(edge, "inference_note", None),
    )
