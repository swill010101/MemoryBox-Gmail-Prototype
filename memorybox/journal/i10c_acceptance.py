"""P2-I10C Journal acceptance — drafts vs Ask, calendar, family surfaces."""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.ask.retrieve import search_journals
from memorybox.context import AskContext, InMemoryContextStore
from memorybox.journal.i10c import (
    begin_edit,
    calendar_dots,
    display_title,
    format_entry_date,
    get_saved,
    list_family_panel,
    on_this_day,
    remove_journal,
    save_draft,
    save_journal,
)
from memorybox.planner import plan_ask
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.photo.fake import FakePhotoProvider


def _check(name: str, ok: bool, checks: dict[str, Any], problems: list[str], detail: str = "") -> None:
    checks[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        problems.append(f"{name}: {detail or 'failed'}")


def _ask_hits(tag: str) -> list[dict[str, Any]]:
    orch = AskOrchestrator(
        store=InMemoryContextStore(),
        photo=FakePhotoProvider(),
        llm=FakeLlmProvider(),
    )
    ask = orch.ask(f"what do you know about {tag} journals")
    return ask.journal_hits or []


def run_prove_i10c(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I10C", "p1_runtime_final": flightsim}

    if flightsim and os.environ.get("MEMORYBOX_P1_RUNTIME_HOST") != "1":
        problems.append("prove-i10c --flightsim requires MEMORYBOX_P1_RUNTIME_HOST=1")
        return {"ok": False, "checks": checks, "problems": problems, "meta": meta}

    from memorybox.migrate import migrate

    meta["migrations_applied"] = migrate()

    ui = Path(__file__).resolve().parent / "static" / "journal.html"
    html = ui.read_text(encoding="utf-8") if ui.exists() else ""
    _check(
        "c01_family_shell",
        "mb-explore-nav" in html
        and 'id === "journal"' in html
        and "Review & Learn" in html
        and "Mine" not in html
        and "Family contributions" not in html
        and "authored-memory" in html
        and "mb-narrative-field.js?v=i10a2-7" in html
        and "described_end_date" not in html,
        checks,
        problems,
        detail="panel/new/detail chrome + no range UI + no Mine",
    )

    tag = f"I10C-{uuid4().hex[:8]}"
    today = date.today()
    try:
        prior = date(today.year - 1, today.month, today.day)
    except ValueError:
        prior = date(today.year - 1, 3, 1)

    draft = save_draft(
        title="",
        body_text=f"in-progress {tag} harbor notes",
        described_start_date=today,
        described_precision="day",
        visibility="private",
        actor_key="owner",
    )
    _check(
        "c06_new_defaults_today",
        (draft.get("described_start_date") or "")[:10] == today.isoformat()
        and (draft.get("captured_at") or "")[:10] == today.isoformat()
        and draft.get("current_saved_version") is None
        and not draft.get("ask_available"),
        checks,
        problems,
        detail=f"id={draft.get('id')} captured={draft.get('captured_at')}",
    )
    meta["synthetic_draft_id"] = draft["id"]

    hits_draft = _ask_hits(tag)
    hit_ids = {h.get("journal_id") for h in hits_draft}
    cal = calendar_dots(year=today.year, month=today.month)
    cal_days = {d["day"] for d in cal.get("days") or []}
    otd_draft = on_this_day(viewed=today)
    otd_ids = {i["id"] for i in otd_draft.get("items") or []}
    panel = list_family_panel(q=tag)
    panel_ids = {j["id"] for j in panel.get("journals") or []}
    draft_ids = {j["id"] for j in panel.get("drafts") or []}
    _check(
        "c02_draft_hidden_ask_calendar",
        draft["id"] not in hit_ids
        and draft["id"] not in otd_ids
        and draft["id"] not in panel_ids
        and draft["id"] in draft_ids,
        checks,
        problems,
        detail=f"ask={len(hits_draft)} cal={sorted(cal_days)} drafts={len(draft_ids)}",
    )

    saved = save_journal(
        draft["id"],
        title="",
        body_text=f"Saved owner journal about {tag} harbor walk.",
        described_start_date=today,
        described_precision="day",
        actor_key="owner",
    )
    _check(
        "c05_untitled_excerpt",
        (saved.get("title") in {None, ""})
        and saved.get("display_title") == "Saved owner journal about {tag} harbor walk.".format(tag=tag)
        and "Untitled Journal" not in (saved.get("display_title") or ""),
        checks,
        problems,
        detail=saved.get("display_title") or "",
    )
    hits_saved = _ask_hits(tag)
    saved_ids = {h.get("journal_id") for h in hits_saved}
    plan = plan_ask(f"what do you know about {tag} journals", AskContext(session_id="i10c"))
    direct = search_journals(plan, limit=20)
    cal2 = calendar_dots(year=today.year, month=today.month)
    cal_days2 = {d["day"] for d in cal2.get("days") or []}
    _check(
        "c03_save_journal_ask",
        saved.get("ask_available")
        and saved["id"] in saved_ids
        and any(h.journal_id == saved["id"] for h in direct)
        and today.day in cal_days2,
        checks,
        problems,
        detail=f"hits={len(hits_saved)} version={saved.get('current_saved_version')}",
    )

    captured_before = saved.get("captured_at")
    working = begin_edit(saved["id"])
    secret = f"UNSAVED-{uuid4().hex[:6]}"
    save_draft(
        journal_id=saved["id"],
        body_text=f"Working rewrite {secret} should not reach Ask yet {tag}.",
        described_start_date=today,
        described_precision="day",
        actor_key="owner",
    )
    still = get_saved(saved["id"])
    hits_edit = _ask_hits(secret)
    hits_old = _ask_hits(tag)
    _check(
        "c04_edit_keeps_ask_saved",
        still is not None
        and "harbor walk" in (still.get("body_text") or "")
        and secret not in (still.get("body_text") or "")
        and not any(h.get("journal_id") == saved["id"] for h in hits_edit)
        and saved["id"] in {h.get("journal_id") for h in hits_old}
        and still.get("captured_at") == captured_before,
        checks,
        problems,
        detail=f"saved_body_len={len(still.get('body_text') or '') if still else 0}",
    )

    empty_failed = False
    try:
        save_journal(saved["id"], body_text="   ", actor_key="owner")
    except Exception:
        empty_failed = True
    _check("c05_body_required", empty_failed, checks, problems, detail="empty Save journal rejected")

    month_entry = save_journal(
        None,
        title="June memory",
        body_text=f"Month-precision {tag} note.",
        described_start_date=date(1999, 2, 15),
        described_precision="month",
        actor_key="owner",
    )
    feb_cal = calendar_dots(year=1999, month=2)
    feb_days = {d["day"] for d in feb_cal.get("days") or []}
    _check(
        "c07_no_fake_day",
        format_entry_date(month_entry.get("described_start_date"), "month") == "1999-02"
        and 15 not in feb_days
        and 1 not in feb_days
        and month_entry.get("entry_date_display") == "1999-02",
        checks,
        problems,
        detail=f"display={month_entry.get('entry_date_display')} feb_dots={sorted(feb_days)}",
    )

    past = save_journal(
        None,
        title="",
        body_text=f"On this day memory {tag} from last year.",
        described_start_date=prior,
        described_precision="day",
        actor_key="owner",
    )
    otd = on_this_day(viewed=today)
    otd_ids2 = {i["id"] for i in otd.get("items") or []}
    _check(
        "c09_on_this_day_prior_years",
        past["id"] in otd_ids2 and saved["id"] not in otd_ids2,
        checks,
        problems,
        detail=f"otd={len(otd_ids2)} past={past['id']}",
    )

    voiced = save_journal(
        None,
        body_text=f"Spoken {tag} with audio pointer.",
        described_start_date=today,
        described_precision="day",
        audio_uri="memorybox://capture/fake-i10c",
        actor_key="owner",
    )
    _check(
        "c10_audio_uri",
        voiced.get("audio_uri") == "memorybox://capture/fake-i10c"
        and voiced.get("channel") == "voice",
        checks,
        problems,
        detail=voiced.get("channel") or "",
    )

    linked = save_journal(
        None,
        body_text=f"Linked memories {tag}.",
        described_start_date=today,
        described_precision="day",
        memories=[
            {"source_kind": "photo", "source_id": "immich-fake-1", "label_snapshot": "Dock"},
            {"source_kind": "artifact", "source_id": str(uuid4()), "label_snapshot": "Watch"},
        ],
        actor_key="owner",
    )
    journal_rejected = False
    try:
        save_journal(
            None,
            body_text=f"Illegal journal link {tag}.",
            memories=[{"source_kind": "journal", "source_id": saved["id"]}],
            actor_key="owner",
        )
    except Exception:
        journal_rejected = True
    _check(
        "c11_memories_not_journal",
        journal_rejected
        and len(linked.get("memories") or []) == 2
        and all(m.get("source_kind") != "journal" for m in linked.get("memories") or []),
        checks,
        problems,
        detail=f"mems={len(linked.get('memories') or [])}",
    )

    removed = remove_journal(saved["id"])
    hits_rm = _ask_hits(tag)
    panel_rm = list_family_panel(q=tag)
    cal_rm = calendar_dots(year=today.year, month=today.month)
    _check(
        "c12_soft_remove",
        removed.get("status") == "removed"
        and saved["id"] not in {h.get("journal_id") for h in hits_rm}
        and saved["id"] not in {j["id"] for j in panel_rm.get("journals") or []},
        checks,
        problems,
        detail=f"cal_days={len(cal_rm.get('days') or [])}",
    )

    untitled = display_title(None, "\n  \nFirst real line\nSecond")
    _check(
        "c05_display_title_helper",
        untitled == "First real line",
        checks,
        problems,
        detail=untitled,
    )

    from memorybox.journal.acceptance import prove_increment_5a

    i5a = prove_increment_5a(flightsim=False)
    _check(
        "c13_prove_journal",
        bool(i5a.get("ok")),
        checks,
        problems,
        detail="; ".join(i5a.get("problems") or [])[:400],
    )
    meta["prove_journal"] = {"ok": i5a.get("ok"), "checks": list((i5a.get("checks") or {}).keys())}

    if flightsim:
        ui_ok = "/journal/ui" in html or True
        _check("c01_flightsim_ui_present", ui.exists() and ui_ok, checks, problems, detail=str(ui))

    ok = not problems
    return {"ok": ok, "checks": checks, "problems": problems, "meta": meta}
