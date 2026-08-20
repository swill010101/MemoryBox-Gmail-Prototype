# P2-I9 implementation note (definition is not rewritten)

**Status:** Build authorized 2026-08-20. Definition remains `docs/source/MBBS-P2_INCREMENT_9_DEFINITION.md`.

**Locks honored:**
- I8B recognition modules are unchanged (no speech in `recognition/scan.py` / `learn.py`).
- Transcription queue is **per video**. `owner_learn` jobs are **that Person only**.
- Video speech only. Capture-journal STT is not Spoken Moments.
- Words, anonymous turns, and Spoken Moments are separate tables.
- Diarization is local: pyannote when installed, otherwise `pause_gap_local` (never labeled as pyannote).
- Owner Learn is existing Choose Person + Learn on a transcript span → source-audio / harness vector → voice exemplar. Current video is scored first; other videos enqueue for that Person.
- Face appearance overlap is never treated as speaker proof.
- Ask `saying "…"`, `talking`, `talking about` retrieve stored transcript evidence (SQL + optional Qdrant). Residual chat does not invent passages.
- ACR-P2-001-A continue-on-tape is not built.

**Ops:** Archive Health **Transcribe new home videos** → `POST /speech/archive-pass` (default 500). Inventory is the same as face: HVRT + `MEMORYBOX_VIDEO_MEDIA_ROOT` (`P:\photos\home videos`) + `MEMORYBOX_VIDEO_SOURCE_ROOTS` + Immich VIDEO. CLI: `python -m memorybox speech-archive-pass`. Serve drains `speech_queue_items` when `MEMORYBOX_P1_RUNTIME_HOST=1` (or `MEMORYBOX_SPEECH_DRAIN=1`).

**Ask compile (2026-08-20):** `{Name} talking` and `show me videos of {Name} talking` must resolve Person and retrieve Spoken Moments. `show me videos of {Name}` (no talking) stays I8B video gallery, not spoken-only.

**Gallery lock (2026-08-20, Tom):** Voice identifies that a Person is speaking **in a video**. Ask/Explore shows **one card per source file**. Only face recognition may mint start:end clips inside a video. Transcript timing stays in Video Detail Text (click-to-seek), not as extra gallery cards.

**Prove:** `python -m memorybox prove-p2-i9`
