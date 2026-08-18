"""P2-I8 Richer Email — structural + fixture logic acceptance."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from memorybox.explore.p2_i4_acceptance import _check
from memorybox.providers.email_read.i8_fixture import write_i8_fixture
from memorybox.providers.email_read.mbox_parse import PARSER_VERSION, inspect_mbox


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("payload_json")
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw or {})


def _structural(checks: dict[str, Any], problems: list[str]) -> None:
    root = Path(__file__).resolve().parents[1]
    parse = (root / "providers" / "email_read" / "mbox_parse.py").read_text(encoding="utf-8")
    sources_paths = (root / "ingest" / "sources_paths.py").read_text(encoding="utf-8")
    dto = (root / "providers" / "email_read" / "dto.py").read_text(encoding="utf-8")
    comms = (root / "ingest" / "comms_email.py").read_text(encoding="utf-8")
    retrieve = (root / "ask" / "retrieve.py").read_text(encoding="utf-8")
    find_py = (root / "explore" / "find.py").read_text(encoding="utf-8")
    explore_js = (root / "explore" / "static" / "explore.js").read_text(encoding="utf-8")
    summary = (root / "status" / "summary.py").read_text(encoding="utf-8")
    main = (root / "__main__.py").read_text(encoding="utf-8")
    app_py = (root / "app.py").read_text(encoding="utf-8")
    phone = (root / "person" / "phone_map.py").read_text(encoding="utf-8")
    attach = (root / "explore" / "email_attach.py").read_text(encoding="utf-8")
    orch = (root / "ask" / "orchestrator.py").read_text(encoding="utf-8")
    i85 = (root / "ingest" / "comms_email.py").read_text(encoding="utf-8")

    _check(
        "i8_inspect_mbox_cli",
        '"inspect-mbox"' in main
        and "inspect_mbox" in parse
        and "bodies are not stored" in parse,
        checks,
        problems,
        "inspect-mbox exists; bodies not committed in inventory",
    )
    _check(
        "i8_parser_attachments_threads",
        "i8-email-1" in PARSER_VERSION
        and "EmailPartDto" in dto
        and "thread_status" in dto
        and "vendor_thread_id" in parse
        and "unthreaded" in parse
        and "extract_attachments" in parse,
        checks,
        problems,
        "I8 parser: MIME parts + RFC/vendor thread fields",
    )
    _check(
        "i8_identity_ladder",
        "resolve_handles" in comms
        and "auto_mapped" in phone
        and "display_name" in comms
        and "Never merge" not in comms,
        checks,
        problems,
        "I7 identity ladder reused for email addresses",
    )
    _check(
        "i8_attachments_not_artifacts",
        "is_artifact" in comms
        and "promoted_to_immich" in comms
        and "automatic_artifact" in attach
        and "Never writes Immich" in attach
        and "email-attachment" in app_py
        and "email-attachment" in explore_js,
        checks,
        problems,
        "Attachment bytes on the message; explicit Artifact copy only",
    )
    _check(
        "i8_gallery_emails_visible",
        "gallery_default_hidden" in find_py
        and "_is_sms_type" in find_py
        and 'type_ = "sms"' in find_py
        and "includeTexts" in explore_js,
        checks,
        problems,
        "SMS default-hide remains SMS-only; emails stay visible",
    )
    _check(
        "i8_ask_email_path",
        "search_email_messages" in retrieve
        and "_email_ask" in retrieve
        and "skipped_for_email_ask" in orch
        and "EMAIL_ASK_RE" in retrieve,
        checks,
        problems,
        "Ask retrieve uses email path (not SMS padding)",
    )
    _check(
        "i8_archive_health",
        "_email_ingested_metric" in summary
        and "Missing source is not zero messages." in summary
        and "Email ingest" in summary,
        checks,
        problems,
        "Archive Health staged vs ingested vs unavailable",
    )
    _check(
        "i8_cli",
        '"ingest-email"' in main
        and '"inspect-mbox"' in main
        and '"prove-p2-i8"' in main
        and "include-spam-trash" in main,
        checks,
        problems,
        "CLI ingest/inspect/prove-p2-i8",
    )
    _check(
        "i8_sources_on_p_drive",
        r"P:\photos\memorybox\sources" in sources_paths
        and "all mail including spam and trash-002.mbox" in sources_paths
        and "email_source_candidates" in sources_paths
        and "email_source_candidates" in parse
        and "mailbox_skip_reason" in parse
        and "skip_spam_trash" in (root / "providers" / "email_read" / "mbox.py").read_text(
            encoding="utf-8"
        ),
        checks,
        problems,
        "Default inspect/ingest uses P:\\photos\\memorybox\\sources and skips Spam/Trash labels",
    )
    _check(
        "i8_no_i85_i9_i10_i11",
        "face evidence" not in i85.lower()
        and "alaska trip narrative" not in comms.lower()
        and "infer_place" not in comms
        and "spoken" not in comms.lower()
        and "stt" not in comms.lower(),
        checks,
        problems,
        "I8.5 / I9 / I10 / I11 not implemented in email ingest",
    )
    _check(
        "i8_i7a_no_untraced_model",
        "openai" not in comms.lower() and "chat.completions" not in comms,
        checks,
        problems,
        "Email ingest is deterministic; no untraced model interpretation",
    )


def _logic(checks: dict[str, Any], problems: list[str]) -> None:
    from memorybox.ask.retrieve import search_email_messages
    from memorybox.context import AskContext
    from memorybox.explore.email_attach import load_email_attachment
    from memorybox.explore.find import explicit_text_gallery, items_from_ask_result
    from memorybox.ingest import store as store
    from memorybox.ingest.comms_email import ingest_mbox
    from memorybox.person import resolve_person_by_name
    from memorybox.planner import plan_ask
    from memorybox.planner.temporal import parse_temporal
    from memorybox.profile.facts import add_contact
    from memorybox.status.summary import _email_ingested_metric

    token = uuid4().hex[:6]
    owner_addr = f"tom.{token}@memorybox.test"
    peggy_addr = f"peggy.{token}@memorybox.test"
    sue_addr = f"sue.{token}@memorybox.test"
    shared_addr = f"shared.{token}@memorybox.test"
    bot_addr = f"bot.{token}@memorybox.test"
    fixture = Path(os.environ.get("TMPDIR") or "/tmp") / f"i8-richer-email-{token}.mbox"
    write_i8_fixture(
        fixture,
        owner=owner_addr,
        peggy=peggy_addr,
        sister=sue_addr,
        shared=shared_addr,
        bot=bot_addr,
    )
    before = fixture.read_bytes()
    inv = inspect_mbox(fixture)
    after_inspect = fixture.read_bytes()
    _check(
        "i8_inspect_real_fixture_format",
        inv.get("ok")
        and inv.get("format") == "mbox"
        and inv.get("original_untouched")
        and before == after_inspect
        and int(inv.get("message_count") or 0) >= 10
        and int(inv.get("labeled_spam") or 0) >= 1
        and int(inv.get("labeled_trash") or 0) >= 1
        and peggy_addr.split("@")[0] in " ".join(inv.get("from_sample") or []).lower()
        and not any("See the snapshot" in str(x) for x in (inv.get("from_sample") or [])),
        checks,
        problems,
        "Q1 inspect records actual fixture format/people samples; no bodies",
    )

    os.environ["MEMORYBOX_OWNER_EMAIL"] = owner_addr
    peggy = resolve_person_by_name(f"Peggy George {token}", create_if_missing=True, confirm=True)
    sue = resolve_person_by_name(f"Sue Will {token}", create_if_missing=True, confirm=True)
    amb_a = resolve_person_by_name(f"I8 PatA {token}", create_if_missing=True, confirm=True)
    amb_b = resolve_person_by_name(f"I8 PatB {token}", create_if_missing=True, confirm=True)
    add_contact(peggy.person_id, contact_kind="email", value_text=peggy_addr)
    add_contact(sue.person_id, contact_kind="email", value_text=sue_addr)
    add_contact(amb_a.person_id, contact_kind="email", value_text=shared_addr)
    add_contact(amb_b.person_id, contact_kind="email", value_text=shared_addr)

    result = ingest_mbox(str(fixture), label=f"i8-fixture-{token}")
    after_ingest = fixture.read_bytes()
    _check(
        "i8_ingest_ok",
        bool(result.get("ok"))
        and int(result.get("inserted") or 0) >= 8
        and int(result.get("skipped_spam") or 0) >= 1
        and int(result.get("skipped_trash") or 0) >= 1,
        checks,
        problems,
        f"ingest inserted={result.get('inserted')} spam={result.get('skipped_spam')} trash={result.get('skipped_trash')}",
    )
    _check(
        "i8_original_untouched",
        before == after_ingest and result.get("original_untouched") is True,
        checks,
        problems,
        "ingest does not rewrite the mbox",
    )

    eids = [UUID(x) for x in (result.get("evidence_ids") or [])]
    payloads = [_payload(store.get_evidence(eid) or {}) for eid in eids]
    by_mid = {str(p.get("rfc_message_id") or p.get("message_id") or ""): p for p in payloads}
    _check(
        "i8_spam_trash_skipped",
        "<i8-spam@memorybox.test>" not in by_mid
        and "<i8-trash@memorybox.test>" not in by_mid,
        checks,
        problems,
        "Spam/Trash labeled messages are not Evidence unless --include-spam-trash",
    )

    unth = by_mid.get("<i8-unthreaded@memorybox.test>") or {}
    same = by_mid.get("<i8-same-subject-not-a-thread@memorybox.test>") or {}
    _check(
        "i8_incomplete_thread_honesty",
        unth.get("thread_status") == "unthreaded"
        and unth.get("thread_id") in (None, "")
        and same.get("thread_status") == "unthreaded"
        and same.get("thread_id") in (None, "")
        and unth.get("subject") == same.get("subject")
        and (by_mid.get("<i8-orphan-reply@memorybox.test>") or {}).get("thread_completeness")
        == "incomplete"
        and (by_mid.get("<i8-orphan-reply@memorybox.test>") or {}).get("thread_status") == "rfc",
        checks,
        problems,
        "Same subject is not a thread; missing parent stays incomplete",
    )
    root = by_mid.get("<i8-thread-root@memorybox.test>") or {}
    reply = by_mid.get("<i8-thread-reply@memorybox.test>") or {}
    _check(
        "i8_rfc_vendor_thread",
        root.get("vendor_thread_id") == "8800112233"
        and reply.get("vendor_thread_id") == "8800112233"
        and root.get("thread_id") == reply.get("thread_id")
        and reply.get("in_reply_to_ids"),
        checks,
        problems,
        "RFC + vendor thread ids preserved",
    )

    xmas = by_mid.get("<i8-xmas-peggy@memorybox.test>") or {}
    atts = xmas.get("attachments") or []
    inline = (by_mid.get("<i8-inline-cid@memorybox.test>") or {}).get("attachments") or []
    xmas_eid = next(
        eid
        for eid, p in zip(eids, payloads)
        if p.get("rfc_message_id") == "<i8-xmas-peggy@memorybox.test>"
    )
    loaded = load_email_attachment(str(xmas_eid), 0)
    _check(
        "i8_attachment_mime_fidelity",
        atts
        and atts[0].get("filename") == "christmas-card.png"
        and str(atts[0].get("mime_type") or "").startswith("image/")
        and atts[0].get("kind") == "attachment"
        and atts[0].get("bytes_ingested") is True
        and atts[0].get("promoted_to_immich") is False
        and atts[0].get("is_artifact") is not True
        and xmas.get("is_artifact") is False
        and bool(loaded.get("bytes_present"))
        and inline
        and inline[0].get("kind") == "inline"
        and inline[0].get("content_id") == "i8-inline-photo@memorybox.test",
        checks,
        problems,
        "Ordinary vs CID/inline distinguished; bytes stored; not Artifact/Immich",
    )
    html = by_mid.get("<i8-html-only@memorybox.test>") or {}
    _check(
        "i8_html_only_disclosed",
        html.get("html_only") is True and not str(html.get("body_text") or "").strip(),
        checks,
        problems,
        "HTML-only body disclosed",
    )

    xmas_ir = xmas.get("identity_resolution") or {}
    peggy_map = xmas_ir.get("mapped") or []
    bot = by_mid.get("<i8-unthreaded@memorybox.test>") or {}
    shared = by_mid.get("<i8-shared-addr@memorybox.test>") or {}
    _check(
        "i8_identity_unique_ambiguous_unmapped",
        any(m.get("person_id") == peggy.person_id for m in peggy_map)
        and (bot.get("identity_resolution") or {}).get("unmapped")
        and (shared.get("identity_resolution") or {}).get("ambiguous"),
        checks,
        problems,
        f"xmas_ir={xmas_ir} bot={bot.get('identity_resolution')} shared={shared.get('identity_resolution')}",
    )

    ctx = AskContext(session_id=f"i8-{token}")
    plan_out = plan_ask("how many times did I email Peggy George?", ctx)
    hits_out = search_email_messages(plan_out, limit=5000)
    _check(
        "i8_ask_outbound_count_scope",
        plan_out.want_communication
        and hits_out
        and "outbound_only" in (hits_out[0].count_scope or "")
        and int(hits_out[0].match_total or 0) >= 1
        and "ingested email" in (hits_out[0].count_scope or ""),
        checks,
        problems,
        f"outbound people={plan_out.person_names} n={hits_out[0].match_total if hits_out else None} scope={hits_out[0].count_scope if hits_out else None}",
    )
    plan_sue = plan_ask("how many times did Sue Will respond to any of my emails?", ctx)
    hits_sue = search_email_messages(plan_sue, limit=5000)
    _check(
        "i8_ask_sister_mapped_equivalent",
        any("sue" in n.lower() for n in plan_sue.person_names)
        and hits_sue
        and int(hits_sue[0].match_total or 0) >= 1,
        checks,
        problems,
        f"EVS-108 mapped equivalent people={plan_sue.person_names} n={hits_sue[0].match_total if hits_sue else None}",
    )
    xmas_time = parse_temporal("around Christmas in 2017")
    plan_xmas = plan_ask(
        "What did Peggy and I coordinate on around Christmas in 2017, in emails?",
        ctx,
    )
    hits_xmas = search_email_messages(plan_xmas, limit=5000)
    _check(
        "i8_ask_holiday_window_mbql",
        bool(xmas_time.windows)
        and plan_xmas.want_communication
        and any("peggy" in n.lower() for n in plan_xmas.person_names)
        and "keyword=christmas" not in (hits_xmas[0].count_scope if hits_xmas else ""),
        checks,
        problems,
        f"windows={plan_xmas.temporal_windows} notes={plan_xmas.notes} scope={hits_xmas[0].count_scope if hits_xmas else None}",
    )
    plan_thread = plan_ask("show me the email thread about Alaska packing list", ctx)
    hits_thread = search_email_messages(plan_thread, limit=5000)
    thread_ids = {h.thread_id for h in hits_thread if h.thread_id}
    _check(
        "i8_thread_open",
        "thread_open_rfc_or_vendor_only" in (hits_thread[0].count_scope if hits_thread else "")
        and len(hits_thread) >= 2
        and len(thread_ids) == 1,
        checks,
        problems,
        f"thread n={len(hits_thread)} ids={thread_ids}",
    )

    email_items = items_from_ask_result(
        {
            "evidence_hits": [h.to_dict() for h in hits_out],
            "plan": {"notes": (), "original_ask": "show me memories"},
        }
    )
    sms_fake = {
        "evidence_id": "00000000-0000-0000-0000-000000000099",
        "evidence_kind": "communication",
        "summary": "sms hide check",
        "score": 1,
        "excerpt": "hi",
        "source": "sms_export",
        "channel": "sms",
        "sent_at": "2020-03-15T00:00:00",
        "people": ["Peggy"],
    }
    mixed = items_from_ask_result(
        {
            "evidence_hits": [h.to_dict() for h in hits_out] + [sms_fake],
            "plan": {"notes": (), "original_ask": "show me memories"},
        }
    )
    _check(
        "i8_mbql_default_gallery",
        email_items
        and all(i.get("type") == "email" for i in email_items)
        and all(not i.get("gallery_default_hidden") for i in email_items)
        and any(
            i.get("type") == "sms" and i.get("gallery_default_hidden") for i in mixed
        )
        and any(i.get("type") == "email" and not i.get("gallery_default_hidden") for i in mixed)
        and not explicit_text_gallery({"plan": {"notes": ()}}, "Show me Peggy"),
        checks,
        problems,
        "Emails visible on default Gallery; SMS hide unchanged",
    )

    metric = _email_ingested_metric(
        count=len(payloads),
        unmapped_rows=1,
        date_min="2016-01-04",
        date_max="2019-06-03",
        staged=True,
        calculated_at="2026-08-18T00:00:00+00:00",
        pg="postgresql",
    )
    missing = _email_ingested_metric(
        count=0,
        unmapped_rows=0,
        date_min=None,
        date_max=None,
        staged=False,
        calculated_at="2026-08-18T00:00:00+00:00",
        pg="postgresql",
    )
    _check(
        "i8_health_honesty",
        metric.get("state") == "available"
        and metric.get("value") == len(payloads)
        and missing.get("state") == "unavailable"
        and missing.get("value") is None,
        checks,
        problems,
        "unavailable ≠ 0",
    )
    try:
        fixture.unlink()
    except OSError:
        pass


def run_p2_i8_acceptance(*, flightsim: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    problems: list[str] = []
    _structural(checks, problems)
    try:
        _logic(checks, problems)
    except Exception as exc:  # noqa: BLE001
        _check(
            "i8_logic_suite",
            False,
            checks,
            problems,
            f"logic suite error: {type(exc).__name__}: {exc}",
        )
    overall = not problems and all(c.get("ok") for c in checks.values())
    return {
        "overall_ok": overall,
        "ok": overall,
        "checks": checks,
        "problems": problems,
        "meta": {
            "increment": "P2-I8",
            "mode": "flightsim" if flightsim else "harness",
            "parser_version": PARSER_VERSION,
        },
        "evs_status": {
            "EVS-107": "harness outbound email count + scope (Peggy fixture); owner runtime maps real Person after inspect-mbox",
            "EVS-108": "harness Sue Will inbound/respond as sister-equivalent",
            "EVS-047": "harness Christmas-window email retrieve; SMS not narrated here",
            "EVS-109": "holiday-window retrieve + cited extract; not Immich",
            "EVS-070": "email-only retrieve/disclosure; I11 narrative out of scope",
        },
        "q_locks": {
            "Q1": "inspect-mbox on the actual staged path; harness fixture is not the corpus",
            "Q2": "map real inspect samples to EVS intent; fixture stands in for harness only",
            "Q3": "RFC Message-ID / In-Reply-To / References; preserve vendor thread ids; no invented membership",
            "Q4": "attachment bytes+metadata with the message; inline/CID distinct; explicit Artifact only",
            "Q5": "I7 identity ladder for email; raw address/display preserved; no display-name merge",
            "Q6": "I8 evidence+correlation readiness; I10 correlate; I11 synthesize",
        },
        "note": (
            "Structural + fixture harness. ACCEPTED requires owner-runtime pass of "
            "definition §9 against the real staged export. Run inspect-mbox on the "
            "P1 host before treating the staged mbox as understood. Do not start I8.5/I9/I10/I11."
        ),
    }
