# MBBS — P2 backlog planning sequence

**Status:** Planning locked (owner confirmed default sequence) · **Date:** 2026-08-12  
**Authority:** Planning only — **not** a build authorization, PRD, or increment definition  
**Source backlog:** P1 closeout parked items / `TASK-P1P2-*` inventory  
**Owner:** Tom

## Gate (hard)

- **No build** until Tom issues an explicit *Build TASK-P1P2-00N* (or numbered P2 increment) plus definition/acceptance.
- **No PRD invent** here — Tom supplies the P2 PRD / build document when ready.
- **No** MBBS-P2 charter, Increment N definition, application code, or FlightSim deploy under this planning note alone.
- Prefer **one** authorized TASK/increment at a time.

## Confirmed sequence

Owner confirmed the default planning order (2026-08-12):

| Order | ID | Theme | Notes |
|------:|----|--------|-------|
| 1 | **TASK-P1P2-004** | Immich Status / Photos inventory | First fix-list item; Status honesty gap |
| 2 | **TASK-P1P2-001** | Universal Immich lazy-teach | Shared Person picker / teach path |
| 3 | **TASK-P1P2-002** | Kinship inference graph | Disclosed inference; no tree viz |
| 4 | *(ops ingest)* | Full mbox → Evidence; SMS ingest; HVRT serve env for video counts | After 004 may parallel if resequenced later; default sits after identity work |
| 5 | **TASK-P1P2-003** | Export import-back / restore | Later portability; higher risk/scope |

```text
004 Status Photos
  → 001 Lazy-teach
    → 002 Kinship
  → ops ingest (default after 001/002; may parallel after 004 if Tom resequences)
  → 003 Import-back (late)
```

## Inventory (parked themes)

| ID | Theme | Nature | Owner signal |
|----|--------|--------|--------------|
| **004** | Immich Status Photos inventory | Ops/key + Status probe harden | First fix-list item for P2 |
| **001** | Universal Immich lazy-teach | Cross-surface Person UX/API | Consistency epic |
| **002** | Kinship inference graph | Domain/Ask read-model | High product value; not genealogy chrome |
| **003** | Export import-back / restore | Portability | After exit-only I12 |
| *(ops)* | Full mbox → Evidence; SMS ingest; HVRT video counts | Ingest/ops | Authorize explicitly; not silent P1 leftover |

## Explicitly out of this backlog plan

Final P2 Dashboard · multi-user (EVS-017) · tone dial (EVS-019) · full Immich mirror export · handwriting · rich EF-13 AI Story Composition — those belong in a future P2 product charter / PRD, not these parked TASKs.

## When a slice is authorized later

Each slice still needs:

1. Explicit owner authorization (*Build TASK-P1P2-00N* or numbered P2 increment).  
2. Definition + acceptance (IN/OUT, FlightSim gate, living-spec updates) matching the P1 pattern.  
3. No silent expansion into neighboring backlog items.

## Awaiting

1. Tom’s P2 PRD / build document under `docs/product/`.  
2. Named authorization for the first slice (default candidate: **TASK-P1P2-004** alone, unless Tom opens a thin P2 opener epic).

Until then: sequence is locked for planning; **build remains blocked**.
