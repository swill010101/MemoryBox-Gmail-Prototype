# MBBS-P2 Increment 10 — Cross-Source Correlation

**Document:** MBBS-P2 Increment 10 Definition  
**Version:** v1.0  
**Status:** **DEFINITION FOR REVIEW** — not build-authorized  
**Date:** 2026-08-20  
**Lineage:** [MBRM-001A](../product/MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) P2-I10 · [MBPS-002](../product/MBPS-002_P2_PRODUCT_SPECIFICATION.md) **P2-GRAPH-02 / P2-GRAPH-03** · prior increments parked “Alaska / Christmas correlation” here (I7, I8, I8A, I9)  
**Roadmap placement:** After **P2-I9 Spoken Moments ACCEPTED** (2026-08-20). Before **P2-I11** evidence-backed narrative. **I8.5 Face-SoT stays later.** **ACR-P2-001 / 001-A** are not I10.

**Does not reopen / does not absorb:** I8B face recognition · I9 transcription / voice Learn · I8A combined-card chrome · I4 Explore redesign (**P2-BL-I4-01**) · I6 kinship product · I7/I8 parsers · live Gmail / send · I11 narrative generation · I8.5 Immich face SoT · multi-user · Settings product · Paprika connector product · handwriting-OCR product · continue-on-tape (**ACR-P2-001-A**)

## Founder locks (carry forward)

These remain product locks. I10 does not reopen them.

1. **I8B / I9 coexistence.** I10 does not cartesian people × videos. I10 does not re-slice videos into voice clips. Face still owns start:end gallery clips. Voice still identifies a Person **in a file** (one card per source file).
2. **Person switch.** `show me {Other}` must not keep the previous Person’s talking tapes. Untagged transcribed-library dump is unscoped talking only.
3. **One MBQL.** I10 must not invent a third planner. Trip / Event / Place / Person slots stay on `compile_ask`. Residual fill stays I7A-traced.
4. **Evidence first.** Correlation is derived, rebuildable, and owner-correctable. Weak or conflicting evidence stays disclosed. Residual chat must not invent a trip that the archive does not support.
5. **GRAPH-03.** Corrections to People, relationships, dates, Places, or Events update discovery without erasing the historical provenance of prior assertions.
6. **No I11 in I10.** I10 links and retrieves. It does not write a trip/year/Person narrative, even from correlated evidence.

**P2-I9** is already **ACCEPTED**. That does not authorize I10 build.

---

## 1. Purpose

P2-I10 turns separately retrieved family evidence into **one correlated occurrence** when the archive supports it.

After I4–I9, MemoryBox can already find photos of Eugene, texts with Peggy, Christmas emails, calendar events, face clips, and spoken passages. Those hits still sit as **parallel result piles**. I10 is the increment that says: these photos, these messages, this calendar row, this tape, and this spoken passage are **the same Place / Event / Trip** (or they are not), with provenance, owner confirmation, and safe unlink.

I10 is not a Knowledge Graph science project and is not a narrative increment. Its product outcome is that a family member can ask about a trip, a holiday, a service, or a recipe **across sources** and drill from the correlated occurrence back to authentic evidence.

## 2. Product Outcome

After I10, MemoryBox can answer questions such as:

- **Show me our Alaska trip** (or the owner-named FlightSim proof trip/event) — photos, videos, emails, texts, calendar, and spoken passages that belong to that Trip, not a coincidental keyword pile.
- **What did Peggy and I coordinate on around Christmas, in emails and texts?** — I7/I8 retrieve; I10 **joins** those windows to the same Event when evidence supports it.
- **Show me everything I have about Grandpa's military service** — Person + event/context across photos, documents, mail, stories, video; sources remain distinct.
- **Include all Alaska texts in the Alaska trip** — SMS already ingested in I7 become members of the Trip, not a second unscoped search.
- **Find Grandpa's roll recipe (and why it mattered)** — recipe/doc plus linked story/annotation when both exist; no invented “why.”

A successful result is:

- a **correlated occurrence** (Place, Event, or Trip) with member evidence;
- mixed-media Gallery + Timeline drill-down to each source;
- explicit **confidence / unknown / conflict**;
- owner **confirm, unlink, or reject** that sticks on reprocess;
- **no** fluent paragraph that pretends to be the trip (that is I11).

## 3. Why I10 Exists Now

I6 correlated **people** (kinship). I7/I8/I8A made communications and calendar first-class. I8B/I9 made video face and voice first-class. I4 already shows mixed media in one Gallery.

What is still missing:

- a durable, owner-correctable **Event / Trip / Place membership** across modalities;
- Ask that uses those memberships instead of OR-ing independent retrieves;
- correction that updates later discovery without rewriting history;
- honest “not the same Christmas” / “not enough evidence to join.”

