"""Legacy HVRT fragment reconciliation gate — offline tests."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from memorybox.recognition.fragment_reconciliation import (
    PILOT_RUN,
    PILOT_SOURCE,
    is_reconcilable_fragment,
    manifest_source_ids,
    preview_projection,
)
from memorybox.recognition.source_moments import project_source_cards


def moment_row(
    *,
    vid: str = PILOT_SOURCE,
    run: str = PILOT_RUN,
    start: float = 0.5,
    person: str = "person-a",
    moment_id: str = "m1",
) -> dict:
    return {
        "id": moment_id,
        "person_id": person,
        "video_provider_key": "hvrt",
        "video_external_id": vid,
        "start_sec": start,
        "end_sec": start + 0.5,
        "method": "mb_native_i8b",
        "status": "accepted",
        "authority": "ai_inferred",
        "confirmation_state": "system_associated",
        "processing_run_id": run,
        "model_version": "sample-model",
    }


def gallery_hit(row: dict) -> dict:
    return {
        "provider_key": "hvrt",
        "video_external_id": row["video_external_id"],
        "start_sec": row["start_sec"],
        "end_sec": row["end_sec"],
        "mb_person_id": row["person_id"],
        "id": row["id"],
        "appearance_evidence": {
            "id": row["id"],
            "processing_run_id": row["processing_run_id"],
            "method": row["method"],
            "status": row["status"],
            "authority": row["authority"],
            "confirmation_state": row["confirmation_state"],
            "model_version": row["model_version"],
            "observation_ids": [f"obs-{row['id']}"],
        },
    }


class FragmentReconciliationGateTests(unittest.TestCase):
    def test_manifest_scoped_not_archive_wide(self):
        self.assertEqual(len(manifest_source_ids()), 22)
        off = moment_row(vid="vid-off-manifest-not-in-list", moment_id="off")
        self.assertNotIn(off["video_external_id"], manifest_source_ids())

    def test_preview_reports_suppressed_presentations(self):
        rows = [moment_row(start=t, moment_id=f"m-{t}") for t in [0.5, 10.5, 20.5, 40.5, 50.5]]
        preview = preview_projection(rows)
        self.assertEqual(preview["before_gallery_cards"], 5)
        self.assertEqual(preview["after_source_cards"], 1)
        self.assertEqual(preview["suppressed_duplicate_presentations"], 4)
        self.assertEqual(preview["retained_moment_rows"], 5)

    def test_project_source_cards_never_leaves_half_second_sample_cards(self):
        rows = [moment_row(start=t, moment_id=f"m-{t}") for t in [0.5, 10.5, 20.5, 30.5, 40.5, 60.5, 70.5]]
        hits = [gallery_hit(r) for r in rows]
        cards = project_source_cards(hits)
        self.assertEqual(len(cards), 1)
        self.assertEqual(len(cards[0]["source_moments"]), 7)
        for card in cards:
            self.assertNotEqual(card.get("duration_sec"), 0.5)

    def test_off_manifest_and_wrong_run_not_reconciled(self):
        self.assertFalse(
            is_reconcilable_fragment(
                "vid-off-manifest",
                "hvrt",
                {"processing_run_id": PILOT_RUN, "method": "mb_native_i8b", "status": "accepted",
                 "authority": "ai_inferred", "confirmation_state": "system_associated"},
                start_sec=0.5,
                end_sec=1.0,
            )
        )
        self.assertFalse(
            is_reconcilable_fragment(
                PILOT_SOURCE,
                "hvrt",
                {"processing_run_id": "unreviewed-run", "method": "mb_native_i8b", "status": "accepted",
                 "authority": "ai_inferred", "confirmation_state": "system_associated"},
                start_sec=0.5,
                end_sec=1.0,
            )
        )

    def test_allowlist_json_is_manifest_scoped(self):
        raw = json.loads(
            (Path(__file__).resolve().parents[1] / "memorybox/recognition/data/legacy_hvrt_fragment_allowlist.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(raw["manifest_id"], "p2-i13-flightsim-22")
        self.assertIn("not archive", raw.get("limits", "").lower())


if __name__ == "__main__":
    unittest.main()
