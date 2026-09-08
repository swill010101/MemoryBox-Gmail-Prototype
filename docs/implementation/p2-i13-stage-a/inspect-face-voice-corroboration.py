"""Read-only face/voice corroboration report for bounded I13 assignments."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

POLICY_VERSION = "i13-fvc-v1"
POLICY_SUMMARY = (
    "Face and voice evidence remain independent. Corroboration reports same-source "
    "interval overlap and bounded voice-pilot outcomes only; it never merges "
    "confidence or replaces owner review."
)
FLIGHTSIM_PYTHON = (
    r"C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe"
)


def _load_module():
    try:
        from memorybox.processing import face_voice_corroboration as fvc

        return fvc
    except ModuleNotFoundError as exc:
        missing = exc.name or str(exc)
        hint = {
            "ok": False,
            "read_only": True,
            "error": f"{type(exc).__name__}: {exc}",
            "policy_version": POLICY_VERSION,
            "policy_summary": POLICY_SUMMARY,
            "flightsim_hint": (
                "On FlightSim use the verified TitaNet tool-release Python, not bare python. "
                "Load the deployment env first so MEMORYBOX_DATABASE_URL is set."
            ),
            "example_command": (
                f"& '{FLIGHTSIM_PYTHON}' -B "
                r"docs\implementation\p2-i13-stage-a\inspect-face-voice-corroboration.py"
            ),
        }
        if missing == "psycopg":
            raise SystemExit(json.dumps(hint, indent=2)) from exc
        raise


def main() -> int:
    fvc = _load_module()
    if not os.environ.get("MEMORYBOX_DATABASE_URL", "").strip():
        report = {
            "ok": False,
            "read_only": True,
            "error": "MEMORYBOX_DATABASE_URL is absent; load the configured FlightSim deployment env first.",
            "policy_version": POLICY_VERSION,
            "policy_summary": POLICY_SUMMARY,
            "flightsim_hint": "Use the same shell/env as `python -m memorybox serve`.",
        }
        print(json.dumps(report, indent=2, default=str))
        return 2

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
