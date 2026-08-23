# P2-I10B — Artifacts

**Status:** Definition **build-authorized 2026-08-23** · **implementing** · not increment-ACCEPTED until prove + owner sign-off  
**PR base:** `cursor/p2-i10a-stories-49da` until I10A lands; rebase/retarget before merge.  
**PRD:** [MBPRD-P2-I10B_ARTIFACTS.md](MBPRD-P2-I10B_ARTIFACTS.md)  
**Assessment:** [MBAS-P2-I10B_ASSESSMENT_RECONCILIATION.md](MBAS-P2-I10B_ASSESSMENT_RECONCILIATION.md)  
**Visuals:** Artifact PNGs on `fe913a4` (`cursor/marvin-capture-v01-3344`) in `docs/source/Screens/MBUX Story Screens/`. Copy into `docs/source/Screens/MBUX Artifact Screens/` before implementation.  
**Depends:** I10A Stories **ACCEPTED** · I10 **ACCEPTED** · I9 Artifact domain · I10A.1 Person Profile (sequence) · **I10A.2 Unified Voice Capture** before Tell its story  
**Does not start:** I10C Journal implementation · I11 narrative · nested Artifacts · Artifact-specific recorder · file GC · family multi-user ACL

## Intent

An Artifact is a durable MemoryBox **object**. Files that **are** the object are representations. Other photos, videos, communications, calendar items, journal entries, and audio are **supporting memories**. Family testimony lives on a first-class **Story**. Save Artifact makes an active record (no working draft). Original uploaded representation files are preserved.

I10B is **not** I11. I10B is **not** a second Story product.

## Build locks (from PRD)

1. Panel filters: All / Objects / Documents / Recipes / Other — mapped to existing kinds.
2. One optional Artifact date (`described_start_date`) with precision `day | month | year | approximate | unknown`. **No** `described_end_date`.
3. Place is `artifacts.place_id` only — no Artifact location string; no runtime `about_place` dual-write.
4. Visibility = I10A `private` | `shared_with_family`. Owner Ask sees private. Do not expose to unauthorized users.
5. No Artifact working draft. Save = panel + Ask (subject to visibility).
6. Zero representations allowed; show Needs context / Needs representation.
6a. New: browser-local staging → Save Artifact → then upload. Cancel before Save writes nothing. Partial upload failure keeps the Artifact.
7. No nested/container Artifacts.
8. Soft-remove Artifact and representations; keep original files; removed reps have no product-visible bytes.
9. Story association = `story_version_memories` `source_kind=artifact`. Compat-read `about_artifact`.
10. Supporting memories: photo, video, communications, calendar, journal, audio — not Artifact→Artifact. Unique `(artifact_id, source_kind, source_id)`; relink reactivates.
11. Rail overflow: Remove link, confirmed; do not delete media or Artifact.
11a. Person unlink: `relationships.status='superseded'` only.
12. Creator = owner/account, not ArtifactPerson.
13. No suggested memories.
14. Representations this increment: listed image/document MIME only; preview vs download/open-original as in the PRD.
15. Link existing Story · new Story prelinked · Tell its story via **I10A.2** only (shared Story editor; no Artifact `MediaRecorder`).

## Locked implementation choices

- Kind filter SQL: Objects = `keepsake_object` + `photograph_of_object`; Documents = `letter` + `document` + `clipping`; Recipes = `recipe_card`; Other = `other`.
- Metadata edits still write `artifact_metadata_revisions` (silent history, no draft UI).
- Tell its story must not ship if I10A.2 is not accepted.
- Sequence remains I10A → I10A.1 → I10A.2 (Stories first) → I10B → I10C → I11.

## Prove (when build is authorized)

`python -m memorybox prove-artifact` extended for I10B, including Save-then-upload, partial fail/retry, Cancel before Save, memory reactivate, person `superseded`, owner vs unauthorized retrieve, and removed-rep bytes hidden. FlightSim: `/artifact/ui` after `migrate` (when authorized). Tell its story prove waits on I10A.2.

## After I10B

**I10C Journal** (same shared voice). **I11** remains closed until I10A + I10A.1 + I10A.2 + I10B + I10C and required recognition/transcription work.
