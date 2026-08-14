# MBBS-P2 Increment 7 — SMS/Text Evidence

**Status:** **DRAFT for founder review** · **NO BUILD** until Tom locks §1 questions and authorizes  
**Date:** 2026-08-14  
**Roadmap:** [MBRM-001A](MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) § P2-I7 (SMS/Text · A) — **not** the superseded MBRM-001 numbering (that file called SMS “I5”)  
**Authority:** Locked [MBPS-002](MBPS-002_P2_PRODUCT_SPECIFICATION.md) P2-COM-01 / P2-COM-03 · [MBCAP-001 v0.2](MBCAP-001_P2_CAPABILITY_CATALOG_v0.2.md) CAP-P2-018 · [MBEVS-001 v1.0](MBEVS-001_EVS_CATALOG_v1.0.md)  
**Thin PRD:** [MBBS-P2_I7_SMS_TEXT_EVIDENCE_PRD.md](MBBS-P2_I7_SMS_TEXT_EVIDENCE_PRD.md)  
**Depends:** P2-I6 **ACCEPTED** · I4 Explore already has an SMS/text card type (engine not connected)  
**Does not reopen:** I5 portrait **P2-BL-I5-01** · I6 kinship **P2-BL-I6-01** · I4 Explore UX · I8 richer email · I8.5 face-evidence ownership · I13/I14 Settings

---

## 0. Product intent (one sentence)

> **Imported text messages become first-class MemoryBox evidence — searchable, Person-linked, dated, provenance-preserved — in the same Ask / Explore / Person surfaces we already have. Missing coverage is disclosed. Messages are never invented.**

I7 is **archive understanding**, not a new messaging product and not a new family app.

End-to-end outcomes:

1. A staged SMS / iMessage / text export is **ingested** without rewriting the original files.  
2. Each message is **Evidence** (`evidence_kind=communication`, channel `sms` / `text`) with participants, timestamp, thread/group metadata when present, and import provenance.  
3. Participants resolve to **canonical MB People** via phone (or equivalent) identity — same Person continuum as photos/video.  
4. Ask can **show**, **count**, and **summarize** texts for a Person / year / keyword, with the underlying messages reachable.  
5. Explore / Person All Memories can show SMS cards on the existing mixed-media canvas (I4 type already reserved).  
6. Archive Health stops saying “SMS ingest deferred” and reports **honest** staged vs ingested vs unavailable.

---

## 1. Open questions for Tom (must lock before build)

| # | Question | Proposed default (review) |
|---|----------|---------------------------|
| **Q1** | What is the **FlightSim export** — path and format? Archive Health already expects **CSV under `Sources/sms`**. | Confirm: path, filename(s), and whether this is iMessage, Android SMS backup, Google Voice, or a mixed CSV. **I7 cannot invent a format.** |
| **Q2** | Acceptance **people / years** on FlightSim? | Propose: owner (Tom Will) ↔ **Peggy** for EVS-065 / 220 / 223 / 224; a **2020** window; outbound counts for EVS-221 / 222. Confirm whether **Denny Pizzani / “3D printing”** (EVS-118) exists in the export. |
| **Q3** | **Group threads** (EVS-117 “Core 4”) in I7? | **Propose OUT of I7 ACCEPTED** unless the export clearly has that group. Retrieve group threads if the file has them; do not invent a Core 4 object. |
| **Q4** | **MMS / attached images**? | **Propose:** keep attachments on the message (show-in-thread). Do **not** promote them into the Immich photo library. Not Explore photo cards. |
| **Q5** | Phone number → Person: auto-map from Profile `phone` facts, or Review-confirm? | **Propose:** auto-map when the number uniquely matches one confirmed Person contact; otherwise Review / unmapped participant (name or raw number shown). No silent merge. |
| **Q6** | Must I7 **LLM-summarize** texts to ACCEPTED, or is retrieve + count + cite enough? | **Propose:** retrieve / count / date-order are the hard gate (EVS-220–223). EVS-065 / 118 / 224 may be a **cited extract or short evidence-backed summary** — never a summary without reachable messages. Full narrative year/trip summaries stay **I11**. |

