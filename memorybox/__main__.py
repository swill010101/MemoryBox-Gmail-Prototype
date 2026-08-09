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
