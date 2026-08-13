# HVRT R2 PRD — Review Console + Learning Loop (POC)

**Status:** Approved (Tom) — implement  
**Owner:** Tom (sole Owner; multi-user deferred)  
**Depends on:** HVRT Phase 1 evidence indexes (videos, faces, whisper, scenes)

## Problem
Meta-rich clips are searchable; hours of old/stitched video are not. Setup wizards won’t scale. Tom needs to **review, mark what matters, and learn** without sitting through entire reels.

## Success criteria
- Mark **location/house** spans (and optional date) while reviewing; playback jumps to spans
- **Face box enroll** → existing person (dropdown) or new person (no duplicate names)
- **Voice enroll** span under a person (multi-sample); diarization/OCR as modular AI suggestions
- Every human action stored with provenance; **Owner > User > AI**; human confirm ≈ confidence **1.0**; human supersedes AI and prior human
- **Learn from annotations** runs in **background** with visible progress; operator can keep reviewing
- **Settings** (baseball/Christmas/etc.) UI placeholder only — no engine
- **No** auto location-from-frames recognition engine (exemplars may be saved for later)

## Scope In
- Annotation spans + places registry (GPS set-from-video + human spans)
- Rescoring / decision model persistence
- Review UI (hit list + player + mark tools + face box)
- Background learning job router + progress panel
- OCR + diarization hooks as optional AI suggestion passes (off-the-shelf when installed)
- Voice enroll samples tied to people

## Scope Out
- Setting/event recognition engines
- Auto house identity from frames
- Multi-user auth (ranks stored; only Owner used)
- Memory Box ingestion
- R3 voice notes on photos/email (roadmap only)

## Constraints
- Originals immutable; versioned engine passes; re-run one engine without full corpus redo
- Local-first
- Evidence First — AI never silently becomes fact
