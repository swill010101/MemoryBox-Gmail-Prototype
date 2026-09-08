# Face/voice corroboration — I13 implementation note

**Date:** 2026-09-08  
**Authority:** Existing I13 scope (`MBPRD-P2-I13` §8 Voice + architectural requirement: independent face/voice evidence with transparent corroboration). No new product decision required.

## Problem

I13 requires face and voice evidence to remain **independent**, with **transparent corroboration** when both exist on the same source interval. Prior work proved bounded voice pilots and stored face appearance moments separately; there was no read-only report tying them together for owner review.

## Policy (v1)

| Rule | Detail |
|---|---|
| Independence | Face moments and voice-pilot outcomes are never merged into a single confidence score. |
| Scope | Canonical **eight** owner-reviewed voice assignments on the bounded 22-source manifest only. |
| Overlap | Same `provider_key` + `source_id` + time interval overlap query on `face_appearance_moments`. |
| Voice side | Latest bounded voice-pilot result matching each assignment's `annotation_id`. |
| Off-camera | `tom_offcamera_held_out` (O1): absence of same-Person face overlap is **expected** (`off_camera_voice_only`). |
| Unknown voice | N1: no Person assignment; face evidence listed independently (`voice_unknown`). |
| Conflicts | Overlapping face for a **different** Person is reported transparently (`face_other_person`); neither modality is overridden. |

## Implementation

| Component | Path |
|---|---|
| Canonical assignments | `memorybox/processing/i13_canonical_assignments.py` |
| Corroboration logic + report | `memorybox/processing/face_voice_corroboration.py` |
| Read-only API | `GET /review/face-voice-corroboration` |
| Review UI section | `memorybox/review/static/review.html` |
| CLI inspector | `docs/implementation/p2-i13-stage-a/inspect-face-voice-corroboration.py` |
| Tests | `tests/test_i13_face_voice_corroboration.py` |

## Explicitly out of scope

- Archive Outcomes C/D/E (founder rejected 2026-09-08)
- Combined Learn score fusion or automatic adjudication
- New voice pilots or face processing runs
- Generalized accuracy claims beyond pinned bounded evidence

## Verification

1. Run unit tests: `python -m unittest tests.test_i13_face_voice_corroboration -v`
2. On FlightSim (read-only): `python docs/implementation/p2-i13-stage-a/inspect-face-voice-corroboration.py`
3. Review UI: `/review/ui` → **Face/voice corroboration** section

Optional JSON export (E: path only):

```powershell
$env:MEMORYBOX_I13_CORROBORATION_OUTPUT = "E:\MemoryBox-dev\p2-i13-stage-a\docs\implementation\p2-i13-stage-a\face-voice-corroboration-report.json"
python docs/implementation/p2-i13-stage-a/inspect-face-voice-corroboration.py
```
