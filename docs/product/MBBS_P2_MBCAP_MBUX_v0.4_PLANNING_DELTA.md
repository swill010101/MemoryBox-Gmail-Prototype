# MBBS — Planning delta: MBCAP-001 v0.2 + MBUX-001 v0.4

**Status:** Planning only (docs ingest authorized 2026-08-13) · **No silent resequence of MBRM-001A**  
**Branch:** `cursor/p2-mbcap-mbux-docs-3061`  
**Masters:**  
- [MBCAP-001 v0.2 DOCX](../source/MBCAP-001_MemoryBox_Capability_Catalog_P2_v0.2.docx) · [markdown extract](MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md)  
- [MBUX-001 v0.4 DOCX](../source/MBUX-001_MemoryBox_UX_Foundation_and_Design_Principles_v0.4.docx) · [markdown extract](MBUX-001_v0.4.md)

## 1. What supersedes what

| Prior artifact | New authority |
|----------------|---------------|
| MBUX-001 v0.4 **I4 Mixed-Media Exploration Addendum** alone as UX SoT | **Full MBUX-001 v0.4** (addendum content absorbed into §22; addendum file kept historical) |
| No in-repo MBCAP catalog | **MBCAP-001 v0.2** capability backlog CAP-P2-001…026 |
| Informal “views / map / viewer” notes | CAP-P2-014 / 024 / 025 / 026 + MBUX §22.4–22.9 |

Traceability reminder (MBCAP §1): **EVS → Experience Flow → Capability → Domain / Services → Implementation Increment**.

## 2. Newly locked product concepts (not auto-scheduled)

| Concept | Authority | Default increment home (proposal only) |
|---------|-----------|----------------------------------------|
| Mixed-media canvas, Timeline, Map lens | MBUX §22.1–22.3, §22.7 · CAP-P2-001 / 025 | **P2-I4** (in progress) |
| Shared Evidence Viewer + rail (People / Story / Artifact / Source / Learn) | MBUX §22.4–22.5 · CAP-P2-026 · [mockup inventory](mockups/P2_SHARED_EVIDENCE_VIEWER_AND_PREVIEW.md) | **I4 candidate** (shell + preview); full Learn/Story authoring may spill later |
| Quick rollover / focus preview | MBUX §22.6 · mockup inventory | **I4 candidate** |
| Named Places (family object; lat/lng detail) | MBUX §22.8 · CAP-P2-024 | **Post-I4** until definition change |
| Living Album (saved intent, recomputes) | MBUX §22.9 · CAP-P2-014 | Map to **P2-I13 Dynamic Views** (or dedicated def) — **not I4** |
| Face / video / speaker / cross-modal learning | CAP-P2-003…010 | Existing I1+ chains; no change without definition |

## 3. CAP-P2 inventory (v0.2)

001 UX Refinement & Product Maturation · 002 Archive Health · 003–010 identity/video/voice/cross-modal · 011 Kinship · 012 Cross-source · 013 Narrative · 014 Dynamic Views / Living Album · 015 Summaries · 016 Correction lifecycle · 017 Trust · 018 SMS · 019 Email · 020 Capture · 021 Family contribution · 022 Multi-user · 023 Settings · **024 Places** · **025 Map exploration** · **026 Shared Evidence Viewer**.

Open MBCAP work (doc §5): refine CAP-P2-001; map 024/025/026 + Living Album to EVS/increments; Place / LivingAlbum domain detail; HVRT→MBCAP inventory.

## 4. I4 boundary (default until Tom changes I4 definition)

**In / candidate for I4 (underneath current Explore; no redesign):**
- Gallery hover/focus quick preview (lightweight; mockup SoT)
- Shared Photo/Video viewer shell; Close restores browse position
- Right rail **People** + **Source** (read-oriented)
- Map as result lens + GPS honesty (already in I4 thread)

**Out of I4 unless definition amended:**
- Named Places / saved pins as durable domain objects
- Living Albums (live / curated / snapshot)
- Full Story/Artifact authoring inside the rail (empty+CTA / link-out OK)
- Video transcript panel (spec: optional, off by default — defer)
- New top-level apps or Explore chrome redesign

## 5. Visual SoT — drill-down mockups

Founder screen mockups (2026-08-13) for Ask gallery → inspect:

1. **Shared Evidence Viewer — right rail states** (Photo + Video; People / Story / Artifact / Source / Learn; transcript off/on)
2. **Gallery mouse rollover / focus preview** (quiet at-a-glance; not mini-detail)

Inventory + I4 mapping: [mockups/P2_SHARED_EVIDENCE_VIEWER_AND_PREVIEW.md](mockups/P2_SHARED_EVIDENCE_VIEWER_AND_PREVIEW.md).  
PNG masters: add under `docs/source/mockups/` when exported; chat images were the review reference.

## 6. Explicit non-goals of this ingest

- No MBRM-001A resequence without a separate founder decision  
- No Explore/Ask runtime code on this branch  
- No inventing Place / LivingAlbum schemas here  

## 7. Founder decisions locked (2026-08-13 evening)

| # | Decision |
|---|----------|
| 1 | **DOCX = master**, markdown = working extract (same as MBPS/MBEVS). |
| 2 | **I4 UI amendment authorized:** Shared Evidence Viewer + gallery rollover/focus preview **only** (not Named Places, not Living Albums, not full Story/Artifact authoring products). |
| 3 | Visual masters: Word doc *Screen mockups from p2I4 shared gallery.docx* with embedded PNGs → park under `docs/source/mockups/` when extracted. |
| 4 | **Full planning delta** (this document) is the planning record. |

### I4 build scope (authorized)

**Build now**
- Shared Evidence Viewer shell (Photo + Video; prev/next; Close restores explore snapshot)
- Right rail tabs People / Story / Artifact / Source / Learn — **contextual panels** with empty/link-out states; Learn reuses existing teach slot / Review paths
- Gallery mouse hover + keyboard focus **quick preview** (lightweight; not mini-detail)

**Still out of I4**
- Named Places / saved pins as durable domain objects
- Living Albums (→ P2-I13 or dedicated definition)
- Video transcript as a required acceptance surface (toggle may exist; off by default; not a gate)

## 8. Next decisions for Tom

1. After FlightSim pass of viewer + preview, whether to expand Learn rail beyond existing I1 correction.  
2. Confirm Living Albums → **I13** (or new increment id).  
3. Confirm Named Places increment home (with CAP-P2-024/025).  
