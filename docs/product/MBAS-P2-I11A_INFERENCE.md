# MBAS-P2-I11A — Inference engine (locked)

**Status:** Planning **LOCKED** 2026-08-25 · **BUILD AUTHORIZED** 2026-08-25

## Pipeline

```
Ask → MBQL/scope → requestor + focal PersonContext
  → retrieve/prep (all eligible units)
  → deterministic batching
  → inference pass(es) + optional merge
  → schema/provenance/relationship validation
  → validated semantic pack
  → narrator / summary / Gallery ranking / show
  → Python/UI system-truth footer
```

Simple retrieve/show **bypasses** inference. `tell`, summarize, and exploratory “what do you know about” **invoke** it. Presentation mode is orthogonal: T3 may stay `show`.

## Requestor vs focal subject

- `requestor_person_id`: owner/current user.
- `focal_subject_person_ids`: who the Ask is about. “My January” includes requestor as focal. “About Peggy” is Peggy; no inherited January window.

## System truth

Operational modality state may enter **inference input**. Validated pack and narrator payload must **not** carry coverage/counts/provider booleans. Python/UI/Trace render those. Queried+empty → `0`; skipped/unavailable/failed ≠ `0`. Deliberate reduction ≠ incomplete.

## Failure

Inference unavailable, unparsable, or unmergeable → fail closed for semantic synthesis (evidence remains; no heuristic essay). Partial chunk failure: incomplete + Python line only if remaining batches still cover subject/time; else fail closed.

## Batching

Every eligible unit in at least one attempted leaf batch. Context limits are implementation partitions, not consider-caps. Retry failed batch up to 2 times (config). Multi-leaf merge is deterministic concat + date sort by default; set `MEMORYBOX_I11A_LLM_MERGE=1` for a second model merge pass.
