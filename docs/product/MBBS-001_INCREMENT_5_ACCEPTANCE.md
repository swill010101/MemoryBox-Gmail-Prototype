# MBBS-001 Increment 5 — Acceptance Report

**Status:** **DESKTOP PROVE PASS — FLIGHTSIM FINAL + OWNER STORY UX PENDING**  
**Date:** 2026-08-09  
**Definition:** [MBBS-001_INCREMENT_5_DEFINITION.md](MBBS-001_INCREMENT_5_DEFINITION.md) — **LOCKED / BUILD AUTHORIZED**  
**Authorization:** Build Increment 5 only  

---

## Verdict

| Gate | Result |
|------|--------|
| Story Service (create/version/retrieve/associations) | **COMPLETE** |
| Ask Story modality + attribution | **COMPLETE** |
| Thin Story UX (`/story/ui`) | **COMPLETE** |
| Desktop `prove-story` | **PASS** (`ok: true`) |
| FlightSim `prove-story --flightsim` + real owner Story | **PENDING operator** |
| Final I5 acceptance | **PENDING FlightSim** |

**Do not begin Increment 5A / 6** without explicit authorization.  
**No Journal, STT, HVRT, polish in this increment.**

---

## Criteria map (desktop)

| ID | Result | Opaque detail |
|----|--------|---------------|
| **I5-A** | PASS | create/save story_id present |
| **I5-B** | PASS | edit → version 2; v1 retained |
| **I5-C** | PASS | current + prior retrieve |
| **I5-D** | PASS | narrator + person + evidence associations |
| **I5-E** | PASS | recollection without corroborating Evidence |
| **I5-F** | PASS | exploratory Ask retrieves Story |
| **I5-G** | PASS | Story citation attribution / provenance |
| **I5-H** | PASS | AI actor persist rejected |
| **I5-I** | PASS | Story naming |
| **I5-J** | PASS (synthetic) | generalized tag; real owner Story pending FS |
| **I5-K** | PASS | health increment=5 |
| **I5-L** | PASS | living specs |

Reports contain **no** Story body text.

---

## What shipped

| Area | Location |
|------|----------|
| Story Service | `memorybox/story/` |
| Ask Story retrieval | `memorybox/ask/retrieve.py` `search_stories` |
| Planner `want_story` | `memorybox/planner/` |
| Orchestrator attribution | `memorybox/ask/orchestrator.py` |
| Story UX | `GET /story/ui` |
| CLI | `python -m memorybox prove-story` |

---

## FlightSim final (operator)

```powershell
cd C:\MemoryBox
git fetch
git checkout cursor/marvin-capture-v01-3344
git pull
python -m memorybox serve
# Open http://127.0.0.1:8790/story/ui — Save one real owner Story; copy opaque story id
$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$env:MEMORYBOX_I5_OWNER_STORY_ID = "<opaque-story-uuid>"
python -m memorybox prove-story --flightsim
```

Manual Ask: `What do you know about <subject from that Story>?` → expect Story recollection with attribution alongside other modalities.

Paste opaque JSON (`ok`, check names, IDs/counts only) below when done.

### FlightSim final

| Field | Value |
|-------|-------|
| Date | _pending_ |
| `prove-story --flightsim` | _pending_ |
| Owner story id | _pending_ |

---

## Stop

- Desktop I5 implementation + prove complete.  
- Final acceptance after FlightSim prove + owner UX Story.  
- **No 5A / Inc 6** without authorization.
