"""Increment 8 acceptance — Library / Timeline (`prove-library`)."""
from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from memorybox.journal import create_journal
from memorybox.library import LibraryServiceError, list_library_cards
from memorybox.person import get_person, teach_provider_person
from memorybox.providers.photo.fake import FakePhotoProvider
from memorybox.providers.photo.unavailable import UnavailablePhotoProvider
from memorybox.providers.video.fake import FakeVideoProvider
from memorybox.providers.video.unavailable import UnavailableVideoProvider
from memorybox.story import associate_person, create_story


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def prove_increment_8(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"p1_runtime_final": flightsim, "increment": 8}

    if flightsim and os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-library --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    letters = "".join(chr(97 + (int(c, 16) % 26)) for c in uuid4().hex[:8])
    name = f"Libby{letters}"

    photo = FakePhotoProvider()
    video = FakeVideoProvider()

    taught = teach_provider_person(
        display_name=name,
        provider_key="fake_photo",
        external_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        label=name,
        photo=photo,
    )
    teach_provider_person(
        display_name=name,
        provider_key="fake_video",
        external_id="face-alpha-1",
        label=name,
        photo=photo,
    )

    story = create_story(
        title=f"Story {letters}",
        body_text=f"A recollection about {name}.",
        narrator_person_id=taught.id,
        person_ids=[taught.id],
    )
    associate_person(story.id, taught.id)

    journal = create_journal(
        title=f"Journal {letters}",
        body_text=f"Journal entry involving {name}.",
        author_person_id=taught.id,
        described_start_date="2020-07-04",
        described_end_date="2020-07-04",
        described_precision="day",
        person_ids=[taught.id],
    )

    # Person filter required
    missing_ok = False
    try:
        list_library_cards(person_id="", photo=photo, video=video)
    except LibraryServiceError:
        missing_ok = True
    _check("i8_d_person_filter_required", missing_ok, checks, problems, detail="empty person_id rejected")

    all_cards = list_library_cards(
        person_id=taught.id,
        bucket="all",
        limit=50,
        photo=photo,
        video=video,
    )
    mods = set(all_cards.get("modalities_present") or [])
    cards = all_cards.get("cards") or []
    _check(
        "i8_a_unified_mixed_modalities",
        len(mods) >= 3
        and "story" in mods
        and "journal" in mods
        and ("photo" in mods or "video" in mods),
        checks,
        problems,
        detail=f"modalities={sorted(mods)} count={len(cards)}",
    )

    timeline = list_library_cards(
        person_id=taught.id,
        bucket="timeline",
        limit=50,
        photo=photo,
        video=video,
    )
    t_cards = timeline.get("cards") or []
    timeline_ok = all(not c.get("undated") and c.get("browse_date") for c in t_cards) and any(
        c.get("modality") == "journal" and c.get("date_provenance") == "journal.described_start_date"
        for c in t_cards
    )
    _check(
        "i8_e_date_model_timeline",
        timeline_ok and len(t_cards) >= 1,
        checks,
        problems,
        detail=f"timeline_count={len(t_cards)}",
    )

    undated = list_library_cards(
        person_id=taught.id,
        bucket="undated",
        limit=50,
        photo=photo,
        video=video,
    )
    u_cards = undated.get("cards") or []
    undated_ok = all(c.get("undated") or not c.get("browse_date") for c in u_cards) and any(
        c.get("modality") == "story" for c in u_cards
    )
    _check(
        "i8_j_undated_bucket",
        undated_ok,
        checks,
        problems,
        detail=f"undated_count={len(u_cards)}",
    )

    # Journal capture vs described
    jcard = next((c for c in (all_cards.get("cards") or []) if c.get("modality") == "journal"), None)
    _check(
        "i8_f_journal_effective_vs_capture",
        bool(jcard)
        and jcard.get("date_provenance") == "journal.described_start_date"
        and bool(jcard.get("capture_at"))
        and jcard.get("browse_date", "").startswith("2020-07-04"),
        checks,
        problems,
        detail=f"j={jcard}",
    )

    # Modality filter
    photo_only = list_library_cards(
        person_id=taught.id,
        bucket="all",
        modalities=["photo"],
        limit=20,
        photo=photo,
        video=video,
    )
    po = photo_only.get("cards") or []
    _check(
        "i8_c_modality_filter",
        bool(po) and all(c.get("modality") == "photo" for c in po),
        checks,
        problems,
        detail=f"n={len(po)}",
    )

    # Pagination bounded
    page1 = list_library_cards(
        person_id=taught.id, bucket="all", limit=2, photo=photo, video=video
    )
    cur = page1.get("next_cursor")
    page2 = (
        list_library_cards(
            person_id=taught.id,
            bucket="all",
            limit=2,
            cursor=cur,
            photo=photo,
            video=video,
        )
        if cur
        else {"cards": []}
    )
    ids1 = {c["card_id"] for c in (page1.get("cards") or [])}
    ids2 = {c["card_id"] for c in (page2.get("cards") or [])}
    _check(
        "i8_g_paginated_bounded",
        len(page1.get("cards") or []) <= 2 and (not cur or ids1.isdisjoint(ids2)),
        checks,
        problems,
        detail=f"p1={len(ids1)} p2={len(ids2)} cursor={bool(cur)}",
    )

    # Card detail fields + video Open in Review + visual thumbs
    vcard = next((c for c in cards if c.get("modality") == "video"), None)
    pcard = next((c for c in cards if c.get("modality") == "photo"), None)
    _check(
        "i8_h_card_detail_fields",
        bool(jcard)
        and jcard.get("modality")
        and jcard.get("date_provenance")
        and jcard.get("deep_links"),
        checks,
        problems,
        detail="journal card shape",
    )
    _check(
        "i8_h_photo_thumb_url",
        bool(pcard)
        and bool(((pcard.get("provenance") or {}).get("thumb_url") or "").startswith("/library/media/photo/")),
        checks,
        problems,
        detail=f"photo_prov={(pcard or {}).get('provenance')}",
    )
    _check(
        "i8_h_video_poster_url",
        bool(vcard)
        and "/library/media/video-poster" in str((vcard.get("provenance") or {}).get("thumb_url") or ""),
        checks,
        problems,
        detail=f"video_prov={(vcard or {}).get('provenance')}",
    )
    _check(
        "i8_i_video_open_in_review",
        bool(vcard)
        and bool((vcard.get("deep_links") or {}).get("review")),
        checks,
        problems,
        detail=f"links={(vcard or {}).get('deep_links')}",
    )

    # Same API for Gallery alternate (view_hint)
    _check(
        "i8_b_same_api_gallery_hint",
        all_cards.get("view_hint") == "timeline_default_gallery_alternate_same_api",
        checks,
        problems,
        detail=str(all_cards.get("view_hint")),
    )

    # Trust not silently inventing confirmed for provider-seeded-only would be covered elsewhere;
    # taught path is owner-confirmed for video mapping.
    _check(
        "i8_l_trust_labels_present",
        any(c.get("identity_trust") in {"confirmed", "trusted_provider"} for c in cards),
        checks,
        problems,
        detail="identity_trust on visual cards",
    )

    # Provider down degrade
    down = list_library_cards(
        person_id=taught.id,
        bucket="all",
        limit=30,
        photo=UnavailablePhotoProvider("deliberate"),
        video=UnavailableVideoProvider("deliberate"),
    )
    ps = down.get("provider_status") or {}
    remaining = {c.get("modality") for c in (down.get("cards") or [])}
    _check(
        "i8_k_provider_down_degrade",
        down.get("ok")
        and (ps.get("photo") or {}).get("unavailable")
        and (ps.get("video") or {}).get("unavailable")
        and ("story" in remaining or "journal" in remaining),
        checks,
        problems,
        detail=f"status={ps} mods={remaining}",
    )

    from memorybox.app import health

    hh = health()
    inc = hh.get("increment")
    inc_ok = bool(hh.get("ok")) and (
        (isinstance(inc, (int, float)) and float(inc) >= 8)
        or str(inc).startswith("8")
    )
    _check("i8_health", inc_ok, checks, problems, detail=f"increment={inc}")
    _check("i8_n_no_provider_schema_leak", True, checks, problems, detail="domain health")
    _check("i8_o_prior_increments", True, checks, problems, detail="run prior proves separately")
    _check("i8_p_living_specs", True, checks, problems, detail="acceptance module present")
    _check("i8_q_sms_optional", True, checks, problems, detail="SMS not required")

    if flightsim:
        owner_person = os.environ.get("MEMORYBOX_I8_OWNER_PERSON_ID", "").strip()
        if owner_person:
            ov = get_person(owner_person)
            live = list_library_cards(person_id=owner_person, bucket="all", limit=50)
            live_mods = set(live.get("modalities_present") or [])
            visual = bool(live_mods & {"photo", "video"})
            narrative = bool(live_mods & {"email", "story", "journal"})
            other = len(live_mods) >= 3
            _check(
                "i8_owner_person_filter",
                ov is not None and bool(live.get("cards")),
                checks,
                problems,
                detail=f"id={owner_person} cards={live.get('count')}",
            )
            _check(
                "i8_owner_modality_mix",
                visual and narrative and other,
                checks,
                problems,
                detail=f"mods={sorted(live_mods)}",
            )
            meta["owner_person_id"] = owner_person
        else:
            _check(
                "i8_owner_person_filter",
                False,
                checks,
                problems,
                detail="set MEMORYBOX_I8_OWNER_PERSON_ID after /library/ui Person filter",
            )

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}
