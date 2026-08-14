"""P2-I6 — Derived kinship inference over the Person relationship graph.

Direct assertions remain SoT in ``person_relationship_assertions``.
This module *derives* extended kinship (cousin, nephew, …) with explainable
paths. Derived results are never written as confirmed SoT.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable
from uuid import UUID

from memorybox.profile.owner import (
    ROLE_AUNT_OF,
    ROLE_CHILD_OF,
    ROLE_DAUGHTER_OF,
    ROLE_FATHER_OF,
    ROLE_GRANDCHILD_OF,
    ROLE_GRANDPARENT_OF,
    ROLE_MOTHER_OF,
    ROLE_NEPHEW_OF,
    ROLE_NIECE_OF,
    ROLE_PARENT_OF,
    ROLE_PARTNER_OF,
    ROLE_SIBLING_OF,
    ROLE_SON_OF,
    ROLE_SPOUSE_OF,
    ROLE_UNCLE_OF,
    ROLE_ADOPTIVE_PARENT_OF,
    ROLE_BIOLOGICAL_PARENT_OF,
    ROLE_STEP_PARENT_OF,
    name_map,
    parse_uuid,
)
from memorybox.profile.relationships import list_relationship_assertions
from memorybox.db import connection

PARENT_ROLES = frozenset(
    {
        ROLE_FATHER_OF,
        ROLE_MOTHER_OF,
        ROLE_PARENT_OF,
        ROLE_BIOLOGICAL_PARENT_OF,
        ROLE_ADOPTIVE_PARENT_OF,
        ROLE_STEP_PARENT_OF,
    }
)
CHILD_ROLES = frozenset({ROLE_CHILD_OF, ROLE_SON_OF, ROLE_DAUGHTER_OF})
SIBLING_ROLES = frozenset({ROLE_SIBLING_OF})
SPOUSE_ROLES = frozenset({ROLE_SPOUSE_OF, ROLE_PARTNER_OF})

# UX vocabulary → SoT role_kind
UX_ROLE_TO_SOT: dict[str, str] = {
    "parent": ROLE_PARENT_OF,
    "mother": ROLE_MOTHER_OF,
    "father": ROLE_FATHER_OF,
    "child": ROLE_CHILD_OF,
    "son": ROLE_SON_OF,
    "daughter": ROLE_DAUGHTER_OF,
    "sibling": ROLE_SIBLING_OF,
    "brother": ROLE_SIBLING_OF,
    "sister": ROLE_SIBLING_OF,
    "spouse": ROLE_SPOUSE_OF,
    "husband": ROLE_SPOUSE_OF,
    "wife": ROLE_SPOUSE_OF,
    "partner": ROLE_PARTNER_OF,
}

DIRECT_GROUP_ORDER = ("parents", "siblings", "spouse_partner", "children")

ROLE_DISPLAY: dict[str, str] = {
    ROLE_FATHER_OF: "Father",
    ROLE_MOTHER_OF: "Mother",
    ROLE_PARENT_OF: "Parent",
    ROLE_BIOLOGICAL_PARENT_OF: "Parent",
    ROLE_ADOPTIVE_PARENT_OF: "Parent",
    ROLE_STEP_PARENT_OF: "Step-parent",
    ROLE_CHILD_OF: "Child",
    ROLE_SON_OF: "Son",
    ROLE_DAUGHTER_OF: "Daughter",
    ROLE_SIBLING_OF: "Sibling",
    ROLE_SPOUSE_OF: "Spouse",
    ROLE_PARTNER_OF: "Partner",
    ROLE_GRANDPARENT_OF: "Grandparent",
    ROLE_GRANDCHILD_OF: "Grandchild",
    ROLE_UNCLE_OF: "Uncle",
    ROLE_AUNT_OF: "Aunt",
    ROLE_NEPHEW_OF: "Nephew",
    ROLE_NIECE_OF: "Niece",
    "cousin_of": "Cousin",
    "aunt_or_uncle_of": "Aunt / Uncle",
    "niece_or_nephew_of": "Niece / Nephew",
    "brother_in_law_of": "Brother-in-law",
    "sister_in_law_of": "Sister-in-law",
    "in_law_of": "In-law",
}


@dataclass
class PathHop:
    from_person_id: str
    to_person_id: str
    role_kind: str
    from_display_name: str | None = None
    to_display_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def phrase(self) -> str:
        a = self.from_display_name or self.from_person_id
        b = self.to_display_name or self.to_person_id
        rel = ROLE_DISPLAY.get(self.role_kind, self.role_kind.replace("_", " "))
        return f"{a} → {rel.lower()} of {b}" if self.role_kind.endswith("_of") else f"{a} — {rel} — {b}"


@dataclass
class KinshipHit:
    person_id: str
    display_name: str | None
    role_kind: str
    label: str
    derived: bool
    path: list[PathHop] = field(default_factory=list)
    path_summary: str = ""
    assertion_ids: list[str] = field(default_factory=list)
    group: str | None = None  # parents|siblings|spouse_partner|children|extended

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["path"] = [h.to_dict() if hasattr(h, "to_dict") else h for h in self.path]
        return d


def normalize_ux_role(role: str) -> str:
    r = (role or "").strip().lower().replace(" ", "_")
    if r in UX_ROLE_TO_SOT:
        return UX_ROLE_TO_SOT[r]
    if r.endswith("_of"):
        return r
    # "father_of" already
    mapped = UX_ROLE_TO_SOT.get(r.replace("_of", ""))
    return mapped or r


def display_label_for_role(role_kind: str, *, ux_hint: str | None = None) -> str:
    if ux_hint:
        hint = ux_hint.strip().lower()
        pretty = {
            "brother": "Brother",
            "sister": "Sister",
            "husband": "Husband",
            "wife": "Wife",
            "mom": "Mother",
            "dad": "Father",
        }.get(hint)
        if pretty:
            return pretty
    return ROLE_DISPLAY.get(role_kind, role_kind.replace("_", " ").title())


def _canonical_directed(role: str, a: str, b: str) -> tuple[str, str, str]:
    """Return (from, to, normalized_role) meaning from --role--> to (of)."""
    if role in PARENT_ROLES:
        return a, b, role  # a is parent of b
    if role in CHILD_ROLES:
        return b, a, ROLE_PARENT_OF  # flip to parent_of
    if role in SIBLING_ROLES:
        # undirected; store lexicographic for stability when building adj
        return a, b, ROLE_SIBLING_OF
    if role in SPOUSE_ROLES:
        return a, b, role
    if role == ROLE_GRANDPARENT_OF:
        return a, b, role
    if role == ROLE_GRANDCHILD_OF:
        return b, a, ROLE_GRANDPARENT_OF
    if role in {ROLE_UNCLE_OF, ROLE_AUNT_OF}:
        return a, b, role
    if role in {ROLE_NEPHEW_OF, ROLE_NIECE_OF}:
        return b, a, ROLE_UNCLE_OF
    return a, b, role


@dataclass
class _Edge:
    assertion_id: str
    a: str  # from
    b: str  # to
    role: str
    a_name: str | None
    b_name: str | None


def _load_edges(person_ids: Iterable[str] | None = None) -> list[_Edge]:
    """Load all confirmed assertions (optionally filtered neighborhood later)."""
    rows = list_relationship_assertions(None)
    out: list[_Edge] = []
    for r in rows:
        fro, to, role = _canonical_directed(
            r.role_kind, r.from_person_id, r.to_person_id
        )
        out.append(
            _Edge(
                assertion_id=r.id,
                a=fro,
                b=to,
                role=role,
                a_name=r.from_display_name if fro == r.from_person_id else r.to_display_name,
                b_name=r.to_display_name if to == r.to_person_id else r.from_display_name,
            )
        )
        # Fix names after possible flip
        if fro == r.from_person_id:
            out[-1].a_name = r.from_display_name
            out[-1].b_name = r.to_display_name
        else:
            out[-1].a_name = r.to_display_name
            out[-1].b_name = r.from_display_name
    return out


def _build_indexes(edges: list[_Edge]) -> dict[str, Any]:
    parents_of: dict[str, list[_Edge]] = defaultdict(list)  # child -> parent edges
    children_of: dict[str, list[_Edge]] = defaultdict(list)  # parent -> child edges
    siblings: dict[str, list[_Edge]] = defaultdict(list)
    spouses: dict[str, list[_Edge]] = defaultdict(list)
    for e in edges:
        if e.role in PARENT_ROLES or e.role == ROLE_PARENT_OF:
            parents_of[e.b].append(e)
            children_of[e.a].append(e)
        elif e.role in SIBLING_ROLES:
            siblings[e.a].append(e)
            siblings[e.b].append(
                _Edge(e.assertion_id, e.b, e.a, e.role, e.b_name, e.a_name)
            )
        elif e.role in SPOUSE_ROLES:
            spouses[e.a].append(e)
            spouses[e.b].append(
                _Edge(e.assertion_id, e.b, e.a, e.role, e.b_name, e.a_name)
            )
    return {
        "parents_of": parents_of,
        "children_of": children_of,
        "siblings": siblings,
        "spouses": spouses,
        "edges": edges,
    }


def _hop(e: _Edge, *, forward: bool = True) -> PathHop:
    if forward:
        return PathHop(e.a, e.b, e.role, e.a_name, e.b_name)
    return PathHop(e.b, e.a, e.role, e.b_name, e.a_name)


def _path_summary(hops: list[PathHop], names: dict[str, str | None], subject: str) -> str:
    """Explain hops from the subject's perspective (never 'Tom → parent of Tom')."""
    if not hops:
        return ""
    cur_id = subject
    bits = [names.get(subject) or subject]
    for h in hops:
        if h.from_person_id == cur_id:
            nxt_id = h.to_person_id
            nxt = h.to_display_name or names.get(nxt_id) or nxt_id
            role = h.role_kind
            leaving = True
        elif h.to_person_id == cur_id:
            nxt_id = h.from_person_id
            nxt = h.from_display_name or names.get(nxt_id) or nxt_id
            role = h.role_kind
            leaving = False
        else:
            nxt_id = h.to_person_id
            nxt = h.to_display_name or names.get(nxt_id) or nxt_id
            role = h.role_kind
            leaving = True
        if role in PARENT_ROLES or role == ROLE_PARENT_OF:
            bits.append(f"parent of {nxt}" if leaving else f"child of {nxt}")
        elif role in CHILD_ROLES:
            bits.append(f"child of {nxt}" if leaving else f"parent of {nxt}")
        elif role in SIBLING_ROLES:
            bits.append(f"sibling of {nxt}")
        elif role in SPOUSE_ROLES:
            bits.append(f"partner of {nxt}")
        else:
            lab = ROLE_DISPLAY.get(role, role).lower()
            bits.append(f"{lab} → {nxt}")
        cur_id = nxt_id
    return " → ".join(bits)


