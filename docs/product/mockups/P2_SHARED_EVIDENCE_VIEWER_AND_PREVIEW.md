# Visual SoT — Shared Evidence Viewer + Gallery quick preview

**Status:** I4 build authority · PNG masters extracted 2026-08-13 · runtime on `cursor/p2-i4-mixed-media-explore-3061`  
**Authority:** [MBUX-001 v0.4](../MBUX-001_v0.4.md) §22.4–22.6 · [MBCAP-001 v0.2](../MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md) CAP-P2-026  
**Planning delta:** [MBBS_P2_MBCAP_MBUX_v0.4_PLANNING_DELTA.md](../MBBS_P2_MBCAP_MBUX_v0.4_PLANNING_DELTA.md)

## 1. Shared Evidence Viewer (drill-down from Ask / Explore gallery)

**One shell. Many contexts.** Photo is the base; Video adds transport (and optional transcript) without changing overall viewer size.

### Chrome
- Header: Previous / Next, position (`N of M`), Close
- Footer (photo): **working zoom** `− % +` (±5%); **Inspect** → Source rail; **Share** (visible now, wiring later); Add story; More later
- Footer (video): play/pause, scrub, time, volume, captions/transcript toggle, expand — same shell proportions

### Media
- Face boxes + labels on the evidence when geometry exists
- Rail is context — **not** a redundant thumbnail strip of the same people
- Do not list placeholder **Unknown** as a confirmed person

### Right rail states (icon toggle)
| State | Intent |
|-------|--------|
| **People** | People in this evidence: avatar, name, relationship, confirmation |
| **Story** | Linked story summary + Read; or empty “No story yet” + Add story |
| **Artifact** | Linked artifact card + View; or empty/add path |
| **Source** | Type, date, location, provider, original preserved, filename + **Camera/EXIF when Immich provides it** (honest empty state when stripped) |
| **Learn** | Selected face + Assign / Reassign / Unassign / Add unknown / Learn from this face |

### Video transcript
- **Off by default**
- On: media viewport shrinks inside the same shell; transcript scrolls with playback; active line highlighted; speaker labels when known

### Return
Closing restores Ask / filters / timeline range & playhead / gallery density & browse position (MBUX §22.4 / CAP-P2-026).

## 2. Gallery mouse rollover / focus preview

Derived from the full viewer; exists only to help decide whether to open.

- **2.5 second** hover delay, then preview appears
- **Upper-left of the preview** sits at the **pointer location at show time**; preview does **not** follow the mouse afterward
- Keyboard focus uses the same delay; anchors at the card’s upper-left
- Touch opens/selects the full viewer (no hover dependency)
- Show only useful at-a-glance fields when available: still, type, date, place, people, short title, brief excerpt, source, duration
- **Do not** turn preview into a miniature detail screen / full rail

Map markers may reuse the same lightweight preview (MBUX §22.7).

## 3. Design principles (from mockup board)
- One shell; rail adapts
- Contextual, not redundant
- Learn anywhere (photo or paused frame) → reusable first-class evidence later

## 4. PNG masters (extracted)

Word master: [`docs/source/mockups/Screen_mockups_from_p2I4_shared_gallery.docx`](../../source/mockups/Screen_mockups_from_p2I4_shared_gallery.docx)

| PNG | Role |
|-----|------|
| [`p2-ask-gallery-mixed-media-canvas.png`](../../source/mockups/p2-ask-gallery-mixed-media-canvas.png) | Ask gallery mixed-media canvas (context; not I4 redesign target) |
| [`p2-shared-evidence-viewer-right-rail.png`](../../source/mockups/p2-shared-evidence-viewer-right-rail.png) | Shared Evidence Viewer + rail states |
| [`p2-gallery-rollover-preview.png`](../../source/mockups/p2-gallery-rollover-preview.png) | Quick rollover / focus preview |
| [`p2-ask-gallery-photo-results.png`](../../source/mockups/p2-ask-gallery-photo-results.png) | Ask photo results gallery (context) |

## 5. I4 vs later (authorized 2026-08-13)

**Authorized for I4 build:** Shared Evidence Viewer shell + gallery rollover/focus preview (this inventory).  
**Out:** Named Places, Living Albums, transcript-as-gate, full Story/Artifact authoring inside the rail, Share plumbing.

### Founder FlightSim notes → product answers
| Note | Answer |
|------|--------|
| Zoom `− 100% +` dead | **Now** — wired (±5%, 50%–300%); stage scrolls so footer stays visible |
| Inspect? | **Now** — opens Source rail (face-overlay inspect later) |
| Share loved | **Future** — button stays; stub alert |
| Recent pic missing EXIF on right | **Now when Immich returns it**; honest empty copy when stripped |
| Rollover position / timing | **Now** — 2.5s hover; UL at pointer; no follow |

See [planning delta §7](../MBBS_P2_MBCAP_MBUX_v0.4_PLANNING_DELTA.md).
