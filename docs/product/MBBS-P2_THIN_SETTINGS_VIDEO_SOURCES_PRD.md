# MBBS — Thin Settings + multi-source video (follow-on)

**Status:** BUILD (Tom 2026-08-14 — “yes, do the PR”; video from any known MB source; quick path change + start thin Settings)  
**Date:** 2026-08-14  
**Owner:** Tom  
**Branch:** `cursor/p2-video-sources-settings-3061` (from I6)  
**Depends:** P2-I6 shipped · P2-I5 ACCEPTED  
**Does not reopen:** I5 Immich portrait **P2-BL-I5-01** · I6 kinship

## Problem

Explore / Person Video only showed **HVRT Home Videos moments**. Immich `VIDEO` assets were fetched on the photo channel, then hard-typed as photos, so the Video filter and video modal never saw them.

Separately, the physical HVRT file root is `MEMORYBOX_VIDEO_MEDIA_ROOT` (startmb loads `config/video_worker.env`). Changing that folder meant editing env and restarting. Mature Settings (CAP-P2-023 / P2-SET-01) is **P2-I13** — too late for a path we have already decided.

## Success criteria

- Explore and Person Explorer Video include **Immich library clips** and **HVRT moments** when both sources have hits.
- Opening an Immich clip plays via `/library/media/immich-video/{id}` (not Review paused-frame).
- Owner can set/clear the Home Videos folder in `/settings/ui` without waiting for I13.
- Saved Settings override env (FlightSim always loads `video_worker.env`; otherwise Settings would never win).
- Env remains the bootstrap default when Settings is empty/cleared.
- Mature Settings is **not** built.

## Scope IN

- Preserve Immich `asset_kind`; map VIDEO → Explore `type: video`
- Playback proxy with Range forwarding
- Thin Settings: one card, Home Videos library path, GET/POST `/settings/video-media-root`
- Persist to `memorybox_runtime_settings` + sidecar `derived_dir/media_root.txt` for the sibling worker
- Worker + Archive Health scan use the same resolver

## Scope OUT

- Mature Settings (providers, processing, recognition, confidence, archive catalog) — **I13 / P2-SET-01**
- Deduping the same clip if it exists in both Immich and Home Videos
- Library cards / Review ingest of Immich native video (Explore/Person only)
- Face-teach on Immich library clips (paused-frame teaching stays HVRT)
- I5 portrait work

## Settings assessment (locked)

| Layer | Role |
|-------|------|
| **Thin Settings (this slice)** | Owner/system home for **decided** knobs. First card: video file root. Stays out of family nav. |
| **Env files / startmb** | Bootstrap + ops default. Do not fight Settings after a save. |
| **Mature Settings (I13)** | Provider connections, processing, recognition, health actions, archive configuration. |

I2 already stubbed `/settings/ui` so the shell had a destination. Growing that stub is correct; inventing a second admin app is not.

**Later thin cards (when Tom decides):** presence-gap seconds, export dir, derived dir, owner-already-in-People. Not this PR.

## Constraints

- No hard-coded hosts/paths
- Original videos remain read-only
- Sidecar so the worker does not require Postgres to honor Settings
- Env override pattern for owner Person (`MEMORYBOX_OWNER_PERSON_ID` wins) is **not** copied here — that would make Settings a no-op on FlightSim

## Prove

```powershell
python -m memorybox prove-p2-settings-thin
python -m memorybox prove-p2-i4
python -m memorybox prove-p2-i5
python -m memorybox prove-p2-i6
```

## FlightSim manual

1. Person with Immich videos: Explore Video filter shows library clips + HVRT moments.
2. Open an Immich clip — HTML5 player, not Review paused-frame.
3. `/settings/ui` — set an alternate Home Videos folder; worker next scan uses it; Archive Health file count follows.
4. Clear Settings — env default returns.
