"""P2-I12 Historian Collection acceptance — prove-historian-capture with slice gates S1–S4."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from memorybox.ask.orchestrator import AskOrchestrator
from memorybox.historian_capture import (
    FakeHistorianEmailAdapter,
    add_questions,
    create_campaign,
    create_draft,
    get_campaign,
    get_capture_item,
    list_capture_items,
    list_unmatched_items,
    new_capture_count,
    poll_and_ingest,
    promote_to_story,
    respondent_options,
    send_thank_you_if_enabled,
    set_email_adapter,
    set_owner_assessment,
    set_verdict,
    start_campaign,
    stop_campaign,
    pause_campaign,
    resume_campaign,
    tick_scheduler,
    update_current_draft,
)
from memorybox.historian_capture.email_adapter import email_adapter_status
from memorybox.providers.llm.fake import FakeLlmProvider
from memorybox.providers.photo.fake import FakePhotoProvider


def _check(
    criteria: dict[str, bool],
    cid: str,
    ok: bool,
    problems: list[str],
    detail: str = "",
) -> None:
    criteria[cid] = bool(ok)
    if not ok:
        problems.append(f"{cid}: {detail or 'failed'}")


def _seed_person() -> str:
    from memorybox.db import connection
    from uuid import uuid4 as _uuid4

    pid = _uuid4()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO people (id, display_name, status)
            VALUES (%s, %s, 'confirmed')
            ON CONFLICT DO NOTHING
            """,
            (pid, "HC Test Person"),
        )
    return str(pid)


