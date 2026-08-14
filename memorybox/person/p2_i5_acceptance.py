"""P2-I5 Universal Person Surfaces — structural acceptance harness."""
from __future__ import annotations

from pathlib import Path

from memorybox.explore.p2_i4_acceptance import _check


def run_p2_i5_acceptance() -> dict:
    checks: dict = {}
    problems: list[str] = []

    person_html = (
        Path(__file__).resolve().parent / "static" / "person-explore.html"
    ).read_text(encoding="utf-8")
    person_css = (
        Path(__file__).resolve().parent / "static" / "person-explore.css"
    ).read_text(encoding="utf-8")
    person_js = (
        Path(__file__).resolve().parent / "static" / "person-explore.js"
    ).read_text(encoding="utf-8")
    explore_js = (
        Path(__file__).resolve().parents[1]
        / "explore"
        / "static"
        / "explore.js"
    ).read_text(encoding="utf-8")
    app_py = (Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )

    _check(
        "i5_person_explore_html",
        "mb-person-header" in person_html
        and "Ask about" in person_html
        and "mb-person-footer" in person_html
        and "MB_PERSON_SURFACE" in person_html
        and 'data-mode="highlights"' in person_html
        and "/static/explore/explore.js" in person_html,
        checks,
        problems,
        "person-explore.html shell",
    )
    _check(
        "i5_person_dark_theme",
        "mb-person-surface" in person_css
        and "#0f141c" in person_css
        and 'html[data-mb-surface="people"]' in person_css
        and ".mb-card-meta" in person_css
        and "#141b27" in person_css
        and ".mb-explore-density" in person_css
        and "#mb-density-label" in person_css,
        checks,
        problems,
        "dark theme CSS (readable cards/filters/density)",
    )
    _check(
        "i5_explore_person_mode",
        "PERSON_MODE" in explore_js
        and "personScopedAsk" in explore_js
        and "rankHighlights" in explore_js
        and "ensureLockedPersonChip" in explore_js
        and "clear everything except" in explore_js
        and 'id: "audio"' in explore_js
        and 'id: "location"' in explore_js
        and "has GPS/Place" in explore_js
        and "I5 visual lock order" in explore_js,
        checks,
        problems,
        "explore.js person mode hooks",
    )
    orch_py = (
        Path(__file__).resolve().parents[1] / "ask" / "orchestrator.py"
    ).read_text(encoding="utf-8")
    find_py = (
        Path(__file__).resolve().parents[1] / "explore" / "find.py"
    ).read_text(encoding="utf-8")
    _check(
        "i5_person_find_locks_person_id",
        "isLockedPersonLibraryAsk" in explore_js
        and "freshSession" in explore_js
        and "&person_id=" in explore_js
        and "PERSON_MODE && PERSON.personId" in explore_js
        and "explore_locked_person_id" in orch_py
        and "_apply_locked_person_to_plan" in orch_py
        and "person_id: str | None = None" in find_py
        and "person_id=person_id" in find_py
        and 'person_id: str | None = Query(' in app_py,
        checks,
        problems,
        "Person Explorer find passes person_id; boot skips stale Ask session",
    )
    _check(
        "i5_people_ui_route",
        "PERSON_EXPLORE_STATIC" in app_py
        and "Person Explorer" in app_py
        and 'person: str | None' in app_py,
        checks,
        problems,
        "/people/ui?person= route",
    )
    _check(
        "i5_person_panels_js",
        "loadProfile" in person_js
        and "mb-person-learn-stats" in person_js
        and "mb-person-ready" in person_js
        and "renderAboutDrawer" in person_js
        and "renderFamilyDrawer" in person_js
        and "renderLearnDrawer" in person_js
        and "/review/ui" in person_js
        and "Born on" in person_js
        and "Lives in" in person_js
        and "relationToOwner" in person_js
        and 'row("Parent of"' not in person_js
        and 'row("Spouse of"' not in person_js
        and "Identify a face" in person_html
        and "mbExploreOpenLearnFromGallery" in explore_js
        and "preferLearnRail" in explore_js
        and "mb-person-learn-identify" in person_html
        and "mb-about-sheet" in person_html,
        checks,
        problems,
        "About compact (name/born/relationship/lives) + Learn Identify/Review",
    )
    _check(
        "i5_person_drawer_shell",
        "mb-person-drawer" in person_html
        and "Open full profile editor" in person_html
        and "locationFilterMode" in person_html,
        checks,
        problems,
        "secondary drawer + Location=D boot config",
    )
    _check(
        "i5_ask_person_commands",
        "go to" in explore_js
        and "instead" in explore_js
        and "trySwitchPersonFromAsk" in explore_js
        and "resolvePersonOption" in explore_js
        and "zoomTimelineToRange" in explore_js
        and "syncPersonChrome" in explore_js
        and "stays locked" in explore_js
        and "person_name=" in explore_js,
        checks,
        problems,
        "Go to … instead + locked-person Ask guards",
    )
    _check(
        "i5_reuse_not_iframe",
        "iframe" not in person_html.lower()
        and "explore.js" in person_html,
        checks,
        problems,
        "reuses explore.js (no iframe)",
    )
    people_html = (
        Path(__file__).resolve().parent / "static" / "people.html"
    ).read_text(encoding="utf-8")
    _check(
        "i5_people_picker_to_explorer",
        "Open Person" in people_html
        and 'id="mb-people-admin"' in people_html
        and "Person Explorer" in people_html
        and "?admin=1" in people_html
        and "continueActivePerson" in people_html
        and "mb_active_person" in people_html,
        checks,
        problems,
        "People picker → Explorer; admin gated; Explore context continue",
    )
    shell_js = (
        Path(__file__).resolve().parents[1] / "shell" / "static" / "shell.js"
    ).read_text(encoding="utf-8")
    _check(
        "i5_shell_people_continues_person",
        "peopleHref" in shell_js
        and "setActivePerson" in shell_js
        and "mb_active_person" in shell_js
        and "syncActivePersonContext" in explore_js
        and "(PERSON && PERSON.personId)" in explore_js,
        checks,
        problems,
        "shell People nav continues active person",
    )
    _check(
        "i5_immich_preferred_portrait",
        "/people/{person_id}/portrait" in app_py
        and "fetch_person_portrait_bytes" in app_py
        and "resolve_immich_external_ids_for_person" in (
            Path(__file__).resolve().parent / "__init__.py"
        ).read_text(encoding="utf-8")
        and "applyPortraitUrl" in person_js
        and "has-photo" in person_js
        and "relationToOwner" in person_js
        and "applyPersonPortrait" in person_js
        and "PERSON_MODE" in explore_js,
        checks,
        problems,
        "Immich preferred portrait endpoint + header/family apply (not curator duplicate)",
    )
    person_init = (
        Path(__file__).resolve().parent / "__init__.py"
    ).read_text(encoding="utf-8")
    _check(
        "i5_portrait_build_photo_import",
        "from memorybox.providers.photo import build_photo" not in person_init
        and "from memorybox.ask.deps import build_photo" in person_init
        and "except Exception" in app_py
        and "portrait unavailable" in app_py,
        checks,
        problems,
        "portrait uses ask.deps.build_photo; endpoint must not 500",
    )
    from memorybox.providers.photo.asset_ref import photo_proxy_asset_id, photo_proxy_url

    thumb_path = (
        "/data/thumbs/261e97ac-f93e-43b3-9b07-61782f14295f/02/2d/"
        "022df03e-b045-4108-aeff-82808c817cbd.jpeg"
    )
    _check(
        "i5_face_evidence_thumb_not_disk_path",
        photo_proxy_asset_id(thumb_path)
        == "022df03e-b045-4108-aeff-82808c817cbd"
        and photo_proxy_url(thumb_path)
        == "/library/media/photo/022df03e-b045-4108-aeff-82808c817cbd"
        and photo_proxy_url("ec875510-6ad2-41e6-8e57-ad8ef09c8a64")
        == "/library/media/photo/ec875510-6ad2-41e6-8e57-ad8ef09c8a64"
        and photo_proxy_asset_id("") is None
        and "photoProxyAssetId" in person_js
        and "photoProxyUrl" in person_js
        and "/library/media/photo/\" + asset" not in person_js
        and "photo_proxy_url" in app_py,
        checks,
        problems,
        "face-evidence thumbs use Immich asset UUID, not /data/thumbs path",
    )

    from memorybox.person import portrait_immich_ids_for_name
    from memorybox.providers.photo.dto import PhotoPersonRef
    from memorybox.providers.photo.fake import FakePhotoProvider

    land = PhotoPersonRef(
        provider_key="fake_photo",
        external_id="11111111-1111-4111-8111-111111111111",
        display_name="Tom Landzaat",
    )
    will = PhotoPersonRef(
        provider_key="fake_photo",
        external_id="22222222-2222-4222-8222-222222222222",
        display_name="Tom Will",
    )
    both = FakePhotoProvider(extra_people=[land, will])
    land_only = FakePhotoProvider(extra_people=[land])
    _check(
        "i5_portrait_exact_name_not_other_tom",
        portrait_immich_ids_for_name(both, "Tom Will", [land.external_id])
        == [will.external_id]
        and portrait_immich_ids_for_name(land_only, "Tom Will", [land.external_id])
        == []
        and "_ask_named_photo_people(provider, name)" not in person_init
        and "elif len(refs) == 1" not in person_init
        and "nameL.startsWith(lab.split" not in explore_js,
        checks,
        problems,
        "portrait + people-bar never attach another Tom via first-token match",
    )

    overall = not problems and all(c.get("ok") for c in checks.values())
    return {
        "overall_ok": overall,
        "checks": checks,
        "problems": problems,
        "meta": {"increment": "P2-I5", "mode": "harness"},
        "note": (
            "Harness is structural. P2-I5 ACCEPTED 2026-08-14 (Tom). "
            "Immich preferred portrait = backlog P2-BL-I5-01 (not a reopen)."
        ),
    }


def main() -> None:
    import json

    print(json.dumps(run_p2_i5_acceptance(), indent=2))


if __name__ == "__main__":
    main()
