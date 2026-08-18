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

_KINSHIP_ROLE = (
    r"father|dad|mother|mom|son|daughter|grandfather|grandmother|"
    r"grandparent|grandpa|grandma|nana|grammy|gram|"
    r"uncle|aunt|spouse|partner|sibling|brother|sister|"
    r"grandson|granddaughter|grandchild|parent|child"
)
_MY_ROLE_RE = re.compile(rf"(?i)\bmy\s+({_KINSHIP_ROLE})\b")
# "show me dad" / "show me pictures of dad" / "show me stories about grandma"
_SHOW_ME_ROLE_RE = re.compile(
    rf"(?i)\bshow\s+me\s+"
    rf"(?:(?:pictures?|photos?|images?|videos?|stills?|stories?)\s+(?:of\s+|about\s+)?)?"
    rf"(?:(?:my|our)\s+)?"
    rf"({_KINSHIP_ROLE})\b"
)
_STORIES_ABOUT_ROLE_RE = re.compile(
    rf"(?i)\bstories?\s+about\s+(?:(?:my|our)\s+)?({_KINSHIP_ROLE})\b"
)
# "pictures of me/myself", "show me myself", "show me me" → owner (not prior dad context)
_PICTURES_OF_ME_RE = re.compile(
    r"(?i)"
    r"(?:\b(?:pictures?|photos?|images?|videos?|stills?)\s+of\s+(?:me|myself)\b)"
    r"|(?:\bof\s+myself\b)"
    r"|(?:\bshow\s+me\s+(?:myself|me)\b)"
    r"|(?:\bshow\s+myself\b)"
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
    # I6 kinship
    kinship_hits: list[dict[str, Any]] | None = None
    path_summary: str | None = None
    path: list[dict[str, Any]] | None = None
    related_person_id: str | None = None
    related_display_name: str | None = None
    derived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_COUSINS_RE = re.compile(
    r"(?i)\b(?:who\s+are|show\s+me(?:\s+(?:pictures?|photos?))?(?:\s+of)?)\s+"
    r"(?:(?:all\s+)?(?:my|our)\s+)?cousins?\b"
    r"|\bmy\s+cousins?\b"
)
_GRANDCHILDREN_RE = re.compile(
    r"(?i)\b(?:who\s+are|show\s+me)\s+(?:(?:all\s+)?(?:my|our|mom'?s|mother'?s)\s+)?"
    r"grandchildren\b"
    r"|\b(?:my|mom'?s|mother'?s)\s+grandchildren\b"
)
_HOW_RELATED_RE = re.compile(
    r"(?i)\bhow\s+(?:am\s+i\s+related\s+to|is\s+(\w[\w\-']*(?:\s+\w[\w\-']*){0,3})\s+related\s+to)\s+"
    r"(\w[\w\-']*(?:\s+\w[\w\-']*){0,3})\b"
    r"|\bhow\s+am\s+i\s+related\s+to\s+(\w[\w\-']*(?:\s+\w[\w\-']*){0,3})\b"
)
_NIECE_NEPHEW_IN_PIC_RE = re.compile(
    r"(?i)\b(?:which|who)\s+of\s+my\s+(?:nieces?|nephews?|nieces\s+and\s+nephews)\s+"
    r"(?:are|is)\s+in\s+(?:this|the)\s+(?:picture|photo|image)\b"
)


def ensure_person_named(display_name: str) -> str:
    r = resolve_person_by_name(display_name, create_if_missing=True, confirm=True)
    return r.person_id


def get_person_profile(person_id: str) -> dict[str, Any]:
    from memorybox.profile.facts import list_aliases, list_contacts, list_facts
    from memorybox.profile.kinship import derive_kinship_for_person

    view = get_person(person_id)
    if not view:
        raise ProfileServiceError(f"person not found: {person_id}")
    owner = owner_config_status()
    kinship = derive_kinship_for_person(person_id)
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
            "direct": kinship.get("direct"),
            "extended": kinship.get("extended"),
            "counts": kinship.get("counts"),
        },
        "life_events": [
            e.to_dict() for e in list_life_events_for_person(person_id)
        ],
    }


