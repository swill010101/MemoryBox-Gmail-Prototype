"""Read-only preflight for Gate 3 evidence-generation (transcription-only); no writes."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PLAN_PATH = ROOT / "docs/implementation/p2-i13-stage-a/bounded-manifest-proposal.json"
EXPECTED_PLAN_SHA = "330c2f90fa0de3b319097d17f31ca5dfabe6bd57b469a1a033a79e3851259b35"


def main() -> int:
    if os.environ.get("MEMORYBOX_RECOGNITION_DRAIN") != "0":
        raise RuntimeError("MEMORYBOX_RECOGNITION_DRAIN must be 0.")
    if os.environ.get("MEMORYBOX_SPEECH_DRAIN") != "0":
        raise RuntimeError("MEMORYBOX_SPEECH_DRAIN must be 0.")
    if os.environ.get("MEMORYBOX_I13_ADMISSION_ID"):
        raise RuntimeError("MEMORYBOX_I13_ADMISSION_ID must be unset for preflight.")

    from memorybox.processing.scope import preview

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8-sig"))
    summary = preview(plan)
    if summary["purpose"] != "evidence_generation":
        raise RuntimeError("Plan purpose must be evidence_generation.")
    if plan["lanes"] != ["transcribe"]:
        raise RuntimeError("Plan must be transcribe-only.")
    if summary["plan_sha256"] != EXPECTED_PLAN_SHA:
        raise RuntimeError("Plan SHA mismatch; stop and reconcile with reviewed artifact.")
    if summary["work_items"] != 22:
        raise RuntimeError("Expected exactly 22 transcription work items.")

    manifest = plan["manifest"]
    if len(manifest["sources"]) != 22:
        raise RuntimeError("Manifest must contain 22 sources.")

    from memorybox.db import connection

    with connection() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        active = conn.execute(
            """
            SELECT count(*)::int AS n
            FROM i13_processing_admissions
            WHERE plan_json->>'purpose' = 'evidence_generation'
              AND state IN ('registered', 'started')
            """
        ).fetchone()["n"]
        if active:
            raise RuntimeError("An evidence_generation admission is already active; preserve it and stop.")

        missing = []
        for source in manifest["sources"]:
            provider = source["provider_key"]
            vid = source["video_external_id"]
            row = conn.execute(
                """
                SELECT count(*)::int AS words
                FROM speech_transcript_words
                WHERE video_provider_key = %s AND video_external_id = %s
                """,
                (provider, vid),
            ).fetchone()
            if row["words"] <= 0:
                missing.append(vid)

    if missing:
        raise RuntimeError(
            f"{len(missing)} manifest source(s) lack stored words; reconcile before Gate 3: {missing[:3]}"
        )

    print(
        json.dumps(
            {
                "ok": True,
                "mode": "check_only",
                "purpose": summary["purpose"],
                "work_items": summary["work_items"],
                "max_attempts": summary["max_attempts"],
                "plan_sha256": summary["plan_sha256"],
                "sources_with_words": 22,
                "expected_runtime": "noop_transcribe_for_existing_words",
                "database_writes": False,
                "admission_created": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_type": "validation_failed",
                    "code": str(exc),
                    "message": "Gate 3 preflight failed; no media or database writes occurred.",
                }
            )
        )
        raise SystemExit(2)
    except Exception as exc:
        detail = str(exc)
        if isinstance(exc, ModuleNotFoundError):
            detail = f"missing_module:{getattr(exc, 'name', detail)}"
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "message": detail,
                    "hint": "Use .titanet-venv under the verified tool release, not bare python.",
                }
            )
        )
        raise SystemExit(2)