**No build** until Q1–Q2 are answered and Tom says the rest of the defaults are good (or changes them).

---

## 2. Proposed locked rules (draft — not locked until Tom says so)

### 2.A Import-only

- I7 ingests a **configured export**. It does not replace Messages.app, carrier SMS, or live phone sync.  
- Originals stay untouched (same rule as mbox email ingest).  
- Multi-user / family-contributed SMS is **out** (late / I15).

### 2.B One evidence model (do not invent a parallel SMS database)

Already in the repo — **reuse, do not fork:**

| Existing | How I7 uses it |
|----------|----------------|
| `evidence` + `evidence_kind=communication` | Email already writes this (`ingest/comms_email.py`). SMS adds `evidence_channel=sms` (or `text`) in `payload_json`. |
| `provider_identities` `identity_kind=phone` | Map numbers → MB Person. |
| Profile `CONTACT_KINDS` includes `phone` | Owner/Person contact facts for unique match. |
| Ask `want_communication` → `search_evidence_pg` | Today this is email-shaped. I7 teaches it SMS channel + Person/year filters. |
| Explore mapper already accepts `sms` / `text` types | Cards on the I4 canvas — **no SMS app, no new nav**. |
| Archive Health `staged_sms` + “SMS ingest — Not connected in P1” | Flip to honest ingested counts; never show `0` for “not connected”. |

### 2.C Person linking

- Canonical MB Person IDs only. Phone / handle is a **provider identity**, never `people.id`.  
- Ambiguous numbers → Review, not a silent second Peggy.  
- Unmapped participants remain visible as number or export display name.

### 2.D Honesty

- Disclose source file, account/scope, date coverage, and unmapped participants.  
- Counts (EVS-220–222) must state the scope used.  
- Unavailable ingest ≠ zero messages (I3 rule).  
- Do not invent missing texts, threads, or “they probably said…”.

### 2.E Surfaces

- **Ask** is the primary acceptance surface (show / count / summarize-with-cite).  
- **Explore / Person Explorer** show SMS in the existing mixed-media Gallery + Timeline when dated.  
- **Archive Health** reports staged vs ingested.  
- Shared Evidence Viewer: SMS body uses the existing comms/detail shell (I4 already reserved the type). **Do not redesign Explore.**

---

## 3. Scope IN

- Ingest the **confirmed FlightSim export** (Q1) into communication Evidence.  
- Preserve original text, timestamp, direction (in/out), thread/group id if present, participants, import provenance.  
- Person association via phone identity (Q5).  
- Ask: EVS-220, 221, 222, 223 as hard gates; EVS-065, 118, 224 per Q6.  
- Explore / Person: SMS cards in the current type model; dated items on Timeline.  
- Archive Health: SMS ingest connected; honest metrics.  
- Prove harness `prove-p2-i7` (structural + fixture) and FlightSim owner gate.

## 4. Scope OUT

| Out | Home |
|-----|------|
| Richer email (threads, attachments-as-artifacts, places) | **P2-I8** |
| Live carrier / iMessage sync, sending texts | Never I7 |
| Replacing Messages / SMS apps | Never |
| Core 4 group object unless Q3 flips | Later / unmapped EVS-117 |
| MMS images as Immich/library photos | Out (Q4) |
| Trip / year **narrative** using texts + photos | **P2-I10 / I11** (EVS-047, 070, 211–213) |
| Spoken moments / STT | **P2-I9** |
| Face-evidence ownership / Learn-rail Immich writes | **I8.5 after I8 ACCEPTED** — not I7 |
| I6 kinship reopen / family tree | Closed |
| Immich preferred portrait | **P2-BL-I5-01** |
| Mature Settings / provider catalog | **I13 / I14** (thin Settings path card is a side slice, not I7) |
| I4 Explore chrome redesign | Closed unless Tom reopens I4 |
| Invented messages or silent completeness | Forbidden |

---

## 5. EVS coverage (I7 homes)

Canonical homes from MBRM-001A Appendix A.1:

