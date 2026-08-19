# P2-I8B implementation note (definition is not rewritten)

**Status:** Build authorized 2026-08-19 (founder locks). Definition remains `docs/source/MBBS-P2_INCREMENT_8B_DEFINITION.md` (locked). This file records how the authorized build was implemented.

**Acceptance people:** Peggy George plus one additional known Person (harness: orthogonal second Person; FlightSim: `MEMORYBOX_P2_I8B_SECOND_PERSON_NAME` when set).

**Locks honored:**
- Existing Review box → Teach / Confirm is the Learn path. No new Person Learn UX.
- After Learn: scan the current video first, then enqueue other eligible videos by priority. No synchronous full-library rescan.
- I1/HVRT `face_appearance_moments` remain visible with `evidence_lineage=i1_hvrt`. I8B writes `method=mb_native_i8b` / `evidence_lineage=mb_native_i8b` only. Native rebuild deletes native rows for that person+video, never legacy rows.
- Exemplar v1: reject tiny/unusable crops, drop near-duplicates (cosine ≥ 0.97), prefer year then pose buckets, cap 16.
- Acceptance corpus: negative video + both-people video in harness; FlightSim scans HVRT inventory under `MEMORYBOX_VIDEO_MEDIA_ROOT` (`P:\photos\home videos`) and Immich VIDEO assets for the Person. Default positive clip: `deb5c1f8-4d01-457c-9637-185268e4b820`. Prove requires a native `mb_native_i8b` range.
- If an I1/HVRT Peggy clip was moved out of Home Videos, prove cannot reverse `vid-` hashes. Use `meta.immich_confirmed_asset.originalFileName` / `originalPath` and `meta.legacy_hvrt_clips`. Put that file back, then `.\startmb.cmd -Restart`.
- I9 speech/voice is not implemented here.

**APIs:** `POST /recognition/seed`, `POST /recognition/learn`, `GET /recognition/status`, `POST /recognition/appearances/correct` with `withdraw: true`. Teach `POST /people/{id}/map` also runs I8B Learn when a Review crop exists.

**Explore Learn tab:** Same owner Learn semantics as Review box → Teach (not a new Person Learn product). Opening Learn pauses the clip, turns on a face-box crosshair, lists known MemoryBox people with **Choose a person…** (nothing pre-selected), and enables **Learn** only after a crop and a person. **Box face** / a new drag starts the box over. After Learn, this video is rescanned first.

**Explore cards:** Native appearance moments take **date + filename + Immich thumbnail** from the originating asset (`/library/media/photo/{asset}`), not an empty undated purple tile.

**Archive pass (incremental overnight):** `POST /recognition/archive-pass` or `python -m memorybox recognition-archive-pass [--seed-immich]` does **not** restart everyone.

- **New Immich name** with enough still faces → seed exemplars for that Person → queue **all** Home Videos + Immich VIDEO assets for that Person only.
- **Immich merge** (or more stills on a mapped Person) → that Person’s exemplar catalog changes → that Person is rescanned against all video sources that night.
- **Unchanged People** are skipped (no re-embed, no re-queue). Brand-new video files still get `new_video`.
- **`--full`** / `full=true` ignores watermarks and rescans everyone.

Serve drains `recognition_queue` one video at a time when `MEMORYBOX_P1_RUNTIME_HOST=1`. This is I8B (people clips for I9), not speech. Owner Learn still scans the current clip in-request, then enqueues other videos for that Person only.
