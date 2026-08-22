#!/usr/bin/env python3
"""Validate local config/mem_questions.json and print a review report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application"))

from marvin_capture import config as cfgmod  # noqa: E402
from marvin_capture.mem_bank import validate_questions_file  # noqa: E402


def main() -> int:
    cfg = cfgmod.load_config()
    path = (cfg.get("mem_bank") or {}).get("questions_file") or str(
        ROOT / "config" / "mem_questions.json"
    )
    report = validate_questions_file(path)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
