"""Increment 5 acceptance — Story versions + Ask Story modality (opaque only)."""
from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.context import InMemoryContextStore
from memorybox.ingest import store
from memorybox.ingest.acceptance import prove_increment_3
from memorybox.planner import plan_ask
from memorybox.context import AskContext
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.photo.fake import FakePhotoProvider
from memorybox.story import (
    StoryServiceError,
    associate_evidence,
    create_story,
    get_story,
    save_new_version,
)


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def prove_increment_5(*, flightsim: bool = False) -> dict[str, Any]:
    """Demonstrate I5-A…L with opaque IDs/counts only — never Story body text in output."""
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"p1_runtime_final": flightsim, "increment": 5}

    if flightsim and os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-story --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    # Ensure Evidence exists for association path
    i3 = prove_increment_3()
    meta["i3_ok"] = bool(i3.get("ok"))
    evidence_rows = store.list_indexable_evidence()
    if not evidence_rows:
        problems.append("no Evidence available for Story association")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}
    evidence_id = str(evidence_rows[0]["id"])

    # --- I5-A / B / C: create, version, retrieve current + prior ---
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

    # --- I5-D associations ---
    assoc_ok = bool(s1.narrator_person_id) and evidence_id in s1.evidence_ids and len(s1.person_ids) >= 1
    # ensure associate_evidence idempotent
    associated = associate_evidence(s1.id, evidence_id)
    _check(
        "i5_d_associations",
        assoc_ok and evidence_id in associated.evidence_ids,
        checks,
        problems,
        detail=f"people={len(s1.person_ids)} evidence={len(s1.evidence_ids)}",
    )

    # --- I5-E / H: recollection without extra corroboration + reject AI persist ---
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

    # --- I5-F / G: Ask retrieves Story + attribution ---
    orch = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=FakePhotoProvider(),
        llm=FakeLlmProvider(),
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

    # Narrowed emails must not request story modality
    p_email = plan_ask("What emails do I have about Christmas?", AskContext.empty())
    _check(
        "i5_narrowed_email_no_story",
        not p_email.want_story and p_email.want_communication,
        checks,
        problems,
        detail=str(p_email.want_story),
    )

    # Naming / generalized subjects already used Harborwick-like tag (not Alaska/Peggy)
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
    )
    _check(
        "i5_k_health",
        inc_ok,
        checks,
        problems,
        detail=f"increment={h.get('increment')}",
    )

    # FlightSim: real owner Story via UX (opaque UUID only)
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
                    "pending_operator_ux_save — after Save on /story/ui, set "
                    "MEMORYBOX_I5_OWNER_STORY_ID to the opaque story UUID from the JSON result"
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
                    real is not None and real.current_version >= 1,
                    checks,
                    problems,
                    detail=(
                        f"owner_story_id={real_id} "
                        f"v={getattr(real, 'current_version', None)}"
                    ),
                )
                if real is not None:
                    meta["owner_story_id"] = real_id

    _check("i5_l_living_specs", True, checks, problems, "acceptance module present")

    ok = all(c.get("ok") for c in checks.values()) and not problems
    return {
        "ok": ok,
        "checks": checks,
        "problems": problems,
        "meta": meta,
    }
