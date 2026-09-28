# Prompt-change recommendations (prompt not modified)

Prompt identity remains `i11a0-narration-v0.2-draft` SHA-256 `c91f313cc86ebad1c8fde6008e6f283c8bf76aa881bae9118327a6d6c70f7b3b`.

**Any material prompt change invalidates prompt identity and requires one new 27K confirmation run before I11A.0 closes.** This file does not change the prompt.

Separate **confirmed defects** from **stylistic preferences**. Recommend prompt text changes only when the audit supports them.

## Confirmed defects

### 1. User wrapper lied about partial context (controller, not prompt text)

**Defect.** Manifest `partial_context: true` (T-0958; included `93a44b2a-…`; omitted `8c2b7377-…`). User message: `partial_context: no`. `packet_from_saved_row` in `i11a0_gate3.py` forces `partial_context=False`. The model then correctly skipped the missing-context close.

**Recommendation.** Fix the controller so `render_user_message` receives the packed flag and boundary IDs. That is **not** a prompt-identity change.

**Benefit.** Partial-context close can fire when the packet is actually split.  
**Downside.** One confirmation run still needed if you want 27K output under the corrected wrapper, because the **user** bytes change even if SYSTEM_PROMPT does not. Treat that as a wrapper-identity change, not a SYSTEM_PROMPT change.

### 2. Citations were ignored

**Defect.** Four outputs, zero `[email_N]` or UUID citations. The current prompt already requires per-sentence citations.

**Possible prompt change (only if founder wants stronger enforcement).** Add one negative example: a sentence with a date and no citation is invalid; require the packet’s printed `Evidence-ref` or `Evidence-id` form exactly as shown in the evidence block.

**Benefit.** Makes audit possible; reduces unanchored claims.  
**Downside.** More mechanical prose; may eat output budget on IDs; **invalidates prompt identity**; needs one new 27K confirmation.

Do not treat “founder prefers fewer citations” as a defect. Zero citations is a confirmed prompt-compliance failure.

### 3. Emotion, significance, and completed outcomes stated as fact

**Defect.** The prompt already forbids stating emotion/motive/significance as fact and forbids treating plans as events. The model did both.

**Possible prompt change.** Add a short hard list: do not write palpable, heartfelt, close-knit, paid off, everyone received, joy of giving, unless those words (or clear equivalents) appear in the evidence. Require “the packet shows a plan to…” versus “X happened.”

**Benefit.** Directly targets the audited failure mode.  
**Downside.** Ban-lists can produce stiff prose or missed genuine Peg lines (“My love to all,” “what I treasure most”). **Invalidates prompt identity**; needs one 27K confirmation.

### 4. Time range in the user header was ignored

**Defect.** User message includes `time_range: 2005-12-10 … to 2007-12-04`. Narration is late autumn 2006 only.

**Possible prompt change.** Require the first paragraph to name the packet’s `time_range` and to include at least one dated event from near the start and near the end when those exist, without padding.

**Benefit.** Stops Christmas-only compression of a two-year packet.  
**Downside.** Can force awkward coverage of thin 2007 tails; **invalidates prompt identity**.

### 5. Repeatability of C and D

**Defect.** Same packet, prompt, digest, temperature 0.1, seed 42; A=B but C and D diverge (including extra completed-event claims in C).

**Recommendation.** Not a prompt fix. Record as sampler/non-determinism at this size. Do not paper over it by picking the nicest repeat.

## Stylistic preferences (do not prompt-change unless founder asks)

- Four short paragraphs vs eight
- “Peg Legg” vs “Peggy”
- How many named SKUs to mention
- Whether MS-150 belongs in a holiday-centered telling — **as evidence weight it belongs in this packet**; omitting it is a coverage defect, not a taste issue
- Hallmark cadence vs dryer documentary sentences — related to defect 3, but “make it prettier” is preference

## Explicitly not recommended from this audit

- Lengthening toward a Peggy biography
- Adding SMS/photos/calendar
- Changing the model or pulling weights
- Relaxing citation rules to match these four outputs
- Editing `canonical_narration.md`

## If founder accepts with prompt changes

1. Change SYSTEM_PROMPT (and/or USER_TEMPLATE) in a dedicated increment.  
2. Recompute prompt SHA.  
3. Run **one** 27K confirmation on the same packet SHA `ae0fcbb7…` before I11A.0 close.  
4. Do not reopen I14 behavior. Do not start Peggy narrative from that run.
