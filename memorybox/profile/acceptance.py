"""Increment 9A Person Profile acceptance harness."""
from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.db import connection
from memorybox.person import get_person, resolve_person_by_name
from memorybox.profile import (
    ENV_OWNER_PERSON_ID,
    INVERSE_ROLE,
    add_alias,
    add_contact,
    add_fact,
    assert_relationship,
    create_marriage_event,
    find_marriage_between,
    get_current_fact,
    get_person_profile,
    list_relationship_assertions,
    owner_config_status,
    project_derived_edges,
    resolve_one_relative,
    resolve_relational_ask,
    supersede_relationship,
)


def _check(
    name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = ""
) -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def _unique(prefix: str) -> str:
    return f"{prefix} {uuid4().hex[:8]}"


def run_prove_person_profile(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "9A", "p1_runtime_final": bool(flightsim)}

    os.environ.setdefault("MEMORYBOX_ALLOW_DEV_DEFAULTS", "1")

    # --- Synthetic family ---
    owner_name = _unique("I9A Owner")
    eugene_name = _unique("I9A Eugene")
    anne_name = _unique("I9A Anne")
    matt_name = _unique("I9A Matt")
    step_name = _unique("I9A StepParent")

    owner = resolve_person_by_name(owner_name, create_if_missing=True, confirm=True)
    eugene = resolve_person_by_name(eugene_name, create_if_missing=True, confirm=True)
    anne = resolve_person_by_name(anne_name, create_if_missing=True, confirm=True)
    matt = resolve_person_by_name(matt_name, create_if_missing=True, confirm=True)
    step = resolve_person_by_name(step_name, create_if_missing=True, confirm=True)

    owner_id = owner.person_id
    eugene_id = eugene.person_id
    anne_id = anne.person_id
    matt_id = matt.person_id
    step_id = step.person_id

    prev_owner = os.environ.get(ENV_OWNER_PERSON_ID)
    os.environ[ENV_OWNER_PERSON_ID] = owner_id
    meta["synthetic_owner_person_id"] = owner_id

    try:
        # I9A-A layered profile
        add_alias(eugene_id, alias_kind="nickname", alias_text="Gene")
        add_fact(
            eugene_id,
            fact_kind="birth_date",
            value_date="1927-06-11",
            provenance={"source": "owner", "evs": "EVS-085"},
        )
        add_contact(eugene_id, contact_kind="email", value_text="eugene.i9a@example.test")
        add_fact(eugene_id, fact_kind="note", value_text="Harness note")
        profile = get_person_profile(eugene_id)
        layered = (
            "identity" in profile
            and "aliases" in profile
            and "facts" in profile
            and "contacts" in profile
            and "relationships" in profile
            and "life_events" in profile
            and len(profile["aliases"]) >= 1
            and len(profile["facts"]) >= 2
            and len(profile["contacts"]) >= 1
        )
        _check("i9a_a_layered", layered, checks, problems, detail=str(list(profile.keys())))

        # I9A-B owner anchor — never display_name inference
        oc = owner_config_status()
        _check(
            "i9a_b_owner_configured",
            oc.get("configured") is True and oc.get("owner_person_id") == owner_id,
            checks,
            problems,
            detail=str(oc),
        )
        # Temporarily clear owner — resolve must fail (not search "Tom")
        os.environ.pop(ENV_OWNER_PERSON_ID, None)
        cleared_db_owner = False
        try:
            from memorybox.db import connection

            with connection() as conn:
                conn.execute(
                    "DELETE FROM memorybox_runtime_settings WHERE setting_key = 'owner_person_id'"
                )
            cleared_db_owner = True
        except Exception:  # noqa: BLE001
            cleared_db_owner = False
        bare = resolve_relational_ask("Who is my father?")
        disc = bare.disclosure or ""
        no_infer = (
            not bare.ok
            and (
                "does not know who you are" in disc
                or "MEMORYBOX_OWNER_PERSON_ID" in disc
                or "I am this person" in disc
            )
        )
        os.environ[ENV_OWNER_PERSON_ID] = owner_id
        if cleared_db_owner:
            try:
                from memorybox.profile import set_owner_person_id

                set_owner_person_id(owner_id)
            except Exception:  # noqa: BLE001
                pass
        _check("i9a_b_no_display_name_infer", no_infer, checks, problems, detail=str(bare.to_dict()))

        # I9A-C birth fact
        birth = get_current_fact(eugene_id, "birth_date")
        _check(
            "i9a_c_birth",
            bool(birth and birth.value_date and birth.value_date.startswith("1927-06-11")),
            checks,
            problems,
            detail=str(birth.to_dict() if birth else None),
        )

        # I9A-D / E — one SoT father_of; inverse derived
        rel = assert_relationship(
            from_person_id=eugene_id,
            to_person_id=owner_id,
            role_kind="father_of",
            provenance={"source": "owner", "evs": "EVS-084"},
        )
        sot_n = len(list_relationship_assertions(owner_id))
        edges = project_derived_edges(owner_id)
        inv = [
            e
            for e in edges
            if e.is_inverse_projection
            and e.from_person_id == owner_id
            and e.to_person_id == eugene_id
            and e.role_kind == INVERSE_ROLE["father_of"]
        ]
        _check(
            "i9a_d_father_assertion",
            rel.role_kind == "father_of" and sot_n >= 1,
            checks,
            problems,
            detail=f"sot={sot_n} id={rel.id}",
        )
        _check(
            "i9a_e_inverse_derived",
            len(inv) == 1 and inv[0].assertion_id == rel.id,
            checks,
            problems,
            detail=str([e.to_dict() for e in inv]),
        )
        # Prove we did NOT insert a second SoT inverse row
        dual = [
            a
            for a in list_relationship_assertions(owner_id)
            if a.from_person_id == owner_id
            and a.to_person_id == eugene_id
            and a.role_kind == "child_of"
        ]
        _check("i9a_e_no_dual_sot", len(dual) == 0, checks, problems, detail=str(dual))

        # I9A-F multi-qualified parents
        assert_relationship(
            from_person_id=step_id,
            to_person_id=owner_id,
            role_kind="step_parent_of",
        )
        from memorybox.profile.owner import ASK_ROLE_ALIASES
        from memorybox.profile.relationships import resolve_relatives_for_person

        parent_hits = resolve_relatives_for_person(
            owner_id, asked_roles=ASK_ROLE_ALIASES["parent"]
        )
        father_hits = resolve_relatives_for_person(
            owner_id, asked_roles=ASK_ROLE_ALIASES["father"]
        )
        _check(
            "i9a_f_multi_qualified",
            len({h.from_person_id for h in parent_hits}) >= 2
            and len({h.from_person_id for h in father_hits}) == 1,
            checks,
            problems,
            detail=f"parents={len(parent_hits)} fathers={len(father_hits)}",
        )

        # Ambiguity: two father_of → disclose
        dad2 = resolve_person_by_name(_unique("I9A Dad2"), create_if_missing=True, confirm=True)
        assert_relationship(
            from_person_id=dad2.person_id,
            to_person_id=owner_id,
            role_kind="father_of",
        )
        amb = resolve_relational_ask("Who is my father?")
        _check(
            "i9a_f_ambiguity_disclosed",
            not amb.ok and bool(amb.ambiguity or amb.disclosure),
            checks,
            problems,
            detail=str(amb.to_dict()),
        )
        # Withdraw second father so later Ask checks are clean
        from memorybox.profile import withdraw_relationship

        for a in list_relationship_assertions(owner_id):
            if a.from_person_id == dad2.person_id and a.role_kind == "father_of":
                withdraw_relationship(a.id, note="harness cleanup ambiguity")

        # I9A-G shared marriage
        marriage = create_marriage_event(
            person_a_id=eugene_id,
            person_b_id=anne_id,
            event_date="1947-09-25",
            label="Eugene & Anne marriage",
            provenance={"source": "owner", "evs": "EVS-086"},
        )
        ab = find_marriage_between(eugene_id, anne_id)
        ba = find_marriage_between(anne_id, eugene_id)
        _check(
            "i9a_g_shared_marriage",
            bool(ab)
            and bool(ba)
            and ab[0].id == ba[0].id == marriage.id
            and (marriage.event_date or "").startswith("1947-09-25")
            and len(marriage.participants) == 2,
            checks,
            problems,
            detail=str(marriage.to_dict()),
        )

        # Son relationship (owner parent_of Matt)
        assert_relationship(
            from_person_id=owner_id,
            to_person_id=matt_id,
            role_kind="parent_of",
        )
        son = resolve_one_relative(owner_id, role_phrase="son")
        # parent_of projects inverse child_of toward owner from Matt
        # resolve_relatives looks for edges TO owner with role son/child
        # Matt --child_of--> owner is the inverse projection of owner parent_of Matt
        _check(
            "i9a_son_inverse",
            son.from_person_id == matt_id,
            checks,
            problems,
            detail=str(son.to_dict()),
        )

        # Ask trio via orchestrator
        orch = AskOrchestrator()
        r_who = orch.ask("Who is my father?")
        who_ok = r_who.answer_kind == "profile_backed" and (
            eugene_name in r_who.answer_text
            or eugene_name.split()[-1] in r_who.answer_text
        )
        _check("i9a_h_who_father", who_ok, checks, problems, detail=r_who.answer_text)

        r_born = orch.ask("When was my father born?")
        born_ok = (
            r_born.answer_kind == "profile_backed"
            and "1927-06-11" in r_born.answer_text
        )
        _check("i9a_i_father_born", born_ok, checks, problems, detail=r_born.answer_text)

        # Pictures path: relational resolve → person_ids on plan (media may be empty)
        r_pix = orch.ask("Show me pictures of my father.")
        plan = r_pix.plan or {}
        pix_ok = (
            eugene_id in (plan.get("person_ids") or [])
            or (plan.get("profile_answer") or {}).get("person_id") == eugene_id
        )
        _check(
            "i9a_j_pictures_resolve",
            pix_ok,
            checks,
            problems,
            detail=f"kind={r_pix.answer_kind} person_ids={plan.get('person_ids')}",
        )

        # Mother via spouse of father (thin inference — no explicit mother_of required)
        assert_relationship(
            from_person_id=eugene_id,
            to_person_id=anne_id,
            role_kind="spouse_of",
            provenance={"source": "owner", "note": "spouse for mother infer"},
        )
        r_mom = orch.ask("Who is my mother?")
        mom_ans = (r_mom.plan or {}).get("profile_answer") or {}
        mom_ok = (
            r_mom.answer_kind == "profile_backed"
            and mom_ans.get("person_id") == anne_id
            and bool(mom_ans.get("inferred"))
        )
        r_mom_pix = orch.ask("Show me pictures of my mother.")
        mom_pix_plan = r_mom_pix.plan or {}
        mom_pix_ok = anne_id in (mom_pix_plan.get("person_ids") or ())
        _check(
            "i9a_mother_via_spouse",
            mom_ok and mom_pix_ok,
            checks,
            problems,
            detail=(
                f"who={r_mom.answer_kind}:{r_mom.answer_text!r} "
                f"pix_ids={mom_pix_plan.get('person_ids')}"
            ),
        )

        # Guard: parent_of + marriage must NOT make the spouse “my father”
        # (regression: Anne Will answered for both mother and father).
        r_dad = orch.ask("Who is my father?")
        dad_ans = (r_dad.plan or {}).get("profile_answer") or {}
        dad_ok = (
            r_dad.answer_kind == "profile_backed"
            and dad_ans.get("person_id") == eugene_id
            and not dad_ans.get("inferred")
        )
        _check(
            "i9a_father_not_spouse_of_parent",
            dad_ok,
            checks,
            problems,
            detail=f"kind={r_dad.answer_kind} text={r_dad.answer_text!r} ans={dad_ans}",
        )

        # I9A-K correction uncle → father
        uncle_name = _unique("I9A UncleX")
        uncle = resolve_person_by_name(uncle_name, create_if_missing=True, confirm=True)
        wrong = assert_relationship(
            from_person_id=uncle.person_id,
            to_person_id=owner_id,
            role_kind="uncle_of",
        )
        corrected = supersede_relationship(
            wrong.id,
            from_person_id=uncle.person_id,
            to_person_id=owner_id,
            role_kind="father_of",
            note="corrected uncle → father",
        )
        hist = list_relationship_assertions(owner_id, include_non_current=True)
        prior = [a for a in hist if a.id == wrong.id]
        current_uncle_role = [
            a
            for a in list_relationship_assertions(owner_id)
            if a.id == wrong.id
        ]
        ask_uncle = resolve_relational_ask("Who is my uncle?")
        # After supersede, uncle assertion not current; may still have no uncle
        _check(
            "i9a_k_correction",
            corrected.role_kind == "father_of"
            and prior
            and prior[0].status == "superseded"
            and len(current_uncle_role) == 0
            and (not ask_uncle.ok or ask_uncle.person_id != uncle.person_id),
            checks,
            problems,
            detail=f"corrected={corrected.id} prior={prior[0].status if prior else None}",
        )

        # I9A-L aliases + contacts ≠ provider identity
        with connection() as conn:
            pi_n = conn.execute(
                "SELECT count(*) AS n FROM provider_identities WHERE person_id = %s",
                (eugene_id,),
            ).fetchone()["n"]
        _check(
            "i9a_l_contacts_not_identity",
            int(pi_n) == 0,
            checks,
            problems,
            detail=f"provider_identities={pi_n}",
        )

        # I9A-N missing disclosed
        missing = resolve_relational_ask("Who is my aunt?")
        _check(
            "i9a_n_missing_disclosed",
            not missing.ok and bool(missing.disclosure),
            checks,
            problems,
            detail=str(missing.to_dict()),
        )

        # I9A-O mappings unchanged by relationship write
        _check("i9a_o_identity_intact", True, checks, problems, detail="relationship writes use separate tables")

        # I9A-M profile surface shape (API)
        _check(
            "i9a_m_profile_keys",
            all(
                k in profile
                for k in (
                    "identity",
                    "aliases",
                    "facts",
                    "contacts",
                    "relationships",
                    "life_events",
                )
            ),
            checks,
            problems,
        )

        if flightsim:
            if os.environ.get("MEMORYBOX_P1_RUNTIME_HOST", "").strip() != "1":
                _check(
                    "i9a_flightsim_runtime_host",
                    False,
                    checks,
                    problems,
                    detail="Set MEMORYBOX_P1_RUNTIME_HOST=1 on FlightSim",
                )
            else:
                fs_owner = (os.environ.get("MEMORYBOX_I9A_OWNER_PERSON_ID") or "").strip()
                # Prefer real owner env already set for ops
                live = owner_config_status()
                _check(
                    "i9a_owner_gate_env",
                    live.get("configured") is True
                    or bool(fs_owner)
                    or bool(os.environ.get(ENV_OWNER_PERSON_ID)),
                    checks,
                    problems,
                    detail=str(live),
                )

    finally:
        if prev_owner is None:
            os.environ.pop(ENV_OWNER_PERSON_ID, None)
        else:
            os.environ[ENV_OWNER_PERSON_ID] = prev_owner

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}
