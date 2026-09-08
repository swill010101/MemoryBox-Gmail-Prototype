"""Synthetic tests for bounded face/voice corroboration policy."""
from __future__ import annotations

import unittest
from uuid import uuid4

from memorybox.processing import face_voice_corroboration as fvc
from memorybox.processing.i13_canonical_assignments import CANONICAL_EIGHT


class Pure(unittest.TestCase):
    def test_interval_overlap(self):
        self.assertTrue(fvc.intervals_overlap(1.0, 3.0, 2.0, 4.0))
        self.assertFalse(fvc.intervals_overlap(1.0, 2.0, 2.0, 3.0))
        self.assertFalse(fvc.intervals_overlap(5.0, 6.0, 1.0, 2.0))

    def test_corroborated_when_same_person_face_overlaps(self):
        person = str(uuid4())
        faces = [{"person_id": person, "start_sec": 1.0, "end_sec": 2.0}]
        result = fvc.classify_corroboration(
            voice_person_id=person,
            speaker_state="person",
            matrix_role="eugene_held_out",
            face_moments=faces,
        )
        self.assertEqual(result["status"], "corroborated")

    def test_off_camera_voice_only_is_expected(self):
        person = str(uuid4())
        result = fvc.classify_corroboration(
            voice_person_id=person,
            speaker_state="person",
            matrix_role="tom_offcamera_held_out",
            face_moments=[],
        )
        self.assertEqual(result["status"], "off_camera_voice_only")
        self.assertTrue(result["expected_off_camera"])

    def test_face_other_person_is_transparent_conflict(self):
        voice_person = str(uuid4())
        other = str(uuid4())
        faces = [{"person_id": other, "start_sec": 0.0, "end_sec": 1.0}]
        result = fvc.classify_corroboration(
            voice_person_id=voice_person,
            speaker_state="person",
            matrix_role="eugene_held_out",
            face_moments=faces,
        )
        self.assertEqual(result["status"], "face_other_person")

    def test_voice_unknown_lists_face_independently(self):
        other = str(uuid4())
        faces = [{"person_id": other, "start_sec": 0.0, "end_sec": 1.0}]
        result = fvc.classify_corroboration(
            voice_person_id=None,
            speaker_state="unknown",
            matrix_role="uncertain_no_match",
            face_moments=faces,
        )
        self.assertEqual(result["status"], "voice_unknown")
        self.assertEqual(result["face_overlap_count"], 1)

    def test_voice_evidence_lookup(self):
        annotation_id = "abc-annotation"
        pilot_rows = [
            {
                "admission_id": "admission-1",
                "stale": False,
                "state": "stopped",
                "created_at": "2026-09-08",
                "thresholds": {"match": 0.45},
                "payload": {"results": [{"key": "H1", "decision": "match", "score": 0.63}]},
                "spans": [
                    {
                        "key": "H1",
                        "annotation_id": annotation_id,
                        "source_id": "vid-test",
                        "start": 1.0,
                        "end": 2.0,
                    }
                ],
            }
        ]
        found = fvc._voice_evidence_for_annotation(annotation_id, pilot_rows)
        self.assertIsNotNone(found)
        self.assertEqual(found["decision"], "match")
        self.assertEqual(found["span_key"], "H1")

    def test_canonical_eight_pins_eight_assignments(self):
        self.assertEqual(len(CANONICAL_EIGHT), 8)
        keys = {item["key"] for item in CANONICAL_EIGHT}
        self.assertIn("O1", keys)
        self.assertIn("N1", keys)


if __name__ == "__main__":
    unittest.main()
