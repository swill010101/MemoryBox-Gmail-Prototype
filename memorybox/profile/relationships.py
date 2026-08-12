"""Person↔Person relationship assertions — one SoT edge; inverses derived."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from memorybox.db import connection
from memorybox.profile.owner import (
    ALLOWED_ROLES,
    ASK_ROLE_ALIASES,
    INVERSE_ROLE,
    AmbiguousRelationshipError,
    ProfileServiceError,
    ensure_person,
    iso,
    name_map,
    parse_uuid,
    prov,
)


@dataclass
class RelationshipAssertion:
    id: str
    from_person_id: str
    to_person_id: str
    role_kind: str
    status: str
    actor_key: str
    note: str | None
    provenance: dict[str, Any]
    created_at: str | None
    superseded_by_id: str | None = None
    from_display_name: str | None = None
    to_display_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DerivedEdge:
    assertion_id: str
    from_person_id: str
    to_person_id: str
    role_kind: str
    is_inverse_projection: bool
    sot_role_kind: str
    from_display_name: str | None = None
    to_display_name: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    inferred: bool = False
    inference_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rel_view(row: dict[str, Any], names: dict[str, str | None]) -> RelationshipAssertion:
    fro = str(row["from_person_id"])
    to = str(row["to_person_id"])
    return RelationshipAssertion(
        id=str(row["id"]),
        from_person_id=fro,
        to_person_id=to,
        role_kind=row["role_kind"],
        status=row["status"],
        actor_key=row.get("actor_key") or "owner",
        note=row.get("note"),
        provenance=prov(row.get("provenance_json")),
        created_at=iso(row.get("created_at")),
        superseded_by_id=str(row["superseded_by_id"]) if row.get("superseded_by_id") else None,
        from_display_name=names.get(fro),
        to_display_name=names.get(to),
    )


def assert_relationship(
    *,
    from_person_id: str,
    to_person_id: str,
    role_kind: str,
    actor_key: str = "owner",
    note: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> RelationshipAssertion:
    fro = ensure_person(from_person_id)
    to = ensure_person(to_person_id)
    if fro == to:
        raise ProfileServiceError("from_person_id and to_person_id must differ")
    role = (role_kind or "").strip().lower()
    if role not in ALLOWED_ROLES:
        raise ProfileServiceError(
            f"role_kind {role!r} not in thin P1 set: {sorted(ALLOWED_ROLES)}"
        )
    rid = uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO person_relationship_assertions (
                id, from_person_id, to_person_id, role_kind, status,
                actor_key, note, provenance_json
            ) VALUES (%s, %s, %s, %s, 'confirmed', %s, %s, %s::jsonb)
            """,
            (rid, fro, to, role, actor_key, note, json.dumps(provenance or {"source": "owner"})),
        )
        conn.execute(
            """
            INSERT INTO assertions (
                id, assertion_kind, subject_type, subject_id, predicate,
                object_type, object_id, statement, authority, status, provenance_json
            ) VALUES (
                %s, 'person_relationship', 'person', %s, %s,
                'person', %s, %s, 'owner', 'confirmed', %s::jsonb
            )
            """,
            (
                uuid4(),
                fro,
                role,
                to,
                f"{fro} {role} {to}",
                json.dumps({"relationship_assertion_id": str(rid)}),
            ),
        )
        row = conn.execute(
            "SELECT * FROM person_relationship_assertions WHERE id = %s", (rid,)
        ).fetchone()
        names = name_map(conn, [fro, to])
    return _rel_view(row, names)


