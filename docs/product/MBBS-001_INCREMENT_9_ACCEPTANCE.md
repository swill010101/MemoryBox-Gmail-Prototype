# MBBS-001 Increment 9 — Acceptance

**Status:** **ACCEPTED** (FlightSim owner gate)  
**Date:** 2026-08-11  
**Definition:** [MBBS-001_INCREMENT_9_DEFINITION.md](MBBS-001_INCREMENT_9_DEFINITION.md)  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 9  
**Ops runbook:** [FLIGHTSIM_I9_ARTIFACT_RUNBOOK.md](../ops/FLIGHTSIM_I9_ARTIFACT_RUNBOOK.md)

## Owner gate (I9-OWNER) — PASSED

Tom on FlightSim used `/artifact/ui` + Library/Ask without developer intervention / SQL:

1. Created Artifact **Dad's Picture of Mom** (`keepsake_object`)
2. Uploaded MB-managed representation to `\\media-server\photos\MemoryBox\Artifacts` (hash + URI in PG)
3. Associated Person **Anne Will** (Immich lazy-teach → MB Person)
4. In-app Capture/STT → explicit Save Story + link (multiple Stories linked)
5. Library modality=`artifact`, **no Person required** — cards browsable; Open Artifact loads provenance
6. Ask / provenance inspectable; unresolved Place/Event remain explicit

| Item | Note |
|------|------|
| Owner Artifact | `afce98f4-80e1-458c-9d2a-d1c22fc578da` |
| Media root | `MEMORYBOX_ARTIFACT_MEDIA_ROOT='\\media-server\photos\MemoryBox\Artifacts'` |
| Surface | `http://127.0.0.1:8790/artifact/ui` · `/library/ui?modalities=artifact&bucket=all` |

## Harness

```text
python -m memorybox prove-artifact
# ok: true — multi-rep, hash, metadata revision no byte-dup, evidence-ref,
#            Library without Person, Person narrows, Ask search, health=9
```

## Storage topology (locked)

| Layer | Location | Holds |
|-------|----------|--------|
| Domain knowledge | **PostgreSQL on FlightSim** | Artifact identity, labels/kinds, revisions, provenance, relationships, hashes, representation records, URI refs |
| Binary originals | **media-server** via `MEMORYBOX_ARTIFACT_MEDIA_ROOT` | MB-managed representation **original bytes** (not PG blobs) |
| App / processing | **FlightSim** | MemoryBox serve + processing |

**P1 ops root:** `\\media-server\photos\MemoryBox\Artifacts` (config-only; never hard-coded in app logic).

## Shipped surface

| Surface | Path |
|---------|------|
| Artifact UI | `/artifact/ui` |
| Artifact API | `GET/POST /artifact`, upload, bytes, associations, Story link |
| Library | `GET /library/cards?modalities=artifact` (person_id optional) |
| Ask | `want_artifact` + `artifact_hits` |
| Prove | `prove-artifact [--flightsim]` |
| Health | `increment: 9` |

## Lessons carried forward

- Immich lazy-teach on Artifact Person/Narrator pickers — universalize later: [TASK-P1P2-001](MBBS_P1_P2_BACKLOG.md).  
- Story body is `version.body_text`; Artifact UI must deep-link `/story/ui?id=…`.  
- Narrator ≠ About person; exact-name enroll creates duplicates without merge.

## Stop

Do **not** begin Increment **9A** / **10** / Guided Capture / Export without explicit authorization.  
Next definition (**REVIEW ONLY**): [MBBS-001_INCREMENT_9A_DEFINITION.md](MBBS-001_INCREMENT_9A_DEFINITION.md).
