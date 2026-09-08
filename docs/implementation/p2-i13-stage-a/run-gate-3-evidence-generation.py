"""Enqueue and process one Gate 3 evidence-generation transcription batch under active admission."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PLAN_PATH = ROOT / "docs/implementation/p2-i13-stage-a/bounded-manifest-proposal.json"


def load_manifest() -> list[dict]:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8-sig"))
    sources = plan["manifest"]["sources"]
    if len(sources) != 22:
        raise RuntimeError("Manifest must contain 22 sources.")
    return sources


def enqueue_manifest(*, force_requeue: bool = True) -> dict:
    from memorybox.speech.queue import enqueue_videos

    videos = [
        {
            "video_provider_key": source["provider_key"],
            "video_external_id": source["video_external_id"],
            "force_requeue": force_requeue,
        }
        for source in load_manifest()
    ]
    return enqueue_videos(videos=videos, enqueue_reason="transcribe", force_requeue=force_requeue)


def process_batch(*, max_items: int = 25) -> dict:
    from memorybox.ask.deps import build_video
    from memorybox.speech.process import process_queue

    return process_queue(video_provider=build_video(), max_items=max_items)


def admitted_queue_status(admission_id: str) -> dict:
    from memorybox.db import connection

    with connection() as conn:
        rows = conn.execute(
            """
            SELECT status, count(*)::int AS n
            FROM speech_queue_items
            WHERE i13_admission_id = %s::uuid
            GROUP BY status
            ORDER BY status
            """,
            (admission_id,),
        ).fetchall()
    by_status = {row["status"]: row["n"] for row in rows}
    return {"by_status": by_status, "total": sum(by_status.values())}


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if not argv or argv[0] not in {"enqueue", "process", "status"}:
        raise RuntimeError("Usage: run-gate-3-evidence-generation.py enqueue|process|status")

    action = argv[0]
    admission_id = (os.environ.get("MEMORYBOX_I13_ADMISSION_ID") or "").strip()
    if not admission_id:
        raise RuntimeError("MEMORYBOX_I13_ADMISSION_ID must be set.")
    if os.environ.get("MEMORYBOX_RECOGNITION_DRAIN") != "0":
        raise RuntimeError("MEMORYBOX_RECOGNITION_DRAIN must remain 0.")

    if action == "enqueue":
        if os.environ.get("MEMORYBOX_SPEECH_DRAIN") == "1":
            raise RuntimeError("Unset speech drain before enqueue.")
        result = enqueue_manifest(force_requeue=True)
        status = admitted_queue_status(admission_id)
        print(json.dumps({"ok": True, "action": "enqueue", **result, "queue": status}, indent=2))
        return 0

    if action == "process":
        result = process_batch(max_items=25)
        status = admitted_queue_status(admission_id)
        print(json.dumps({"ok": True, "action": "process", **result, "queue": status}, indent=2))
        return 0

    print(json.dumps({"ok": True, "action": "status", "queue": admitted_queue_status(admission_id)}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error_type": "validation_failed", "code": str(exc)}))
        raise SystemExit(2)
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__, "message": str(exc)}))
        raise SystemExit(2)
