# HVRT — Learn face rescan + voice recognition

**Status:** Approved (Tom go 2026-08-02) — implemented in `build learn-face-voice`

## Problem
Learn only indexed exemplars. Enrolling Eugene in Grandpa Sessions 001 did not create AI hits in 002.

## Success
- Learn **rescans videos** with InsightFace against gallery centroids → `face_appearances`
- Learn **scores transcript spans** against enrolled voice clips → AI `person_voice` annotations
- Owner marks still win via rescoring

## Modules
- [`hvrt/face_learn.py`](../hvrt/face_learn.py)
- [`hvrt/voice_learn.py`](../hvrt/voice_learn.py)
- Wired from [`hvrt/learning.py`](../hvrt/learning.py)

## Desktop deps
- Faces: same `.venv` as `process_videos` (insightface)
- Voice: `pip install speechbrain torch torchaudio` (+ ffmpeg)