def _direct_view_for_subject(subject_id: str, edges: list[_Edge]) -> list[KinshipHit]:
    """Direct relationships as seen FROM subject (other person + label)."""
    hits: list[KinshipHit] = []
    seen: set[str] = set()
    for e in edges:
        other = None
        role_for_other = None
        group = None
        hops: list[PathHop] = []
        # e: a --role--> b
        if e.b == subject_id and e.role in PARENT_ROLES | {ROLE_PARENT_OF}:
            # a is parent of subject
            other = e.a
            role_for_other = e.role
            group = "parents"
            hops = [PathHop(e.a, e.b, e.role, e.a_name, e.b_name)]
        elif e.a == subject_id and e.role in PARENT_ROLES | {ROLE_PARENT_OF}:
            # subject is parent of b → b is child
            other = e.b
            role_for_other = ROLE_CHILD_OF
            if e.role == ROLE_FATHER_OF:
                role_for_other = ROLE_CHILD_OF
            group = "children"
            hops = [PathHop(e.a, e.b, e.role, e.a_name, e.b_name)]
        elif e.role in SIBLING_ROLES and subject_id in (e.a, e.b):
            other = e.b if e.a == subject_id else e.a
            role_for_other = ROLE_SIBLING_OF
            group = "siblings"
            hops = [
                PathHop(
                    subject_id,
                    other,
                    ROLE_SIBLING_OF,
                    e.a_name if e.a == subject_id else e.b_name,
                    e.b_name if e.a == subject_id else e.a_name,
                )
            ]
        elif e.role in SPOUSE_ROLES and subject_id in (e.a, e.b):
            other = e.b if e.a == subject_id else e.a
            role_for_other = e.role
            group = "spouse_partner"
            hops = [
                PathHop(
                    subject_id,
                    other,
                    e.role,
                    e.a_name if e.a == subject_id else e.b_name,
                    e.b_name if e.a == subject_id else e.a_name,
                )
            ]
        else:
            continue
        if not other or other in seen:
            continue
        seen.add(other)
        name = e.a_name if other == e.a else e.b_name
        hits.append(
            KinshipHit(
                person_id=other,
                display_name=name,
                role_kind=role_for_other or ROLE_SIBLING_OF,
                label=display_label_for_role(role_for_other or ROLE_SIBLING_OF),
                derived=False,
                path=hops,
                path_summary="",
                assertion_ids=[e.assertion_id],
                group=group,
            )
        )
    return hits


