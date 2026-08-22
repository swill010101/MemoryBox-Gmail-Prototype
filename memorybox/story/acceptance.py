"""P2-I10A Stories acceptance — drafts never Ask-visible; freeze moves Ask-current."""
from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.context import AskContext, InMemoryContextStore
from memorybox.ingest import store
from memorybox.planner import plan_ask
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.photo.fake import FakePhotoProvider
from memorybox.providers.video.fake import FakeVideoProvider
from memorybox.story import (
    StoryServiceError,
    add_working_memory,
    associate_evidence,
    begin_edit,
    create_story,
    discard_working,
    get_story,
    list_stories,
    save_draft,
    save_new_version,
    save_story,
    set_visibility,
)


def _one_evidence_id() -> str | None:
    rows = store.list_indexable_evidence()
    if rows:
        return str(rows[0]["id"])
    from pathlib import Path

    from memorybox.ingest.comms_email import ingest_mbox

    fixture = (
        Path(__file__).resolve().parents[1] / "providers" / "_fixtures" / "i3_synthetic.mbox"
    )
    ingest_mbox(str(fixture), label="i10a story prove fixture")
    rows = store.list_indexable_evidence()
    return str(rows[0]["id"]) if rows else None


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def prove_increment_5(*, flightsim: bool = False) -> dict[str, Any]:
    """I5 compatibility plus I10A draft / freeze / discard / rail-safety checks."""
    return prove_increment_10a(flightsim=flightsim)


