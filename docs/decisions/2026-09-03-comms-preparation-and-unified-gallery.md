# Communications preparation and unified Gallery

**Date:** 2026-09-03  
**Status:** Locked product decision (record only — not implemented in this change)  
**Supersedes:** Earlier Gallery proposal that returned pictures first, retrieved communications for ~45 seconds in the background, inserted them later, and abandoned that work when another Ask began.

## Decision

### 1. Immutable communications archive

The immutable communications archive remains intact.

Original email, SMS, attachments, headers, timestamps, provenance, evidence IDs, and source relationships are never rewritten, replaced, or destroyed by cleanup.

### 2. Separate optimized communications representation

During email/SMS ingestion, MemoryBox creates and incrementally maintains clean, normalized communication threads suitable for Gallery retrieval, Ask retrieval, and model chunking.

The clean representation may:

- group complete threads/conversations;
- remove or mark known boilerplate and signatures;
- classify automated notices and commercial noise;
- deduplicate safely;
- normalize participants and chronology;
- retain links to every immutable source item;
- preserve uncertainty and incomplete-thread indicators;
- retain evidence IDs and hashes;
- expose token counts and chunk-readiness metadata.

It must never erase or replace the originals.

Existing archives require a one-time derived backfill. Later ingestion updates only new or changed material.

### 3. Ask consumes optimized communication threads

Ask should retrieve the prepared communication representation instead of rebuilding and cleaning raw communications during every request.

Original evidence remains available for inspection, citation, audit, and reprocessing.

### 4. Restore unified mixed-media Gallery response

For person asks such as “Show me Peggy,” collect and return applicable:

- photos;
- playable videos/video moments;
- email communications;
- SMS communications;
- calendar events;

as one coordinated Gallery result.

Display the assembled result together rather than initially showing pictures and silently inserting communications later.

The existing Communications filter/dropdown and precision-bucket rules remain applicable unless separately changed.

### 5. Purpose and rationale

This decision:

- preserves evidence integrity;
- removes repeated Ask-time communications cleanup;
- reduces Gallery latency;
- restores the intended mixed-media experience;
- makes prepared evidence immediately available for chunking;
- remains valuable if comprehensive narration pauses;
- better supports growing electronic footprints.

### 6. Scope boundary

This decision is recorded for roadmap/backlog alignment only. The optimized communications store and Gallery change are **not** implemented here.

## Roadmap / backlog impact

| Item | Effect |
|------|--------|
| Prior deferred Gallery background-comms insertion behavior | **Superseded** by unified mixed-media Gallery (§4) |
| P2-I6 Richer Email (`MBRM-001`) | Should absorb optimized communications representation + backfill |
| P2-I11 Narrative / Ask retrieval | Ask should consume prepared threads (§3) |
| P2-I3 / Gallery mixed-media | Restore coordinated Gallery assembly (§4) |

## Unresolved placement questions

- Whether optimized communications live as a new derived store, materialized views, or ingestion sidecars (implementation TBD).
- Exact increment split between P2-I6 ingestion/backfill and Gallery/Ask consumption work.
- Whether Communications filter rules need a separate ADR when unified Gallery ships.
