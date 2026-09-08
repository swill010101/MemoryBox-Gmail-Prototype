"""Pinned canonical eight owner voice assignments for bounded I13 acceptance."""
from __future__ import annotations

EUGENE = "b67708d8-0262-404d-a230-2cc99900cea4"
TOM = "33509a4c-0869-458a-b0b9-35a669aace16"
PROVIDER = "hvrt"

CATEGORIES = (
    "eugene_training",
    "eugene_held_out",
    "tom_training",
    "tom_offcamera_held_out",
    "uncertain_no_match",
)

CANONICAL_EIGHT = [
    {
        "key": "T1",
        "matrix_role": "eugene_training",
        "pilot_role": "training",
        "annotation_id": "d5a3d050-76d6-446e-91d4-ff89986856cb",
        "source_id": "vid-da41273dbd9ac4bb",
        "start": 138.72,
        "end": 144.66,
        "person_id": EUGENE,
        "notes": "Original Eugene training; reference retired — admission 1039c733 stale",
    },
    {
        "key": "H1",
        "matrix_role": "eugene_held_out",
        "pilot_role": "held_out",
        "annotation_id": "f47ee4ec-6b28-442a-81b2-152fbe8f45e2",
        "source_id": "vid-c57dbd21f993f6d1",
        "start": 325.22,
        "end": 345.56,
        "person_id": EUGENE,
        "notes": "Eugene positive held-out in original Eugene pilot",
    },
    {
        "key": "U1-clear",
        "matrix_role": "eugene_held_out",
        "pilot_role": "held_out",
        "annotation_id": "5651a4bd-dffd-4d26-a985-16e8abaf37c2",
        "source_id": "vid-c57dbd21f993f6d1",
        "start": 129.64,
        "end": 138.72,
        "person_id": EUGENE,
        "notes": "Clear portion of former U1 window; remainder unreviewed",
    },
    {
        "key": "O1",
        "matrix_role": "tom_offcamera_held_out",
        "pilot_role": "held_out",
        "annotation_id": "3fa1c4e1-d8a6-423f-9c9b-1a229d550945",
        "source_id": "vid-c57dbd21f993f6d1",
        "start": 152.24,
        "end": 158.34,
        "person_id": TOM,
        "notes": "Owner-confirmed off-camera Tom; Tom pilot positive held-out",
    },
    {
        "key": "T2",
        "matrix_role": "tom_training",
        "pilot_role": "training",
        "annotation_id": "5e106e50-76ce-4fb2-8f62-0083119154cc",
        "source_id": "vid-da41273dbd9ac4bb",
        "start": 37.12,
        "end": 42.4,
        "person_id": TOM,
        "notes": "Tom training reference for Tom/N1/Patio/reprocessing/overlap controls",
    },
    {
        "key": "N1",
        "matrix_role": "uncertain_no_match",
        "pilot_role": "held_out",
        "annotation_id": "74cc9646-82db-4899-960d-f795f691c524",
        "source_id": "vid-c015e0fe07414fcc",
        "start": 0.0,
        "end": 6.74,
        "person_id": None,
        "speaker_state": "unknown",
        "notes": "TV announcer; Unknown — never assign a Person",
    },
    {
        "key": "R1-gs2-fresh",
        "matrix_role": "eugene_training",
        "pilot_role": "training",
        "annotation_id": "3eb88a19-7249-4ce6-b976-e3066daf205a",
        "source_id": "vid-34df63e61b949890",
        "start": 26.3,
        "end": 34.78,
        "person_id": EUGENE,
        "notes": "Current Eugene training after T1 retirement; reused in overlap pilot",
    },
    {
        "key": "H1-gs2-held-out",
        "matrix_role": "eugene_held_out",
        "pilot_role": "held_out",
        "annotation_id": "5d87a6ac-d512-4504-857e-ec8589e8bd78",
        "source_id": "vid-34df63e61b949890",
        "start": 86.42,
        "end": 105.44,
        "person_id": EUGENE,
        "notes": "Lifecycle Eugene held-out on grandpa 002",
    },
]

CATEGORY_PILOT_EVIDENCE = {
    "eugene_training": [
        {"admission_id": "66fb93af-92a9-4ef1-b3e6-c0f700e89276", "training_key": "R1-gs2-fresh", "stale": False},
        {"admission_id": "1039c733-2149-40b2-b027-97058e032af3", "training_key": "T1", "stale": True},
    ],
    "eugene_held_out": [
        {"admission_id": "1039c733-2149-40b2-b027-97058e032af3", "keys": ["H1", "U1-clear"], "stale": True},
        {"admission_id": "66fb93af-92a9-4ef1-b3e6-c0f700e89276", "keys": ["H1-gs2-held-out"], "stale": False},
        {"admission_id": "339b3a14-5069-4554-846f-dc84d6745c00", "keys": ["E2-1532-overlap-held-out"], "stale": False},
        {"admission_id": "f59050d5-cb4b-4ff7-beee-609b28f7af61", "keys": ["E3-patio-held-out"], "stale": False},
    ],
    "tom_training": [
        {"admission_id": "9e0a2605-8bfc-4ec7-aa6e-501f9bca7cea", "training_key": "T2", "stale": False},
    ],
    "tom_offcamera_held_out": [
        {"admission_id": "9e0a2605-8bfc-4ec7-aa6e-501f9bca7cea", "keys": ["O1"], "decision": "match", "score": 0.487, "stale": False},
    ],
    "uncertain_no_match": [
        {"admission_id": "46cb1d21-b464-4bc4-bf7c-7d0de0202ca6", "keys": ["N1"], "decision": "no_match", "stale": False},
        {"admission_id": "339b3a14-5069-4554-846f-dc84d6745c00", "keys": ["N1-TV-announcer-unknown"], "decision": "no_match", "stale": False},
    ],
}