def resolve_relational_ask(ask_text: str) -> RelationalAskResolve:
    """Resolve owner-relative language via Relationship / kinship services."""
    from memorybox.profile.kinship import how_related, relatives_of_kind

    q = (ask_text or "").strip()
    if not q:
        return RelationalAskResolve(ok=False, intent="none", disclosure="empty ask")

    who_am_i = bool(_WHO_AM_I_RE.search(q))
    pictures_me = bool(_PICTURES_OF_ME_RE.search(q))
    anniversary_me = bool(_ANNIVERSARY_RE.search(q) and re.search(r"(?i)\bmy\b", q))
    my_role = (
        _MY_ROLE_RE.search(q)
        or _SHOW_ME_ROLE_RE.search(q)
        or _STORIES_ABOUT_ROLE_RE.search(q)
    )
    cousins = bool(_COUSINS_RE.search(q))
    grandchildren = bool(_GRANDCHILDREN_RE.search(q))
    how_rel = _HOW_RELATED_RE.search(q)
    niece_pic = bool(_NIECE_NEPHEW_IN_PIC_RE.search(q))

    kinship_intent = cousins or grandchildren or how_rel or niece_pic

    # Non-relational asks must not touch owner config (leave planner / retrieve alone).
    if not (who_am_i or pictures_me or anniversary_me or my_role or kinship_intent):
        return RelationalAskResolve(ok=False, intent="none")

    try:
        owner_id = require_owner_person_id()
    except ProfileServiceError as exc:
        if kinship_intent or who_am_i or (my_role and _WHO_IS_RE.search(q)):
            intent = "kinship" if kinship_intent else "who"
        elif pictures_me:
            intent = "self"
        elif anniversary_me:
            intent = "anniversary"
        elif my_role and _SHOW_ME_ROLE_RE.search(q):
            intent = "pictures"
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

    # --- I6 kinship intents ---
    if cousins:
        hits = relatives_of_kind(owner_id, "cousins")
        want_pics = bool(re.search(r"(?i)\b(?:pictures?|photos?|images?)\b", q))
        return RelationalAskResolve(
            ok=True,
            intent="kinship_pictures" if want_pics else "kinship_list",
            role_phrase="cousin",
            person_id=owner_id,
            display_name=owner_name,
            kinship_hits=hits,
            derived=True,
            disclosure=(
                f"{len(hits)} cousin(s) derived from direct parent/sibling relationships."
                if hits
                else "No cousins derived from current direct relationships."
            ),
        )

    if grandchildren:
        subject_id = owner_id
        subject_name = owner_name
        role_phrase = "grandchild"
        # Mom's grandchildren
        if re.search(r"(?i)\b(?:mom'?s|mother'?s)\b", q):
            try:
                mom = resolve_one_relative(owner_id, role_phrase="mother")
                subject_id = mom.from_person_id
                subject_name = mom.from_display_name
                role_phrase = "mom_grandchild"
            except Exception as exc:  # noqa: BLE001
                return RelationalAskResolve(
                    ok=False,
                    intent="kinship_list",
                    role_phrase="mom_grandchild",
                    disclosure=str(exc),
                )
        hits = relatives_of_kind(subject_id, "grandchildren")
        # Also named person "Peggy's grandchildren"
        named = re.search(
            r"(?i)\b(?:who\s+are|show\s+me)\s+(\w[\w\-']*(?:\s+\w[\w\-']*){0,2})'?s\s+grandchildren\b",
            q,
        )
        if named and not re.search(r"(?i)\b(?:mom|mother|my|our)\b", named.group(1)):
            try:
                pid = ensure_person_named(named.group(1))
                subject_id = pid
                p = get_person(pid)
                subject_name = p.display_name if p else named.group(1)
                hits = relatives_of_kind(subject_id, "grandchildren")
                role_phrase = "named_grandchild"
            except Exception as exc:  # noqa: BLE001
                return RelationalAskResolve(
                    ok=False,
                    intent="kinship_list",
                    disclosure=str(exc),
                )
        return RelationalAskResolve(
            ok=True,
            intent="kinship_list" if not re.search(r"(?i)\bpictures?|photos?\b", q) else "kinship_pictures",
            role_phrase=role_phrase,
            person_id=subject_id,
            display_name=subject_name,
            kinship_hits=hits,
            derived=True,
            disclosure=(
                f"{len(hits)} grandchild(ren) derived for {subject_name}."
                if hits
                else f"No grandchildren derived for {subject_name}."
            ),
        )

    if how_rel:
        # how am I related to NAME  OR  how is A related to B
        g = how_rel.groups()
        # patterns: (A, B) from "how is A related to B" or (None, None, NAME) from "how am I related to NAME"
        if g[2]:
            name_b = g[2].strip().rstrip("?.!")
            try:
                b_id = ensure_person_named(name_b)
            except Exception as exc:  # noqa: BLE001
                return RelationalAskResolve(
                    ok=False, intent="how_related", disclosure=str(exc)
                )
            result = how_related(owner_id, b_id)
            b = get_person(b_id)
            return RelationalAskResolve(
                ok=bool(result.get("related")),
                intent="how_related",
                person_id=owner_id,
                display_name=owner_name,
                related_person_id=b_id,
                related_display_name=b.display_name if b else name_b,
                path_summary=result.get("path_summary"),
                path=result.get("path"),
                derived=bool(result.get("derived")),
                role_phrase=result.get("label"),
                disclosure=result.get("disclosure"),
                ambiguity="Multiple paths" if result.get("ambiguous") else None,
            )
        name_a = (g[0] or "").strip()
        name_b = (g[1] or "").strip().rstrip("?.!")
        try:
            a_id = ensure_person_named(name_a)
            b_id = ensure_person_named(name_b)
        except Exception as exc:  # noqa: BLE001
            return RelationalAskResolve(
                ok=False, intent="how_related", disclosure=str(exc)
            )
        result = how_related(a_id, b_id)
        pa = get_person(a_id)
        pb = get_person(b_id)
        return RelationalAskResolve(
            ok=bool(result.get("related")),
            intent="how_related",
            person_id=a_id,
            display_name=pa.display_name if pa else name_a,
            related_person_id=b_id,
            related_display_name=pb.display_name if pb else name_b,
            path_summary=result.get("path_summary"),
            path=result.get("path"),
            derived=bool(result.get("derived")),
            role_phrase=result.get("label"),
            disclosure=result.get("disclosure")
            or result.get("note"),
            ambiguity="Multiple materially different paths" if result.get("ambiguous") else None,
        )

    if niece_pic:
        hits = relatives_of_kind(owner_id, "nieces_nephews")
        return RelationalAskResolve(
            ok=True,
            intent="kinship_in_photo",
            role_phrase="niece_nephew",
            person_id=owner_id,
            display_name=owner_name,
            kinship_hits=hits,
            derived=True,
            disclosure=(
                "Filter recognized People in the selected photo against "
                f"{len(hits)} derived niece/nephew id(s). Requires an open photo "
                "with recognized faces (I5); no new recognition in I6."
            ),
        )

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
