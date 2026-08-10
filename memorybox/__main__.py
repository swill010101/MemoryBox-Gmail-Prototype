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

        host = args.host or settings.host
        port = args.port or settings.port
        uvicorn.run("memorybox.app:app", host=host, port=port, reload=False)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
