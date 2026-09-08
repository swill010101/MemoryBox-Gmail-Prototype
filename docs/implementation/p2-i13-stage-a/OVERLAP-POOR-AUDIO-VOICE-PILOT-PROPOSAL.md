# Overlap / poor-audio voice pilot proposal

**Status:** design only — **no run authorized**  
**Proposal:** [overlap-poor-audio-voice-pilot-proposal.json](overlap-poor-audio-voice-pilot-proposal.json)  
**Inventory:** [overlap-voice-annotations-inventory.json](overlap-voice-annotations-inventory.json) (FlightSim 2026-09-08)

---

## What the inspector found

| Pool | Count | Notes |
|---|---|---|
| Active Eugene | 8 | 3 on excluded 1532; 4 used in prior pilots; 1 retired (T1) |
| Active Tom | 4 | O1 and T2 used in prior pilots; **2 unused on 1532** |
| Active Unknown | 1 | N1 — reused as control |

**Unused annotations (prior to this proposal):**

| ID | Person | Source | Interval | Words |
|---|---|---|---|---|
| `bbceb696…` | Eugene | 1532 | 09:02.82–09:12.78 | 28 |
| `2b013ef8…` | Tom | 1532 | 15:48.30–15:55.50 | 13 |
| `d890e55e…` | Tom | 1532 | 10:20.14–10:22.04 | 9 (too short; not selected) |

Prior pilot spans (H1, U1-clear, O1, R1, H1-gs2, Patio, N1) are **not** reused as overlap held-outs.

---

## Proposed four-span pilot (Eugene Will first)

| Key | Role | Annotation | Expected |
|---|---|---|---|
| **T-gs2-reuse** | Training | `3eb88a19…` grandpa 002 00:26.30–00:34.78 | Eugene reference (same clear interval as lifecycle R1-gs2-fresh) |
| **E2-1532-overlap-held-out** | Held-out | `bbceb696…` 1532 09:02.82–09:12.78 | Eugene **match** — overlap/poor-audio acceptance case |
| **O2-tom-offcamera-negative** | Held-out | `2b013ef8…` 1532 15:48.30–15:55.50 | Eugene **no_match** — new off-camera Tom control |
| **N1-TV-announcer-unknown** | Held-out | `74cc9646…` meals on wheels | Eugene **no_match** |

**Budget:** 32.38 s selected audio; one attempt per span; no automatic retry.

---

## Founder waiver required before execution

The blanket rule excludes `vid-c57dbd21f993f6d1` from **Eugene training and Eugene held-out match evidence** because TV/background overlaps Eugene throughout Tom's review.

This proposal uses **one** Eugene assignment on 1532 (`bbceb696…`) as the overlap/poor-audio **positive** held-out. That requires you to confirm:

1. **`bbceb696…` is truthful** — Eugene Will speaking on that interval despite overlap/poor audio.  
2. **Interval-specific waiver** — you approve using this annotation only for bounded overlap acceptance, without reopening H1/U1/O1 or general 1532 Eugene matching.

If you reject the waiver, save a new Eugene overlap annotation on an **approved** non-1532 source and we revise the proposal.

---

## Explicitly not in scope

- Q1 (02:18–02:23) — still listening-only; no saved annotation  
- Positive Tom recognition — O2 is an Eugene **negative** control only  
- Gate 4, Learn unlock, drains, or transcription  
- Generalized accuracy across 1532 or the corpus  

---

## Next steps

1. **Tom:** Confirm or reject the `bbceb696` waiver and that `2b013ef8` is the intended off-camera Tom control (vs `d890e55e`).  
2. **Agent:** After approval, add `prepare-overlap-poor-audio-voice-pilot.py`, readiness doc, and deployment guard (same pattern as reprocessing pilot).  
3. **Tom:** Explicit production approval before `-Execute`.

Preflight (after approval package exists):

```powershell
$python = 'C:\MemoryBox-releases\p2-i13-voice-pilot-6d56da5\.titanet-venv\Scripts\python.exe'
cd C:\MemoryBox
& $python -B docs\implementation\p2-i13-stage-a\prepare-overlap-poor-audio-voice-pilot.py
```

No recognition run until waiver + production approval are recorded.
