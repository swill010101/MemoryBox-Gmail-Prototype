"""Read-only face/voice corroboration report for bounded I13 assignments."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memorybox.processing import face_voice_corroboration as fvc  # noqa: E402


def main() -> int:
    try:
        report = fvc.build_report_from_connection()
    except Exception as exc:
        report = {
            "ok": False,
            "read_only": True,
            "error": f"{type(exc).__name__}: {exc}",
            "policy_version": fvc.POLICY_VERSION,
            "policy_summary": fvc.POLICY_SUMMARY,
        }

    out_path = os.environ.get("MEMORYBOX_I13_CORROBORATION_OUTPUT", "").strip()
    if out_path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        report["output_file"] = str(path)

    print(json.dumps(report, indent=2, default=str))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
