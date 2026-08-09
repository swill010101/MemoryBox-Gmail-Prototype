"""CLI: python -m memorybox migrate | serve | health."""
from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memorybox", description="MemoryBox monolith CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("migrate", help="Apply pending SQL migrations")
    sub.add_parser("health", help="Print /health-equivalent JSON via DB checks")
    sub.add_parser(
        "seed-synthetic",
        help="Load Increment 1 synthetic Grandpa photo graph (not real archive)",
    )
    sub.add_parser(
        "prove-synthetic",
        help="Retrieve synthetic Grandpa graph and verify relationships",
    )
    p_serve = sub.add_parser("serve", help="Run uvicorn (Increment 1 API)")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)

    args = parser.parse_args(argv)

    if args.cmd == "migrate":
        from memorybox.migrate import migrate

        applied = migrate()
        print(json.dumps({"applied": applied}, indent=2))
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
