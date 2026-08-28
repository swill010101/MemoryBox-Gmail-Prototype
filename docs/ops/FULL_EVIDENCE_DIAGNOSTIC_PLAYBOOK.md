# Peggy Full-Fidelity Evidence Diagnostic

**Branch:** `cursor/p2-i11a-full-evidence-diag-49da`  
**Machine:** FlightSim (`C:\memorybox`)  
**Purpose:** Export the complete eligible Peggy evidence set **before** `OBSERVATION_EXTRACT` / semantic compression. Measurement only — **no LLM calls**, no production I11A behavior changes.

---

## What this does / does not do

| Does | Does not |
|------|----------|
| Resolve the same Peggy Person scope as the historian fixture | Call OBSERVATION_EXTRACT / Ask-relative / narrator |
| Retrieve every eligible family (SMS, email, calendar, stories, journal, travel, photo/video, artifacts, Person facts, …) | Sample, significance-rank, semantically select, or silently cap evidence |
| Normalize provider-neutrally; count exact duplicates removed | Truncate email/SMS bodies to production unit `[:2000]` |
| Write human-readable + metrics + clean cloud paste | Modify production inference |
| Chunk at ~100–150K tokens when total > 200K, with union proof | Omit evidence between full set and chunks |

---

## Phase 0 — Deploy

```bat
cd C:\memorybox
git fetch origin
git pull origin cursor/p2-i11a-full-evidence-diag-49da
.\startmb.cmd -Restart
```

Offline acceptance (no archive):

```bat
python -m memorybox prove-full-evidence-diagnostic
```

---

## Phase 1 — Export full Peggy evidence

Prefer pairing with the latest frozen Peggy HISTFIX so metrics include downstream obs / roll-up / HO sizes:

```bat
cd C:\memorybox
python -m memorybox full-evidence-diagnostic --flightsim --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_20260828T034329Z_d7f1713c.json
```

Or without fixture (downstream comparison marked unavailable):

```bat
python -m memorybox full-evidence-diagnostic --flightsim
```

**Output directory:** `C:\memorybox\docs\test-output\full-evidence\`

| File | Contents |
|------|----------|
| `PEGGY_FULL_EVIDENCE.txt` | Chronological / source-organized normalized evidence |
| `PEGGY_FULL_EVIDENCE_METRICS.json` | Per-source + total counts, bytes, chars, tokens, date range; downstream comparison |
| `CLOUDREQ_peggy_full_evidence_paste.txt` | Person context + complete evidence (clean paste; no traces/embeddings) |
| `PEGGY_FULL_EVIDENCE_ITEMS.json` | Machine-readable item list + fingerprints |
| `PEGGY_FULL_EVIDENCE_CHUNK_*.txt` | Only if estimated tokens > 200K |
| `PEGGY_FULL_EVIDENCE_CHUNK_MANIFEST.json` | Proves `union(chunks) == all normalized items` |

---

## What to record

From `PEGGY_FULL_EVIDENCE_METRICS.json` → `total`:

- retrieved_item_count / normalized_item_count / exact_duplicates_removed
- estimated_tokens / earliest_date / latest_date

From `downstream_comparison` (when fixture provided):

- validated_observation_count + tokens
- rollup_count + tokens
- ho_count + tokens

Confirm `llm_calls` is `0` and `production_inference_modified` is `false`.
