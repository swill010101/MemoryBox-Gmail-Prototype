# Voice assignment coverage — canonical eight vs five-category matrix

**Inspector:** [inspect-voice-assignment-coverage.py](inspect-voice-assignment-coverage.py)  
**Checkpoint:** `codex/p2-i13-stage-a` at or after `a0c4119`  
**Read-only:** no Learn, drains, transcription, or pilot execution

Tom’s original founder review returned **four** core assignments (T1, H1, O1, U1-clear). **T2**, **N1**, and the **grandpa 002 pair** (R1-gs2-fresh, H1-gs2-held-out) extend the set to **eight** pinned assignments used below. Additional annotations exist (Patio, overlap E2/O2, etc.) but are not required to fill the five matrix categories.

---

## Canonical eight assignments

| Key | Matrix category | Pilot role | Source | Interval (s) | Annotation | Person |
|---|---|---|---|---:|---|---|
| T1 | Eugene training | training | `vid-da41273dbd9ac4bb` | 138.72–144.66 | `d5a3d050…` | Eugene Will |
| R1-gs2-fresh | Eugene training | training | `vid-34df63e61b949890` | 26.30–34.78 | `3eb88a19…` | Eugene Will |
| H1 | Eugene held-out | held-out | `vid-c57dbd21f993f6d1` | 325.22–345.56 | `f47ee4ec…` | Eugene Will |
| U1-clear | Eugene held-out | held-out | `vid-c57dbd21f993f6d1` | 129.64–138.72 | `5651a4bd…` | Eugene Will |
| H1-gs2-held-out | Eugene held-out | held-out | `vid-34df63e61b949890` | 86.42–105.44 | `5d87a6ac…` | Eugene Will |
| T2 | Tom training | training | `vid-da41273dbd9ac4bb` | 37.12–42.40 | `5e106e50…` | Tom Will |
| O1 | Off-camera Tom held-out | held-out | `vid-c57dbd21f993f6d1` | 152.24–158.34 | `3fa1c4e1…` | Tom Will |
| N1 | Uncertain / different-speaker no-match | held-out | `vid-c015e0fe07414fcc` | 0.00–6.74 | `74cc9646…` | Unknown |

**Training vs held-out:** No annotation ID appears in both training and held-out roles within this canonical set.

---

## Five-category coverage (current stopped pilots)

| Required category | Satisfied by assignment(s) | Current pilot evidence (do not retry) |
|---|---|---|
| Eugene training | T1 (retired ref), **R1-gs2-fresh** | `66fb93af…` (R1-gs2-fresh training); `1039c733…` stale |
| Eugene held-out | H1, U1-clear, H1-gs2 | `66fb93af…`, `339b3a14…` (E2 overlap), `f59050d5…` (Patio E3); original `1039c733…` stale |
| Tom training | T2 | `9e0a2605…` |
| Off-camera Tom held-out | O1 | `9e0a2605…` — O1 **match** 0.487 |
| Uncertain / no-match | N1 (Unknown TV) | `46cb1d21…`, `339b3a14…` — N1 **no_match** |

**Result:** All five categories are **present** in owner assignments and **measured** by stopped **current** admissions. **No additional annotation** is required for this matrix.

---

## Explicitly not in this matrix

- Q1 listening-only interval on 1532 (no saved annotation)
- U1 unclear remainder (unreviewed words)
- Face/voice corroboration (separate acceptance track)
- Gate 4 archive register/unlock/start
- Full 22-source owner truth

---

## Regenerate on FlightSim (optional)

```powershell
cd C:\MemoryBox
$env:MEMORYBOX_I13_COVERAGE_OUTPUT = 'E:\MemoryBox-dev\p2-i13-stage-a\docs\test-output\voice-assignment-coverage.json'
python -B docs\implementation\p2-i13-stage-a\inspect-voice-assignment-coverage.py
```

Do not commit `docs/test-output/voice-assignment-coverage.json` unless separately reviewed (may echo private intervals).