| EVS | Ask (short) | I7 bar |
|-----|-------------|--------|
| **EVS-220** | How many times did Peggy and I text each other? | Count + scope disclosure |
| **EVS-221** | How many text messages did I send in 2024? | Outbound count for owner + year |
| **EVS-222** | How many total text messages have I sent? | Outbound count + coverage |
| **EVS-223** | Show me all my text messages with Peggy. | Retrieve dated originals |
| **EVS-224** | Summarize all my text messages with Peggy. | Cited summary or extract (Q6) |
| **EVS-065** | Summarize texts Peggy and I sent in 2020 | Year window + cite (Q6) |
| **EVS-118** | Summarize texts with “3D printing” and Denny Pizzani | Keyword + person if corpus has it (Q2) |
| **EVS-106** | Find messages where my sister and I signed off with a funny name | **Earn-in if** sister + texts exist; else disclose gap — do not invent |

**Not I7 ACCEPTED** (even if texts appear in the wording):

- EVS-047 / 070 — email **and** texts around events / year capsule → **I8 + I11**  
- EVS-117 Core 4 → Q3; default later  
- EVS-211–213 / 235–236 trip/year/person narratives → **I11**  
- Email-only counts (EVS-107 / 108) → **I8**

Aliases are not separate acceptance.

---

## 6. Discovery (already in the tree — do not reinvent)

| Area | Finding |
|------|---------|
| Email ingest | `memorybox/ingest/comms_email.py` — mbox → Source + Evidence; originals untouched; `evidence_channel=email`. **Copy this pattern.** |
| Evidence schema | `evidence_kind=communication` already in `001_domain_v0.sql`. |
| Phone identity | `provider_identities.identity_kind` includes `phone`; Profile contacts include `phone`. |
| Ask | `want_communication` already searches PG communication Evidence (email-shaped today). |
| Explore | `explore/find.py` already maps `sms` / `text` onto comms cards. |
| Archive Health | `staged_sms` looks for `sms/`; ingested SMS metric is **unavailable** with note “CSV is staged under Sources/sms — ingest still deferred in P1”. |
| I4 | Definition already defers “full SMS engine” to I7; display/link OK. |

No new top-level product. No parallel `sms_messages` SoT unless ingest proves the communication payload cannot hold thread metadata (default: it can).

---

## 7. Build plan (sequencing only — not authorized)

1. Confirm Q1 export on FlightSim; write a read-only parser (CSV first if that is the file).  
2. Ingest job mirroring email: Source + Evidence; hash skip; never rewrite export.  
3. Phone → Person map (unique contact / Review).  
4. Ask retrieve: channel=sms, Person, year, keyword; counts with scope.  
5. Explore / Person cards via existing mapper; Evidence Viewer comms body.  
6. Archive Health: staged vs ingested honesty.  
7. `prove-p2-i7` harness + FlightSim owner gate.

---

## 8. Acceptance gate (draft — owner ACCEPTED later)

Pass **all** on FlightSim after build is authorized:

1. Export ingested; originals unchanged.  
2. “Show me all my text messages with Peggy” returns **real dated messages**, not stories-only and not “provider unavailable”.  
3. Peggy↔owner count and owner outbound counts match the ingested corpus and **state their scope**.  
4. Unmapped numbers / missing years are **disclosed**, not zeroed.  
5. SMS appears in Explore / Person when the find includes comms — no new app.  
6. Archive Health no longer claims SMS ingest is P1-deferred if ingest ran.  
7. I5 / I6 prove stay green. I6 kinship and I5 portrait are untouched.  
8. Missing export or empty Person thread ≠ invented messages.

Structural `prove-p2-i7` does **not** equal ACCEPTED.

---

## 9. Authorization stop-line

| Step | Status |
|------|--------|
| I6 ACCEPTED | **Yes** (2026-08-14 — Tom) |
| I7 definition draft | **This document** — review |
| Q1–Q2 (export + corpus) | **OPEN** |
| Q3–Q6 defaults | **PROPOSED** |
| Build | **NOT AUTHORIZED** |
| Implementation | **NONE** |

**Do not write I7 runtime** until Tom locks the questions and explicitly authorizes build.
