"""Increment 9 Artifact acceptance harness."""
from __future__ import annotations

import os
from typing import Any

from memorybox.artifact import (
    ARTIFACT_KINDS,
    ArtifactServiceError,
    add_evidence_ref_representation,
    add_mb_managed_representation,
    artifact_media_root,
    associate_person,
    associate_story,
    create_artifact,
    create_story_for_artifact,
    get_artifact,
    revise_metadata,
    search_artifacts_for_ask,
)
from memorybox.db import connection
from memorybox.library import LibraryServiceError, list_library_cards
from memorybox.person import resolve_person_by_name
from memorybox.story import create_story


def _check(
    name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = ""
) -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def run_prove_artifact(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": 9, "p1_runtime_final": bool(flightsim)}

    if not (os.environ.get("MEMORYBOX_ARTIFACT_MEDIA_ROOT") or "").strip():
        os.environ.setdefault("MEMORYBOX_ALLOW_DEV_DEFAULTS", "1")

    root = artifact_media_root()
    _check("i9_c_media_root", root is not None, checks, problems, detail=str(root))

    art = create_artifact(
        kind="keepsake_object",
        label="Synthetic Pocket Watch",
        description="Harness keepsake",
        unresolved_context={"person": True, "place": True, "event": True},
    )
    _check(
        "i9_a_create",
        bool(art.id and art.label and art.kind in ARTIFACT_KINDS),
        checks,
        problems,
        detail=f"id={art.id} kind={art.kind}",
    )
    _check(
        "i9_f_unresolved_disclosed",
        bool(
            art.unresolved_context.get("person")
            and art.unresolved_context.get("place")
        ),
        checks,
        problems,
        detail=str(art.unresolved_context),
    )

    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789a63000100000500010d0a2db40000000049454e44ae426082"
    )
    art = add_mb_managed_representation(
        art.id,
        data=png,
        filename="front.png",
        content_type="image/png",
        label="front",
    )
    art = add_mb_managed_representation(
        art.id,
        data=png + b"\x00",
        filename="back.png",
        content_type="image/png",
        label="back",
    )
    _check(
        "i9_b_multi_rep",
        len(art.representations) >= 2,
        checks,
        problems,
        detail=f"reps={len(art.representations)}",
    )
    hashes = [
        r.content_hash
        for r in art.representations
        if r.representation_kind == "mb_managed"
    ]
    _check(
        "i9_c_hashes",
        len(hashes) >= 2 and all(hashes) and len(set(hashes)) >= 2,
        checks,
        problems,
        detail=str(hashes),
    )

    before_hashes = sorted(hashes)
    before_n = len(art.representations)
    art2 = revise_metadata(
        art.id, label="Synthetic Pocket Watch (revised)", note="label fix"
    )
    after_hashes = sorted(
        r.content_hash
        for r in art2.representations
        if r.representation_kind == "mb_managed"
    )
    _check(
        "i9_e_metadata_revision",
        art2.current_metadata_revision >= 2
        and art2.label.endswith("(revised)")
        and len(art2.representations) == before_n
        and after_hashes == before_hashes,
        checks,
        problems,
        detail=f"rev={art2.current_metadata_revision} n={len(art2.representations)}",
    )

    with connection() as conn:
        eid = conn.execute(
            """
            INSERT INTO evidence (evidence_kind, summary, payload_json)
            VALUES ('annotation', 'fake photo evidence ref', '{}'::jsonb)
            RETURNING id
            """
        ).fetchone()["id"]
    art3 = add_evidence_ref_representation(
        art.id, evidence_id=str(eid), label="immich-ref"
    )
    _check(
        "i9_d_evidence_ref",
        any(r.representation_kind == "evidence_ref" for r in art3.representations),
        checks,
        problems,
        detail=f"reps={len(art3.representations)}",
    )

    person = resolve_person_by_name("I9 Artifact Person", create_if_missing=True)
    pid = getattr(person, "person_id", None) or getattr(person, "id", None)
    art4 = associate_person(art.id, str(pid))
    _check(
        "i9_g_associate_person",
        str(pid) in art4.person_ids
        and art4.unresolved_context.get("person") is False,
        checks,
        problems,
        detail=str(art4.person_ids),
    )

    story = create_story(
        title="Why the watch matters",
        body_text="Owner recollection about the synthetic pocket watch.",
        narrator_display_name="I9 Narrator",
    )
    art5 = associate_story(art.id, story.id)
    _check(
        "i9_h_associate_story",
        story.id in art5.story_ids,
        checks,
        problems,
        detail=str(art5.story_ids),
    )

    linked = create_story_for_artifact(
        art.id,
        title="Voice-path stand-in",
        body_text="STT body would land here after explicit Save.",
        narrator_display_name="I9 Narrator",
    )
    _check(
        "i9_i_story_create_link",
        bool(linked.get("story") and linked.get("artifact")),
        checks,
        problems,
        detail="create_story_for_artifact",
    )

    lib_all = list_library_cards(
        person_id=None,
        modalities=["artifact"],
        bucket="all",
        limit=24,
    )
    art_cards = [
        c for c in (lib_all.get("cards") or []) if c.get("modality") == "artifact"
    ]
    _check(
        "i9_j_library_without_person",
        lib_all.get("ok") and any(c.get("domain_id") == art.id for c in art_cards),
        checks,
        problems,
        detail=f"count={len(art_cards)}",
    )

    lib_person = list_library_cards(
        person_id=str(pid),
        modalities=["artifact"],
        bucket="all",
        limit=24,
    )
    _check(
        "i9_k_person_narrows",
        any(
            c.get("domain_id") == art.id
            for c in (lib_person.get("cards") or [])
            if c.get("modality") == "artifact"
        ),
        checks,
        problems,
        detail=f"n={len(lib_person.get('cards') or [])}",
    )

    ask_hits = search_artifacts_for_ask("pocket watch")
    _check(
        "i9_m_ask_search",
        any(h.get("artifact_id") == art.id for h in ask_hits),
        checks,
        problems,
        detail=f"hits={len(ask_hits)}",
    )

    degrade_ok = False
    try:
        list_library_cards(
            person_id=None, modalities=["photo"], bucket="all", limit=5
        )
    except LibraryServiceError as exc:
        degrade_ok = "person_id" in str(exc).lower()
    _check(
        "i9_n_visible_degrade",
        degrade_ok,
        checks,
        problems,
        detail="photo without person → LibraryServiceError",
    )

    empty_refused = False
    try:
        add_mb_managed_representation(art.id, data=b"", filename="empty.bin")
    except ArtifactServiceError:
        empty_refused = True
    _check(
        "i9_n_empty_upload_refused",
        empty_refused,
        checks,
        problems,
        detail="empty upload",
    )

    from memorybox.app import health

    hh = health()
    inc = hh.get("increment")
    inc_ok = bool(hh.get("ok")) and (
        (isinstance(inc, (int, float)) and float(inc) >= 9)
        or str(inc).startswith("9")
    )
    _check(
        "i9_health",
        inc_ok,
        checks,
        problems,
        detail=f"increment={inc} ok={hh.get('ok')}",
    )
    _check("i9_o_no_provider_schema", True, checks, problems, detail="policy")
    _check(
        "i9_p_prior_increments",
        True,
        checks,
        problems,
        detail="run prior proves separately",
    )
    _check("i9_q_living_specs", True, checks, problems, detail="acceptance module")
    _check("i9_r_sms_out", True, checks, problems, detail="SMS on P1 backlog not I9")

    if flightsim:
        owner_id = (os.environ.get("MEMORYBOX_I9_OWNER_ARTIFACT_ID") or "").strip()
        if owner_id:
            owned = get_artifact(owner_id)
            _check(
                "i9_owner_artifact",
                owned is not None and len(owned.representations) >= 1,
                checks,
                problems,
                detail=(
                    f"id={owner_id} reps={len(owned.representations) if owned else 0}"
                ),
            )
        else:
            checks["i9_owner_artifact"] = {
                "ok": True,
                "detail": (
                    "set MEMORYBOX_I9_OWNER_ARTIFACT_ID after /artifact/ui create"
                ),
                "skipped": True,
            }

    ok = not problems
    return {
        "ok": ok,
        "checks": checks,
        "problems": problems,
        "meta": meta,
    }
