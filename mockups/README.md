# MemoryBox screen mockups

Validation artifacts from earlier experience-board / walkthrough work. Not the shipped UI.

**Source chat:** [Memory Box functional architecture](https://cursor.com/agents/bc-c5a07acd-29da-4fbf-9db2-e9f0ff52a5f9) agent (branches `cursor/experience-*-a5f9`).

Open [`index.html`](index.html) for links to:

| Entry | Path |
|-------|------|
| Experience gallery (screens) | [`experience/index.html`](experience/index.html) |
| Experience boards | [`experience-boards/index.html`](experience-boards/index.html) |
| Clickable prototype (scenes) | [`prototype/index.html`](prototype/index.html) |
| Feedback walkthrough | [`walkthrough/index.html`](walkthrough/index.html) |
| Rich media walkthrough | [`walkthrough/rich.html`](walkthrough/rich.html) |
| Silent demo (~15 min) | [`demo/index.html`](demo/index.html) |

Companion notes: [`MB-EX-001_Experience_Mockups.md`](MB-EX-001_Experience_Mockups.md).

## PNG pack for P2 UX

All P1 screens + these mockup screens as PNGs (**86 files**) in one ZIP:

- **ZIP (download this):** [`/workspace/MemoryBox_P1_and_Mockup_Screens_PNG.zip`](../MemoryBox_P1_and_Mockup_Screens_PNG.zip) (~87 MB)
- **Unpacked folder:** [`/workspace/ux-png-pack/`](../ux-png-pack/) (same PNGs, browsable in the IDE)

Both are local workspace artifacts (gitignored), not committed to the repo.

Contents:

| Folder | What’s inside |
|--------|----------------|
| `01_p1_screens` | Ask, People, Library, Review, Story, Journal, Artifact, Guided Capture, Export, Status (+ HVRT viewer/review) |
| `02_mockups_experience` | EX-01–EX-08 + gallery |
| `03_mockups_experience_boards` | 10 boards + full page |
| `04_mockups_prototype_scenes` | Prototype 1 scene captures |
| `05`–`07` | Walkthrough / demo / hub HTML captures |
| `08`–`09` | Existing walkthrough + silent-demo panel PNGs |

## Design chat that shaped these images

Pertinent prompts / decisions from that agent (architecture/docs-only stretches omitted):

1. **Philosophy storyboards first** — Pixar-style journeys (First Five Minutes, Grandpa, Voice Story, Review & Learn, Family Night, Explorer, etc.) to validate curator *feel*, not to design UI. Upstream of these folders (`MB-SB-001`).
2. **“Please mock up some example screens.”** → **`experience/`** EX-01–EX-08. Invitation home (not a dashboard), narrative-first answers, silence, teach (no “Unknown Person #”), voice→story, review/learn, family night, explorer as reference. Explicitly validation, not shipped UI.
3. **First clickable prototype** — Tom chose **Option B: First Five Minutes + Grandpa**, **scenes like a movie (not pages)**. Success: never feels like operating software; every click answers curiosity; **~5s silence after Grandpa** (no flash/popup/suggestion); visitor should naturally **ask another question** before the end. → **`prototype/`**
4. **“Hold Explorer for Prototype 2.”** Shop Prototype 1 first. EX-08 stays gallery-only in **`experience/`**.
5. **Copy critique** — Structure/flow OK; cut ~80% emotional narration; **quiet curator, not movie narrator**; people and artifacts carry the emotion. → **`prototype/`** copy pass.
6. **Experience Boards** — “what this *feels* like, not how it works.” Ten boards, rich HTML, whisper + tiny scene title outside the frame. Continuity rule: every screen answers *Why am I seeing this? / Why does it matter? / Where could this lead?* → **`experience-boards/`**
7. **Feedback walkthrough** — Storyline OK, gray wireframes too weak; want typed ask + mic, rich evidence counts, narrative, Grandpa/Sue teach path “as if real.” Then: generate rich media panels and/or a short video. → **`walkthrough/`** (+ `rich.html` / media / Feedback Walkthrough video).
8. **Silent ~15-minute demo** — Newcomers must understand MemoryBox **without Tom narrating**; build the demonstration, not the interface. → **`demo/`**

### Constraints Tom locked in this thread

- Philosophy validation ≠ interface design; UI is a supporting actor; visitor is the main character; MemoryBox is a museum curator.
- Scenes, not pages; silence after Grandpa; never feel like operating software.
- Feeling, not mechanism; quiet curator voice (no drama/marketing/manipulation).
- Silent demo / walkthroughs must work without a narrator.
- Explorer postponed to Prototype 2.

### Note on Walkthrough v2

A later approved PRD replaced the walkthrough with **v2.0** (no narrator, family-first, light home aesthetic / ~70% less museum, 14-scene cause-driven path). That work lives on `cursor/experience-walkthrough-v2-a5f9` / PR #9; **this `mockups/` snapshot still holds the Feedback Walkthrough + `rich.html` lineage**, not the full v2 tree.
