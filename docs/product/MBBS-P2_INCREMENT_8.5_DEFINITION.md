# MBBS — P2-I8.5 Face Evidence Ownership & Immich Decoupling · Increment Definition

**Status:** **LOCKED for roadmap insertion** · **NO BUILD** until P2-I8 is ACCEPTED and Tom explicitly authorizes this increment  
**Date:** 2026-08-14  
**Authority:** [MBBS-P2_I8.5_FACE_EVIDENCE_OWNERSHIP_PRD.md](MBBS-P2_I8.5_FACE_EVIDENCE_OWNERSHIP_PRD.md) · MBPS-002 P2-ID-01..05 · CAP-P2-003…006 / 010 / 016 / 017  
**Execution:** After **P2-I8 Richer Email**, before **P2-I9 Spoken Moments**  
**ID lock:** **P2-I8.5** — drafts that said I7.5 are retired.

## Primary outcome

MemoryBox owns durable active face observations used by MemoryBox. Immich remains a replaceable read-only provider of media and face/identity evidence.

## IN

- MB-owned FaceObservation / FaceEvidence working records (distinct from live Immich face rows)
- Idempotent import of eligible Immich face observations (mapped People linked; unknown faces unassigned)
- Provider provenance + original provider boxes preserved; MB working boxes are runtime authority
- Owner override / tombstone so sync cannot resurrect or overwrite MB corrections
- Face UX + recognition exemplar reads switch to MB-owned observations
- Override-safe ongoing Immich discovery (read-only)
- Migration counts/status; Immich-unavailable retention tests

## OUT (locked)

- No write-back to Immich
- No original media edits
- **No Shared Evidence Viewer Learn rail UI** (follow-on after this increment is ACCEPTED)
- No new photo-recognition engine; no continuous video-playback boxes
- No Immich People editing from MemoryBox; no Immich replacement in this increment

## Blocks

Learn-rail Assign / Reassign / Adjust box / Unassign / Learn from this face must not be treated as complete until I8.5 is ACCEPTED. Current Explore Learn chrome is provisional and must not become Immich-mutating authority.

## Sequence when authorized

PRD §29: Inspect → Plan (conflicts) → model → migrate → switch reads → override-safe sync → regression / provider-loss tests → living specs.

## Prove (when built)

Harness + FlightSim acceptance tests in the PRD §27. Do not start those until build is authorized.
