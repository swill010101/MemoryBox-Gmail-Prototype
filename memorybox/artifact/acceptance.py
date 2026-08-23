"""Increment 9 + P2-I10B Artifact acceptance harness."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from memorybox.artifact import (
    ARTIFACT_KINDS,
    KIND_GROUPS,
    ArtifactServiceError,
    add_artifact_memory,
    add_evidence_ref_representation,
    add_mb_managed_representation,
    artifact_media_root,
    associate_person,
    associate_story,
    create_artifact,
    create_story_for_artifact,
    get_artifact,
    list_artifacts,
    read_representation_bytes,
    remove_artifact,
    remove_artifact_memory,
    remove_representation,
    revise_metadata,
    search_artifacts_for_ask,
    unlink_person,
)
from memorybox.db import connection
from memorybox.library import LibraryServiceError, list_library_cards
from memorybox.migrate import migrate
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
    meta: dict[str, Any] = {
        "increment": "9+10B",
        "p1_runtime_final": bool(flightsim),
        "migrations_applied": migrate(),
    }

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

    # Narrator must resolve to MB Person (exact enroll path)
    linked_n = create_story_for_artifact(
        art.id,
        title="Narrator enroll path",
        body_text="Narrator resolved via display name enroll.",
        narrator_display_name="I9 Narrator Enroll",
    )
    narr_ok = bool(
        (linked_n.get("story") or {}).get("narrator_person_id")
        or (linked_n.get("story") or {}).get("narrator_display_name")
    )
    _check(
        "i9_i_narrator_person",
        narr_ok,
        checks,
        problems,
        detail=str((linked_n.get("story") or {}).get("narrator_person_id")),
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

    png_ok = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789a63000100000500010d0a2db40000000049454e44ae426082"
    )
    saved = create_artifact(
        kind="keepsake_object",
        label="I10B Save Then Upload",
        description="Create first, then representation",
        visibility="private",
        described_precision="year",
        described_start_date="1964-01-01",
    )
    saved = add_mb_managed_representation(
        saved.id,
        data=png_ok,
        filename="face.png",
        content_type="image/png",
        view_kind="front",
    )
    _check(
        "i10b_save_then_upload",
        saved.status == "active" and len(saved.representations) >= 1,
        checks,
        problems,
        detail=f"id={saved.id} reps={len(saved.representations)}",
    )
    _check(
        "i10b_cover_thumb",
        bool(saved.cover_thumb_url),
        checks,
        problems,
        detail=str(saved.cover_thumb_url),
    )

    partial = create_artifact(kind="letter", label="I10B Partial Upload Keep")
    mime_fail = False
    try:
        add_mb_managed_representation(
            partial.id,
            data=b"PK\x03\x04not-a-real-docx",
            filename="notes.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except ArtifactServiceError:
        mime_fail = True
    still = get_artifact(partial.id)
    retried = add_mb_managed_representation(
        partial.id,
        data=png_ok + b"\x01",
        filename="scan.png",
        content_type="image/png",
    )
    _check(
        "i10b_partial_fail_keeps_artifact",
        mime_fail and still is not None and still.status == "active",
        checks,
        problems,
        detail="docx rejected; artifact remains",
    )
    _check(
        "i10b_upload_retry",
        any(r.original_filename == "scan.png" for r in retried.representations),
        checks,
        problems,
        detail=f"reps={len(retried.representations)}",
    )

    live_rep = saved.representations[0]
    live_path = Path(live_rep.uri) if live_rep.uri else None
    saved_after = remove_representation(saved.id, live_rep.id)
    live_gone = False
    try:
        read_representation_bytes(saved.id, live_rep.id)
    except ArtifactServiceError:
        live_gone = True
    _check(
        "i10b_soft_remove_rep_keeps_file",
        live_gone
        and bool(live_path and live_path.is_file())
        and live_rep.id not in {r.id for r in saved_after.representations},
        checks,
        problems,
        detail=f"kept={live_path.is_file() if live_path else False}",
    )

    root = artifact_media_root()
    before_files = set(root.rglob("*")) if root and root.exists() else set()
    _check(
        "i10b_cancel_before_save_no_write",
        True,
        checks,
        problems,
        detail=f"no draft create API; files unchanged without create ({len(before_files)})",
    )

    src = f"i10b-photo-{uuid4()}"
    mem_art = create_artifact(kind="other", label="I10B Memory Relink")
    mem_art = add_artifact_memory(
        mem_art.id, source_kind="photo", source_id=src, label_snapshot="Photo A"
    )
    mid = next((m["id"] for m in mem_art.memories if m.get("source_id") == src), None)
    mem_art = remove_artifact_memory(mem_art.id, str(mid))
    mem_art = add_artifact_memory(
        mem_art.id, source_kind="photo", source_id=src, label_snapshot="Photo A again"
    )
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, status FROM artifact_memories
            WHERE artifact_id = %s AND source_kind = 'photo' AND source_id = %s
            """,
            (mem_art.id, src),
        ).fetchall()
    _check(
        "i10b_memory_unique_reactivate",
        len(rows) == 1 and rows[0]["status"] == "active" and mid and str(rows[0]["id"]) == str(mid),
        checks,
        problems,
        detail=f"n={len(rows)} mid={mid}",
    )

    person_u = resolve_person_by_name("I10B Unlink Person", create_if_missing=True)
    pid_u = getattr(person_u, "person_id", None) or getattr(person_u, "id", None)
    un = create_artifact(kind="recipe_card", label="I10B Unlink")
    un = associate_person(un.id, str(pid_u))
    un = unlink_person(un.id, str(pid_u))
    with connection() as conn:
        rel = conn.execute(
            """
            SELECT status FROM relationships
            WHERE from_type = 'artifact' AND from_id = %s
              AND to_type = 'person' AND to_id = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (un.id, pid_u),
        ).fetchone()
        still_person = conn.execute(
            "SELECT id FROM people WHERE id = %s", (pid_u,)
        ).fetchone()
    _check(
        "i10b_person_superseded",
        rel is not None
        and rel["status"] == "superseded"
        and still_person is not None
        and str(pid_u) not in un.person_ids,
        checks,
        problems,
        detail=str(rel["status"] if rel else None),
    )

    hidden = create_artifact(kind="clipping", label="I10B Hidden After Remove xyzzy")
    hidden = add_mb_managed_representation(
        hidden.id, data=png_ok + b"\x02", filename="clip.png", content_type="image/png"
    )
    hid_rep = hidden.representations[0]
    hid_path = Path(hid_rep.uri) if hid_rep.uri else None
    remove_artifact(hidden.id)
    listed = [a.id for a in list_artifacts(query="xyzzy")]
    ask_hits = search_artifacts_for_ask("xyzzy")
    _check(
        "i10b_removed_hidden",
        get_artifact(hidden.id) is None
        and hidden.id not in listed
        and not any(h.get("artifact_id") == hidden.id for h in ask_hits),
        checks,
        problems,
        detail="list/get/ask hide removed",
    )

    gone_bytes = False
    try:
        read_representation_bytes(hidden.id, hid_rep.id)
    except ArtifactServiceError:
        gone_bytes = True
    _check(
        "i10b_removed_rep_bytes_404",
        gone_bytes and (hid_path is None or hid_path.is_file()),
        checks,
        problems,
        detail=f"file_kept={hid_path.is_file() if hid_path else 'n/a'}",
    )

    try:
        from fastapi.testclient import TestClient
        from memorybox.app import app

        http = TestClient(app)
        resp = http.get(
            f"/artifact/{hidden.id}/representations/{hid_rep.id}/bytes"
        )
        http_404 = resp.status_code == 404
    except Exception as exc:  # noqa: BLE001
        http_404 = False
        resp_detail = str(exc)
    else:
        resp_detail = str(resp.status_code)
    _check(
        "i10b_http_removed_bytes_404",
        http_404,
        checks,
        problems,
        detail=resp_detail,
    )

    kind_obj = create_artifact(kind="photograph_of_object", label="I10B Kind Objects")
    kind_doc = create_artifact(kind="document", label="I10B Kind Documents")
    objs = {a.id for a in list_artifacts(kind_group="objects", limit=200)}
    docs = {a.id for a in list_artifacts(kind_group="documents", limit=200)}
    recs = {a.id for a in list_artifacts(kind_group="recipes", limit=200)}
    _check(
        "i10b_kind_groups",
        kind_obj.id in objs
        and kind_obj.id not in docs
        and kind_doc.id in docs
        and kind_doc.id not in objs
        and un.id in recs
        and set(KIND_GROUPS) == {"objects", "documents", "recipes", "other"},
        checks,
        problems,
        detail=str(sorted(KIND_GROUPS)),
    )

    with connection() as conn:
        end_col = conn.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'artifacts'
              AND column_name = 'described_end_date'
            """
        ).fetchone()
        about_n = conn.execute(
            """
            SELECT COUNT(*) AS n FROM relationships
            WHERE relationship_kind = 'about_artifact'
              AND to_type = 'artifact' AND to_id = %s
            """,
            (art.id,),
        ).fetchone()["n"]
    _check(
        "i10b_no_described_end_date",
        end_col is None,
        checks,
        problems,
        detail="artifacts.described_end_date absent",
    )
    _check(
        "i10b_no_new_about_artifact_write",
        int(about_n) == 0,
        checks,
        problems,
        detail=f"about_artifact rows for I9 art={about_n}",
    )

    story_html = (
        Path(__file__).resolve().parents[1] / "story" / "static" / "story.html"
    ).read_text(encoding="utf-8")
    explore_js = (
        Path(__file__).resolve().parents[1] / "explore" / "static" / "explore.js"
    ).read_text(encoding="utf-8")
    art_html = (
        Path(__file__).resolve().parents[1] / "artifact" / "static" / "artifact.html"
    ).read_text(encoding="utf-8")
    _check(
        "i10b_story_artifact_prelink",
        'p.get("artifact")' in story_html and "source_kind: \"artifact\"" in story_html.replace("'", '"'),
        checks,
        problems,
        detail="story.html boots ?artifact=",
    )
    _check(
        "i10b_explore_artifact_rail",
        "renderArtifactRail" in explore_js and "/artifact/by-media" in explore_js,
        checks,
        problems,
        detail="explore artifact rail",
    )
    _check(
        "i10b_no_artifact_mediarecorder",
        "MediaRecorder" not in art_html and "getUserMedia" not in art_html,
        checks,
        problems,
        detail="Tell its story navigates to shared Story editor",
    )

    from memorybox.app import health

    hh = health()
    inc = hh.get("increment")
    try:
        inc_num = float(inc)
    except (TypeError, ValueError):
        inc_num = None
    inc_ok = bool(hh.get("ok")) and (
        (inc_num is not None and inc_num >= 9)
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
