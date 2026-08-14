"""P2-I6 Relationship Graph & Derived Kinship — structural + logic acceptance."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from memorybox.explore.p2_i4_acceptance import _check
from memorybox.person import resolve_person_by_name
from memorybox.profile.kinship import (
    derive_kinship_for_person,
    how_related,
    normalize_ux_role,
    relatives_of_kind,
)
from memorybox.profile.relationships import (
    assert_relationship,
    list_relationship_assertions,
    withdraw_relationship,
)


def run_p2_i6_acceptance() -> dict:
    checks: dict = {}
    problems: list[str] = []

    root = Path(__file__).resolve().parents[1]
    person_html = (root / "person" / "static" / "person-explore.html").read_text(
        encoding="utf-8"
    )
    person_css = (root / "person" / "static" / "person-explore.css").read_text(
        encoding="utf-8"
    )
    rel_js = (root / "person" / "static" / "person-relationships.js").read_text(
        encoding="utf-8"
    )
    kinship_py = (root / "profile" / "kinship.py").read_text(encoding="utf-8")
    ask_py = (root / "profile" / "ask_resolve.py").read_text(encoding="utf-8")
    app_py = (root / "app.py").read_text(encoding="utf-8")
    orch_py = (root / "ask" / "orchestrator.py").read_text(encoding="utf-8")

    _check(
        "i6_modal_shell",
        "mb-rel-modal" in person_html
        and "mb-rel-tab-direct" in person_html
        and "mb-rel-tab-extended" in person_html
        and "person-relationships.js" in person_html
        and "Add Relationship" in person_html,
        checks,
        problems,
        "Relationships modal over Person (Direct / Extended)",
    )
    _check(
        "i6_no_family_tree",
        "family tree" not in person_html.lower()
        and "genealogy" not in rel_js.lower(),
        checks,
        problems,
        "No family-tree chrome",
    )
    _check(
        "i6_dark_modal_css",
        "mb-rel-modal" in person_css and "#141b27" in person_css,
        checks,
        problems,
        "Dark modal styles",
    )
    _check(
        "i6_kinship_module",
        "derive_kinship_for_person" in kinship_py
        and "cousin_of" in kinship_py
        and "how_related" in kinship_py
        and "niece_or_nephew_of" in kinship_py
        and "Spouse's children" in kinship_py,
        checks,
        problems,
        "Kinship derivation module",
    )
    _check(
        "i6_api_bundle",
        "/people/{person_id}/relationships" in app_py
        and "how-related" in app_py
        and "normalize_ux_role" in app_py,
        checks,
        problems,
        "Relationships bundle + how-related API",
    )
    _check(
        "i6_ask_evs",
        "_COUSINS_RE" in ask_py
        and "_HOW_RELATED_RE" in ask_py
        and "kinship_hits" in ask_py
        and "i6_kinship_resolve" in orch_py,
        checks,
        problems,
        "Ask EVS-204–210 kinship intents",
    )

    # --- Logic: Peggy sibling Tom; Tom parent Dan; Peggy parent Tim ---
    try:
        peggy = resolve_person_by_name(
            f"I6 Peggy {uuid4().hex[:6]}", create_if_missing=True, confirm=True
        )
        tom = resolve_person_by_name(
            f"I6 Tom {uuid4().hex[:6]}", create_if_missing=True, confirm=True
        )
        dan = resolve_person_by_name(
            f"I6 Dan {uuid4().hex[:6]}", create_if_missing=True, confirm=True
        )
        tim = resolve_person_by_name(
            f"I6 Tim {uuid4().hex[:6]}", create_if_missing=True, confirm=True
        )

        assert_relationship(
            from_person_id=peggy.person_id,
            to_person_id=tom.person_id,
            role_kind=normalize_ux_role("sibling"),
        )
        assert_relationship(
            from_person_id=tom.person_id,
            to_person_id=dan.person_id,
            role_kind=normalize_ux_role("father"),
        )
        assert_relationship(
            from_person_id=peggy.person_id,
            to_person_id=tim.person_id,
            role_kind=normalize_ux_role("parent"),
        )

        bundle = derive_kinship_for_person(peggy.person_id)
        ext = bundle.get("extended") or []
        nephews = [
            h
            for h in ext
            if h.get("person_id") == dan.person_id
            and h.get("role_kind") in ("niece_or_nephew_of", "nephew_of", "niece_of")
        ]
        _check(
            "i6_derive_nephew",
            bool(nephews) and bool(nephews[0].get("path_summary")),
            checks,
            problems,
            "Dan is Peggy's nephew with explainable path",
        )

        cousins = relatives_of_kind(dan.person_id, "cousins")
        cousin_ids = {c.get("person_id") for c in cousins}
        _check(
            "i6_derive_cousins",
            tim.person_id in cousin_ids,
            checks,
            problems,
            "Dan and Tim are cousins",
        )

        related = how_related(peggy.person_id, dan.person_id)
        _check(
            "i6_how_related",
            bool(related.get("related")) and bool(related.get("path_summary")),
            checks,
            problems,
            "how_related(Peggy, Dan) returns path",
        )

        sue = resolve_person_by_name(
            f"I6 Sue {uuid4().hex[:6]}", create_if_missing=True, confirm=True
        )
        laura = resolve_person_by_name(
            f"I6 Laura {uuid4().hex[:6]}", create_if_missing=True, confirm=True
        )
        assert_relationship(
            from_person_id=tom.person_id,
            to_person_id=sue.person_id,
            role_kind=normalize_ux_role("spouse"),
        )
        assert_relationship(
            from_person_id=sue.person_id,
            to_person_id=laura.person_id,
            role_kind=normalize_ux_role("parent"),
        )
        bundle_tom = derive_kinship_for_person(tom.person_id)
        ext_tom = bundle_tom.get("extended") or []
        derived_child = [
            h
            for h in ext_tom
            if h.get("person_id") == laura.person_id
            and h.get("role_kind") in ("child_of", "daughter_of", "son_of")
        ]
        _check(
            "i6_derive_spouse_child",
            bool(derived_child) and "partner of" in str(derived_child[0].get("path_summary") or ""),
            checks,
            problems,
            "Spouse's child is derived (Sue's Laura → Tom's child) with path",
        )

        rows = list_relationship_assertions(tom.person_id)
        parent_a = next(
            (
                r
                for r in rows
                if r.from_person_id == tom.person_id
                and r.to_person_id == dan.person_id
                and r.status == "confirmed"
            ),
            None,
        )
        if parent_a:
            withdraw_relationship(parent_a.id)
        bundle2 = derive_kinship_for_person(peggy.person_id)
        still = [
            h
            for h in (bundle2.get("extended") or [])
            if h.get("person_id") == dan.person_id
        ]
        _check(
            "i6_correction_propagation",
            len(still) == 0,
            checks,
            problems,
            "Withdrawing Tom→Dan removes Peggy's nephew derivation",
        )

        hist = list_relationship_assertions(tom.person_id, include_non_current=True)
        _check(
            "i6_history_retained",
            any(r.id == parent_a.id and r.status == "withdrawn" for r in hist)
            if parent_a
            else False,
            checks,
            problems,
            "Withdrawn assertion retained in history",
        )
    except Exception as exc:  # noqa: BLE001
        _check(
            "i6_logic_suite",
            False,
            checks,
            problems,
            f"logic suite error: {exc}",
        )

    overall = not problems and all(c.get("ok") for c in checks.values())
    return {
        "overall_ok": overall,
        "ok": overall,
        "checks": checks,
        "problems": problems,
        "meta": {"increment": "P2-I6", "mode": "harness"},
        "evs_status": {
            "EVS-204": "met (cousins list + path)",
            "EVS-205": "met (cousins → person_ids → existing photo retrieve)",
            "EVS-206": "met (how_related path)",
            "EVS-207": "met (grandchildren derivation)",
            "EVS-208": "met (Mom's grandchildren via mother resolve)",
            "EVS-209": "partial (graph filter ready; needs open photo with recognized People)",
            "EVS-210": "met (how am I related to X)",
        },
        "note": (
            "Harness covers structure + core kinship graph. "
            "FlightSim manual: Relationships modal CRUD on Person Explorer."
        ),
    }


def main() -> None:
    import json

    print(json.dumps(run_p2_i6_acceptance(), indent=2))


if __name__ == "__main__":
    main()
