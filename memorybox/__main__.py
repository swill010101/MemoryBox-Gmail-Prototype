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
    p_email.add_argument("--uri", required=True)
    p_email.add_argument("--limit", type=int, default=None)
    p_cal = sub.add_parser("ingest-calendar", help="Ingest ICS → Evidence")
    p_cal.add_argument("--uri", required=True)
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
    p_prove5 = sub.add_parser("prove-story", help="Increment 5 Story acceptance prove")
    p_prove5.add_argument(
        "--flightsim",
        action="store_true",
        help="Final P1-runtime-host acceptance (set MEMORYBOX_I5_OWNER_STORY_ID after UX save)",
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
        from memorybox.ingest.comms_email import ingest_mbox

        payload = ingest_mbox(args.uri, limit=args.limit)
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("ok") else 1

    if args.cmd == "ingest-calendar":
        from memorybox.ingest.comms_calendar import ingest_ics

        payload = ingest_ics(args.uri, limit=args.limit)
        print(json.dumps(payload, indent=2, default=str))
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
