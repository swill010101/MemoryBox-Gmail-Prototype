# P2-I12 — Historian Collection & Campaigns V1

**Status:** **ACCEPTED** 2026-09-04 (Tom: “i12 is accepted”) · Definition **LOCKED** 2026-09-03 · **BUILD AUTHORIZED S1–S5** 2026-09-03  
**Increment ID:** **P2-I12 Historian Collection & Campaigns** (replacement increment — not P1 Increment 12 Export; not former P2-I12 Dynamic Views)  
**Roadmap:** [MBRM-001B](MBRM-001B_P2_HISTORIAN_COLLECTION_AND_CAMPAIGNS.md)  
**PRD:** [MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md](MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md)  
**Domain model:** [MBDC-P2-I12_DOMAIN_MODEL.md](MBDC-P2-I12_DOMAIN_MODEL.md)  
**Screens:** [MBSC-P2-I12_HISTORIAN_COLLECTION_SCREEN_CONTRACT.md](MBSC-P2-I12_HISTORIAN_COLLECTION_SCREEN_CONTRACT.md)  
**Integration:** [MBAS-P2-I12_INTEGRATION_MAP.md](MBAS-P2-I12_INTEGRATION_MAP.md)  
**PoC reuse:** [MBAS-P2-I12_POC_REUSE_MATRIX.md](MBAS-P2-I12_POC_REUSE_MATRIX.md)  
**Migration:** [MBMP-P2-I12_MIGRATION_REPLAY.md](MBMP-P2-I12_MIGRATION_REPLAY.md)  
**Acceptance:** [MBAT-P2-I12_ACCEPTANCE.md](MBAT-P2-I12_ACCEPTANCE.md)  
**Depends:** I10A Stories **ACCEPTED** · I10A.1 People **ACCEPTED** · I10B Artifacts **ACCEPTED** · I11 Narration **BUILD AUTHORIZED**  
**Does not start:** I11B Curator learning · I13 Dynamic Views · I14 Settings · contributor mobile app · automatic campaign strategy · External Historical Context (EVS-254–256)

---

## Intent

P2-I12 is a **MemoryBox-native external-recollection solicitation, intake, owner-review, and adjudication system**.

The owner/historian:

1. Creates a **Campaign** with ordered questions for one or more **known canonical MB People** as respondents.  
2. Sends **one question at a time** per respondent through the dedicated Capture email channel.  
3. Receives replies as **immutable Capture Items** — external evidence, not accepted knowledge.  
4. Works in **versioned Review Drafts** without altering the inbound source.  
5. Records a **private qualitative owner assessment** separate from contributor words and system confidence.  
6. Issues an **explicit verdict** (retain / reject / promote-ready).  
7. **Optionally promotes** reviewed material into Story, Artifact, or accepted-source evidence with full provenance chain.

---

## What P2-I12 is not

- A direct-write questionnaire that immediately changes MemoryBox  
- A second MarvinCapture application beside MemoryBox  
- An automatic Story generator  
- A system that decides whether a relative is truthful  
- The old **P1 Increment 12 Minimum Viable Export**  
- The former **P2-I12 Dynamic Views** increment (now **P2-I13**)  
- Multi-user family contribution accounts (Late-P2/P2.5)

---

## Locked V1 lifecycle

```text
Campaign
  → per-recipient Question Cycle (Delivery)
    → immutable Capture Item
      → owner Review Draft(s)
        → explicit owner Verdict
          → optional Promotion
```

### Campaign

- Created and controlled by the sole owner/historian  
- One or more canonical **MB People** as respondents (each with confirmed contact route)  
- Ordered owner-authored or owner-selected questions  
- States: `draft` · `running` · `paused` · `stopped` · `completed` / `exhausted`  
- Questions sent **one at a time** per respondent  
- Each respondent has an independently traceable question/delivery cycle  
- Stop or exhaust prevents additional sends  

### Known-person respondent

- Every recipient resolves to a canonical **MB Person** before send  
- Outbound contact route **explicitly confirmed** by owner  
- Respondent does **not** need a MemoryBox account  
- **Never** silently guess among ambiguous people or contact methods  

### Question and delivery

- Preserve exact **question snapshot** sent (later campaign edits do not rewrite sent snapshots)  
- Record campaign, question order, respondent Person, contact route, channel, sent time, correlation, delivery status, retries  

### Immutable Capture Item

