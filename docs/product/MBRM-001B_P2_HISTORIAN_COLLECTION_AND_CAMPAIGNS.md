# MBRM-001B — MemoryBox Roadmap: Historian Collection & Campaigns

**Status:** **ACCEPTED** 2026-09-04 (Tom: “i12 is accepted”) · Planning **RECOVERED** 2026-09-03 · **BUILD AUTHORIZED S1–S5** 2026-09-03  
**ID:** MBRM-001B  
**Owner:** Tom  
**Recovered from:** Founder-approved planning decisions (August 29, 2026 packet). The branch `codex/historian-capture-reference-screens-20260829` remote HEAD (`fe913a4`, August 22) does **not** contain this packet; this document is the authoritative Markdown equivalent recreated in Git.  
**Supersedes sequencing for:** P2-I12 through P2-I16 relative to [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) §3 rows for I12–I17  
**Does not supersede:** [MBRM-001_P2_ROADMAP.md](MBRM-001_P2_ROADMAP.md) shell history; P1 increment definitions; accepted I1–I11C builds  
**Planning package:** [MBBS-P2_INCREMENT_12_DEFINITION.md](MBBS-P2_INCREMENT_12_DEFINITION.md) · [MBPRD-P2-I12](MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md) · [domain model](MBDC-P2-I12_DOMAIN_MODEL.md) · [screens](MBSC-P2-I12_HISTORIAN_COLLECTION_SCREEN_CONTRACT.md) · [integration](MBAS-P2-I12_INTEGRATION_MAP.md) · [PoC matrix](MBAS-P2-I12_POC_REUSE_MATRIX.md) · [migration](MBMP-P2-I12_MIGRATION_REPLAY.md) · [acceptance](MBAT-P2-I12_ACCEPTANCE.md)

---

## 1. Purpose

This roadmap revision locks **replacement P2-I12 — Historian Collection & Campaigns V1** as the next founder-directed increment after P2-I11A strategic hold, and renumbers downstream increments without reopening completed P1 work or accepted P2 builds.

It authorizes **planning only**. Implementation requires explicit build authorization after Tom reviews this package.

---

## 2. Numbering distinctions (do not conflate)

| Label | Meaning | Status |
|-------|---------|--------|
| **P1 Increment 12 — Minimum Viable Export** | P1 export/import-back slice | **Completed and accepted** — historical record in `MBBS-001_INCREMENT_12_*` on PoC branch only; **do not rename or reopen** |
| **Replacement P2-I12 — Historian Collection & Campaigns V1** | MemoryBox-native external recollection solicitation, intake, review, adjudication | **ACCEPTED** 2026-09-04 (Tom: “i12 is accepted”) — `prove-historian-capture` · branch `cursor/p2-i12-s5-live-prove-7f27` |
| **Former P2-I12 — Dynamic Views** | Saved views, collections, persistence | Renumbered **P2-I13** |
| **Former P2-I13 — Settings & Processing Controls** | Settings maturation | Renumbered **P2-I14** |
| **P2-I15 — Trust Consistency & Private Owner Trust** | Formal trust/correction consistency | **Retained** (was I16 in MBRM-001A) |
| **P2-I16 — Portability & Import-back** | TASK-003 / EVS-020 | **Retained** (was I17 in MBRM-001A) |
| **MBRM-001A “P2-I12 External Historical Context”** | EVS-254–256 web/discovery context | **Not this increment** — remains a separate late narrative backlog item |

---

## 3. Execution sequence

### 3.1 Superseded sequence (August 29, 2026 — no longer authoritative)

```text
P2-I11A acceptance → P2-I11B acceptance → then P2-I12 Historian Collection
```

### 3.2 Current founder-directed sequence (September 2026)

```text
P2-I11A — on strategic hold (C1T gate / direct-narrative path may reopen later)
  → P2-I12 — Historian Collection & Campaigns V1  ← **ACCEPTED** 2026-09-04
  → P2-I11B — Curator responses / historian learning — DEFERRED until after I12
  → P2-I13 — Dynamic Views
  → P2-I14 — Settings & Processing Controls
  → P2-I15 — Trust Consistency & Private Owner Trust
  → P2-I16 — Portability & Import-back
```

I11A narration may later reopen through its recorded direct-narrative / verified-thinking gate. That does not block I12 planning or build authorization decisions.

---

## 4. Replacement P2-I12 — summary

**One-line:** The owner/historian intentionally asks known people for recollections, preserves exactly what arrives, reviews it, records a private assessment, and optionally promotes reviewed material into appropriate first-class MemoryBox knowledge.

**Locked V1 lifecycle:**

```text
Campaign → per-recipient Question Cycle → immutable Capture Item
  → owner Review Draft(s) → explicit owner verdict → optional promotion
```

**Dedicated Capture mailbox (locked):** `memorybox@marvinbot.net`  
- Hosting: Namecheap  
- Outbound Capture email uses this account  
- Inbound replies via Gmail inbox/integration for this Capture account  
- Credentials/tokens **outside Git**  
- Full inbound/outbound provenance preserved  

**Not in V1:** Curator-generated questions; contributor accounts; automatic Story generation; automatic credibility scoring; voice contributor workflow; multi-user editing; old Gmail `+MEM`/`+JRN` plus-address production architecture.

Full scope, exclusions, data contracts, UX, integration, PoC reuse, migration, and acceptance: see linked planning package above.

---

## 5. Renumbered increment map (MBRM-001A → MBRM-001B)

