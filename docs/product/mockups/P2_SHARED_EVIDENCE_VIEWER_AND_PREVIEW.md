# Visual SoT — Shared Evidence Viewer + Gallery quick preview

**Status:** Planning inventory · founder mockups reviewed 2026-08-13 · **no UI build on this branch**  
**Authority:** [MBUX-001 v0.4](../MBUX-001_v0.4.md) §22.4–22.6 · [MBCAP-001 v0.2](../MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md) CAP-P2-026  
**Planning delta:** [MBBS_P2_MBCAP_MBUX_v0.4_PLANNING_DELTA.md](../MBBS_P2_MBCAP_MBUX_v0.4_PLANNING_DELTA.md)

## 1. Shared Evidence Viewer (drill-down from Ask / Explore gallery)

**One shell. Many contexts.** Photo is the base; Video adds transport (and optional transcript) without changing overall viewer size.

### Chrome
- Header: Previous / Next, position (`N of M`), Close
- Footer (photo): zoom; Inspect; Share; Add to story; More
- Footer (video): play/pause, scrub, time, volume, captions/transcript toggle, expand — same shell proportions

### Media
- Face boxes + labels on the evidence (e.g. Peggy / Rick / Tom)
- Rail is context — **not** a redundant thumbnail strip of the same people

### Right rail states (icon toggle)
| State | Intent |
|-------|--------|
| **People** | People in this evidence: avatar, name, relationship, confirmation |
| **Story** | Linked story summary + Read; or empty “No story yet” + Add story |
| **Artifact** | Linked artifact card + View; or empty/add path |
| **Source** | Type, date, location, provider, original preserved, imported, filename + View file info |
| **Learn** | Selected face + Assign / Reassign / Unassign / Add unknown / Learn from this face |

### Video transcript
- **Off by default**
- On: media viewport shrinks inside the same shell; transcript scrolls with playback; active line highlighted; speaker labels when known

### Return
Closing restores Ask / filters / timeline range & playhead / gallery density & browse position (MBUX §22.4 / CAP-P2-026).

## 2. Gallery mouse rollover / focus preview

Derived from the full viewer; exists only to help decide whether to open.

- Mouse hover and keyboard focus are equivalent
- Touch opens/selects the full viewer (no hover dependency)
- Show only useful at-a-glance fields when available: still, type, date, place, people, short title, brief excerpt, source, duration
- **Do not** turn preview into a miniature detail screen / full rail

Map markers may reuse the same lightweight preview (MBUX §22.7).

## 3. Design principles (from mockup board)
- One shell; rail adapts
- Contextual, not redundant
- Learn anywhere (photo or paused frame) → reusable first-class evidence later

## 4. PNG masters
Place exported PNGs here when available:

```text
docs/source/mockups/p2-shared-evidence-viewer-right-rail.png
docs/source/mockups/p2-gallery-rollover-preview.png
```

Until then, founder chat mockups (2026-08-13) remain the review reference.

## 5. I4 vs later (authorized 2026-08-13)

**Authorized for I4 build:** Shared Evidence Viewer shell + gallery rollover/focus preview (this inventory).  
**Out:** Named Places, Living Albums, transcript-as-gate, full Story/Artifact authoring inside the rail.

See [planning delta §7](../MBBS_P2_MBCAP_MBUX_v0.4_PLANNING_DELTA.md).
