# MBBS-001 Increment 9 — Acceptance

**Status:** **SHIPPED / harness ready** — awaiting FlightSim **I9-OWNER** gate  
**Date:** 2026-08-10 (storage topology corrected 2026-08-11)  
**Definition:** [MBBS-001_INCREMENT_9_DEFINITION.md](MBBS-001_INCREMENT_9_DEFINITION.md)  
**Decision log:** [MBBS_DECISION_LOG.md](MBBS_DECISION_LOG.md) § Increment 9  
**Ops runbook:** [FLIGHTSIM_I9_ARTIFACT_RUNBOOK.md](../ops/FLIGHTSIM_I9_ARTIFACT_RUNBOOK.md)

## Storage topology (locked)

| Layer | Location | Holds |
|-------|----------|--------|
| Domain knowledge | **PostgreSQL on FlightSim** | Artifact identity, labels/descriptions/kinds, metadata revisions, provenance, relationships, integrity hashes, representation records, storage URI refs |
| Binary originals | **media-server** via `MEMORYBOX_ARTIFACT_MEDIA_ROOT` | MB-managed representation **original bytes** (not PG blobs) |
| App / processing | **FlightSim** | MemoryBox serve + processing |

**P1 Artifact original-media root (ops):** `\\media-server\photos\MemoryBox\Artifacts`  
(Same MemoryBox durable tree as `Sources`; set via env only — **never hard-coded in app logic**. Ops may create the folder if absent.)

Do **not** invent alternate durable folder names. Do **not** use FlightSim local disk as archive SoT. Derived thumbs/OCR/indexes remain rebuildable.

## Harness

```text
# FlightSim: set MEMORYBOX_ARTIFACT_MEDIA_ROOT to the locked ops path (see runbook)
python -m memorybox migrate
python -m memorybox prove-artifact
# ok: true — multi-rep, hash, metadata revision no byte-dup, evidence-ref,
#            Library without Person, Person narrows, Ask search, health=9
```

FlightSim owner prove (after creating a real keepsake in `/artifact/ui`):

```powershell
cd C:\memorybox
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$env:MEMORYBOX_ARTIFACT_MEDIA_ROOT = '\\media-server\photos\MemoryBox\Artifacts'
$env:MEMORYBOX_I9_OWNER_ARTIFACT_ID = '<opaque-artifact-uuid>'
python -m memorybox prove-artifact --flightsim
```

Serve with the same root:

```powershell
cd C:\memorybox
$env:MEMORYBOX_ARTIFACT_MEDIA_ROOT = '\\media-server\photos\MemoryBox\Artifacts'
python -m memorybox serve
```

## Owner gate (I9-OWNER) — pending Tom

On FlightSim without developer/SQL intervention:

1. Create Artifact (+ kind) at `/artifact/ui`
2. Upload ≥1 representation (prefer ≥2) to durable media-server root (above)
3. Label (+ optional description) — PG metadata
4. Associate Person if known (optional)
5. Optionally Save Story + link (typed and/or STT draft → explicit Save)
6. Library: modality=`artifact`, **no Person required** (Bucket All/Undated)
7. Open/view representation(s)
8. Ask retrieves by Artifact identity/metadata
9. Provenance / unresolved context honest; hashes + PG refs inspectable

## Shipped surface

| Surface | Path |
|---------|------|
| Artifact UI | `/artifact/ui` |
| Artifact API | `GET/POST /artifact`, upload `/artifact/{id}/representations`, bytes, associations |
| Library | `GET /library/cards?modalities=artifact` (person_id optional) |
| Ask | `want_artifact` + `artifact_hits` |
| Prove | `prove-artifact [--flightsim]` |
| Health | `increment: 9` |
| Config example | `config/artifact.env.example` |

## Env

| Var | Role |
|-----|------|
| `MEMORYBOX_ARTIFACT_MEDIA_ROOT` | Durable SoT for MB-managed Artifact representation originals (**required** on FlightSim; P1 ops value above) |
| `MEMORYBOX_ALLOW_DEV_DEFAULTS` | Desktop/prove temp root only — never FlightSim archive SoT |
| `MEMORYBOX_I9_OWNER_ARTIFACT_ID` | Optional FlightSim prove pointer |

## Stop

Do **not** begin Increment **9A** / **10** / Guided Capture / Export / SMS. Continue **I9 testing only**.  
Next review (after I9 accept): [MBBS-001_INCREMENT_9A_DEFINITION.md](MBBS-001_INCREMENT_9A_DEFINITION.md).