- Every inbound response creates an immutable Capture Item  
- Preserve original body, attachments, headers/transport metadata, timestamps, respondent, campaign, question, delivery, provenance, hashes  
- **Never** rewrite or replace inbound source  
- Unmatched/ambiguous replies → owner-visible holding/reconciliation  
- Duplicate transport IDs → idempotent  
- Capture Item = external evidence awaiting adjudication  

### Owner Review Drafts

- Editing, cleanup, transcription correction, contextual notes, proposed links → **versioned Review Drafts**  
- Every draft links to immutable Capture Item  
- Drafting never changes inbound source  
- Review history distinguishes original, earlier drafts, current proposed version  

### Explicit verdict

Owner must explicitly decide (minimum concepts):

- **Retain without promotion** — preserved testimony, not promoted knowledge  
- **Accept / promote** — owner authorizes promotion from reviewed draft  
- **Believe incorrect / reject as affirmative evidence** — preserved but cannot serve as affirmative evidence  

Rejection **never** deletes the Capture Item.

### Optional promotion

- Promotion copies from reviewed version; permanent link to Capture Item + Review Draft  
- May create/support: Story · Artifact representation · accepted-source evidence  
- **Do not** force every response into a Story  
- No promotion merely because a reply arrived  
- No silent publish or rewrite of testimony  

### Attribution

- Respondent = contributor/source of recollection  
- Tom = owner reviewer and MB record creator  
- Promoted recollection remains **human testimony**, not independently verified fact  
- Ask/narration must retain attribution and provenance  

---

## Owner assessment (V1 — founder lock)

One overall owner-assigned qualitative confidence assessment for the accepted contribution or promoted Story.

**Locked labels:** **High confidence** · **Moderate confidence** · **Low confidence** · **Uncertain**

- Private to owner  
- Separate from contributor’s words and from **verdict**  
- Separate from MemoryBox system/evidence confidence  
- Not sent back to contributor (including thank-you acknowledgments)  
- Reversible with history/provenance  
- Available to retrieval, aggregation, narration  
- Never transformed into automatic numeric truth percentage  

**Verdict** (separate): **Keep in archive** · **Reject as evidence** · **Promote to MemoryBox**

---

## Mail channel (locked)

| Item | Decision |
|------|----------|
| Mailbox | `memorybox@marvinbot.net` |
| Hosting | Namecheap |
| Outbound | This account |
| Inbound | Gmail inbox/integration for Capture account |
| Secrets | Outside Git |
| Provenance | Full inbound/outbound preserved |

Older Gmail plus-address PoC (`+MEM`, `+JRN`, subject-tag, Trash) = **reference only**.

---

## V1 scope — IN

- One owner/historian  
- Known canonical MB People  
- Owner-authored or owner-selected questions  
- Typed **email** responses  
- Thin campaign controls  
- Per-recipient question cycles  
- Immutable Capture Items  
- Owner review queue  
- Versioned Review Drafts  
- Explicit verdict  
- Private qualitative assessment  
- Optional deliberate promotion  
- Provenance-aware later retrieval  

## V1 scope — OUT (V2 feasibility backlog only)

- Curator-generated questions  
- Archive-gap-driven recommendations  
- Automatic adaptive follow-up  
- Automatic campaign strategy  
- iOS/Android contribution app  
- Voice recording / STT as contributor workflow  
- Speaker recognition  
- Contributor MemoryBox accounts  
- General multi-user editing  
- Social collaboration  
- Automatic credibility scoring  
- Automatic rewriting or publication  
- Automatic factual acceptance  
- Broad permissions/consent redesign  
- Cross-contributor reconciliation automation  

---

## Implementation sequence (when build authorized)

See [MBRM-001B §8](MBRM-001B_P2_HISTORIAN_COLLECTION_AND_CAMPAIGNS.md).

---

## Historical documents (unchanged)

| Document | Treatment |
|----------|-----------|
| `MBBS-001_INCREMENT_12_*` (P1 Export) | Historical on PoC branch — **do not reopen** |
| `MBRM-001` P2-I12 Dynamic Views row | Historical shell — superseded by MBRM-001B renumbering |
| `MBRM-001A` P2-I12 External Historical Context | Deferred backlog — not this increment |
| `codex/historian-capture-reference-screens-20260829` @ `fe913a4` | Reference screens only — **does not** contain Aug 29 packet |

---

**ACCEPTED** 2026-09-04 (Tom: “i12 is accepted”). Do not reopen.