def derive_kinship_for_person(person_id: str) -> dict[str, Any]:
    """Return direct groups + extended derived kinship for subject person_id."""
    sid = str(parse_uuid(person_id, field="person_id"))
    edges = _load_edges()
    idx = _build_indexes(edges)
    direct = _direct_view_for_subject(sid, edges)
    direct_ids = {h.person_id for h in direct}

    # Also treat shared-parent as sibling (direct-like) if not already linked
    parent_edges = idx["parents_of"].get(sid, [])
    co_parents_children: dict[str, list[_Edge]] = defaultdict(list)
    for pe in parent_edges:
        for ce in idx["children_of"].get(pe.a, []):
            if ce.b != sid:
                co_parents_children[ce.b].append(ce)
    for other, ces in co_parents_children.items():
        if other in direct_ids:
            continue
        # path: subject ←parent— P —parent→ other  => sibling
        pe = parent_edges[0]
        ce = ces[0]
        hops = [
            PathHop(sid, pe.a, ROLE_CHILD_OF, None, pe.a_name),
            PathHop(pe.a, other, pe.role if pe.role in PARENT_ROLES else ROLE_PARENT_OF, pe.a_name, ce.b_name),
        ]
        hit = KinshipHit(
            person_id=other,
            display_name=ce.b_name,
            role_kind=ROLE_SIBLING_OF,
            label="Sibling",
            derived=False,  # treated as direct family group
            path=hops,
            path_summary="",
            assertion_ids=[pe.assertion_id, ce.assertion_id],
            group="siblings",
        )
        direct.append(hit)
        direct_ids.add(other)

    with connection() as conn:
        all_ids = {sid}
        for h in direct:
            all_ids.add(h.person_id)
        names = name_map(conn, [UUID(x) for x in all_ids])

    for h in direct:
        if not h.display_name:
            h.display_name = names.get(h.person_id)
        h.path_summary = _path_summary(h.path, names, sid) if h.path else ""

    # --- Extended derivation ---
    extended: list[KinshipHit] = []
    ext_seen: set[str] = set(direct_ids)
    ext_seen.add(sid)

    def add_ext(
        other: str,
        role: str,
        hops: list[PathHop],
        assertion_ids: list[str],
        *,
        name: str | None = None,
    ) -> None:
        if other in ext_seen:
            return
        ext_seen.add(other)
        label = display_label_for_role(role)
        extended.append(
            KinshipHit(
                person_id=other,
                display_name=name,
                role_kind=role,
                label=label,
                derived=True,
                path=hops,
                path_summary="",
                assertion_ids=assertion_ids,
                group="extended",
            )
        )

    # Grandparents: parents of parents
    for pe in parent_edges:
        for gpe in idx["parents_of"].get(pe.a, []):
            hops = [
                PathHop(sid, pe.a, ROLE_CHILD_OF, None, pe.a_name),
                PathHop(pe.a, gpe.a, ROLE_CHILD_OF, pe.a_name, gpe.a_name),
            ]
            # Flip wording: grandparent is gpe.a of subject
            hops2 = [
                PathHop(gpe.a, pe.a, gpe.role, gpe.a_name, pe.a_name),
                PathHop(pe.a, sid, pe.role, pe.a_name, None),
            ]
            add_ext(
                gpe.a,
                ROLE_GRANDPARENT_OF,
                hops2,
                [pe.assertion_id, gpe.assertion_id],
                name=gpe.a_name,
            )

    # Grandchildren: children of children
    for ce in idx["children_of"].get(sid, []):
        for gce in idx["children_of"].get(ce.b, []):
            hops = [
                PathHop(sid, ce.b, ce.role, None, ce.b_name),
                PathHop(ce.b, gce.b, gce.role, ce.b_name, gce.b_name),
            ]
            add_ext(
                gce.b,
                ROLE_GRANDCHILD_OF,
                hops,
                [ce.assertion_id, gce.assertion_id],
                name=gce.b_name,
            )

    # Aunts/uncles: siblings of parents (+ their spouses as in-laws)
    for pe in parent_edges:
        for se in idx["siblings"].get(pe.a, []):
            aunt_uncle = se.b if se.a == pe.a else se.a
            if aunt_uncle == sid:
                continue
            hops = [
                PathHop(pe.a, sid, pe.role, pe.a_name, None),
                PathHop(pe.a, aunt_uncle, ROLE_SIBLING_OF, pe.a_name, se.b_name if se.b == aunt_uncle else se.a_name),
            ]
            # Prefer aunt/uncle neutral via uncle_of as generic extended; use aunt_of label only if known — stay neutral Uncle/Aunt via uncle_of display "Aunt/Uncle"
            role = ROLE_UNCLE_OF  # neutral display overridden
            add_ext(
                aunt_uncle,
                "aunt_or_uncle_of",
                [
                    PathHop(sid, pe.a, ROLE_CHILD_OF, None, pe.a_name),
                    PathHop(pe.a, aunt_uncle, ROLE_SIBLING_OF, pe.a_name, None),
                ],
                [pe.assertion_id, se.assertion_id],
                name=se.b_name if se.b == aunt_uncle else se.a_name,
            )
            # Spouses of aunts/uncles → in-laws
            for sp in idx["spouses"].get(aunt_uncle, []):
                inlaw = sp.b if sp.a == aunt_uncle else sp.a
                add_ext(
                    inlaw,
                    "in_law_of",
                    [
                        PathHop(sid, pe.a, ROLE_CHILD_OF, None, pe.a_name),
                        PathHop(pe.a, aunt_uncle, ROLE_SIBLING_OF, pe.a_name, None),
                        PathHop(aunt_uncle, inlaw, sp.role, None, None),
                    ],
                    [pe.assertion_id, se.assertion_id, sp.assertion_id],
                    name=sp.b_name if sp.b == inlaw else sp.a_name,
                )

    # Spouse's children who are not already yours → derived children
    for sp in idx["spouses"].get(sid, []):
        spouse = sp.b if sp.a == sid else sp.a
        spouse_name = sp.b_name if sp.a == sid else sp.a_name
        for ce in idx["children_of"].get(spouse, []):
            if ce.b == sid:
                continue
            hops = [
                PathHop(sid, spouse, sp.role, None, spouse_name),
                PathHop(spouse, ce.b, ce.role, spouse_name, ce.b_name),
            ]
            add_ext(
                ce.b,
                ROLE_CHILD_OF,
                hops,
                [sp.assertion_id, ce.assertion_id],
                name=ce.b_name,
            )

    # Parent's spouse who is not already a parent → derived parent
    known_parents = {h.person_id for h in direct if h.group == "parents"}
    for pe in parent_edges:
        for sp in idx["spouses"].get(pe.a, []):
            other = sp.b if sp.a == pe.a else sp.a
            if other == sid or other in known_parents:
                continue
            other_name = sp.b_name if sp.b == other else sp.a_name
            hops = [
                PathHop(sid, pe.a, ROLE_CHILD_OF, None, pe.a_name),
                PathHop(pe.a, other, sp.role, pe.a_name, other_name),
            ]
            add_ext(
                other,
                ROLE_STEP_PARENT_OF,
                hops,
                [pe.assertion_id, sp.assertion_id],
                name=other_name,
            )

    # Nieces/nephews: children of siblings
    sib_assertion: dict[str, str] = {}
    for h in direct:
        if h.group == "siblings" and h.assertion_ids:
            sib_assertion[h.person_id] = h.assertion_ids[0]
    for sib, said in sib_assertion.items():
        for ce in idx["children_of"].get(sib, []):
            hops = [
                PathHop(sid, sib, ROLE_SIBLING_OF, None, None),
                PathHop(sib, ce.b, ce.role, None, ce.b_name),
            ]
            add_ext(
                ce.b,
                "niece_or_nephew_of",
                hops,
                [said, ce.assertion_id],
                name=ce.b_name,
            )

    # Cousins: children of parents' siblings
    for pe in parent_edges:
        for se in idx["siblings"].get(pe.a, []):
            aunt_uncle = se.b if se.a == pe.a else se.a
            for ce in idx["children_of"].get(aunt_uncle, []):
                if ce.b == sid or ce.b in direct_ids:
                    continue
                hops = [
                    PathHop(sid, pe.a, ROLE_CHILD_OF, None, pe.a_name),
                    PathHop(pe.a, aunt_uncle, ROLE_SIBLING_OF, pe.a_name, None),
                    PathHop(aunt_uncle, ce.b, ce.role, None, ce.b_name),
                ]
                add_ext(
                    ce.b,
                    "cousin_of",
                    hops,
                    [pe.assertion_id, se.assertion_id, ce.assertion_id],
                    name=ce.b_name,
                )

    # Fill names + path summaries
    with connection() as conn:
        ids = {sid}
        for h in extended:
            ids.add(h.person_id)
        names = name_map(conn, [UUID(x) for x in ids])
    for h in extended:
        if not h.display_name:
            h.display_name = names.get(h.person_id)
        h.path_summary = _path_summary(h.path, names, sid)

    groups: dict[str, list[dict[str, Any]]] = {g: [] for g in DIRECT_GROUP_ORDER}
    for h in direct:
        g = h.group or "siblings"
        if g not in groups:
            groups[g] = []
        groups[g].append(h.to_dict())

    return {
        "person_id": sid,
        "direct": groups,
        "direct_flat": [h.to_dict() for h in direct],
        "extended": [h.to_dict() for h in extended],
        "counts": {
            "direct": len(direct),
            "extended": len(extended),
            **{g: len(groups.get(g) or []) for g in DIRECT_GROUP_ORDER},
        },
    }


