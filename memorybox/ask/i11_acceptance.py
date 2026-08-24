"""P2-I11 Narrative & Summaries — Ask output_mode tell on existing curator."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from memorybox.ask.narrative import memories_from_citations, persistable_view, synthesize_tell
from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.context import AskContext, InMemoryContextStore
from memorybox.explore.find import curator_answer_text
from memorybox.planner import compile_output_mode, plan_ask
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.photo.fake import FakePhotoProvider


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def run_prove_i11(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I11", "p1_runtime_final": flightsim}

    if flightsim and os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-i11 --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    from memorybox.migrate import migrate

    meta["migrations_applied"] = migrate()

    root = Path(__file__).resolve().parents[1]
    explore_html = (root / "explore" / "static" / "explore.html").read_text(encoding="utf-8")
    app_py = (root / "app.py").read_text(encoding="utf-8")
    explore_js = (root / "explore" / "static" / "explore.js").read_text(encoding="utf-8")
    _check(
        "c05_c10_no_narration_screen",
        "/narration" not in app_py
        and 'id="mb-explore-copy"' in explore_html
        and 'id="mb-explore-save-story"' in explore_html
        and "Save as Story" in explore_html
        and "/story/drafts" in explore_js
        and "composed_by_model: true" in explore_js,
        checks,
        problems,
        detail="Copy/Save as Story on Explore; no narration route",
    )

    ctx = AskContext(session_id="i11-prove")
    tell_plan = plan_ask("Tell me about Peggy", ctx)
    know_plan = plan_ask("what do you know about Peggy", ctx)
    show_plan = plan_ask("Show me Peggy", ctx)
    said_plan = plan_ask("what did Peggy say", ctx)
    have_plan = plan_ask("what do I have about Peggy", ctx)
    _check(
        "c01_tell_compiles",
        tell_plan.output_mode == "tell"
        and know_plan.output_mode == "tell"
        and compile_output_mode("Summarize our Alaska trip") == "tell"
        and tell_plan.act == "find"
        and tell_plan.gallery_show_sms is not True,
        checks,
        problems,
        detail=f"tell={tell_plan.output_mode} act={tell_plan.act} sms_gallery={tell_plan.gallery_show_sms}",
    )
    _check(
        "c02_show_not_essay",
        show_plan.output_mode == "show"
        and have_plan.output_mode == "show"
        and said_plan.output_mode == "show",
        checks,
        problems,
        detail=f"show={show_plan.output_mode} have={have_plan.output_mode} said={said_plan.output_mode}",
    )
    _check(
        "c09_said_about_not_tell",
        said_plan.output_mode == "show"
        and not said_plan.want_story
        and said_plan.want_communication,
        checks,
        problems,
        detail=f"story={said_plan.want_story} comms={said_plan.want_communication}",
    )

    tell_pack = curator_answer_text(
        {
            "answer_kind": "mixed",
            "answer_text": "Owner journal: harbor walk. Communications: packing list email.",
            "plan": {"output_mode": "tell"},
        }
    )
    show_pack = curator_answer_text(
        {
            "answer_kind": "photo_backed",
            "answer_text": "Found 12 photo hit(s).",
            "plan": {"output_mode": "show"},
        }
    )
    _check(
        "c04_tell_passes_answer_text",
        tell_pack is not None
        and "harbor walk" in tell_pack
        and show_pack is None,
        checks,
        problems,
        detail=f"tell={tell_pack!r} show={show_pack!r}",
    )

    tag = f"I11-{uuid4().hex[:8]}"
    from memorybox.journal.i10c import save_draft as save_journal_draft, save_journal

    draft_j = save_journal_draft(
        title="",
        body_text=f"Owner journal about {tag} harbor walk with a hidden-comms check phrase.",
        described_start_date=date.today(),
        described_precision="day",
        actor_key="owner",
    )
    saved = save_journal(
        draft_j["id"],
        title="",
        body_text=f"Owner journal about {tag} harbor walk with a hidden-comms check phrase.",
        described_start_date=date.today(),
        described_precision="day",
        actor_key="owner",
    )
    meta["synthetic_journal_id"] = saved.get("id")
    orch = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=FakePhotoProvider(),
        llm=FakeLlmProvider(),
    )
    told = orch.ask(f"Tell me about {tag} harbor")
    journal_in_tell = tag.lower() in (told.answer_text or "").lower() or any(
        tag.lower() in str((s.get("text") or "")).lower()
        for s in (told.statements or [])
    )
    _check(
        "c03_tell_uses_journal_pack",
        (told.plan or {}).get("output_mode") == "tell"
        and "evidence-backed account" in (told.answer_text or "")
        and journal_in_tell
        and saved.get("ask_available"),
        checks,
        problems,
        detail=(told.answer_text or "")[:240],
    )
    shown = orch.ask("Show me Peggy")
    show_text = shown.answer_text or ""
    _check(
        "c02_show_answer_is_result_set",
        (shown.plan or {}).get("output_mode") == "show"
        and "evidence-backed account" not in show_text.lower()
        and "not family truth until you Save Story" not in show_text,
        checks,
        problems,
        detail=show_text[:200],
    )

    hidden_sms = {
        "answer_kind": "mixed",
        "answer_text": "Communications in the archive: packing list for Alaska.",
        "plan": {"output_mode": "tell"},
        "citations": [{"kind": "evidence", "evidence_id": "e1", "source": "sms_export", "summary": "packing list"}],
    }
    _check(
        "c03_hidden_comms_in_tell_prose",
        "packing list" in (curator_answer_text(hidden_sms) or ""),
        checks,
        problems,
        detail=str(curator_answer_text(hidden_sms)),
    )

    stitched = synthesize_tell(
        tell_plan,
        [{"text": "SMS: see you in Alaska", "label": "Fact", "evidence_ids": ["e1"], "provenance_kind": "archive_evidence"}],
        [{"kind": "evidence", "evidence_id": "e1", "source": "sms_export"}],
    )
    _check(
        "c03_stitch_includes_hidden_style_comms",
        "Alaska" in stitched and "not family truth" in stitched.lower(),
        checks,
        problems,
        detail=stitched[:180],
    )

    view = persistable_view(
        original_ask="Tell me about Peggy",
        plan=tell_plan.to_dict(),
        presentation={"gallery_show_sms": False},
    )
    _check(
        "c08_living_view_json",
        view.get("schema_version") == 1
        and view.get("output_mode") == "tell"
        and view.get("original_ask") == "Tell me about Peggy"
        and isinstance(view.get("plan"), dict)
        and view.get("presentation", {}).get("gallery_show_sms") is False,
        checks,
        problems,
        detail=str(sorted(view.keys())),
    )

    mems = memories_from_citations(
        [{"kind": "journal", "journal_id": saved.get("id"), "title": "j"}]
    )
    _check(
        "c07_memories_from_citations",
        mems and mems[0]["source_kind"] == "journal" and mems[0]["source_id"] == saved.get("id"),
        checks,
        problems,
        detail=str(mems),
    )

    from memorybox.story import StoryServiceError, get_story, save_draft, save_story

    draft = save_draft(
        title=f"I11 {tag}",
        body_text=told.answer_text or "proposed",
        composed_by_model=True,
    )
    freeze_rejected = False
    try:
        save_story(
            draft.id,
            title=f"I11 {tag}",
            body_text="proposed",
            composed_by_model=True,
        )
    except StoryServiceError:
        freeze_rejected = True
    again = get_story(draft.id)
    _check(
        "c06_c07_copy_noop_save_as_story_draft",
        (not draft.ask_available)
        and freeze_rejected
        and again is not None
        and not again.ask_available,
        checks,
        problems,
        detail=f"ask_available={draft.ask_available} freeze_rejected={freeze_rejected}",
    )

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}
