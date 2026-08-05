# MB-FW-001 — MemoryBox Experience Walkthrough

| Field | Value |
|-------|--------|
| **Doc ID** | MB-FW-001 |
| **Title** | Experience Walkthrough |
| **Version** | 2.0 |
| **Status** | Canonical walkthrough for product communication + user testing |
| **Purpose** | Communicate MemoryBox to someone who has never seen it — without narration |
| **Location** | [`application/ui/mockup/walkthrough/`](../../application/ui/mockup/walkthrough/index.html) |

## Why this exists

This is **not** a UI redesign and **not** a storyboard.

It is an Experience Walkthrough whose job is to make a first-time viewer understand:

- what the user did
- why MemoryBox responded
- how the archive became richer
- why the next screen appears

Every transition must have an obvious cause.

Experience Boards convey feeling. Prototype 1 validates clickable discovery. This walkthrough validates **product understanding** for reviewers who will never hear Tom narrate.

## Philosophy

MemoryBox is not the star. **The family is.**

The software quietly disappears into the background. The archive becomes richer through exploration. The experience should feel calm, warm, natural, and authentic.

Avoid drama, theatrical writing, marketing language, and emotional manipulation. Let people and their stories create the emotion.

### Visual direction

Reduce the museum aesthetic (~70%). Prefer:

- Apple Photos / Apple TV / Apple Journal calm
- A beautifully designed family room
- Warm wood, natural light, soft whites, light grays, muted blues
- Family photography

Elegant trusted companion — not an exhibit.

## Optimize for user testing (not presentation)

Do not polish for applause. Every panel should invite critique.

If a reviewer says **“I wish I could…”** or **“What if it also…”**, the walkthrough has succeeded.

## Every screen must answer

1. What did the user just do?
2. What did MemoryBox understand?
3. What changed?
4. Why is the next screen appearing?

The viewer should never wonder: “How did we get here?”

## Interaction styles shown

Voice · Typing · Mouse selection · Touch · Rubber-band object · Rubber-band face · Simple clicking · Natural conversation

Not everything is voice.

## Timing

No static panel should linger ~45 seconds.

| Kind | Typical |
|------|---------|
| Simple interaction | 3–5 seconds |
| Result | 6–10 seconds |
| Story / voice intentionally playing | Longer only while it plays |

## Canonical scenes (1–14)

| Scene | Beat |
|-------|------|
| 1 | Family after dinner. MemoryBox: “What would you like to explore today?” |
| 2 | Voice: “Show me pictures of Dad from his later years.” Beautiful photographs — memories, not folders/grids. |
| 3 | User selects one photograph → enlarges. |
| 4 | Rubber-band Grandpa’s pocket watch. “This object doesn’t have a story yet. Would you like to add one?” |
| 5 | Voice story about the watch. Transcript. Links: Dad · Pocket Watch · This photograph · This time period. “I’ll remember that.” |
| 6 | Return to Dad’s photographs. |
| 7 | Rubber-band a woman’s face → type “Aunt Sue” → “Who was Aunt Sue to your family?” → short voice story. |
| 8 | “I found Aunt Sue in 184 photographs, 7 home movies, and 3 family stories.” Shown naturally. |
| 9 | Another photo with the same watch → **Story Available** (prior teaching can play). MemoryBox remembers. |
| 10 | Return Home. |
| 11 | “Show me Christmas from last year.” Christmas memories; Grandpa’s dinner rolls visible. |
| 12 | “Do we still have Dad’s roll recipe?” Recipe card, Christmas photos, video, email, text, Grandpa’s voice — connected. |
| 13 | Family makes the rolls. Quiet note: today the grandchildren made Grandpa’s rolls. Archive grows. |
| 14 | Home → “Show me our Alaska trip from 2026.” Exploration continues indefinitely. |

## Pass / fail (success criteria)

A person who has never heard of MemoryBox can view this without narration and answer:

1. What is MemoryBox?
2. How do I interact with it?
3. How does it learn?
4. Why does every interaction make the archive better?
5. Why would I want this?

If those cannot be answered naturally, the walkthrough is not complete.

Also: each panel’s on-screen **cause strip** (User did / Understood / Changed / Why next) should make transitions obvious.

## Open this

**Primary (show folks this):** [walkthrough/index.html](../../application/ui/mockup/walkthrough/index.html) — timed player + cause captions + scene strip

**Video export:** [`MemoryBox-Walkthrough-v2.mp4`](../../application/ui/mockup/walkthrough/v2/MemoryBox-Walkthrough-v2.mp4) (~110s, test pacing)

**Legacy (superseded):** [walkthrough/rich.html](../../application/ui/mockup/walkthrough/rich.html) — dark museum-era panels + ~48s v1 video

## Related

- [MB-XB-001 Experience Boards](MB-XB-001%20Experience%20Boards.md) — feeling / continuity
- [MB-DEMO-001 Silent Demonstration](MB-DEMO-001%20Silent%20Demonstration.md) — longer silent demo (legacy pacing)
- [Prototype 1](../../application/ui/mockup/prototype/index.html) — clickable scenes
- [MBUX-001](MBUX-001%20Memory%20Box%20User%20Experience%20Specification.md) — three-question rule