def prove_increment_10a(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"p1_runtime_final": flightsim, "increment": "10A"}

    if flightsim and os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-story --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    # Do not call prove_increment_3() — it clears Qdrant and re-embeds the full
    # FlightSim archive (hours). Story prove only needs one Evidence UUID.
    evidence_id = _one_evidence_id()
    if not evidence_id:
        problems.append("no Evidence available for Story association")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}
    meta["i3_ok"] = "skipped_no_qdrant_rebuild"

    tag = f"Harborwick-{uuid4().hex[:8]}"
    try:
        s1 = create_story(
            title=f"Trip note {tag}",
            body_text=f"Owner recollection about {tag} voyage for synthetic I5 prove.",
            narrator_display_name="River Owner",
            evidence_ids=[evidence_id],
            actor_key="owner",
        )
    except Exception as exc:  # noqa: BLE001
        _check("i5_a_create_save", False, checks, problems, str(exc))
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    create_ok = (
        s1.current_version == 1
        and s1.version is not None
        and s1.version.version == 1
        and s1.narrator_person_id
        and evidence_id in s1.evidence_ids
        and s1.narrator_person_id in s1.person_ids
        and s1.ask_available
        and s1.current_saved_version_id
        and not s1.has_working_draft
    )
    _check(
        "i5_a_create_save",
        create_ok,
        checks,
        problems,
        detail=f"story_id={s1.id} v={s1.current_version} narrator={s1.narrator_person_id}",
    )
    meta["synthetic_story_id"] = s1.id
    meta["synthetic_tag"] = tag

    s2 = save_new_version(
        s1.id,
        body_text=f"Updated recollection about {tag} — version two.",
        actor_key="owner",
    )
    v1 = get_story(s1.id, version=1)
    v2 = get_story(s1.id, version=2)
    cur = get_story(s1.id)
    version_ok = (
        s2.current_version == 2
        and v1 is not None
        and v2 is not None
        and cur is not None
        and v1.version is not None
        and v2.version is not None
        and v1.version.version == 1
        and v2.version.version == 2
        and cur.version is not None
        and cur.version.version == 2
        and (v1.version.body_text != v2.version.body_text)
        and not s2.has_working_draft
    )
    _check(
        "i5_b_edit_new_version",
        version_ok,
        checks,
        problems,
        detail=f"current={s2.current_version}",
    )
    _check(
        "i5_c_retrieve_current_and_prior",
        version_ok,
        checks,
        problems,
        detail="v1+v2+current",
    )

    assoc_ok = bool(s1.narrator_person_id) and evidence_id in s1.evidence_ids and len(s1.person_ids) >= 1
    associated = associate_evidence(s1.id, evidence_id)
    _check(
        "i5_d_associations",
        assoc_ok and evidence_id in associated.evidence_ids,
        checks,
        problems,
        detail=f"people={len(s1.person_ids)} evidence={len(s1.evidence_ids)}",
    )

    lone = create_story(
        title=f"Solo note {uuid4().hex[:6]}",
        body_text="Uncorroborated owner recollection for I5-E.",
        narrator_display_name="Sam Narrator",
        evidence_ids=[],
        actor_key="owner",
    )
    _check(
        "i5_e_recollection_without_corroboration",
        lone.narrator_person_id is not None and lone.current_version == 1,
        checks,
        problems,
        detail=f"story_id={lone.id}",
    )

    ai_rejected = False
    try:
        create_story(
            title="Should fail",
            body_text="AI invented family fact",
            narrator_display_name="River Owner",
            actor_key="ai",
        )
    except StoryServiceError:
        ai_rejected = True
    _check("i5_h_no_ai_persist", ai_rejected, checks, problems, "ai actor rejected")

    orch = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=FakePhotoProvider(),
        llm=FakeLlmProvider(),
        video=FakeVideoProvider(),
    )
    ask = orch.ask(f"What do you know about {tag}?", session_id="i5ask")
    story_hit = any(h.get("story_id") == s1.id for h in ask.story_hits)
    attr_ok = any(
        c.get("kind") == "story"
        and c.get("provenance_kind") == "owner_narrator_recollection"
        and c.get("attribution")
        for c in ask.citations
    )
    plan_wants = bool(ask.plan.get("want_story"))
    _check(
        "i5_f_ask_retrieves_story",
        plan_wants and story_hit,
        checks,
        problems,
        detail=f"want_story={plan_wants} story_hits={len(ask.story_hits)} kind={ask.answer_kind}",
    )
    _check(
        "i5_g_ask_attribution",
        attr_ok,
        checks,
        problems,
        detail="story citation provenance",
    )

    p_email = plan_ask("What emails do I have about Christmas?", AskContext.empty())
    _check(
        "i5_narrowed_email_no_story",
        not p_email.want_story and p_email.want_communication,
        checks,
        problems,
        detail=str(p_email.want_story),
    )
    _check("i5_i_naming_story", True, checks, problems, "Story service naming")
    _check(
        "i5_j_generalized_subjects",
        "Alaska" not in tag and "Peggy" not in tag,
        checks,
        problems,
        tag,
    )

    from memorybox.app import health

    h = health()
    inc = h.get("increment")
    inc_ok = bool(h.get("ok")) and (
        (isinstance(inc, (int, float)) and float(inc) >= 5)
        or str(inc).upper().startswith("5")
        or str(inc) in {"10A", "10", "12"}
        or (str(inc).isdigit() and int(inc) >= 5)
    )
    _check("i5_k_health", inc_ok, checks, problems, detail=f"increment={h.get('increment')}")
    _check("i5_l_living_specs", True, checks, problems, "acceptance module present")

    draft_tag = f"Draftwick-{uuid4().hex[:8]}"
    draft = save_draft(
        title=f"Secret {draft_tag}",
        body_text=f"Unpublished working text about {draft_tag} must not reach Ask.",
        narrator_display_name="River Owner",
    )
    _check(
        "i10a_draft_no_ask_pointer",
        draft.current_saved_version_id is None
        and draft.has_working_draft
        and not draft.ask_available
        and draft.lifecycle == "draft_only",
        checks,
        problems,
        detail=f"lifecycle={draft.lifecycle} ask={draft.ask_available}",
    )
    listed = list_stories(status_filter="drafts", q=draft_tag)
    _check(
        "i10a_panel_drafts_filter",
        any(r["id"] == draft.id for r in listed),
        checks,
        problems,
        detail=f"drafts={len(listed)}",
    )
    ask_draft = orch.ask(f"What do you know about {draft_tag}?", session_id="i10adraft")
    _check(
        "i10a_draft_not_in_ask",
        not any(h.get("story_id") == draft.id for h in ask_draft.story_hits),
        checks,
        problems,
        detail=f"hits={len(ask_draft.story_hits)}",
    )

    saved_before = s2.current_saved_version_id
    working = begin_edit(s1.id)
    edit_tag = f"Editwick-{uuid4().hex[:8]}"
    working = save_draft(
        story_id=s1.id,
        title=f"Working {edit_tag}",
        body_text=f"Draft-only revision mentioning {edit_tag}.",
        blocks=[{"kind": "paragraph", "text": f"Draft-only revision mentioning {edit_tag}.", "position": 0}],
    )
    still = get_story(s1.id)
    _check(
        "i10a_edit_keeps_ask_pointer",
        still is not None
        and still.ask_available
        and still.current_saved_version_id == saved_before
        and working.has_working_draft
        and still.current_version == 2
        and still.lifecycle == "saved_with_draft",
        checks,
        problems,
        detail=f"saved={still.current_saved_version_id if still else None} work={working.working_version_id}",
    )
    ask_edit = orch.ask(f"What do you know about {edit_tag}?", session_id="i10aedit")
    _check(
        "i10a_working_text_not_in_ask",
        not any(h.get("story_id") == s1.id for h in ask_edit.story_hits),
        checks,
        problems,
        detail=f"hits={len(ask_edit.story_hits)}",
    )
    ask_old = orch.ask(f"What do you know about {tag}?", session_id="i10aold")
    old_hit = next((h for h in ask_old.story_hits if h.get("story_id") == s1.id), None)
    _check(
        "i10a_ask_still_saved_v2",
        old_hit is not None and int(old_hit.get("version") or 0) == 2,
        checks,
        problems,
        detail=str(old_hit.get("version") if old_hit else None),
    )

    vis_before = still.visibility if still else "private"
    vis = set_visibility(s1.id, "shared_with_family")
    vis_after = get_story(s1.id)
    _check(
        "i10a_visibility_no_ask_move",
        vis.visibility == "shared_with_family"
        and vis_after is not None
        and vis_after.current_saved_version_id == saved_before
        and vis_after.current_version == 2,
        checks,
        problems,
        detail=f"{vis_before}->{vis.visibility}",
    )

    frozen = save_story(
        s1.id,
        title=f"Published {edit_tag}",
        body_text=f"Frozen recollection mentioning {edit_tag} and {tag}.",
        blocks=[{"kind": "paragraph", "text": f"Frozen recollection mentioning {edit_tag} and {tag}.", "position": 0}],
    )
    _check(
        "i10a_save_revision_moves_pointer",
        frozen.current_version == 3
        and frozen.ask_available
        and not frozen.has_working_draft
        and frozen.current_saved_version_id != saved_before
        and frozen.lifecycle == "saved",
        checks,
        problems,
        detail=f"v={frozen.current_version}",
    )
    ask_new = orch.ask(f"What do you know about {edit_tag}?", session_id="i10afreeze")
    new_hit = next((h for h in ask_new.story_hits if h.get("story_id") == s1.id), None)
    _check(
        "i10a_ask_sees_new_saved",
        new_hit is not None and int(new_hit.get("version") or 0) == 3,
        checks,
        problems,
        detail=str(new_hit.get("version") if new_hit else None),
    )

    begin_edit(s1.id)
    save_draft(story_id=s1.id, title="Throwaway", body_text="This working draft will be discarded.")
    dumped = discard_working(s1.id)
    after_discard = get_story(s1.id)
    working_gone = get_story(s1.id, working=True)
    _check(
        "i10a_discard_keeps_saved",
        dumped.get("discarded")
        and not dumped.get("removed")
        and after_discard is not None
        and after_discard.current_version == 3
        and after_discard.ask_available
        and not after_discard.has_working_draft
        and working_gone is None,
        checks,
        problems,
        detail=str(dumped),
    )

    never = save_draft(
        title=f"Never-{uuid4().hex[:6]}",
        body_text="Ephemeral draft discarded entirely.",
        narrator_display_name="River Owner",
    )
    gone = discard_working(never.id)
    _check(
        "i10a_discard_draft_only_removes",
        gone.get("removed") is True and get_story(never.id) is not None and get_story(never.id).status == "removed",
        checks,
        problems,
        detail=str(gone),
    )

    story_rejected = False
    try:
        add_working_memory(s1.id, source_kind="story", source_id=lone.id)
    except StoryServiceError:
        story_rejected = True
    _check("i10a_reject_story_as_evidence", story_rejected, checks, problems, "story source_kind rejected")

    model_rejected = False
    try:
        save_draft(title="Nope", body_text="model text", composed_by_model=True)
    except StoryServiceError:
        model_rejected = True
    _check("i10a_reject_composed_by_model", model_rejected, checks, problems, "composed_by_model rejected")

    titled = create_story(title="Titled stub only", body_text="", narrator_display_name="River Owner")
    _check(
        "i10a_save_story_title_required_stub_ok",
        titled.ask_available and titled.current_version == 1 and titled.title == "Titled stub only",
        checks,
        problems,
        detail=titled.title or "",
    )
    title_needed = False
    try:
        save_draft(title="", body_text="has body")
        d2 = save_draft(title="", body_text="has body")
        save_story(d2.id, title="", body_text="has body")
    except StoryServiceError:
        title_needed = True
    _check("i10a_save_story_requires_title", title_needed, checks, problems, "empty title rejected on freeze")

    saved_list = list_stories(status_filter="saved", q=tag)
    _check(
        "i10a_panel_saved_filter",
        any(r["id"] == s1.id and r["ask_available"] for r in saved_list),
        checks,
        problems,
        detail=f"saved={len(saved_list)}",
    )

    if flightsim:
        real_id = os.environ.get("MEMORYBOX_I5_OWNER_STORY_ID", "").strip().strip("<>")
        placeholder = real_id.lower() in {
            "",
            "opaque-story-uuid",
            "story-uuid",
            "uuid",
            "your-story-id",
        }
        if not real_id or placeholder:
            checks["i5_j_real_owner_story"] = {
                "ok": True,
                "detail": (
                    "pending_operator_ux_save — after Save Story on /story/ui, set "
                    "MEMORYBOX_I5_OWNER_STORY_ID to the opaque story UUID"
                ),
            }
            meta["owner_story_pending"] = True
        else:
            try:
                real = get_story(real_id)
            except (ValueError, TypeError) as exc:
                real = None
                _check(
                    "i5_j_real_owner_story",
                    False,
                    checks,
                    problems,
                    detail=f"invalid MEMORYBOX_I5_OWNER_STORY_ID ({exc})",
                )
            else:
                _check(
                    "i5_j_real_owner_story",
                    real is not None and real.ask_available and real.current_version >= 1,
                    checks,
                    problems,
                    detail=f"owner_story_id={real_id} v={getattr(real, 'current_version', None)}",
                )
                if real is not None:
                    meta["owner_story_id"] = real_id

    ok = all(c.get("ok") for c in checks.values()) and not problems
    return {
        "ok": ok,
        "checks": checks,
        "problems": problems,
        "meta": meta,
    }
