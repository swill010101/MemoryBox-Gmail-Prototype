# FlightSim — Increment 9 Artifact storage & acceptance

**Status:** P1 storage topology **locked** (2026-08-11)  
**Product:** [MBBS-001_INCREMENT_9_DEFINITION.md](../product/MBBS-001_INCREMENT_9_DEFINITION.md) · [MBBS-001_INCREMENT_9_ACCEPTANCE.md](../product/MBBS-001_INCREMENT_9_ACCEPTANCE.md)  
**Stop:** I9 testing only — do **not** begin 9A / 10 under this runbook.

## Topology (locked)

| Host | Role |
|------|------|
| **FlightSim** | MemoryBox application + **PostgreSQL** (Artifact domain knowledge) + processing |
| **media-server** | Durable family/archive **binary** storage for MB-managed Artifact representation originals |

PostgreSQL on FlightSim remains authoritative for Artifact **identity**, labels/descriptions/kinds, metadata revisions, provenance, relationships, **integrity hashes**, representation records, and **storage references (URIs)**.

**Do not** store uploaded Artifact binary originals as PostgreSQL blobs.  
**Do not** move PostgreSQL or the MemoryBox app runtime off FlightSim.  
**Do not** treat FlightSim local disk as the Artifact archive SoT.

Derived thumbnails / OCR / indexes (when added later) are rebuildable and are **not** authoritative originals.

## Durable Artifact original-media root (ops)

Under the established MemoryBox durable tree on media-server (`\\media-server\photos\MemoryBox\…`, same family as `Sources`), the P1 Artifact original-media root is:

```text
\\media-server\photos\MemoryBox\Artifacts
```

Ops/setup may create this directory if absent. Application logic **must not** hard-code the UNC — set it via config only:

```text
MEMORYBOX_ARTIFACT_MEDIA_ROOT
```

There is no separate generalized “all media” root env today beyond modality-specific roots (e.g. `MEMORYBOX_VIDEO_MEDIA_ROOT`). Artifact originals use **`MEMORYBOX_ARTIFACT_MEDIA_ROOT`**.

Example env file: [`config/artifact.env.example`](../../config/artifact.env.example).

## FlightSim pull + migrate

```powershell
cd C:\memorybox
git fetch
git checkout cursor/marvin-capture-v01-3344
git pull
python -m memorybox migrate
```

## Serve (I9 Artifact uploads)

**Single-quote** the UNC in PowerShell so backslashes are preserved:

```powershell
cd C:\memorybox
$env:MEMORYBOX_ARTIFACT_MEDIA_ROOT = '\\media-server\photos\MemoryBox\Artifacts'
python -m memorybox serve
```

Harness (no owner object required):

```powershell
cd C:\memorybox
$env:MEMORYBOX_ARTIFACT_MEDIA_ROOT = '\\media-server\photos\MemoryBox\Artifacts'
python -m memorybox prove-artifact
```

Owner prove after `/artifact/ui` create:

```powershell
cd C:\memorybox
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$env:MEMORYBOX_ARTIFACT_MEDIA_ROOT = '\\media-server\photos\MemoryBox\Artifacts'
$env:MEMORYBOX_I9_OWNER_ARTIFACT_ID = '<opaque-artifact-uuid>'
python -m memorybox prove-artifact --flightsim
```

## Owner gate checklist

1. Create Artifact (+ kind) at `/artifact/ui`
2. Upload ≥1 representation (prefer ≥2) — bytes land under configured media-server root
3. Label (+ optional description) — PG metadata only
4. Associate Person if known (optional)
5. Optional Story Save + link
6. Library: modality=`artifact`, bucket All/Undated, **Person not required**
7. Open/view representation(s)
8. Ask by Artifact identity/metadata
9. Provenance / unresolved context honest; hashes + PG refs inspectable

## Integrity rules (I9)

- Preserve original uploaded bytes on the configured durable root  
- Store content hash in PostgreSQL; refuse silent overwrite of distinct originals  
- Representation bytes immutable; metadata edits create revisions without duplicating bytes  
- Desktop `MEMORYBOX_ALLOW_DEV_DEFAULTS` temp root is **prove-only** — never FlightSim archive SoT  

## Surfaces

| Surface | URL / command |
|---------|----------------|
| Artifact UI | `http://flightsim:8790/artifact/ui` |
| Library artifacts | `http://flightsim:8790/library/ui?modalities=artifact&bucket=all` |
| Prove | `python -m memorybox prove-artifact` |
| Health | `GET /health` → `increment: 9` |
