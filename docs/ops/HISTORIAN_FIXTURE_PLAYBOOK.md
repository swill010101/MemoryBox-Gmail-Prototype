# I11A Historian Frozen-Fixture Playbook

**Release:** `cursor/p2-i11a-historian-fixture-49da` (PR #66)  
**Machine:** FlightSim (`C:\memorybox`)  
**Purpose:** Freeze deterministic I11A prepared input once; test historian models (Ask-relative + narrator) without re-running archive retrieval, normalization, or observation extraction.

Print this page and check boxes as you go.

---

## What this does / does not do

| Does | Does not |
|------|----------|
| Runs four canonical Asks through retrieval → observations → roll-ups → HO IR | Change production Ask prompts, IR, validation, or narrator behavior |
| Freezes prepared input **before** the ASK_RELATIVE LLM call | Re-run retrieval during model tests |
| Replays Ask-relative + narrator from frozen JSON | Send fixtures to cloud unless you pass `--provider cloud` explicitly |
| Writes small JSON metrics + human-readable `.txt` per run | Produce 14–141 MB regression dumps |

**Four cases (fixed wording — do not invent new Asks):**

| Case ID | Ask text |
|---------|----------|
| `peggy` | tell me what you know about Peggy |
| `january_2025` | write a narrative about my January 2025 |
| `vegas` | write a narrative about my trip to las vegas in January 2026 |
| `alaska` | write a narrative about my alaska trip in 2026 |

---

## Prerequisites (before you start)

- [ ] FlightSim is up; Ollama is running; archive is warm (observation cache populated from prior Peggy work).
- [ ] You want **warm** fixture build: no `--rebuild-observations`, no `--enrich-first`.
- [ ] Models you plan to test are pulled in Ollama (e.g. `gemma4:26b`, `llama3.2`).
- [ ] One large model at a time on the 4090 (manifest runs cases **sequentially**).

---

## Phase 0 — Deploy branch (once per release)

Open **cmd** as usual on FlightSim:

```bat
cd C:\memorybox
git fetch origin
git pull origin cursor/p2-i11a-historian-fixture-49da
startmb.cmd -Restart
```

Optional sanity check:

```bat
python -m memorybox prove-historian-fixture
python -m memorybox prove-i11a
```

Both should report `"ok": true`.

---

## Phase 1 — Build all four fixtures (one preparation run)

This runs the **real production pipeline** through historian prep only.  
**Zero** Ask-relative calls. **Zero** narrator calls.

```bat
cd C:\memorybox
python -m memorybox historian-fixture-build --flightsim --cases peggy,january_2025,vegas,alaska
```

**Output directory:** `C:\memorybox\docs\test-output\historian-fixtures\`

**Expected files:**

```
HISTFIX_peggy_<UTC>_<sha8>.json
HISTFIX_january_2025_<UTC>_<sha8>.json
HISTFIX_vegas_<UTC>_<sha8>.json
HISTFIX_alaska_<UTC>_<sha8>.json
HISTFIX_manifest_<UTC>.json
```

**Record manifest path here (fill in after run):**

```
Manifest: docs\test-output\historian-fixtures\HISTFIX_manifest________________.json
Built at: ____________________
Git commit: ____________________
```

---

## Phase 2 — Verify manifest (before any model run)

Open the manifest JSON and confirm for **each** case:

- [ ] `observation_extract_calls` is **0** (or absent / zero in build accounting)
- [ ] `ask_relative_calls` is **0**
- [ ] `ho_unit_count`, `rollup_count`, `validated_observation_count` look reasonable
- [ ] `duplicate_ho_id_count` is recorded (known issue — **do not repair** for fixture v1)
- [ ] `input_sha256` is present per case
- [ ] Fixture file sizes are modest (KB–low MB), not hundreds of MB

Quick dir listing:

```bat
dir C:\memorybox\docs\test-output\historian-fixtures\HISTFIX_*
```

**Stop if:** build printed errors, any case missing, or `ask_relative_calls > 0`.

**Stop if:** `historian-fixture-run` reports `fixture input SHA mismatch` — pull the latest branch (SHA contract fix) and rebuild fixtures; v1 files from before the fix cannot replay.

---

## Phase 3 — Model run: Gemma (all four cases, sequential)

Replace `<MANIFEST>` with your manifest filename from Phase 1.

```bat
cd C:\memorybox
python -m memorybox historian-fixture-run ^
  --manifest docs\test-output\historian-fixtures\<MANIFEST> ^
  --provider ollama ^
  --model gemma4:26b ^
  --timeout 1800
```

**Output directory:** `C:\memorybox\docs\test-output\historian-runs\`

**Per case you get two files:**

```
HISTRUN_<case>_ollama_gemma4-26b_<UTC>_<sha8>.json   ← small metrics
HISTRUN_<case>_ollama_gemma4-26b_<UTC>_<sha8>.txt    ← human review; response at EOF
```

**After run, verify in each JSON:**

- [ ] `"provider": "ollama"`
- [ ] `"requested_model": "gemma4:26b"`
- [ ] `"actual_model": "gemma4:26b"` (must match — if not, run aborted before LLM)
- [ ] `"fixture_sha256"` matches manifest for that case

**Inspect what the historian said (last 100 lines):**

```bat
Get-Content docs\test-output\historian-runs\HISTRUN_peggy_ollama_gemma4-26b_*.txt -Tail 100
```

Repeat for vegas, alaska, january_2025 as needed.

---

## Phase 4 — Model run: llama3.2 (same fixtures, same manifest)

Same manifest, different model. Ollama keep_alive may retain the prior model until this run loads llama.

```bat
cd C:\memorybox
python -m memorybox historian-fixture-run ^
  --manifest docs\test-output\historian-fixtures\<MANIFEST> ^
  --provider ollama ^
  --model llama3.2 ^
  --timeout 1800
```

**Verify again:**

- [ ] `"actual_model": "llama3.2"` in every JSON
- [ ] Same `fixture_sha256` per case as Gemma run (same frozen input)
- [ ] Compare wall times, token counts, timeout vs success between Gemma and llama JSONs

---

## Phase 5 — Single-case rerun (optional)

If one case failed or timed out, rerun only that fixture:

```bat
python -m memorybox historian-fixture-run ^
  --fixture docs\test-output\historian-fixtures\HISTFIX_peggy_<UTC>_<sha8>.json ^
  --provider ollama ^
  --model gemma4:26b ^
  --timeout 1800
```

---

## Reading the `.txt` report

**Top:** CASE, ASK, FIXTURE, INPUT SHA, PROVIDER, MODEL REQUESTED/ACTUAL, TIMEOUT, token/timing summary, status flags.

**Middle (if present):** `ASK-RELATIVE RAW RESPONSE` — full structured/raw Ask-relative output.

**Bottom (always last content before EOF):**

```
============================================================
MODEL RESPONSE
============================================================

<plain text — narrator answer if success, else raw Ask-relative or timeout message>
```

| Outcome | Tail content |
|---------|----------------|
| Narrator succeeded | Final family-facing narrative |
| Ask-relative failed schema/validation | Complete raw Ask-relative response |
| Provider timeout, no text | `[NO MODEL RESPONSE — PROVIDER TIMEOUT AFTER N SECONDS]` |
| Partial text before error | `[PARTIAL MODEL RESPONSE]` then preserved text |

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| JSON shows `llama3.2` when you wanted Gemma | Old harness used env default, not `--model` | Use **this** runner only; confirm `requested_model == actual_model` in JSON |
| `MODEL_MISMATCH` / abort before call | Provider instance has wrong model loaded | Pass `--model` explicitly; restart Ollama if needed |
| Fixture build slow / extract calls > 0 | Cold cache or wrong flags | Do not pass `--rebuild-observations`; ensure warm archive |
| All cases timeout at 600s | Wrong branch (old timeout) | Confirm on `historian-fixture` branch; use `--timeout 1800` on runs |
| Cloud error immediately | Cloud not implemented yet | Use `--provider ollama` only |
| Huge JSON output | Wrong command (`i11a-regression`) | Use `historian-fixture-run`, not full regression |

---

## Do not (common mistakes)

- Do **not** use `i11a-regression` for model A/B — it re-runs the full pipeline every time.
- Do **not** pass `--enrich-first` or `--rebuild-observations` during fixture build.
- Do **not** rely on `MEMORYBOX_OLLAMA_CHAT_MODEL` alone — **`--model` is required** on fixture-run.
- Do **not** run multiple large Ollama models concurrently during benchmarks.
- Do **not** pass `--provider cloud` unless you intentionally want cloud (stub blocks today).
- Do **not** edit fixture JSON to “fix” duplicate HO IDs — that is fixture v2 work.

---

## File layout cheat sheet

```
C:\memorybox\
  docs\test-output\
    historian-fixtures\          ← frozen inputs (model-independent)
      HISTFIX_<case>_<UTC>_<sha8>.json
      HISTFIX_manifest_<UTC>.json
    historian-runs\              ← model run results
      HISTRUN_<case>_ollama_<model>_<UTC>_<sha8>.json
      HISTRUN_<case>_ollama_<model>_<UTC>_<sha8>.txt
```

**Comparison key:** same `fixture_sha256` + different `actual_model` = controlled model comparison.

---

## Quick reference — copy/paste block

```bat
REM === SETUP (once) ===
cd C:\memorybox
git fetch origin
git pull origin cursor/p2-i11a-historian-fixture-49da
startmb.cmd -Restart

REM === BUILD FIXTURES (once per frozen snapshot) ===
python -m memorybox historian-fixture-build --flightsim --cases peggy,january_2025,vegas,alaska

REM === MODEL: GEMMA (all four) ===
python -m memorybox historian-fixture-run --manifest docs\test-output\historian-fixtures\HISTFIX_manifest_<UTC>.json --provider ollama --model gemma4:26b --timeout 1800

REM === MODEL: LLAMA (all four) ===
python -m memorybox historian-fixture-run --manifest docs\test-output\historian-fixtures\HISTFIX_manifest_<UTC>.json --provider ollama --model llama3.2 --timeout 1800

REM === INSPECT ===
Get-Content docs\test-output\historian-runs\HISTRUN_peggy_ollama_gemma4-26b_*.txt -Tail 100
```

---

## Future: cloud provider (not available yet)

When implemented, same fixtures, explicit opt-in only:

```bat
python -m memorybox historian-fixture-run --manifest ... --provider cloud --model <api-model-id> --timeout 1800
```

Cloud will receive the **same** system message and user JSON as Ollama; no ChatGPT history or MemoryBox memory.

---

*End of playbook.*