def how_related(person_a_id: str, person_b_id: str) -> dict[str, Any]:
    """Shortest supported kinship path between two people (from A's perspective)."""
    a = str(parse_uuid(person_a_id, field="person_a_id"))
    b = str(parse_uuid(person_b_id, field="person_b_id"))
    if a == b:
        return {
            "ok": True,
            "related": True,
            "role_kind": "self",
            "label": "Self",
            "derived": False,
            "path_summary": "",
            "path": [],
            "ambiguous": False,
        }
    bundle = derive_kinship_for_person(a)
    hits = [
        h
        for h in (bundle.get("direct_flat") or []) + (bundle.get("extended") or [])
        if h.get("person_id") == b
    ]
    if not hits:
        # try reverse
        bundle_b = derive_kinship_for_person(b)
        hits_rev = [
            h
            for h in (bundle_b.get("direct_flat") or []) + (bundle_b.get("extended") or [])
            if h.get("person_id") == a
        ]
        if hits_rev:
            h = hits_rev[0]
            return {
                "ok": True,
                "related": True,
                "role_kind": h.get("role_kind"),
                "label": h.get("label"),
                "derived": bool(h.get("derived")),
                "path_summary": h.get("path_summary") or "",
                "path": h.get("path") or [],
                "ambiguous": len(hits_rev) > 1,
                "perspective_person_id": b,
                "note": "Path expressed from the other person's perspective.",
            }
        return {
            "ok": True,
            "related": False,
            "disclosure": "No supported kinship path on current direct relationships.",
        }
    # Prefer shortest path
    hits.sort(key=lambda h: len(h.get("path") or []))
    best = hits[0]
    ambiguous = len(hits) > 1 and any(
        (h.get("role_kind") != best.get("role_kind")) for h in hits[1:]
    )
    return {
        "ok": True,
        "related": True,
        "role_kind": best.get("role_kind"),
        "label": best.get("label"),
        "derived": bool(best.get("derived")),
        "path_summary": best.get("path_summary") or "",
        "path": best.get("path") or [],
        "ambiguous": ambiguous,
        "perspective_person_id": a,
        "alternates": hits[1:3] if ambiguous else [],
    }


