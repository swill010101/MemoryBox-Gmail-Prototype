"""P2-I10A.1 Person Explorer / About / Edit acceptance (chrome + route + SoT)."""
from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import Any

from memorybox.person import merge_people, reject_mapping, rename_person, teach_provider_person
from memorybox.profile.facts import add_fact, format_life_date

ROOT = Path(__file__).resolve().parents[1]
EXPLORE_HTML = ROOT / "person" / "static" / "person-explore.html"
EXPLORE_JS = ROOT / "person" / "static" / "person-explore.js"
APP_PY = ROOT / "app.py"
PRD = ROOT.parent / "docs" / "product" / "MBPRD-P2-I10A1_PERSON_PROFILE_EDITOR.md"
SCREEN = ROOT.parent / "docs" / "product" / "MBSC-P2-I10A1_PERSON_SCREEN_CONTRACT.md"
FIELD_MAP = ROOT.parent / "docs" / "product" / "MBAS-P2-I10A1_FIELD_ACTION_MAP.md"
ACCEPT_DOC = ROOT.parent / "docs" / "product" / "MBAT-P2-I10A1_ACCEPTANCE.md"


def _check(
    name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = ""
) -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def run_prove_person_i10a1(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {
        "increment": "P2-I10A.1",
        "p1_runtime_final": bool(flightsim),
        "note": "P2-I10A.1 chrome + /people/{id}/edit + date precision.",
    }

    html = EXPLORE_HTML.read_text(encoding="utf-8") if EXPLORE_HTML.is_file() else ""
    js = EXPLORE_JS.read_text(encoding="utf-8") if EXPLORE_JS.is_file() else ""
    app = APP_PY.read_text(encoding="utf-8") if APP_PY.is_file() else ""
    edit_html = (ROOT / "person" / "static" / "person-edit.html").read_text(encoding="utf-8")
    edit_js = (ROOT / "person" / "static" / "person-edit.js").read_text(encoding="utf-8")

    _check(
        "docs_prd",
        PRD.is_file() and "I10A.1" in PRD.read_text(encoding="utf-8"),
        checks,
        problems,
        str(PRD),
    )
    _check("docs_screen_contract", SCREEN.is_file(), checks, problems, str(SCREEN))
    _check("docs_field_map", FIELD_MAP.is_file(), checks, problems, str(FIELD_MAP))
    _check("docs_acceptance", ACCEPT_DOC.is_file(), checks, problems, str(ACCEPT_DOC))

    _check(
        "a1_single_person_header",
        'id="mb-person-header"' in html,
        checks,
        problems,
        "need #mb-person-header",
    )
    curator_present = 'id="mb-explore-curator"' in html
    curator_hidden = (
        'id="mb-explore-curator" hidden' in html
        or 'mb-explore-curator" hidden' in html
        or "mb-person-hide-curator" in html
    )
    _check(
        "a2_no_curator_identity_card",
        (not curator_present) or curator_hidden,
        checks,
        problems,
        "remove or hide #mb-explore-curator on Person Explorer",
    )
    _check(
        "a3_about_action",
        'id="mb-person-about"' in html and ">About<" in html,
        checks,
        problems,
        "header About action #mb-person-about",
    )
    _check(
        "a3_edit_action",
        'id="mb-person-edit"' in html and ">Edit<" in html,
        checks,
        problems,
        "header Edit action",
    )
    _check(
        "a3_relationships_learn",
        'id="mb-person-relationships"' in html and 'id="mb-person-learn-link"' in html,
        checks,
        problems,
        "Relationships and Learn actions",
    )
    _check(
        "a4_no_view_edit_details",
        "View / Edit details" not in html,
        checks,
        problems,
        "relabel or remove View / Edit details",
    )
    _check(
        "a5_labeled_life_dates",
        "data-mb-life-dates" in html or "mb-person-life-dates" in html,
        checks,
        problems,
        "labeled life-date slot on header",
    )
    _check(
        "a6_labeled_memory_totals",
        "data-mb-memory-totals" in html or "mb-person-memory-totals" in html,
        checks,
        problems,
        "labeled memory totals by kind",
    )
    header_chunk = html
    if 'id="mb-person-header"' in html:
        start = html.index('id="mb-person-header"')
        header_chunk = html[start : start + 2500]
    _check(
        "a7_header_no_contact_dump",
        "Confirmed phone" not in header_chunk and "Confirmed email" not in header_chunk,
        checks,
        problems,
        "header must not dump contacts",
    )
    _check(
        "a8_also_known_as_slot",
        "data-mb-also-known-as" in html or "mb-person-aka" in html,
        checks,
        problems,
        "also-known-as slot",
    )
    _check(
        "a9_place_slot",
        "data-mb-important-place" in html or "mb-person-place" in html,
        checks,
        problems,
        "important-place slot",
    )
    about_dl_has_contacts = "Confirmed phone" in js or "Confirmed email" in js
    footer_about = 'id="mb-person-about-dl"' in html
    _check(
        "a7b_footer_card_no_contact_dump",
        not (footer_about and about_dl_has_contacts),
        checks,
        problems,
        "always-visible About card must not list emails/phones",
    )

    _check(
        "b1_about_opens_view_mode",
        "view=1" in js
        and "function aboutHref" in js
        and "renderAboutDrawer" not in js[js.find("function bindAboutNow") : js.find("function bindAboutNow") + 700]
        if "function bindAboutNow" in js
        else False,
        checks,
        problems,
        "About must go to /people/{id}/edit?view=1, not the text drawer",
    )
    _check(
        "a11_family_kinship_portraits",
        "collectFamily" in js
        and "applyFamilyPortrait" in js
        and "/portrait" in js
        and "prettyRole" in js,
        checks,
        problems,
        "Family strip must use kinship labels and preferred portraits",
    )
    _check(
        "a12_about_card_structured",
        'id="mb-person-about-dl"' in html
        and 'id="mb-person-about-rel"' in html
        and "Open About for the full read-only record" not in html
        and "Open About for the full read-only record" not in js,
        checks,
        problems,
        "Footer About card must be a structured dl, not a sentence",
    )
    _check(
        "b2_edit_href_people_id_edit",
        "/people/" in js
        and "/edit" in js
        and "adminHref" not in js[js.find("mb-person-edit") : js.find("mb-person-edit") + 400]
        if "mb-person-edit" in js
        else False,
        checks,
        problems,
        "Edit must go to /people/{id}/edit, not adminHref/About",
    )
    edit_opens_about = False
    idx = js.find('getElementById("mb-person-edit")')
    if idx >= 0:
        window = js[idx : idx + 220]
        edit_opens_about = "renderAboutDrawer" in window and "preventDefault" in window
    _check(
        "b2_edit_bypasses_about",
        not edit_opens_about,
        checks,
        problems,
        "Edit must not call renderAboutDrawer",
    )
    _check(
        "b3_about_footer_to_edit",
        'id="mb-person-about-open"' in html
        and "view=1" in js
        and 'id="mb-edit-enter-edit"' in edit_html,
        checks,
        problems,
        "About card Open profile → view=1; view screen has Edit → /people/{id}/edit",
    )
    about_complete = all(
        s in edit_html
        for s in (
            "Profile",
            "Relationships",
            "Identity and Sources",
            "mb-edit-aliases",
            "mb-edit-contacts",
            "data-mb-important-place",
        )
    )
    _check(
        "b4_about_complete_readonly",
        about_complete
        and "mb-edit-readonly" in edit_js
        and 'get("view")' in edit_js,
        checks,
        problems,
        "About/view uses person-edit cards and read-only view mode",
    )
    _check(
        "b5_about_view_readonly",
        "mb-edit-readonly" in edit_js and "mb-edit-advanced" in edit_js,
        checks,
        problems,
        "view=1 must disable writes and hide Advanced",
    )
    _check(
        "b6_edit_route",
        '@app.get("/people/{person_id}/edit")' in app
        or '@app.get("/people/{id}/edit")' in app,
        checks,
        problems,
        "register GET /people/{person_id}/edit",
    )
    _check(
        "b7_family_edit_not_admin",
        "people.html" not in app.split("/people/{person_id}/edit")[-1][:400]
        if "/people/{person_id}/edit" in app
        else False,
        checks,
        problems,
        "Edit route must not serve people.html admin",
    )

    rename_src = inspect.getsource(rename_person)
    _check(
        "c1_rename_mb_only",
        "UPDATE people" in rename_src and "immich" not in rename_src.lower(),
        checks,
        problems,
        "rename_person must stay MB-only",
    )
    reject_src = inspect.getsource(reject_mapping)
    teach_src = inspect.getsource(teach_provider_person)
    merge_src = inspect.getsource(merge_people)
    _check(
        "c2_reject_mb_only",
        "identity_negatives" in reject_src and "immich" not in reject_src.lower(),
        checks,
        problems,
        "reject_mapping MB-only",
    )
    _check(
        "c2_teach_no_immich_patch",
        "def teach_provider_person" in teach_src
        and "patch" not in teach_src.lower()
        and "/api/people" not in teach_src.lower(),
        checks,
        problems,
        "teach must not PATCH Immich people",
    )
    _check(
        "c2_merge_mb_only",
        "merged_away" in merge_src and "immich" not in merge_src.lower(),
        checks,
        problems,
        "merge_people MB-only",
    )
    _check(
        "c3_profile_bundle",
        'fetch("/people/"' in js and "/profile" in js,
        checks,
        problems,
        "Explorer still loads GET /people/{id}/profile",
    )
    add_src = inspect.getsource(add_fact)
    _check(
        "c4_date_precision",
        "date_precision" in add_src
        and format_life_date("1927-01-01", "year") == "1927"
        and format_life_date("1927-06-01", "month") == "Jun 1927",
        checks,
        problems,
        "add_fact persists precision; format_life_date does not fake a day",
    )
    _check(
        "edit_regions",
        all(s in edit_html for s in ("Profile", "Relationships", "Identity and Sources", "Advanced")),
        checks,
        problems,
        "editor has Profile / Relationships / Identity / Advanced",
    )
    _check(
        "edit_keeps_relationships",
        'id="mb-edit-relationships"' in edit_html and "mb-edit-rel-groups" in edit_html,
        checks,
        problems,
        "Edit must keep the full Relationships region",
    )

    if flightsim:
        host = os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") == "1"
        _check(
            "d1_p1_runtime_host",
            host,
            checks,
            problems,
            "MEMORYBOX_P1_RUNTIME_HOST=1 required for --flightsim",
        )

    ok = not problems
    return {
        "ok": ok,
        "increment": "P2-I10A.1",
        "checks": checks,
        "problems": problems,
        "meta": meta,
    }
