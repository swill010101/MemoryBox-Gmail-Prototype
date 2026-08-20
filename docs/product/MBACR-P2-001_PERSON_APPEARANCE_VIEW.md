# MBACR-P2-001 — Person appearance view (start → stop, then end)

**ID:** ACR-P2-001  
**Status:** PARKED · not authorized to build · does not reopen I8B  
**Date parked:** 2026-08-20  
**Owner:** Tom Will  
**Depends:** P2-I8B Person-Seeded Video Recognition (ranges + gallery poster at `start_sec` already on the card)  
**Does not start:** extracted/physical clips · face-crop-only thumbs · RANGE_GAP / HVRT 60s merge · I9 speech · continue-on-tape (see follow-on)

**Authority:** Owner 2026-08-20 — prefer HVRT-style *visit* playback over “jump into a longer tape and keep rolling,” without cutting a new file. Always a **view into the original**.

Related: [I8B definition](../source/MBBS-P2_INCREMENT_8B_DEFINITION.md) §5.4–5.5 (immutable source; appearance ranges; return to source at start offset) · [I8B implementation](MBBS-P2_INCREMENT_8B_IMPLEMENTATION.md) · [P2 backlog](MBBS_P2_BACKLOG_PLANNING.md)

---

## 1. Problem

I8B Explore opens the **full original** and seeks to the appearance `start_sec`. Playback **ignores `end_sec`**. The card already knows the visit (`start_sec` / `end_sec`; detail like `12.0s–18.5s`). The gallery **poster is already specified** as the frame at `start_sec` (`/library/media/video-poster?t=`), not tape `00:00`.

The owner wants the **Person visit** to play like an HVRT window: start at the recognition start, stop at the recognition end, **then end**. No real, physical cut or derived clip file.

## 2. Success criteria (when authorized)

On FlightSim, for a Peggy (or second-person) native appearance card:

1. Gallery thumb is the **first frame of the appearance** (`t = start_sec` on the original). Not the first frame of the file unless `start_sec` is ~0.
2. Opening the card seeks to `start_sec` on the **same original** (Immich UUID or MB-owned `vid-*`).
3. Playback **pauses at `end_sec`** (visit ended). Native scrubber must not silently treat the rest of the tape as this card’s clip — clamp seeking to `[start_sec, end_sec]` for this view.
4. No new media asset, no ffmpeg extract, no new inventory id, no Immich writeback.
5. Learn / correction / I9 tape timestamps still use **source** offsets, not a clip-local 00:00.

Harness: Explore player honors `item.start_sec` and `item.end_sec` already present on video cards.

## 3. Scope

### In (this ACR)

- Explore (and only if already sharing the binder: Review) **appearance view**: play `[start_sec, end_sec]`, then end.
- Gallery / modal poster = appearance **start** frame (fix any cards still using file t=0 or Immich still).
- Clamp `seeking` / `timeupdate` so this view cannot wander past stop.

### Out (this ACR)

- Physical/derived clip files; new `vid-*` / Immich assets.
- Face-only cropped thumbs (full-frame poster at `start_sec` only).
- Changing I8B `RANGE_GAP_SEC` (8s) or HVRT 60s merge.
- Recognition, queue, Archive Health jobs, overnight.
- **Continue on tape** after stop (parked — see §6).

## 4. Constraints

- Source video remains immutable original evidence (I8B §5.4 / §7.6).
- Appearance ranges remain derived bookmarks (`start_sec` / `end_sec` already stored).
- I8B §5.5: opening must still return to the source at or near the start offset — this ACR *is* that return, plus stop.
- Do not build until Tom authorizes this ACR (or absorbs it into a named increment). Do not slip it into I8B acceptance or I9 speech.

## 5. Build plan (when authorized — sequencing only)

1. Confirm every Person video card carries numeric `start_sec`, `end_sec`, and poster `t=start_sec`.
2. `bindExploreVideoPlayer`: seek start; pause at end; clamp seek.
3. Stray poster URLs: same `video-poster?t=start_sec` (Immich and `vid-*`).
4. Owner pass: Peggy card plays the visit and stops; tape file unchanged on disk.

## 6. Work list — parked, not now

| ID | Item | Notes |
|----|------|--------|
| **ACR-P2-001-A** | **Continue on tape** | After stop, owner can keep playing the original past `end_sec` (Learn a later face, watch the rest of the party). **On the work list. Not in this ACR’s build.** Do not invent a second player or a derived file to do this. |

## 7. Risk (this slice only)

Low. Explore player + poster URL consistency. No recognition schema. Learn on this card is a frame **inside the visit** (or the last frame if it ended) until 001-A exists.

---

**Stop.** PARKED 2026-08-20. No build. Continue-on-tape is **ACR-P2-001-A** (later).