I8 promised **correlation readiness**. I10 performs correlation. I11 will narrate from correlated evidence.

## 4. Governing Architecture

### 4.1 Evidence stays in its home

Photos stay Immich/Library. Video face ranges stay I8B. Spoken files stay I9. Email/SMS/calendar stay I7/I8/I8A. Artifacts/documents stay artifacts.

I10 adds **membership + provenance**, not a second copy of the bytes.

### 4.2 Occurrence vs keyword pile

A Gallery that happens to contain Alaska photos and an Alaska email is **not** I10.

I10 requires a typed occurrence (Trip / Event / Place) whose members were joined because of:

- shared time window; and/or
- shared Place; and/or
- owner assertion; and/or
- explicit identifiers (thread, calendar event, filename/origin);

and **not** solely because a model said the word “Alaska.”

### 4.3 Proposed vs confirmed

System-proposed membership is **candidate**. Owner confirm is **owner_confirmed**. Owner unlink/reject is durable negative evidence (GRAPH-03). Reprocess must not silently restore a rejected join from the same features.

### 4.4 Person identity mapping is not this increment

Provider mapping, Immich/HVRT reconcile-after-reprocess, and Person projection indexes already exist in the Person service (historical comments may say “I10”). That durability work is **not** P2-I10 Cross-Source Correlation and must not be rebuilt here.

### 4.5 MBQL and Explore

Ask still compiles through MBQL-001. I10 retrieval reads occurrence memberships. Explore remains Ask → Gallery / Timeline / Map. I10 must not start a new Family Nav app.

I8A combined day cards may **surface** correlated members. They are not themselves the correlation SoT.

## 5. Scope IN

1. **Durable occurrence records** for Trip, Event, and Place (reuse existing slots/tables where they already exist; do not mint a parallel graph).
2. **Membership** of already-ingested evidence: photo, video (face clip and/or voice-presence file), spoken moment/file, email, SMS, calendar event, artifact/document, existing Story/Journal **pointers** (not I11 generation).
3. **Ask/Explore** using membership: person + trip/event/place returns the correlated set with modality mix and drill-down.
4. **Owner confirm / unlink / reject** on proposed members; history preserved.
5. **GRAPH-03:** date/place/person correction on an occurrence updates discovery; prior assertions remain in provenance.
6. **Disclosure:** missing modality, unmapped participant, weak join, conflicting dates.
7. **I7A traces** for any model-assisted join proposal.
8. **Controlled FlightSim proof corpus** — one owner-named trip or holiday with real mixed sources — not the entire archive as a prerequisite.
9. **Recipe / artifact EVSs** only insofar as they are **join + retrieve** over evidence MemoryBox already has (or can ingest with existing artifact/email attachment paths). Do not start Paprika or handwriting products.

## 6. Explicitly Out of Scope

I10 does **not** include:

- I11 trip/year/Person **narrative** or saved Story generation;
- I11-later external U.S./world history (EVS-254–256);
- I8.5 Face-SoT / Immich decoupling;
- reopening I8B recognition `--full` or I9 transcribe product;
- ACR-P2-001 appearance playback / ACR-P2-001-A continue-on-tape;
- live Gmail, sending mail, new Email/SMS/Calendar apps;
- a forced KnowledgeLinks busywork UI;
- silent correlation under weak evidence;
- inventing a Trip from a single keyword;
- dumping untagged spoken tapes onto a Person or Event that does not own them;
- Paprika connector / recipe-manager product (EVS-244: count and disclose sources MemoryBox already ingested);
- a new handwriting-OCR engine as the I10 product (EVS-147/161: candidate + owner confirm if extraction already exists);
- I13 saved views, I14 Settings, multi-user;
- Explore visual polish (**P2-BL-I4-01**).

## 7. Trust and Provenance Rules

1. Original media and messages remain the source of truth.
2. Correlation is derived evidence with method, confidence, and actor.
3. Candidate ≠ confirmed.
4. Owner unlink/reject outranks the same-system re-proposal.
5. Unknown stay unknown; conflicts stay conflicts.
6. Kinship (I6) is not Event membership. A nephew in photos of a trip is a Person on the Trip, not a new kinship fact.
7. Spoken membership follows I9 identity rules: Learned/tagged voice or owner assignment — never “everyone talking.”
8. Face membership follows I8B: owner-confirmed / trusted-provider / candidate remain distinct.
9. I10 must never imply a Person attended or spoke at an occurrence without supporting evidence.
10. Fluent model text is not an occurrence record.

## 8. Required Data / Service Concepts

### 8.1 Occurrence

Typed Trip, Event, or Place with display label, optional time window(s), optional geography, provenance, confirmation state.

### 8.2 Membership

`occurrence_id` + evidence kind + evidence id + join method + confidence + actor + status (`candidate` | `owner_confirmed` | `rejected` | `withdrawn`).

