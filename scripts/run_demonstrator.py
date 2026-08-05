#!/usr/bin/env python3
"""Start MBD-001 MemoryBox Demonstrator on Media-Server (default :8780)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "application"
sys.path.insert(0, str(APP))

import uvicorn

from api import config  # noqa: E402


def main() -> None:
    print(f"MemoryBox Demonstrator  http://127.0.0.1:{config.PORT}")
    print(f"  (bind {config.HOST}:{config.PORT} — Tailscale IP + port for remote)")
    print(f"HVRT Review iframe      {config.HVRT_ORIGIN}")
    print(f"Ask proxy               {config.ASK_ORIGIN or '(local memories only)'}")
    print(f"Demonstrator DB         {config.DEMONSTRATOR_DB}")
    uvicorn.run(
        "api.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
