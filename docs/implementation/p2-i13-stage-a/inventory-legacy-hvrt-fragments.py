"""Read-only inventory of legacy HVRT 0.5–2s fragment moments on the accepted manifest.

Does not modify database, media, Gallery or retrieval. Off-manifest sources are
reported separately and excluded from reconciliation apply.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memorybox.recognition.fragment_reconciliation import (  # noqa: E402
    load_manifest_sources,
    manifest_source_ids,
    matches_base_eligibility,
    moment_duration_sec,
    preview_projection,
)


def main() -> int:
    if not os.environ.get("MEMORYBOX_DATABASE_URL", "").strip():
        print(json.dumps({"ok": False, "error": "MEMORYBOX_DATABASE_URL absent"}))
        return 2
    import psycopg
    from psycopg.rows import dict_row

    manifest = load_manifest_sources()
    manifest_ids = sorted(manifest_source_ids())
    by_id = {s["video_external_id"]: s for s in manifest}
    with psycopg.connect(
        os.environ["MEMORYBOX_DATABASE_URL"],
        connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=60000 -c lock_timeout=3000",
        row_factory=dict_row,
    ) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        snapshot = conn.execute(
            """
            SELECT current_database() AS database,
                   transaction_timestamp() AS captured_at,
                   current_setting('transaction_read_only') AS read_only
            """
        ).fetchone()
        rows = conn.execute(
            """
            SELECT id::text, person_id::text, video_provider_key, video_external_id,
                   start_sec, end_sec, method, status, authority, confirmation_state,
                   processing_run_id::text, model_version, evidence_lineage,
                   observation_ids, created_at
            FROM public.face_appearance_moments
            WHERE video_provider_key = 'hvrt'
              AND (end_sec - start_sec) >= 0.5
              AND (end_sec - start_sec) <= 2.0
            ORDER BY video_external_id, person_id, start_sec, id
            """
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["duration_sec"] = moment_duration_sec(item)
        item["on_manifest"] = str(item["video_external_id"]) in by_id
        item["manifest_filename"] = (by_id.get(str(item["video_external_id"])) or {}).get("relative_path")
        item["eligible_for_reconciliation"] = matches_base_eligibility(item) and item["on_manifest"]
        items.append(item)
    eligible = [r for r in items if r["eligible_for_reconciliation"]]
    off_manifest = [r for r in items if not r["on_manifest"]]
    preview = preview_projection([dict(r) for r in eligible])
    proposed = {}
    for row in eligible:
        key = (row["video_external_id"], row["processing_run_id"])
        proposed.setdefault(
            key,
            {
                "video_external_id": row["video_external_id"],
                "processing_run_id": row["processing_run_id"],
                "relative_path": row.get("manifest_filename"),
                "moment_count": 0,
                "person_ids": set(),
            },
        )
        proposed[key]["moment_count"] += 1
        proposed[key]["person_ids"].add(row["person_id"])
    proposed_runs = []
    for (_src, _run), meta in sorted(proposed.items()):
        proposed_runs.append(
            {
                "video_external_id": meta["video_external_id"],
                "processing_run_id": meta["processing_run_id"],
                "relative_path": meta["relative_path"],
                "moment_count": meta["moment_count"],
                "person_count": len(meta["person_ids"]),
            }
        )
    report = {
        "ok": True,
        "read_only": True,
        "snapshot": snapshot,
        "manifest_id": "p2-i13-flightsim-22",
        "manifest_source_count": len(manifest_ids),
        "limits": [
            "Manifest-scoped reconciliation only; not archive-wide Learn or recognition",
            "Off-manifest rows inventoried but excluded from apply",
            "No source video, observation or provenance mutation",
        ],
        "counts": {
            "total_half_to_two_sec_rows": len(items),
            "on_manifest_rows": sum(1 for r in items if r["on_manifest"]),
            "off_manifest_rows": len(off_manifest),
            "eligible_fragment_rows": len(eligible),
        },
        "preview": preview,
        "proposed_allowlist_extensions": proposed_runs,
        "rows": items,
    }
    out = os.environ.get("MEMORYBOX_I13_FRAGMENT_INVENTORY_OUTPUT", "").strip()
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        report["output_file"] = str(path)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
