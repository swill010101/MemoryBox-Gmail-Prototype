# MB-EX-001 — MemoryBox Experience Mockups

| Field | Value |
|-------|--------|
| **Doc ID** | MB-EX-001 |
| **Title** | Experience Mockups (low / mid fidelity) |
| **Version** | 0.2 |
| **Status** | Validation artifact — not final UI |
| **Authority** | Subordinate to Founder's Book, MBPS, MBUX, MBMS, MBIA, MB-SB-001. Screens and scenes are a supporting actor only. |
| **Gallery** | [`experience/`](experience/index.html) |
| **Prototype 1** | [`prototype/`](prototype/index.html) — clickable **scenes** (First Five Minutes + Grandpa) |
| **Experience Boards** | [`experience-boards/`](experience-boards/index.html) — feeling, not mechanism ([MB-XB-001](MB-XB-001%20Experience%20Boards.md)) |

## Purpose

Let reviewers *feel* curator attention and discovery flow without mistaking this for a shipped design system.

- Still frames: [experience gallery](experience/index.html)
- Clickable Prototype 1: [prototype/index.html](prototype/index.html)

## Prototype 1 — scenes (not pages)

Mindset: **Storyboard → Scenes** (like a movie), not Storyboard → Screens/Pages.

| Scene | Intent |
|-------|--------|
| Threshold | Wonder; invitation; no folders |
| Invitation | Human question accepted as conversation |
| Discovery | Narrative first (Christmas, then Grandpa) |
| Reflection | Trust; soft invite; evidence only if curiosity asks |
| Teaching | Family teaches; MB remembers — after emotion |
| Presence | Photos & papers serve understanding |
| **Silence** | After Grandpa’s story/voice: **~5 seconds of nothing** — no flashing button, popup, suggestion, or animation |
| Wonder | Another door; bloom; open ask |

**Explorer Mode is postponed to Prototype 2.** Shop Prototype 1 first; adjust from feedback.

### Voice (Prototype 1 copy pass)

Quiet curator — not movie narrator. Reduce emotional narration; let people and artifacts create the emotion. Software is respectful, factual, and curious.

### Success criteria (Yes / No)

1. **One entry URL** — Prototype 1 opens from a single link and walks the scene sequence.
2. **Never feels like operating software** — visitor feels a museum with a quiet curator.
3. **Every click answers curiosity rather than navigates** — moves between discoveries, not “pages.”
4. **Silence is honored** — after Grandpa, the prototype waits before any invite returns.
5. **Favorite:** The visitor **naturally asks another question before the end**. If they only say “Okay,” Prototype 1 failed.

## Still-frame gallery (EX-01–EX-08)

| ID | File | Validates |
|----|------|-----------|
| EX-01 | [ex-01-home.html](experience/ex-01-home.html) | Conversation front door; invitation not dashboard |
| EX-02 | [ex-02-narrative.html](experience/ex-02-narrative.html) | Narrative first; evidence available; human confidence phrasing |
| EX-03 | [ex-03-listening.html](experience/ex-03-listening.html) | Silence; story has right of way |
| EX-04 | [ex-04-teach.html](experience/ex-04-teach.html) | Invite not “Unknown Person #”; teach after emotion |
| EX-05 | [ex-05-voice-story.html](experience/ex-05-voice-story.html) | Human Story capture; People/Place/Moment |
| EX-06 | [ex-06-review-learn.html](experience/ex-06-review-learn.html) | Stewardship; suggestion ≠ knowledge |
| EX-07 | [ex-07-family-night.html](experience/ex-07-family-night.html) | Family Mode; multi-generational; no admin |
| EX-08 | [ex-08-explorer.html](experience/ex-08-explorer.html) | Explorer reference still — **not in Prototype 1 path** |

## Validation questions

1. Does this still feel like a museum curator — or like software to operate?
2. Is the visitor the main character?
3. Does evidence support understanding without stealing the emotional beat?
4. Would MBUX “never say” lines appear anywhere? (They must not.)
5. Did silence after Grandpa feel like a feature — or a bug?
6. Did the visitor want another question before the end?

## Out of scope

- FastAPI / live archive wiring  
- Final visual design system  
- **Explorer in Prototype 1** (held for Prototype 2)  
- Family Night / Memory Care / Funeral as full journeys  
- Replacing philosophy storyboards (MB-SB-001)
