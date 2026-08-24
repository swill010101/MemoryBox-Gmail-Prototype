"""CLI: python -m memorybox <command>."""
from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv: list[str] | None = None) -> int:
    if "MEMORYBOX_DATABASE_URL" not in os.environ and "MEMORYBOX_ALLOW_DEV_DEFAULTS" not in os.environ:
        os.environ["MEMORYBOX_ALLOW_DEV_DEFAULTS"] = "1"

    parser = argparse.ArgumentParser(prog="memorybox", description="MemoryBox monolith CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("migrate", help="Apply pending SQL migrations")
    sub.add_parser("health", help="Print health JSON")
    sub.add_parser("seed-synthetic", help="I1 synthetic Grandpa graph")
    sub.add_parser("prove-synthetic", help="I1 prove Grandpa graph")
    sub.add_parser("prove-providers", help="I2 provider acceptance")
    p_email = sub.add_parser("ingest-email", help="Ingest mbox → Evidence")
    p_email.add_argument(
        "--uri",
        default=None,
        help=r"Path to mbox/Maildir (default: P:\photos\memorybox\sources\email\all mail including spam and trash-002.mbox)",
    )
    p_email.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after this many kept messages (Spam/Trash skipped first unless --include-spam-trash)",
    )
    p_email.add_argument(
        "--include-spam-trash",
        action="store_true",
        help="Ingest Gmail Spam/Trash labeled messages (default: skip those labels; originals untouched)",
    )
    p_inspect_mbox = sub.add_parser(
        "inspect-mbox",
        help="Read-only mbox/Maildir inventory (counts Spam/Trash labels; does not skip them)",
    )
    p_inspect_mbox.add_argument(
        "--uri",
        default=None,
        help=r"Default: P:\photos\memorybox\sources\email\all mail including spam and trash-002.mbox",
    )
    p_inspect_mbox.add_argument("--limit", type=int, default=None)
    sub.add_parser(
        "ingest-email-report",
        help="Read-only: last ingest-email job + email Evidence count (no UUID dump)",
    )
    p_prove_p2i8 = sub.add_parser(
        "prove-p2-i8",
        help="P2-I8 Richer Email acceptance prove",
    )
    p_prove_p2i8.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "FlightSim ACCEPTED gate remains manual (definition §9). "
            "Harness uses the in-repo I8 fixture; inspect-mbox the real export separately."
        ),
    )
    p_prove_p2i8a = sub.add_parser(
        "prove-p2-i8a",
        help="P2-I8A Unified Communications Gallery & Timeline Precision prove",
    )
    p_prove_p2i8a.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "Includes live calendar_event / Archive Health inspect. "
            "§11 ACCEPTED remains a manual owner pass."
        ),
    )
    p_prove_p2i8b = sub.add_parser(
        "prove-p2-i8b",
        help="P2-I8B Person-seeded video recognition & owner Learn prove",
    )
    p_prove_p2i8b.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "FlightSim: real Immich GET /faces + HVRT. Owner ACCEPTED is Peggy George "
            "plus one additional Person, negative video, both-in-one where available. "
            "Does not include I9 speech/voice."
        ),
    )
    p_archive = sub.add_parser(
        "recognition-archive-pass",
        help="I8B incremental overnight: new/changed people only, then drain one video at a time",
    )
    p_archive.add_argument(
        "--seed-immich",
        action="store_true",
        help=(
            "Refresh Immich people, then seed only when still-face catalogs changed "
            "(new named person, new stills, Immich merge). Walks the MB-owned home-video "
            "folder for new files (not Immich ingest) and queues them as new_video for "
            "people who already have exemplars. Does not restart unchanged people."
        ),
    )
    p_archive.add_argument(
        "--full",
        action="store_true",
        help="Ignore watermarks: re-seed and queue every named Person against every video",
    )
    p_archive.add_argument("--person-limit", type=int, default=80)
    p_rec_export = sub.add_parser(
        "recognition-people-export",
        help="Write one CSV row per Person in the face-recognition queue (not one row per video)",
    )
    p_rec_export.add_argument(
        "--out",
        required=True,
        help="Destination CSV path (Excel-friendly UTF-8 with BOM)",
    )
    p_rec_apply = sub.add_parser(
        "recognition-people-apply",
        help="Keep only People listed in the edited CSV; drop others from queued face scan",
    )
    p_rec_apply.add_argument(
        "--keep",
        required=True,
        help="Edited CSV: leave only people to search, or set keep=N on people to drop",
    )
    p_rec_apply.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts only; do not update the queue or people.face_scan",
    )
    p_speech_archive = sub.add_parser(
        "speech-archive-pass",
        help="I9 incremental: transcribe newly added videos only (not people × files)",
    )
    p_speech_archive.add_argument(
        "--limit",
        type=int,
        default=8,
        help="Max new videos to queue this pass (default 8 for first review). Raise later.",
    )
    p_speech_archive.add_argument(
        "--video-id",
        action="append",
        default=[],
        help="Queue only this video_external_id (repeatable).",
    )
    p_prove_p2i9 = sub.add_parser(
        "prove-p2-i9",
        help="P2-I9 Spoken Moments prove (harness; --flightsim live tape when P1=1)",
    )
    p_prove_p2i9.add_argument(
        "--flightsim",
        action="store_true",
        help="FlightSim: structural always; live tape+Person when MEMORYBOX_P1_RUNTIME_HOST=1",
    )
    p_prove_p2i9.add_argument(
        "--person",
        default=None,
        help='MemoryBox Person to prove (default: Sam LaMartina / MEMORYBOX_P2_I9_PERSON_NAME)',
    )
    p_prove_p2i9.add_argument(
        "--video-id",
        default=None,
        help="video_external_id to transcribe for proof (default: the open Immich leftover tape)",
    )
    p_prove_p2i9.add_argument(
        "--more",
        type=int,
        default=8,
        help="Also enqueue this many newly added videos (per-video, not people × files)",
    )
    p_prove_p2i10 = sub.add_parser(
        "prove-p2-i10",
        help="P2-I10 Cross-Source Correlation prove (harness; optional DB pack)",
    )
    p_prove_p2i10.add_argument(
        "--flightsim",
        action="store_true",
        help="Includes definition-authorized check. Owner ACCEPTED remains a manual mixed-pack pass.",
    )
    p_inspect_cal = sub.add_parser(
        "inspect-calendar",
        help="Read-only: staged ICS vs PG calendar_event (Archive Health calendar slice; no ingest)",
    )
    p_inspect_cal.add_argument(
        "--uri",
        default=None,
        help=r"ICS file or calendar/ folder. Default: Sources/calendar under MEMORYBOX_SOURCES_ROOT",
    )
    p_cal = sub.add_parser(
        "ingest-calendar",
        help="Ingest ICS file or staged calendar/ folder → calendar_event Evidence",
    )
    p_cal.add_argument(
        "--uri",
        required=True,
        help=r"ICS file or folder (e.g. P:\photos\memorybox\sources\calendar)",
    )
    p_cal.add_argument("--limit", type=int, default=None)
    p_sms = sub.add_parser("ingest-sms", help="Ingest SMS/iMessage CSV → Evidence")
    p_sms.add_argument("--uri", default=None, help="Path to export CSV (default: staged Sources/sms)")
    p_sms.add_argument("--limit", type=int, default=None)
    p_sms.add_argument(
        "--attachments-dir",
        default=None,
        help="Folder of Export Attachments (sets MEMORYBOX_SMS_ATTACHMENTS_DIR for this run)",
    )
    p_inspect_sms = sub.add_parser(
        "inspect-sms",
        help="Read-only SMS export inventory (headers/counts; no ingest; no rewrite)",
    )
    p_inspect_sms.add_argument("--uri", default=None)
    p_inspect_att = sub.add_parser(
        "inspect-sms-attachments",
        help="Read-only probe of an Export Attachments folder (no ingest)",
    )
    p_inspect_att.add_argument(
        "--dir",
        required=True,
        dest="attachments_dir",
        help="Folder of per-chat Export Attachments",
    )
    sub.add_parser(
        "repair-sms-identities",
        help="Backfill People confirmed phones from ingested unique SMS auto-maps",
    )
    sub.add_parser("rebuild-comms-index", help="Rebuild derived Qdrant from PG")
    sub.add_parser("prove-ingest", help="Increment 3 acceptance prove")
    p_ask = sub.add_parser("ask", help="One-shot Ask (JSON)")
    p_ask.add_argument("text", help="Ask text")
    p_ask.add_argument("--session", default=None)
    p_prove4 = sub.add_parser("prove-ask", help="Increment 4 acceptance prove")
    p_prove4.add_argument(
        "--flightsim",
        action="store_true",
        help="Final P1-runtime-host acceptance (requires Immich + configured env)",
    )
    p_prove5 = sub.add_parser("prove-story", help="P2-I10A Stories acceptance prove (includes I5)")
    p_prove5.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "Sets MEMORYBOX_P1_RUNTIME_HOST=1. After Save Story on /story/ui, "
            "set MEMORYBOX_I5_OWNER_STORY_ID to that story UUID."
        ),
    )
    p_prove5a = sub.add_parser("prove-journal", help="Increment 5A Journal acceptance prove")
    p_prove5a.add_argument(
        "--flightsim",
        action="store_true",
        help="Final P1-runtime-host acceptance (set MEMORYBOX_I5A_OWNER_*_JOURNAL_ID after UX save)",
    )
    p_prove6 = sub.add_parser("prove-person", help="Increment 6 Person & Identity acceptance prove")
    p_prove6.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "Final P1-runtime-host acceptance "
            "(set MEMORYBOX_I6_OWNER_PERSON_ID after /people/ui Teach)"
        ),
    )
    p_prove7 = sub.add_parser("prove-video", help="Increment 7 Video Intelligence + Review acceptance prove")
    p_prove7.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "Final P1-runtime-host acceptance "
            "(set MEMORYBOX_I7_OWNER_PERSON_ID after /review/ui Teach)"
        ),
    )
    p_prove8 = sub.add_parser("prove-library", help="Increment 8 Library / Timeline acceptance prove")
    p_prove8.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "Final P1-runtime-host acceptance "
            "(set MEMORYBOX_I8_OWNER_PERSON_ID after /library/ui Person filter)"
        ),
    )
    p_prove9 = sub.add_parser("prove-artifact", help="Increment 9 Artifact acceptance prove")
    p_prove9.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "Final P1-runtime-host acceptance "
            "(set MEMORYBOX_ARTIFACT_MEDIA_ROOT; optional MEMORYBOX_I9_OWNER_ARTIFACT_ID)"
        ),
    )
    p_prove_i10a1 = sub.add_parser(
        "prove-person-i10a1",
        help="P2-I10A.1 Person Explorer / About / Edit acceptance prove",
    )
    p_prove_i10a1.add_argument(
        "--flightsim",
        action="store_true",
        help="Final P1-runtime-host acceptance (set MEMORYBOX_P1_RUNTIME_HOST=1)",
    )
    p_prove_i10a2 = sub.add_parser(
        "prove-i10a2",
        help="P2-I10A.2 speech input regression prove (increment ACCEPTED)",
    )
    p_prove_i10a2.add_argument(
        "--flightsim",
        action="store_true",
        help="Final P1-runtime-host acceptance (set MEMORYBOX_P1_RUNTIME_HOST=1)",
    )
    p_prove9a = sub.add_parser(
        "prove-person-profile",
        help="Increment 9A Person Profile acceptance prove",
    )
    p_prove9a.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "Final P1-runtime-host acceptance "
            "(set MEMORYBOX_P1_RUNTIME_HOST=1 and MEMORYBOX_OWNER_PERSON_ID)"
        ),
    )
    p_prove10 = sub.add_parser(
        "prove-cross-provider-person",
        help="Increment 10 cross-provider Person (EVS-014) acceptance prove",
    )
    p_prove10.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "Final P1-runtime-host acceptance "
            "(MEMORYBOX_P1_RUNTIME_HOST=1, HVRT worker running, "
            "MEMORYBOX_I10_OWNER_PERSON_ID after Review Immich+HVRT teach)"
        ),
    )
    p_prove11 = sub.add_parser(
        "prove-guided-capture",
        help="Increment 11 Guided Capture (EF-11) acceptance prove",
    )
    p_prove11.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "Final P1-runtime-host acceptance "
            "(MEMORYBOX_P1_RUNTIME_HOST=1; real Gmail via MEMORYBOX_GC_EMAIL_PROVIDER=marvin)"
        ),
    )
    p_prove12 = sub.add_parser(
        "prove-export",
        help="Increment 12 Minimum Viable Export (EF-16) acceptance prove",
    )
    p_prove12.add_argument(
        "--flightsim",
        action="store_true",
        help="Final P1-runtime-host acceptance (MEMORYBOX_P1_RUNTIME_HOST=1)",
    )
    p_prove_p2i1 = sub.add_parser(
        "prove-p2-i1",
        help="P2-I1 Show me Peggy (Person-in-Media Vertical) acceptance prove",
    )
    p_prove_p2i1.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "FlightSim ACCEPTED gate: MEMORYBOX_P1_RUNTIME_HOST=1, real Immich + real HVRT "
            "(fakes/degraded fail). Also set MEMORYBOX_P2_I1_POSITIVE_VIDEO_ID, "
            "MEMORYBOX_P2_I1_NEGATIVE_VIDEO_ID; optional PERSON_NAME/PERSON_ID/HVRT_FACE_ID"
        ),
    )
    p_prove_p2i2 = sub.add_parser(
        "prove-p2-i2",
        help="P2-I2 Product Shell & Context Maturation acceptance prove",
    )
    p_prove_p2i2.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "FlightSim ACCEPTED gate: MEMORYBOX_P1_RUNTIME_HOST=1, live serve at "
            "MEMORYBOX_BASE_URL (default http://127.0.0.1:$MEMORYBOX_PORT or :8790), "
            "plus prove-p2-i1 --flightsim"
        ),
    )
    p_prove_p2i3 = sub.add_parser(
        "prove-p2-i3",
        help="P2-I3 Archive Health & Provider Honesty acceptance prove",
    )
    p_prove_p2i3.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "FlightSim ACCEPTED gate: MEMORYBOX_P1_RUNTIME_HOST=1, live Archive Health "
            "at MEMORYBOX_BASE_URL, plus prove-p2-i1 and prove-p2-i2 --flightsim"
        ),
    )
    p_prove_p2i4 = sub.add_parser(
        "prove-p2-i4",
        help="P2-I4 Mixed-Media Find / Explore acceptance prove",
    )
    p_prove_p2i4.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "FlightSim ACCEPTED gate: MEMORYBOX_P1_RUNTIME_HOST=1, live Explore at "
            "MEMORYBOX_BASE_URL (default http://127.0.0.1:$MEMORYBOX_PORT or :8790)"
        ),
    )
    p_prove_p2i5 = sub.add_parser(
        "prove-p2-i5",
        help="P2-I5 Universal Person Surfaces acceptance prove",
    )
    p_prove_p2i5.add_argument(
        "--flightsim",
        action="store_true",
        help="Reserved for FlightSim manual gate (structural harness today)",
    )
    p_prove_p2i6 = sub.add_parser(
        "prove-p2-i6",
        help="P2-I6 Relationship Graph & Derived Kinship acceptance prove",
    )
    p_prove_p2i6.add_argument(
        "--flightsim",
        action="store_true",
        help="Reserved for FlightSim manual gate (structural+logic harness today)",
    )
    p_prove_p2i7 = sub.add_parser(
        "prove-p2-i7",
        help="P2-I7 SMS/Text Evidence acceptance prove",
    )
    p_prove_p2i7.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "FlightSim ACCEPTED gate remains manual (definition §8). "
            "Harness uses the in-repo fixture; inspect-sms the real export separately."
        ),
    )
    p_prove_p2i7_01 = sub.add_parser(
        "prove-p2-bl-i7-01",
        help="P2-BL-I7-01 SMS Export Attachments backfill prove (does not reopen I7)",
    )
    p_prove_p2i7_01.add_argument(
        "--flightsim",
        action="store_true",
        help="Reserved; harness proves unique match / collision / orphan / no wipe",
    )
    p_prove_p2i7a = sub.add_parser(
        "prove-p2-i7a",
        help="P2-I7A AI Model Trace acceptance prove",
    )
    p_prove_p2i7a.add_argument(
        "--flightsim",
        action="store_true",
        help=(
            "P2-I7A ACCEPTED 2026-08-15 (Tom). "
            "Harness remains a regression check; /dev/ai-trace is developer-only."
        ),
    )
    p_prove_mbql = sub.add_parser(
        "prove-mbql-001",
        help="MBQL-001 Ask/query/command compile acceptance prove",
    )
    p_prove_mbql.add_argument(
        "--flightsim",
        action="store_true",
        help="FlightSim ACCEPTED gate remains manual (definition §6 phrases).",
    )
    p_export = sub.add_parser(
        "export",
        help="Build MV export package synchronously (format 1 folder)",
    )
    p_export.add_argument(
        "--destination",
        default=None,
        help="Parent directory (default: MEMORYBOX_EXPORT_DIR)",
    )
    p_export.add_argument(
        "--zip",
        action="store_true",
        help="Also write optional ZIP derivative of the folder",
    )
    p_stt = sub.add_parser(
        "stt-check",
        help="Smoke Capture/STT on a local audio file (FlightSim diagnose)",
    )
    p_stt.add_argument("--file", required=True, help="Path to webm/wav/mp3 clip")
    p_serve = sub.add_parser("serve", help="Run uvicorn")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)

    args = parser.parse_args(argv)

    if args.cmd == "migrate":
        from memorybox.migrate import migrate

        print(json.dumps({"applied": migrate()}, indent=2))
        return 0

    if args.cmd == "health":
        from memorybox.app import health

        payload = health()
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "seed-synthetic":
        from memorybox.synthetic_i1 import seed

        payload = seed()
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-synthetic":
        from memorybox.synthetic_i1 import prove

        payload = prove()
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-providers":
        from memorybox.providers.acceptance import prove_increment_2

        payload = prove_increment_2()
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "ingest-email":
        from memorybox.ingest.comms_email import ingest_mbox, inspect_default_or_uri
        from memorybox.providers.email_read.mbox_parse import default_email_source_path

        uri = args.uri or (str(default_email_source_path()) if default_email_source_path() else None)
        if not uri:
            payload = inspect_default_or_uri(None)
            print(json.dumps(payload, indent=2, default=str))
            return 1
        payload = ingest_mbox(
            uri, limit=args.limit, include_spam_trash=bool(args.include_spam_trash)
        )
        from memorybox.ingest.comms_email import compact_ingest_cli_payload

        print(json.dumps(compact_ingest_cli_payload(payload), indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "ingest-email-report":
        from memorybox.ingest.comms_email import email_ingest_report

        payload = email_ingest_report()
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "inspect-mbox":
        from memorybox.ingest.comms_email import inspect_default_or_uri

        payload = inspect_default_or_uri(args.uri, limit=args.limit)
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "inspect-calendar":
        from memorybox.ingest.comms_calendar import inspect_calendar_state

        payload = inspect_calendar_state(uri=args.uri)
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "ingest-calendar":
        from memorybox.ingest.comms_calendar import (
            compact_calendar_cli_payload,
            ingest_calendar_uri,
        )

        payload = ingest_calendar_uri(args.uri, limit=args.limit)
        print(json.dumps(compact_calendar_cli_payload(payload), indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "ingest-sms":
        from memorybox.ingest.comms_sms import ingest_sms

        payload = ingest_sms(
            args.uri, limit=args.limit, attachments_dir=args.attachments_dir
        )
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "inspect-sms":
        from memorybox.ingest.comms_sms import inspect_default_or_uri

        payload = inspect_default_or_uri(args.uri)
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "inspect-sms-attachments":
        from memorybox.ingest.comms_sms import inspect_sms_attachments_dir

        payload = inspect_sms_attachments_dir(args.attachments_dir)
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "repair-sms-identities":
        from memorybox.person.phone_map import repair_sms_identity_contacts

        payload = repair_sms_identity_contacts()
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "rebuild-comms-index":
        from memorybox.ingest.rebuild_index import rebuild_comms_index

        payload = rebuild_comms_index()
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-ingest":
        from memorybox.ingest.acceptance import prove_increment_3

        payload = prove_increment_3()
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "ask":
        from memorybox.ask.orchestrator import AskOrchestrator

        result = AskOrchestrator().ask(args.text, session_id=args.session)
        print(json.dumps(result.to_dict(), indent=2, default=str))
        return 0

    if args.cmd == "prove-ask":
        from memorybox.ask.acceptance import prove_increment_4

        payload = prove_increment_4(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-story":
        from memorybox.story.acceptance import prove_increment_5

        if args.flightsim:
            os.environ["MEMORYBOX_P1_RUNTIME_HOST"] = "1"
        payload = prove_increment_5(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-journal":
        from memorybox.journal.acceptance import prove_increment_5a

        payload = prove_increment_5a(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-person":
        from memorybox.person.acceptance import prove_increment_6

        payload = prove_increment_6(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-video":
        from memorybox.review.acceptance import prove_increment_7

        payload = prove_increment_7(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-library":
        from memorybox.library.acceptance import prove_increment_8

        payload = prove_increment_8(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-artifact":
        from memorybox.artifact.acceptance import run_prove_artifact

        payload = run_prove_artifact(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-person-i10a1":
        from memorybox.person.i10a1_acceptance import run_prove_person_i10a1

        if args.flightsim:
            os.environ["MEMORYBOX_P1_RUNTIME_HOST"] = "1"
        payload = run_prove_person_i10a1(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-i10a2":
        from memorybox.speech.i10a2_acceptance import run_prove_i10a2

        if args.flightsim:
            os.environ["MEMORYBOX_P1_RUNTIME_HOST"] = "1"
        payload = run_prove_i10a2(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-person-profile":
        from memorybox.profile.acceptance import run_prove_person_profile

        payload = run_prove_person_profile(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-cross-provider-person":
        from memorybox.person.cross_provider_acceptance import (
            prove_cross_provider_person,
        )

        payload = prove_cross_provider_person(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-guided-capture":
        from memorybox.guided_capture.acceptance import prove_guided_capture

        payload = prove_guided_capture(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-export":
        from memorybox.export.acceptance import prove_export

        payload = prove_export(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-p2-i1":
        from memorybox.person.p2_i1_acceptance import prove_p2_i1

        payload = prove_p2_i1(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-p2-i2":
        from memorybox.shell.p2_i2_acceptance import prove_p2_i2

        payload = prove_p2_i2(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-p2-i3":
        from memorybox.status.p2_i3_acceptance import prove_p2_i3

        payload = prove_p2_i3(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-p2-i4":
        from memorybox.explore.p2_i4_acceptance import prove_p2_i4

        payload = prove_p2_i4(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-p2-i5":
        from memorybox.person.p2_i5_acceptance import run_p2_i5_acceptance

        payload = run_p2_i5_acceptance()
        # Normalize to {ok: bool} for CLI
        out = {
            "ok": bool(payload.get("overall_ok")),
            **payload,
        }
        print(json.dumps(out, indent=2, default=str))
        return 0 if out["ok"] else 1

    if args.cmd == "prove-p2-i6":
        from memorybox.person.p2_i6_acceptance import run_p2_i6_acceptance

        payload = run_p2_i6_acceptance()
        out = {
            "ok": bool(payload.get("overall_ok")),
            **payload,
        }
        print(json.dumps(out, indent=2, default=str))
        return 0 if out["ok"] else 1

    if args.cmd == "prove-p2-i7":
        from memorybox.ingest.p2_i7_acceptance import run_p2_i7_acceptance

        payload = run_p2_i7_acceptance(flightsim=bool(args.flightsim))
        out = {
            "ok": bool(payload.get("overall_ok")),
            **payload,
        }
        print(json.dumps(out, indent=2, default=str))
        return 0 if out["ok"] else 1

    if args.cmd == "prove-p2-bl-i7-01":
        from memorybox.ingest.p2_bl_i7_01_acceptance import run_p2_bl_i7_01_acceptance

        payload = run_p2_bl_i7_01_acceptance(flightsim=bool(args.flightsim))
        out = {
            "ok": bool(payload.get("overall_ok")),
            **payload,
        }
        print(json.dumps(out, indent=2, default=str))
        return 0 if out["ok"] else 1

    if args.cmd == "prove-p2-i7a":
        from memorybox.ai_trace.p2_i7a_acceptance import prove_p2_i7a

        payload = prove_p2_i7a(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-mbql-001":
        from memorybox.mbql.p2_mbql_acceptance import prove_p2_mbql_001

        payload = prove_p2_mbql_001(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-p2-i8":
        from memorybox.ingest.p2_i8_acceptance import run_p2_i8_acceptance

        payload = run_p2_i8_acceptance(flightsim=bool(args.flightsim))
        out = {
            "ok": bool(payload.get("overall_ok")),
            **payload,
        }
        print(json.dumps(out, indent=2, default=str))
        return 0 if out["ok"] else 1

    if args.cmd == "prove-p2-i8a":
        from memorybox.ingest.p2_i8a_acceptance import run_p2_i8a_acceptance

        payload = run_p2_i8a_acceptance(flightsim=bool(args.flightsim))
        out = {
            "ok": bool(payload.get("overall_ok")),
            **payload,
        }
        print(json.dumps(out, indent=2, default=str))
        return 0 if out["ok"] else 1

    if args.cmd == "recognition-archive-pass":
        from memorybox.ask.deps import build_photo, build_video
        from memorybox.recognition.archive_pass import enqueue_known_people_archive

        payload = enqueue_known_people_archive(
            video_provider=build_video(),
            photo_provider=build_photo(),
            seed_immich=bool(args.seed_immich),
            person_limit=int(args.person_limit),
            full=bool(args.full),
        )
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "recognition-people-export":
        from memorybox.recognition.allowlist import list_queue_people, write_people_csv

        rows = list_queue_people()
        dest = write_people_csv(args.out, rows)
        print(
            json.dumps(
                {
                    "ok": True,
                    "path": str(dest.resolve()),
                    "people": len(rows),
                    "queued_people": sum(1 for r in rows if int(r.get("queued") or 0) > 0),
                    "note": (
                        "One row per Person. Delete rows you do not want searched "
                        "(or set keep=N), then: python -m memorybox recognition-people-apply "
                        f"--keep {dest}"
                    ),
                },
                indent=2,
            )
        )
        return 0

    if args.cmd == "recognition-people-apply":
        from memorybox.recognition.allowlist import apply_keep_csv

        payload = apply_keep_csv(args.keep, dry_run=bool(args.dry_run))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-p2-i8b":
        from memorybox.recognition.p2_i8b_acceptance import prove_p2_i8b

        payload = prove_p2_i8b(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "speech-archive-pass":
        from memorybox.ask.deps import build_photo, build_video
        from memorybox.speech.archive_pass import enqueue_new_videos_for_transcribe

        payload = enqueue_new_videos_for_transcribe(
            video_provider=build_video(),
            photo_provider=build_photo(),
            limit=int(args.limit),
            video_ids=list(args.video_id or []),
        )
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-p2-i9":
        from memorybox.speech.p2_i9_acceptance import prove_p2_i9

        payload = prove_p2_i9(
            flightsim=bool(args.flightsim),
            person_name=getattr(args, "person", None),
            video_id=getattr(args, "video_id", None),
            more=int(getattr(args, "more", 8) or 8),
        )
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "prove-p2-i10":
        from memorybox.correlate.p2_i10_acceptance import prove_p2_i10

        payload = prove_p2_i10(flightsim=bool(args.flightsim))
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "export":
        from memorybox.export.package import ExportError, build_export_package

        try:
            result = build_export_package(
                destination_parent=args.destination,
                make_zip=bool(args.zip),
            )
        except ExportError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            return 1
        print(
            json.dumps(
                {
                    "ok": True,
                    "export_root": str(result.export_root),
                    "zip_path": str(result.zip_path) if result.zip_path else None,
                    "created_at": result.created_at,
                    "counts": result.counts,
                },
                indent=2,
                default=str,
            )
        )
        return 0

    if args.cmd == "stt-check":
        from pathlib import Path

        from memorybox.providers.capture.faster_whisper import smoke_transcribe_file

        path = Path(args.file)
        if not path.is_file():
            print(json.dumps({"ok": False, "error": f"file not found: {path}"}))
            return 1
        try:
            payload = smoke_transcribe_file(path)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            return 1
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "serve":
        import uvicorn

        from memorybox.config import settings
        from memorybox.migrate import migrate
        from memorybox.profile.bootstrap import ensure_default_owner_session

        try:
            applied = migrate()
            if applied:
                print(f"migrate: {applied}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"migrate warning: {exc}", flush=True)
        try:
            from memorybox.ai_trace.store import ensure_schema

            ensure_schema()
        except Exception as exc:  # noqa: BLE001
            print(f"ai_trace schema warning: {exc}", flush=True)

        boot = ensure_default_owner_session()
        if not boot.get("skipped"):
            print(f"owner bootstrap: {boot}", flush=True)

        host = args.host or settings.host
        port = args.port or settings.port
        uvicorn.run("memorybox.app:app", host=host, port=port, reload=False)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
