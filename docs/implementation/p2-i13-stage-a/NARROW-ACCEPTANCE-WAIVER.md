# Narrow bounded voice acceptance waiver

**Status:** Tom authorized 2026-09-08 (chat option **2**)  
**Waiver reference:** `Tom-narrow-bounded-voice-acceptance-waiver-2026-09-08`  
**Owner-truth export reference:** `Tom-owner-truth-export-flightsim-2026-09-08`

This waiver satisfies the **bounded acceptance prerequisite** for Gate 4 archive planning. It does **not** authorize register, unlock, start, drains, Learn, full I13 acceptance, or P2-I14.

---

## Problem

Full 22-source `acceptance_learning` requires owner truth and complete coverage tags on every manifest source. FlightSim export on 2026-09-08 shows **388 / 35,861** words reviewed (**5 / 22** sources with saved assignments). Corpus-wide acceptance is not realistic before archive planning.

Seven bounded voice pilots already produced stopped, current evidence with immutable admission provenance.

---

## What this waiver accepts

Tom records that **bounded voice acceptance** for I13 Stage A is satisfied by:

| Evidence | Admission IDs (stopped, do not retry) |
|---|---|
| Original Eugene (T1, stale) | `1039c733-2149-40b2-b027-97058e032af3` |
| Tom off-camera positive | `9e0a2605-8bfc-4ec7-aa6e-501f9bca7cea` |
| N1 Unknown no-match | `46cb1d21-b464-4bc4-bf7c-7d0de0202ca6` |
| Eugene Patio | `f59050d5-cb4b-4ff7-beee-609b28f7af61` |
| Eugene reprocessing lifecycle | `66fb93af-92a9-4ef1-b3e6-c0f700e89276` |
| Overlap / poor-audio Eugene | `339b3a14-5069-4554-846f-dc84d6745c00` |

Plus **13 active owner annotations** on **five manifest sources** from GET `/annotations/transcript/coverage` (export ref above).

---

## What this waiver does not accept

- Full 22-source corpus owner truth or coverage completeness
- Face/voice corroboration matrix completion
- Generalized speaker accuracy across the manifest
- Archive processing execution (unlock/start/drain)
- Full I13 increment sign-off or P2-I14 authorization

---

## Use as `--acceptance-ref`

When Gate 4 moves beyond plan-only preview, the archive `unlock` command must use:

```text
--acceptance-ref Tom-narrow-bounded-voice-acceptance-waiver-2026-09-08
```

Unlock still requires a **separate** founder unlock reference and a reviewed archive plan. Start remains a third separate decision.

---

## Archive plan scope (Outcome B — plan-only)

[archive-manifest-proposal.json](archive-manifest-proposal.json):

| Field | Value |
|---|---|
| `scope_kind` | `archive` |
| Sources | 5 with owner truth (1530, 1532, meals on wheels, Grandpa sessions 003, grandpa 002) |
| People | Eugene Will, Tom Will |
| Lanes | `face` only (archive pass preview) |
| Work items | **10** (5 × 2 × face) |
| Max attempts | **20** (10 × 2) |
| Plan SHA-256 | `f36cdb19c51abe13234b80c08b746901d5d195c5e8be621e10e5f2a85f46316c` |

Re-run preview on FlightSim after pull; SHA must match if plan bytes unchanged.

---

## Sign-off

| Field | Value |
|---|---|
| Decision | Narrow waiver + Gate 4 Outcome B (plan-only) |
| Signed | Tom (chat 2026-09-08, option 2) |
| Date | 2026-09-08 |