### 8.3 Ask retrieval

MBQL Person / Place / Event / Trip / time → occurrence resolve → member retrieve → Explore items. Independent modality retrieve remains a fallback with disclosure when no occurrence exists.

### 8.4 Correction

Unlink member; change occurrence dates/label; merge/split occurrences only with owner action and preserved provenance (no silent merge of two Christmases).

## 9. EVS coverage (I10 homes)

Canonical homes from MBRM-001A Appendix A.1. I10 **bar** is join + retrieve + provenance, not narrative and not a new ingest product.

| EVS | Ask (short) | I10 bar |
|-----|-------------|---------|
| **EVS-152** | Show me everything I have about Grandpa's military service | Person + service context across existing sources; provenance per item; gaps disclosed |
| **EVS-047** (I8 parked joint) | Peggy and I around Christmas, emails **and** texts | Join to the same Event/window when supported; both modalities reachable |
| **EVS-004** | Grandpa's roll recipe (and why it mattered) | Recipe/doc retrieve + **linked** story/annotation if present; no invented “why” |
| **EVS-010** | What recipes did Peggy save? | Recipes/docs/email attachments MemoryBox already has; gap if incomplete |
| **EVS-149** | Letter Dad wrote when I graduated | Artifact + Person + graduation Event/time; uncertainty if several match |
| **EVS-157** | Dad's letters from 1968 | Person + date-window on artifacts; OCR dates stay confidence-tagged |
| **EVS-158** | Recipe cards that mention walnuts | Full-text on extracted recipe text already stored |
| **EVS-159** | Newspaper clipping about Dad's baseball team | Clipping + Person/activity; highlight supporting text, do not invent the team |
| **EVS-161** | Who wrote this letter / when? | Candidates + evidence; owner confirm; never silent fact |
| **EVS-147** | Mom's handwritten notes | Import/link with existing artifact path; uncertain extraction stays uncertain |
| **EVS-244** | How many recipes in MB or Paprika | Count ingested recipe records by source; disclose if Paprika is not connected |

Hard FlightSim gate is **one owner-named occurrence** spanning at least **two modalities** already live on FlightSim (typically photos + mail/SMS, plus video and/or spoken if present). Artifact EVSs earn in when those objects exist; they do not block the trip/holiday gate.

## 10. Acceptance

### A. Definition / honesty

1. I10 definition approved; build not started until Tom authorizes.
2. I8B, I9, I8A, I4, I6 remain ACCEPTED and unreopened.
3. Prove command (when built) does not cartesian recognition or re-transcribe the archive.

### B. Join

1. Two authentic items from different modalities that share the proof Trip/Event become members.
2. A near-miss (same keyword, wrong year or Place) is **not** auto-joined, or is candidate-only with disclosure.
3. Opening a member plays/opens the authentic source (photo, message, video at face `t=` or voice file start — I9 gallery lock holds).

### C. Ask

1. Ask the proof occurrence by name/year → mixed members, not only one modality.
2. Person switch after a talking Ask does not leak the previous Person’s tapes into this occurrence.
3. “Include texts in this trip” uses membership (or explicit eligible SMS for that window), not a dump of all texts.

### D. GRAPH-03

1. Owner unlinks a wrong email from the Trip; re-Ask does not silently restore it.
2. Date correction on the occurrence updates the window used for discovery; old assertion remains in history.

### E. Scale

Controlled FlightSim subset. Not “correlate the entire archive” as a prerequisite.

## 11. Critical Success Factors

1. **Join is the product**, not a bigger OR-search.
2. **Candidate vs confirmed** stays visible.
3. **Corrections stick.**
4. **Sources remain drillable.**
5. **I11 is not smuggled in.**
6. **I8B/I9 locks hold.**
7. **MBQL stays one contract.**
8. **Weak evidence is disclosed, not narrated away.**

## 12. Open questions for Tom (close before build)

1. **Proof occurrence.** Which FlightSim Trip/Event is the gate (Alaska, Christmas year, other named trip)?
2. **SoT.** New `occurrences` / memberships tables vs extending existing event/trip labels already on Ask context?
3. **Auto-propose.** Time+Place heuristic only, or model-assisted proposals (I7A-traced) in v1?
4. **Artifact depth.** Is EVS-152 (Grandpa military) in the first FlightSim walk, or trip/holiday only for ACCEPTED?
5. **I8A cards.** May combined day cards read I10 memberships, or is Explore item-level membership enough for v1?

## 13. Hold / build authorization

v1.0 is **definition for review**. **Do not write I10 runtime** until Tom approves this document and explicitly authorizes build.

Sequence: **I9 ACCEPTED** → I10 definition → Tom “build i10 authorized” → dedicated I10 branch. I8.5 and ACR-P2-001 remain off this path unless Tom reorders.