def withdraw_relationship(
    assertion_id: str,
    *,
    actor_key: str = "owner",
    note: str | None = None,
) -> RelationshipAssertion:
    aid = parse_uuid(assertion_id, field="assertion_id")
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM person_relationship_assertions WHERE id = %s", (aid,)
        ).fetchone()
        if not row:
            raise ProfileServiceError(f"relationship assertion not found: {aid}")
        if row["status"] != "confirmed":
            raise ProfileServiceError("only confirmed relationships can be withdrawn")
        p = prov(row.get("provenance_json"))
        p["withdrawn_by"] = actor_key
        if note:
            p["withdraw_note"] = note
        conn.execute(
            """
            UPDATE person_relationship_assertions
            SET status = 'withdrawn', updated_at = now(),
                note = COALESCE(%s, note),
                provenance_json = %s::jsonb
            WHERE id = %s
            """,
            (note, json.dumps(p), aid),
        )
        row = conn.execute(
            "SELECT * FROM person_relationship_assertions WHERE id = %s", (aid,)
        ).fetchone()
        names = name_map(conn, [row["from_person_id"], row["to_person_id"]])
    return _rel_view(row, names)


def supersede_relationship(
    assertion_id: str,
    *,
    from_person_id: str,
    to_person_id: str,
    role_kind: str,
    actor_key: str = "owner",
    note: str | None = None,
) -> RelationshipAssertion:
    old_id = parse_uuid(assertion_id, field="assertion_id")
    fro = ensure_person(from_person_id)
    to = ensure_person(to_person_id)
    role = (role_kind or "").strip().lower()
    if role not in ALLOWED_ROLES:
        raise ProfileServiceError(f"role_kind {role!r} not allowed")
    new_id = uuid4()
    with connection() as conn:
        old = conn.execute(
            "SELECT * FROM person_relationship_assertions WHERE id = %s", (old_id,)
        ).fetchone()
        if not old:
            raise ProfileServiceError(f"relationship assertion not found: {old_id}")
        if old["status"] != "confirmed":
            raise ProfileServiceError("only confirmed relationships can be superseded")
        conn.execute(
            """
            INSERT INTO person_relationship_assertions (
                id, from_person_id, to_person_id, role_kind, status,
                actor_key, note, provenance_json
            ) VALUES (%s, %s, %s, %s, 'confirmed', %s, %s, %s::jsonb)
            """,
            (
                new_id,
                fro,
                to,
                role,
                actor_key,
                note,
                json.dumps(
                    {
                        "source": "owner_correction",
                        "supersedes": str(old_id),
                        "prior_role": old["role_kind"],
                    }
                ),
            ),
        )
        conn.execute(
            """
            UPDATE person_relationship_assertions
            SET status = 'superseded', superseded_by_id = %s, updated_at = now()
            WHERE id = %s
            """,
            (new_id, old_id),
        )
        row = conn.execute(
            "SELECT * FROM person_relationship_assertions WHERE id = %s", (new_id,)
        ).fetchone()
        names = name_map(conn, [fro, to])
    return _rel_view(row, names)