| MBRM-001A ID | MBRM-001A name | MBRM-001B ID | MBRM-001B name |
|--------------|----------------|--------------|----------------|
| P2-I12 | External Historical Context (EVS-254–256) | *(deferred backlog)* | Not replaced by Historian Capture; schedule separately |
| P2-I13 | Dynamic Views | **P2-I13** | Dynamic Views *(unchanged ID)* |
| P2-I14 | Settings & Processing Controls | **P2-I14** | Settings & Processing Controls *(unchanged ID)* |
| P2-I15 | Owner-run Capture Campaigns | **P2-I12** | **Historian Collection & Campaigns V1** *(absorbs and expands)* |
| P2-I16 | Trust Consistency & Private Owner Trust | **P2-I15** | Trust Consistency & Private Owner Trust |
| P2-I17 | Portability & Import-back | **P2-I16** | Portability & Import-back |

---

## 6. Dependency position

```text
… → I10 Stories/Artifacts/Journal → I11 Narration → I11A Inference (hold)
  → I12 Historian Collection & Campaigns
  → I11B Historian Learning (deferred)
  → I13 Dynamic Views → I14 Settings → I15 Trust → I16 Portability
```

**Prerequisites for I12 build (when authorized):**

- Accepted P2 People surfaces (I10A.1) for canonical respondent selection  
- Accepted Stories (I10A) for Story promotion target  
- Accepted Artifacts (I10B) for optional Artifact promotion  
- Ask/narration (I11) for promoted-testimony retrieval with attribution  
- Partial `memorybox/guided_capture/` and Marvin PoC (`cursor/marvin-capture-v01-3344`) as **reference only** — not integration baseline  

**Does not require:** I11A FlightSim ACCEPTED · I11B · Dynamic Views · Settings redesign

---

## 7. Document conflict reconciliation

| Conflict | Resolution |
|----------|------------|
| Old **P1 Increment 12 Export** vs replacement **P2-I12** | Different programs. P1 I12 docs remain historical on PoC branch. P2-I12 uses `MBBS-P2_INCREMENT_12_*` naming in `docs/product/` only. |
| August 29 order (I11A+I11B before I12) vs current order | **Current founder sequence supersedes** (§3.2). |
| MBRM-001A row “P2-I12 External Historical Context” vs Historian Capture | External Historical Context is **deferred**; Historian Capture is the **new P2-I12**. |
| MBRM-001 shell “P2-I12 Dynamic Views” | **Renumbered to P2-I13**; MBRM-001 remains historical shell. |
| MBRM-001A “P2-I15 Owner-run Capture Campaigns” vs new I12 | **Same product intent, expanded lifecycle**; I15 row absorbed into replacement I12. |
| Old MarvinCapture Gmail plus-address (`+MEM`, `+JRN`, subject tags, Trash-after-verify) vs dedicated mailbox | Plus-address PoC is **reference behavior**. V1 uses `memorybox@marvinbot.net` with MB-native correlation (`[MB-HC-<token>]`, delivery records). No forced Trash behavior. |
| Old “response promotes to Story” language vs optional promotion model | V1: **explicit verdict** then **optional** promotion to Story, Artifact, or accepted-source evidence — never automatic on receipt. |
| Old multi-field / system confidence vs single private owner assessment | V1: **one overall private owner qualitative assessment** per accepted contribution; separate from system/evidence confidence; never a numeric truth percentage. |
| `guided_capture_responses` direct-write / `mark_reviewed` vs immutable Capture Item + Review Draft | V1: inbound **immutable**; editing only in **versioned Review Drafts**; verdict is explicit. Existing I11 `guided_capture` schema is a **starting point to adapt**, not the final model. |
| I11 pack reserved kind `external_historical` for old I12 | Promoted historian testimony uses **guided_capture / historian_capture** provenance kinds with attribution; EVS-254–256 external web context remains separate backlog. |

---

## 8. V1 build slices (proposed — founder review)

| Slice | Outcome | Prove gate |
|-------|---------|------------|
| **I12-S1** | Domain schema (Campaign → Delivery → Capture Item → Review Draft → Verdict → Assessment); campaign lifecycle with fake email adapter; question snapshots on send | `prove-historian-capture --slice s1` |
| **I12-S2** | Dedicated-mailbox transport interface; inbound poll → immutable Capture Items; correlation; quarantine/unmatched; idempotent duplicates | `--slice s2` + harness inbox |
| **I12-S3** | Review Draft editor; immutable-source viewer; private owner assessment; explicit verdict (retain / reject / promote-ready) | `--slice s3` |
| **I12-S4** | Promotion to Story (minimum); provenance chain to Capture Item + Draft; Ask retrieval with attribution | `--slice s4` |
| **I12-S5** | FlightSim real-mail acceptance path; pause/resume/stop; multi-respondent campaigns; optional Artifact promotion if authorized | `prove-historian-capture --flightsim` |

---

## 9. Open questions for Tom (not silently decided)

See [MBPRD-P2-I12 §12](MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md) and [MBAT-P2-I12 §5](MBAT-P2-I12_ACCEPTANCE.md).

---

## 10. Gate

| Action | Status |
|--------|--------|
| Planning package in Git | **Done** |
| Production implementation | **Done** (S1–S5) |
| FlightSim owner acceptance | **ACCEPTED** 2026-09-04 |
| Live email send/poll | **Shipped** (FlightSim) |

**Closed:** Tom accepted P2-I12 on FlightSim 2026-09-04. Do not reopen without explicit founder direction.