def relatives_of_kind(person_id: str, kind: str) -> list[dict[str, Any]]:
    """Filter derived+direct for Ask (cousins, grandchildren, nieces, …)."""
    k = (kind or "").strip().lower()
    bundle = derive_kinship_for_person(person_id)
    out: list[dict[str, Any]] = []
    if k in ("cousin", "cousins"):
        out = [h for h in bundle["extended"] if h.get("role_kind") == "cousin_of"]
    elif k in ("grandchild", "grandchildren"):
        out = [
            h
            for h in bundle["extended"]
            if h.get("role_kind") == ROLE_GRANDCHILD_OF
        ]
    elif k in ("niece", "nephew", "nieces", "nephews", "nieces_nephews"):
        out = [
            h
            for h in bundle["extended"]
            if h.get("role_kind") in {ROLE_NEPHEW_OF, ROLE_NIECE_OF, "niece_or_nephew_of"}
        ]
    elif k in ("grandparent", "grandparents"):
        out = [
            h
            for h in bundle["extended"]
            if h.get("role_kind") == ROLE_GRANDPARENT_OF
        ]
    elif k in ("aunt", "uncle", "aunts", "uncles"):
        out = [
            h
            for h in bundle["extended"]
            if h.get("role_kind") in {ROLE_AUNT_OF, ROLE_UNCLE_OF, "aunt_or_uncle_of"}
        ]
    elif k in ("sibling", "siblings", "brother", "sister"):
        out = bundle["direct"].get("siblings") or []
    elif k in ("child", "children", "son", "daughter"):
        out = bundle["direct"].get("children") or []
    elif k in ("parent", "parents", "mother", "father", "mom", "dad"):
        out = bundle["direct"].get("parents") or []
    return out


def relationship_history(person_id: str) -> list[dict[str, Any]]:
    """Lightweight history of assertions touching this person (incl. withdrawn)."""
    rows = list_relationship_assertions(person_id, include_non_current=True)
    out = []
    for r in rows:
        out.append(
            {
                "assertion_id": r.id,
                "from_person_id": r.from_person_id,
                "to_person_id": r.to_person_id,
                "from_display_name": r.from_display_name,
                "to_display_name": r.to_display_name,
                "role_kind": r.role_kind,
                "label": display_label_for_role(r.role_kind),
                "status": r.status,
                "actor_key": r.actor_key,
                "note": r.note,
                "created_at": r.created_at,
                "superseded_by_id": r.superseded_by_id,
                "provenance": r.provenance,
            }
        )
    return out