def list_relationship_assertions(
    person_id: str | None = None,
    *,
    include_non_current: bool = False,
) -> list[RelationshipAssertion]:
    with connection() as conn:
        if person_id:
            pid = ensure_person(person_id)
            if include_non_current:
                rows = conn.execute(
                    """
                    SELECT * FROM person_relationship_assertions
                    WHERE from_person_id = %s OR to_person_id = %s
                    ORDER BY created_at ASC
                    """,
                    (pid, pid),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM person_relationship_assertions
                    WHERE status = 'confirmed'
                      AND (from_person_id = %s OR to_person_id = %s)
                    ORDER BY created_at ASC
                    """,
                    (pid, pid),
                ).fetchall()
        else:
            q = "SELECT * FROM person_relationship_assertions"
            if not include_non_current:
                q += " WHERE status = 'confirmed'"
            q += " ORDER BY created_at ASC"
            rows = conn.execute(q).fetchall()
        ids: list[UUID] = []
        for r in rows:
            ids.extend([r["from_person_id"], r["to_person_id"]])
        names = name_map(conn, list({UUID(str(i)) for i in ids}))
    return [_rel_view(r, names) for r in rows]


def project_derived_edges(person_id: str) -> list[DerivedEdge]:
    assertions = list_relationship_assertions(person_id)
    out: list[DerivedEdge] = []
    for a in assertions:
        out.append(
            DerivedEdge(
                assertion_id=a.id,
                from_person_id=a.from_person_id,
                to_person_id=a.to_person_id,
                role_kind=a.role_kind,
                is_inverse_projection=False,
                sot_role_kind=a.role_kind,
                from_display_name=a.from_display_name,
                to_display_name=a.to_display_name,
                provenance=a.provenance,
            )
        )
        inv = INVERSE_ROLE.get(a.role_kind)
        if inv:
            out.append(
                DerivedEdge(
                    assertion_id=a.id,
                    from_person_id=a.to_person_id,
                    to_person_id=a.from_person_id,
                    role_kind=inv,
                    is_inverse_projection=True,
                    sot_role_kind=a.role_kind,
                    from_display_name=a.to_display_name,
                    to_display_name=a.from_display_name,
                    provenance=a.provenance,
                )
            )
    return out


def resolve_relatives_for_person(
    person_id: str,
    *,
    asked_roles: frozenset[str] | set[str],
) -> list[DerivedEdge]:
    pid = str(ensure_person(person_id))
    roles = frozenset(asked_roles)
    matches: list[DerivedEdge] = []
    for edge in project_derived_edges(pid):
        if edge.to_person_id == pid and edge.role_kind in roles:
            matches.append(edge)
    seen: set[str] = set()
    uniq: list[DerivedEdge] = []
    for m in matches:
        key = f"{m.assertion_id}:{m.from_person_id}"
        if key in seen:
            continue
        seen.add(key)
        uniq.append(m)
    return uniq


def resolve_one_relative(person_id: str, *, role_phrase: str) -> DerivedEdge:
    """Resolve a relative for person_id.

    Direct SoT/derived edges win. Thin P1 inference (explicit owner ask):
    - mother/mom ← spouse/partner (or marriage co-participant) of father_of only
    - father/dad ← spouse/partner (or marriage co-participant) of mother_of only
    Never use generic parent_of as the inference anchor — that made Anne the
    “father” when Eugene was only recorded as parent_of + marriage partner.
    Does not build a full genealogy; discloses ambiguity.
    """
    from memorybox.person import get_person
    from memorybox.profile.life_events import list_life_events_for_person
    from memorybox.profile.owner import (
        GENERIC_PARENT_ROLES,
        ROLE_FATHER_OF,
        ROLE_MOTHER_OF,
        ROLE_PARTNER_OF,
        ROLE_SPOUSE_OF,
    )

    phrase = (role_phrase or "").strip().lower()
    roles = ASK_ROLE_ALIASES.get(phrase)
    if not roles:
        raise ProfileServiceError(f"unsupported relationship phrase: {role_phrase!r}")

    matches = resolve_relatives_for_person(person_id, asked_roles=roles)
    if matches:
        people = {m.from_person_id for m in matches}
        if len(people) > 1:
            raise AmbiguousRelationshipError(
                f"Multiple current {phrase} relationships; clarify which person.",
                candidates=[m.to_dict() for m in matches],
            )
        return matches[0]

    # Thin spouse-of-parent inference (gendered anchor only)
    spouse_roles = frozenset({ROLE_SPOUSE_OF, ROLE_PARTNER_OF})

    if phrase in ("mother", "mom"):
        anchors = resolve_relatives_for_person(
            person_id, asked_roles=frozenset({ROLE_FATHER_OF})
        )
        anchor_label = "father"
        inferred_role = ROLE_MOTHER_OF
    elif phrase in ("father", "dad"):
        anchors = resolve_relatives_for_person(
            person_id, asked_roles=frozenset({ROLE_MOTHER_OF})
        )
        anchor_label = "mother"
        inferred_role = ROLE_FATHER_OF
    else:
        anchors = []
        anchor_label = ""
        inferred_role = ""

    if not anchors:
        generics = resolve_relatives_for_person(
            person_id, asked_roles=GENERIC_PARENT_ROLES
        )
        if generics and phrase in ("father", "dad", "mother", "mom"):
            names = ", ".join(
                sorted(
                    {
                        (g.from_display_name or g.from_person_id)
                        for g in generics
                    }
                )
            )
            raise ProfileServiceError(
                f"No current {phrase} relationship recorded. "
                f"Parent(s) on file: {names}. "
                f"Save “father of” / “mother of” (not only “parent of”) — "
                f"then the other parent can be inferred from spouse/marriage."
            )
        raise ProfileServiceError(
            f"No current {phrase} relationship recorded, and none can be inferred "
            f"(need a father_of or mother_of plus their spouse or marriage partner)."
        )

    # Multiple distinct anchors → do not guess which parent's spouse is mother/father
    anchor_people = {a.from_person_id for a in anchors}
    if len(anchor_people) > 1:
        raise AmbiguousRelationshipError(
            f"Multiple {anchor_label}s recorded; clarify before inferring {phrase} "
            f"from a spouse.",
            candidates=[a.to_dict() for a in anchors],
        )

    inferred: list[DerivedEdge] = []
    for anchor in anchors:
        # 1) Explicit spouse/partner edges
        spouses = resolve_relatives_for_person(
            anchor.from_person_id, asked_roles=spouse_roles
        )
        for sp in spouses:
            if sp.from_person_id in {person_id, anchor.from_person_id}:
                continue
            note = (
                f"Inferred {phrase} as spouse/partner of your {anchor_label} "
                f"{anchor.from_display_name or anchor.from_person_id}"
            )
            inferred.append(
                DerivedEdge(
                    assertion_id=sp.assertion_id,
                    from_person_id=sp.from_person_id,
                    to_person_id=person_id,
                    role_kind=inferred_role,
                    is_inverse_projection=True,
                    sot_role_kind=sp.sot_role_kind,
                    from_display_name=sp.from_display_name,
                    to_display_name=None,
                    provenance={
                        **(sp.provenance or {}),
                        "inferred_from": "spouse_of_parent",
                        "anchor_person_id": anchor.from_person_id,
                        "anchor_role": anchor_label,
                    },
                    inferred=True,
                    inference_note=note,
                )
            )

        # 2) Marriage / anniversary life-event co-participants (no spouse_of row required)
        for ev in list_life_events_for_person(anchor.from_person_id):
            if ev.event_kind != "marriage" or ev.status != "confirmed":
                continue
            for part in ev.participants or []:
                pid = str(part.get("person_id") or "")
                if not pid or pid in {person_id, anchor.from_person_id}:
                    continue
                view = get_person(pid)
                name = (view.display_name if view else None) or part.get("display_name")
                note = (
                    f"Inferred {phrase} as marriage partner of your {anchor_label} "
                    f"{anchor.from_display_name or anchor.from_person_id}"
                )
                inferred.append(
                    DerivedEdge(
                        assertion_id=ev.id,
                        from_person_id=pid,
                        to_person_id=person_id,
                        role_kind=inferred_role,
                        is_inverse_projection=True,
                        sot_role_kind="marriage",
                        from_display_name=name,
                        to_display_name=None,
                        provenance={
                            "inferred_from": "marriage_life_event",
                            "life_event_id": ev.id,
                            "anchor_person_id": anchor.from_person_id,
                            "anchor_role": anchor_label,
                        },
                        inferred=True,
                        inference_note=note,
                    )
                )

    by_person: dict[str, DerivedEdge] = {}
    for edge in inferred:
        by_person[edge.from_person_id] = edge
    uniq = list(by_person.values())
    if len(uniq) == 1:
        return uniq[0]
    if len(uniq) > 1:
        raise AmbiguousRelationshipError(
            f"Multiple possible {phrase}s via spouse/marriage of your {anchor_label}; "
            "clarify or record an explicit mother_of/father_of.",
            candidates=[e.to_dict() for e in uniq],
        )
    raise ProfileServiceError(
        f"Your {anchor_label} "
        f"({anchors[0].from_display_name or anchors[0].from_person_id}) is recorded, "
        f"but no spouse/partner or marriage partner is linked to them — "
        f"add “spouse of” or a marriage date with both people, "
        f"or an explicit {phrase}_of relationship."
    )
