# P2-I8B implementation note (definition is not rewritten)

**Status:** Build authorized 2026-08-19 (founder locks). Definition remains `docs/source/MBBS-P2_INCREMENT_8B_DEFINITION.md` (locked). This file records how the authorized build was implemented.

**Acceptance people:** Peggy George plus one additional known Person (harness: orthogonal second Person; FlightSim: `MEMORYBOX_P2_I8B_SECOND_PERSON_NAME` when set).

**Locks honored:**
- Existing Review box → Teach / Confirm is the Learn path. No new Person Learn UX.
- After Learn: scan the current video first, then enqueue other eligible videos by priority. No synchronous full-library rescan.
- I1/HVRT `face_appearance_moments` remain visible with `evidence_lineage=i1_hvrt`. I8B writes `method=mb_native_i8b` / `evidence_lineage=mb_native_i8b` only. Native rebuild deletes native rows for that person+video, never legacy rows.
- Exemplar v1: reject tiny/unusable crops, drop near-duplicates (cosine ≥ 0.97), prefer year then pose buckets, cap 16.
- Acceptance corpus: negative video + both-people video in harness; FlightSim scans HVRT inventory under `MEMORYBOX_VIDEO_MEDIA_ROOT` (`P:\photos\home videos` via `startmb` / `config/video_worker.env`). FlightSim prove requires at least one `mb_native_i8b` appearance range (queue completion alone is not enough).
- I9 speech/voice is not implemented here.

**APIs:** `POST /recognition/seed`, `POST /recognition/learn`, `GET /recognition/status`, `POST /recognition/appearances/correct` with `withdraw: true`. Teach `POST /people/{id}/map` also runs I8B Learn when a Review crop exists.

**Prove:** `python -m memorybox prove-p2-i8b` (harness). FlightSim: `MEMORYBOX_P1_RUNTIME_HOST=1 python -m memorybox prove-p2-i8b --flightsim`. Owner ACCEPTED remains a manual pass.