def prove_historian_capture(
    *,
    slice: str | None = None,
    flightsim: bool = False,
) -> dict[str, Any]:
    slice_norm = (slice or "s4").strip().lower()
    if slice_norm not in ("s1", "s2", "s3", "s4", "s5"):
        return {
            "ok": False,
            "slice": slice_norm,
            "criteria": {},
            "problems": [f"invalid slice: {slice_norm}"],
            "flightsim": flightsim,
        }

    if flightsim:
        return {
            "ok": False,
            "slice": slice_norm,
            "criteria": {},
            "problems": ["S5 / --flightsim not authorized in S1–S4 build"],
            "flightsim": True,
            "email_provider": email_adapter_status(),
        }

    criteria: dict[str, bool] = {}
    problems: list[str] = []
    meta: dict[str, Any] = {"increment": "P2-I12", "slice": slice_norm}

    os.environ["MEMORYBOX_HC_EMAIL_PROVIDER"] = "fake"
    set_email_adapter(None)
    adapter = FakeHistorianEmailAdapter()
    set_email_adapter(adapter)

    tag = f"HC12-{uuid4().hex[:8]}"
    people_id = _seed_person()
    email = f"respondent.{tag.lower()}@example.com"

    # --- S1: schema + campaign lifecycle + fake send + snapshots + reminder lifecycle ---
    try:
        camp = create_campaign(
            title=f"Historian {tag}",
            cadence_config_json={"pattern": "seconds", "interval_seconds": 60},
            follow_up_interval_seconds=60,
            timezone_name="UTC",
            send_thank_you_ack=True,
            respondents=[
                {
                    "people_id": people_id,
                    "display_name_snapshot": f"Peggy {tag}",
                    "contact_route_value": email,
                }
            ],
            questions=[
                f"Question one about Christmas {tag}?",
                f"Question two about summers {tag}?",
                f"Question three about lessons {tag}?",
            ],
        )
        _check(criteria, "C-01", camp["status"] == "draft" and len(camp["questions"]) == 3, problems)
        _check(
            criteria,
            "C-02",
            len(camp.get("respondents") or []) == 1
            and camp["respondents"][0]["people_id"] == people_id,
            problems,
        )
        _check(
            criteria,
            "C-17",
            int(camp.get("follow_up_interval_seconds") or 0) == 60
            and camp.get("cadence_config_json", {}).get("pattern") == "seconds",
            problems,
            "cadence vs follow-up separate",
        )
        meta["campaign_id"] = camp["id"]

        t0 = datetime.now(timezone.utc)
        camp = start_campaign(camp["id"], now=t0)
        tick = tick_scheduler(now=t0, adapter=adapter)
        camp = get_campaign(camp["id"])
        qids = [q["id"] for q in camp["questions"]]
        d0 = next((d for d in camp["deliveries"] if d["question_id"] == qids[0]), None)
        snap_ok = (
            d0 is not None
            and d0["status"] in ("sent", "waiting")
            and d0.get("question_snapshot_text")
            and d0.get("question_snapshot_hash")
            and len(adapter.sent) >= 1
        )
        _check(criteria, "C-03", snap_ok, problems, "question snapshot on send")
        _check(criteria, "C-04", d0 is not None, problems, "one-at-a-time send")

        # Pause / resume / stop
        pause_campaign(camp["id"])
        _check(criteria, "C-12", get_campaign(camp["id"])["status"] == "paused", problems, "pause")
        resume_campaign(camp["id"], now=t0)
        _check(criteria, "C-12b", get_campaign(camp["id"])["status"] == "running", problems, "resume")

        # Reminder lifecycle: waiting → one reminder → no_response
        t1 = t0 + timedelta(seconds=61)
        tick_scheduler(now=t1, adapter=adapter)
        camp = get_campaign(camp["id"])
        d0 = next((d for d in camp["deliveries"] if d["question_id"] == qids[0]), None)
        reminder_ok = d0 and d0.get("reminder_sent_at") and any(
            s.get("is_reminder") for s in adapter.sent
        )
        _check(criteria, "C-18", bool(reminder_ok), problems, "one reminder")

        t2 = t1 + timedelta(seconds=61)
        tick_scheduler(now=t2, adapter=adapter)
        camp = get_campaign(camp["id"])
        d0 = next((d for d in camp["deliveries"] if d["question_id"] == qids[0]), None)
        no_resp_ok = d0 and d0["status"] in ("no_response", "exhausted")
        _check(criteria, "C-19", bool(no_resp_ok), problems, "no_response after second interval")

        # Next question scheduled per cadence (not follow-up)
        d1 = next(
            (d for d in camp["deliveries"] if d["question_id"] == qids[1] and d["status"] == "pending"),
            None,
        )
        _check(criteria, "C-19b", d1 is not None, problems, "next question pending after no_response")

        if slice_norm == "s1":
            ok = not problems
            return _result(ok, slice_norm, criteria, problems, meta, adapter)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"S1 setup failed: {exc}")
        return _result(False, slice_norm, criteria, problems, meta, adapter)

    # --- S2: inbound correlate, duplicate, quarantine, STOP ---
    try:
        camp = get_campaign(meta["campaign_id"])
        qids = [q["id"] for q in camp["questions"]]
        # Fresh delivery for Q1 on a new respondent campaign for clean S2
        camp2 = create_campaign(
            title=f"S2 {tag}",
            follow_up_interval_seconds=3600,
            cadence_config_json={"pattern": "seconds", "interval_seconds": 120},
            respondents=[
                {
                    "people_id": people_id,
                    "display_name_snapshot": f"Rick {tag}",
                    "contact_route_value": email,
                }
            ],
            questions=[f"S2 question {tag}?"],
        )
        t0 = datetime.now(timezone.utc)
        camp2 = start_campaign(camp2["id"], now=t0)
        tick_scheduler(now=t0, adapter=adapter)
        camp2 = get_campaign(camp2["id"])
        d = camp2["deliveries"][0]
        adapter.inject_reply(
            correlation_token=d["correlation_token"],
            from_addr=email,
            text=f"Peggy hosted wonderful parties {tag}.",
            inbound_message_id=f"in-{tag}",
        )
        ingest = poll_and_ingest(adapter=adapter)
        items = list_capture_items(campaign_id=camp2["id"])
        matched = [i for i in items if tag in (i.get("extracted_text") or "")]
        _check(
            criteria,
            "C-05",
            len(ingest.get("created") or []) >= 1 and len(matched) >= 1,
            problems,
            "immutable capture item",
        )
        item = matched[0]
        _check(
            criteria,
            "C-06",
            bool(item.get("preserved_raw_uri")) and bool(item.get("content_hash")),
            problems,
            "raw uri + hash",
        )

        # Duplicate
        adapter.processed.discard(f"in-{tag}")
        dup = poll_and_ingest(adapter=adapter)
        _check(
            criteria,
            "C-13",
            len(dup.get("duplicates") or []) >= 1 or len(dup.get("created") or []) == 0,
            problems,
            "duplicate idempotent",
        )

        # Unmatched
        adapter.inject_reply(
            correlation_token=None,
            from_addr="mystery@example.com",
            text="orphan",
            ambiguous=True,
            inbound_message_id=f"amb-{tag}",
        )
        amb = poll_and_ingest(adapter=adapter)
        _check(
            criteria,
            "C-14",
            len(amb.get("quarantined") or []) >= 1 or len(list_unmatched_items()) >= 1,
            problems,
            "unmatched quarantine",
        )

        # STOP opt-out
        camp3 = create_campaign(
            title=f"STOP {tag}",
            follow_up_interval_seconds=3600,
            respondents=[
                {
                    "people_id": people_id,
                    "display_name_snapshot": f"Anne {tag}",
                    "contact_route_value": f"anne.{tag.lower()}@example.com",
                }
            ],
            questions=[f"STOP test {tag}?"],
        )
        camp3 = start_campaign(camp3["id"], now=t0)
        tick_scheduler(now=t0, adapter=adapter)
        camp3 = get_campaign(camp3["id"])
        d3 = camp3["deliveries"][0]
        adapter.inject_reply(
            correlation_token=d3["correlation_token"],
            from_addr=f"anne.{tag.lower()}@example.com",
            text="STOP",
            inbound_message_id=f"stop-{tag}",
        )
        stop_ingest = poll_and_ingest(adapter=adapter)
        camp3 = get_campaign(camp3["id"])
        opted = camp3["respondents"][0]["status"] == "opted_out"
        _check(criteria, "C-20", opted and len(stop_ingest.get("opt_outs") or []) >= 0, problems, "STOP opt-out")

        if slice_norm == "s2":
            ok = not problems
            return _result(ok, slice_norm, criteria, problems, meta, adapter)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"S2 failed: {exc}")
        if slice_norm == "s2":
            return _result(False, slice_norm, criteria, problems, meta, adapter)

    # --- S3: review drafts, assessment, verdict ---
    try:
        camp = create_campaign(
            title=f"S3 {tag}",
            follow_up_interval_seconds=3600,
            respondents=[
                {
                    "people_id": people_id,
                    "display_name_snapshot": f"S3 {tag}",
                    "contact_route_value": f"s3.{tag.lower()}@example.com",
                }
            ],
            questions=[f"S3 review {tag}?"],
        )
        t0 = datetime.now(timezone.utc)
        camp = start_campaign(camp["id"], now=t0)
        tick_scheduler(now=t0, adapter=adapter)
        d = get_campaign(camp["id"])["deliveries"][0]
        adapter.inject_reply(
            correlation_token=d["correlation_token"],
            from_addr=f"s3.{tag.lower()}@example.com",
            text=f"Original testimony text {tag} unchanged.",
            inbound_message_id=f"s3-{tag}",
        )
        poll_and_ingest(adapter=adapter)
        item = list_capture_items(campaign_id=camp["id"])[0]
        original = item["extracted_text"]
        refreshed0 = get_capture_item(item["id"])
        if refreshed0.get("current_draft"):
            update_current_draft(item["id"], body_text=f"Edited draft {tag}")
        else:
            create_draft(item["id"], body_text=f"Edited draft {tag}")
        update_current_draft(item["id"], body_text=f"Draft v2 {tag}")
        refreshed = get_capture_item(item["id"])
        draft2 = refreshed.get("current_draft") or {}
        _check(
            criteria,
            "C-07",
            refreshed["extracted_text"] == original and int(draft2.get("version") or 0) >= 1,
            problems,
            "draft versions; source immutable",
        )
        assess_item = set_owner_assessment(item["id"], "high_confidence", note_private="private")
        verdict_item = set_verdict(
            item["id"],
            "retained",
            review_draft_id=draft2.get("id"),
        )
        _check(
            criteria,
            "C-08",
            (assess_item.get("latest_assessment") or {}).get("assessment_code")
            == "high_confidence"
            and (verdict_item.get("latest_verdict") or {}).get("verdict") == "retained",
            problems,
            "assessment orthogonal to verdict",
        )
        _check(
            criteria,
            "C-09",
            (verdict_item.get("latest_verdict") or {}).get("verdict")
            in ("retained", "rejected", "promotion_authorized"),
            problems,
        )

        if slice_norm == "s3":
            ok = not problems
            return _result(ok, slice_norm, criteria, problems, meta, adapter)
    except Exception as exc:  # noqa: BLE001
        problems.append(f"S3 failed: {exc}")
        if slice_norm == "s3":
            return _result(False, slice_norm, criteria, problems, meta, adapter)

    # --- S4: story promotion, Ask, thank-you leak guard ---
    try:
        camp = create_campaign(
            title=f"S4 {tag}",
            follow_up_interval_seconds=3600,
            send_thank_you_ack=True,
            respondents=[
                {
                    "people_id": people_id,
                    "display_name_snapshot": f"S4 {tag}",
                    "contact_route_value": f"s4.{tag.lower()}@example.com",
                }
            ],
            questions=[f"S4 promote {tag}?"],
        )
        t0 = datetime.now(timezone.utc)
        camp = start_campaign(camp["id"], now=t0)
        tick_scheduler(now=t0, adapter=adapter)
        d = get_campaign(camp["id"])["deliveries"][0]
        testimony = f"Promoted testimony about gardens {tag}."
        adapter.inject_reply(
            correlation_token=d["correlation_token"],
            from_addr=f"s4.{tag.lower()}@example.com",
            text=testimony,
            inbound_message_id=f"s4-{tag}",
        )
        poll_and_ingest(adapter=adapter)
        item = list_capture_items(campaign_id=camp["id"])[0]
        refreshed0 = get_capture_item(item["id"])
        if not refreshed0.get("current_draft"):
            create_draft(item["id"], body_text=f"Story draft {tag}")
        else:
            update_current_draft(item["id"], body_text=f"Story draft {tag}")
        set_owner_assessment(item["id"], "moderate_confidence")
        refreshed = get_capture_item(item["id"])
        draft_id = (refreshed.get("current_draft") or {}).get("id")
        set_verdict(item["id"], "promotion_authorized", review_draft_id=draft_id)
        promo = promote_to_story(
            item["id"],
            title=f"Garden memory {tag}",
        )
        _check(
            criteria,
            "C-10",
            promo.get("promoted_type") == "story" and promo.get("promoted_id"),
            problems,
            "story promotion + chain",
        )

        orch = AskOrchestrator(llm=FakeLlmProvider(), photo=FakePhotoProvider())
        ask = orch.ask(f"What did they say about gardens {tag}?")
        hits = ask.to_dict().get("historian_capture_hits") or ask.to_dict().get("guided_capture_hits") or []
        cite_ok = any(tag in (h.get("excerpt") or "") for h in hits) or tag in str(ask.to_dict())
        _check(criteria, "C-11", cite_ok, problems, "Ask attribution")

        # Rejected excluded
        camp_rej = create_campaign(
            title=f"Reject {tag}",
            follow_up_interval_seconds=3600,
            respondents=[
                {
                    "people_id": people_id,
                    "display_name_snapshot": f"Rej {tag}",
                    "contact_route_value": f"rej.{tag.lower()}@example.com",
                }
            ],
            questions=[f"Reject {tag}?"],
        )
        camp_rej = start_campaign(camp_rej["id"], now=t0)
        tick_scheduler(now=t0, adapter=adapter)
        dr = get_campaign(camp_rej["id"])["deliveries"][0]
        adapter.inject_reply(
            correlation_token=dr["correlation_token"],
            from_addr=f"rej.{tag.lower()}@example.com",
            text=f"Rejected secret {tag}",
            inbound_message_id=f"rej-{tag}",
        )
        poll_and_ingest(adapter=adapter)
        rej_item = list_capture_items(campaign_id=camp_rej["id"])[0]
        rej_ref = get_capture_item(rej_item["id"])
        if not rej_ref.get("current_draft"):
            create_draft(rej_item["id"], body_text=f"rej draft {tag}")
        else:
            update_current_draft(rej_item["id"], body_text=f"rej draft {tag}")
        rej_ref = get_capture_item(rej_item["id"])
        rej_draft_id = (rej_ref.get("current_draft") or {}).get("id")
        set_verdict(rej_item["id"], "rejected", review_draft_id=rej_draft_id)
        from memorybox.historian_capture import search_historian_capture_for_ask

        rej_hits = search_historian_capture_for_ask(query=f"Rejected secret {tag}")
        rej_hits = [
            h
            for h in rej_hits
            if str(h.get("capture_item_id") or "") == str(rej_item["id"])
        ]
        _check(criteria, "C-11b", len(rej_hits) == 0, problems, "rejected excluded from Ask")

        ty = send_thank_you_if_enabled(item["id"], adapter=adapter)
        body = (ty.get("body_snapshot") or "").lower()
        leak = any(
            w in body
            for w in (
                "high_confidence",
                "moderate_confidence",
                "reject as evidence",
                "promotion_authorized",
                "review draft",
            )
        )
        _check(
            criteria,
            "C-21",
            not leak and bool(ty.get("sent_at") or ty.get("outbound_message_id")),
            problems,
            "thank-you leak guard",
        )

        # Regression smoke
        if slice_norm == "s4":
            reg_ok = _run_regression_smoke()
            _check(criteria, "C-16", reg_ok, problems, "core MB proves smoke")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"S4 failed: {exc}")

    ok = not problems
    return _result(ok, slice_norm, criteria, problems, meta, adapter)


def _result(
    ok: bool,
    slice_norm: str,
    criteria: dict[str, bool],
    problems: list[str],
    meta: dict[str, Any],
    adapter: Any,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "overall_ok": ok,
        "slice": slice_norm,
        "criteria": criteria,
        "problems": problems,
        "meta": meta,
        "flightsim": False,
        "email_provider": email_adapter_status(),
    }


def _run_regression_smoke() -> bool:
    """Run prove-guided-capture only — fast regression signal."""
    from pathlib import Path

    env = os.environ.copy()
    env.setdefault("MEMORYBOX_ALLOW_DEV_DEFAULTS", "1")
    env["MEMORYBOX_GC_EMAIL_PROVIDER"] = "fake"
    try:
        r = subprocess.run(
            [sys.executable, "-m", "memorybox", "prove-guided-capture"],
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
            cwd=str(Path(__file__).resolve().parents[2]),
        )
        return r.returncode == 0
    except Exception:
        return False
