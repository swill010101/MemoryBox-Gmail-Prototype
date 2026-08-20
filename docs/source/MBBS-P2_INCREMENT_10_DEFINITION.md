# MBBS-P2 Increment 10 — Cross-Source Correlation

**Document:** MBBS-P2 Increment 10 Definition  
**Version:** v1.1  
**Status:** **BUILD AUTHORIZED** — 2026-08-20 (Tom: “Approved to build”)  
**Date:** 2026-08-20  
**Lineage:** [MBRM-001A](../product/MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md) P2-I10 · [MBPS-002](../product/MBPS-002_P2_PRODUCT_SPECIFICATION.md) **P2-GRAPH-02 / P2-GRAPH-03** · v1.0 review 2026-08-20 · founder locks below  
**Roadmap placement:** After **P2-I9 Spoken Moments ACCEPTED** (2026-08-20). Before **P2-I11** evidence-backed narrative. **I8.5 Face-SoT stays later.** **ACR-P2-001 / 001-A** are not I10.

**Does not reopen / does not absorb:** I8B face recognition · I9 transcription / voice Learn · I8A combined-card chrome · I4 Explore redesign (**P2-BL-I4-01**) · I6 kinship product · I7/I8 parsers · live Gmail / send · I11 narrative generation · I8.5 Immich face SoT · multi-user · Settings product · Paprika connector product · handwriting-OCR product · continue-on-tape (**ACR-P2-001-A**)

## Founder locks (2026-08-20)

Tom: approved to build 2026-08-20. Runtime is on a dedicated I10 branch.

1. **Place is not an Occurrence type.** An Occurrence is an **Event or Trip**. Place remains a first-class MemoryBox **anchor** (like Person): it may be linked to evidence and to an Event/Trip, and it may strongly support or constrain correlation. Do not treat “Dad's house” or “Yellowstone” as events.
2. **Preserve I9 evidence precision.** Where I9 provides a time-addressable Spoken Moment, I10 membership shall retain that precise evidence reference (source video + start/end). UI density may group multiple Spoken Moments through one source-video card per I9 / MBUX rules, but correlation must **not** reduce an exact Spoken Moment to an undifferentiated whole-file association. I11 will narrate from this precision.
3. **Proof occurrence is selected by inventory, not by slogan.** Do not hard-code Alaska or Christmas in this definition. At implementation start, inventory FlightSim and select the owner-named Trip/Event with the strongest authentic cross-source evidence. Target **at least three** useful modalities where available; **two** is the absolute minimum for acceptance. Ideal mix: photos + communications + video/spoken.
4. **One Occurrence model; schema is engineering.** There shall be one durable MemoryBox Occurrence concept and one durable membership/provenance mechanism. Reuse or extend existing domain structures where they genuinely fit. Do not create a competing Event/Place model or a parallel knowledge graph. Exact table names are not a founder decision.
5. **Deterministic evidence leads; the model proposes, it does not confirm.** Strong: owner assertion, exact/overlapping date window, exact Place/GPS, existing Event/calendar identity, explicit metadata/origin relationships. Supporting: Person overlap, subject/thread context, filename/path/context. Model assistance may propose that two pieces appear related; it must be I7A-traced; it remains **candidate**; a model proposal alone never owner-confirms an occurrence or a member.
6. **Artifacts are coverage, not the first gate.** EVS-152 (Grandpa's military service) and related artifact/document cases remain valid I10 architecture coverage. They are **not** hard blockers for first acceptance. First acceptance uses the selected mixed-source Trip/Event already operational on FlightSim. Artifacts may be tested opportunistically after that works.
7. **I8A chrome is not reopened.** I10 may feed existing combined day cards where straightforward. Combined-card integration is **not** required for I10 acceptance. Item-level occurrence membership and mixed Explore Gallery/Timeline retrieval are sufficient for v1.
8. **Three distinct behaviors.** (1) **Occurrence discovery** — MemoryBox may say these items may belong to Christmas 2001. (2) **Occurrence membership** — individual evidence items become candidate / confirmed / rejected members, durably. (3) **Occurrence retrieval** — “Show me Christmas 2001” retrieves the durable membership set, not a fresh OR/fuzzy search. GRAPH-03 is real here: unlink one email, the next Ask respects the correction.

### Carry-forward locks (I8B / I9 / MBQL)

These remain. I10 does not reopen them.

- I10 does not cartesian people × videos. Face still owns start:end **gallery clips**.
- Person switch: `show me {Other}` must not keep the previous Person’s talking tapes. Untagged transcribed-library dump is unscoped talking only.
- One MBQL. Trip / Event / Place / Person slots stay on `compile_ask`. Residual fill stays I7A-traced. Place stays a typed slot and a first-class exploration dimension; it is not an Occurrence.
- Evidence first. Weak or conflicting evidence stays disclosed. Residual chat must not invent a trip the archive does not support.
- GRAPH-03. Corrections to People, relationships, dates, Places, or Events update discovery without erasing historical provenance of prior assertions.
- No I11 in I10. I10 discovers, members, and retrieves. It does not write a trip/year/Person narrative.

**P2-I9** is **ACCEPTED**. I10 runtime is authorized 2026-08-20.

---

## 1. Purpose

P2-I10 turns separately retrieved family evidence into **one correlated Occurrence** when the archive supports it.

After I4–I9, MemoryBox can already find photos of Eugene, texts with Peggy, Christmas emails, calendar events, face clips, and spoken passages. Those hits still sit as **parallel result piles**. I10 is the increment that says: these photos, these messages, this calendar row, this face range, and this Spoken Moment **belong to the same Event or Trip** (or they do not), with provenance, owner confirmation, and safe unlink.

Place is how MemoryBox knows **where**. Person is **who**. Occurrence (Event or Trip) is **what happened / what we did**, optionally **at** a Place, **with** People, **in** a time window.

I10 is not a Knowledge Graph science project and is not a narrative increment. Its product outcome is that a family member can ask about a trip or an event **across sources** and get the evidence that **belongs to it**, then still see additional **candidates** nearby — not silently added history.

## 2. Product Outcome

### Before I10

“Show me our Alaska trip.”

MemoryBox independently searches photos, email, text, calendar, video, transcript, and hopes the piles line up.

### After I10

“Show me our Alaska trip.”

MemoryBox **resolves the Alaska Trip occurrence** and **retrieves the evidence that belongs to it**.

It may still say: “I found 14 additional items near this date/place that may also belong to this trip.” Those are **candidates**, not silently added history.

That durable middle layer is the heart of I10.

Illustrative asks (names are examples, not the FlightSim gate):

- **Show me our Alaska trip** — members of that Trip, not a coincidental keyword pile.
- **What did Peggy and I coordinate on around Christmas, in emails and texts?** — I7/I8 retrieve; I10 **joins** those items to the same Event when evidence supports it.
- **Include all Alaska texts in the Alaska trip** — eligible SMS become members of the Trip, not a second unscoped search.
- **Show me everything I have about Grandpa's military service** — architecture must support Person + event/context across sources; **not** the first ACCEPTED gate.

A successful result is:

- a **correlated Occurrence** (Event or Trip) with durable member evidence;
- optional **Place** links that support/constrain the join;
- mixed-media Gallery + Timeline drill-down to each source;
- Spoken Moment members that remain **time-addressable**;
- explicit **confidence / unknown / conflict**;
- owner **confirm, unlink, or reject** that sticks on reprocess;
- **no** fluent paragraph that pretends to be the trip (that is I11).

## 3. Why I10 Exists Now

I6 correlated **people** (kinship). I7/I8/I8A made communications and calendar first-class. I8B/I9 made video face and voice first-class. I4 already shows mixed media in one Gallery. Place is already a first-class exploration dimension.

What is still missing:

- a durable, owner-correctable **Event / Trip membership** across modalities;
- Ask that **retrieves membership** instead of OR-ing independent retrieves every time;
- correction that updates later discovery without rewriting history;
- honest “not the same Christmas” / “not enough evidence to join”;
- additional **candidates** offered without being silently merged into history.

I8 promised **correlation readiness**. I10 performs correlation. I11 will narrate from correlated, precise evidence.

## 4. Governing Architecture

### 4.1 Domain model

| Concept | Kind | Role |
|---------|------|------|
| **Person** | Anchor | Who |
| **Place** | Anchor | Where (Yellowstone, Mom's house). Not an Occurrence. |
| **Event** | Occurrence | What happened (Christmas 2001, Christmas dinner at Mom's house) |
| **Trip** | Occurrence | What we did over a span (Yellowstone Trip 2026, Alaska cruise) |

An Event or Trip **happens at/in** a Place. Evidence may link to Person, Place, and/or Occurrence independently.

Examples:

- Yellowstone = Place  
- Yellowstone Trip 2026 = Trip (Occurrence), linked to Place Yellowstone  
- Christmas 2001 = Event (Occurrence)  
- Mom's house = Place  
- Christmas dinner at Mom's house = Event linked to that Place  

### 4.2 Evidence stays in its home

Photos stay Immich/Library. Video face ranges stay I8B. Spoken Moments stay I9. Email/SMS/calendar stay I7/I8/I8A. Artifacts/documents stay artifacts.

I10 adds **membership + provenance**, not a second copy of the bytes.

### 4.3 Three behaviors (required)

1. **Occurrence discovery** — MemoryBox may propose that these items appear to belong to one Event or Trip (candidate set).
2. **Occurrence membership** — each evidence item is stored as `candidate` | `owner_confirmed` | `rejected` | `withdrawn` on that Occurrence, with join method and actor.
3. **Occurrence retrieval** — Ask for that Occurrence returns the durable membership set. It does **not** merely repeat a fresh OR/fuzzy search. Discovery may still **offer additional candidates** beside the membership set.

### 4.4 Occurrence vs keyword pile

A Gallery that happens to contain Alaska photos and an Alaska email is **not** I10.

Members are joined because of the evidence hierarchy in founder lock 5, **not** solely because a model said the word “Alaska.”

### 4.5 Membership evidence reference (precision)

Each membership points at the **most precise available** evidence reference:

- **Spoken Moment:** source video + `t_start` / `t_end` (example: Peggy talks about the Alaska cruise, 18:42–19:31). The video is the source; the moment is the member.
- **Face appearance:** source video + I8B start/end range.
- **Photo, email, SMS, calendar, artifact:** the item id (and existing timestamps/places on that item).

Explore **presentation** may collapse several Spoken Moments on one source-video **card** under I9 / MBUX density rules (one card per file in the talking gallery). That is UI. Correlation SoT must still store the Spoken Moment span so I11 can cite 18:42–19:31 rather than “somewhere in this tape.”

### 4.6 Proposed vs confirmed

System-proposed membership is **candidate**. Owner confirm is **owner_confirmed**. Owner unlink/reject is durable negative evidence (GRAPH-03). Reprocess must not silently restore a rejected join from the same features. Model-only proposals never auto-confirm.

### 4.7 Person identity mapping is not this increment

Provider mapping, Immich/HVRT reconcile-after-reprocess, and Person projection indexes already exist in the Person service (historical comments may say “I10”). That durability work is **not** P2-I10 Cross-Source Correlation and must not be rebuilt here.

### 4.8 MBQL and Explore

Ask still compiles through MBQL-001. Place remains a typed slot and a Map/Gallery dimension. I10 retrieval: resolve Occurrence → read membership → Explore items; optionally list nearby candidates.

I10 must not start a new Family Nav app. I8A combined day cards are **not** the correlation SoT and are **not** required for acceptance.

### 4.9 Schema

One Occurrence concept. One membership/provenance mechanism. Inspect existing event/trip/place structures and **extend or add** as needed. Do not mint a second graph. Table names are an implementation choice after definition approval.

## 5. Scope IN

1. Durable **Event** and **Trip** Occurrences; **Place** as linked anchor (not a third Occurrence type).
2. **Membership** of already-ingested evidence, at the precision in §4.5: photo, I8B face range, I9 Spoken Moment, email, SMS, calendar event, artifact/document, existing Story/Journal **pointers** (not I11 generation).
3. The three behaviors: discovery, durable membership, membership retrieval.
4. Ask/Explore: resolve named Trip/Event → members + optional candidate disclosure.
5. Owner confirm / unlink / reject; history preserved.
6. GRAPH-03: date/place/person correction on an Occurrence updates discovery; prior assertions remain in provenance.
7. Disclosure: missing modality, unmapped participant, weak join, conflicting dates.
8. I7A traces for any model-assisted candidate proposal.
9. At implementation start: **inventory FlightSim** and select the proof Trip/Event (lock 3).
10. Recipe / artifact EVSs as **architecture coverage** over evidence MemoryBox already has. Do not start Paprika or handwriting products. Do not hold first ACCEPTED on EVS-152.

## 6. Explicitly Out of Scope

I10 does **not** include:

- treating Place as an Event/Trip/Occurrence type;
- collapsing Spoken Moments to whole-file membership in the correlation SoT;
- I11 trip/year/Person **narrative** or saved Story generation;
- I11-later external U.S./world history (EVS-254–256);
- I8.5 Face-SoT / Immich decoupling;
- reopening I8B recognition `--full` or I9 transcribe product;
- ACR-P2-001 appearance playback / ACR-P2-001-A continue-on-tape;
- live Gmail, sending mail, new Email/SMS/Calendar apps;
- a forced KnowledgeLinks busywork UI or a parallel knowledge graph;
- silent correlation under weak evidence; inventing a Trip from a single keyword;
- dumping untagged spoken tapes onto a Person or Occurrence that does not own them;
- Paprika connector / recipe-manager product (EVS-244: count and disclose sources already ingested);
- a new handwriting-OCR engine as the I10 product (EVS-147/161: candidate + owner confirm if extraction already exists);
- reopening I8A chrome; requiring combined-card wiring for ACCEPTED;
- I13 saved views, I14 Settings, multi-user;
- Explore visual polish (**P2-BL-I4-01**);
- hard-coding Alaska or Christmas as the FlightSim gate.

## 7. Trust and Provenance Rules

1. Original media and messages remain the source of truth.
2. Correlation is derived evidence with method, confidence, and actor.
3. Candidate ≠ confirmed. Additional candidates beside a retrieved Occurrence are not membership until confirmed or left explicitly candidate.
4. Owner unlink/reject outranks the same-system re-proposal.
5. Unknown stay unknown; conflicts stay conflicts.
6. Kinship (I6) is not Event membership. A nephew in photos of a trip is a Person linked to that Trip, not a new kinship fact.
7. Spoken membership follows I9 identity rules (Learned/tagged voice or owner assignment — never “everyone talking”) **and** retains Spoken Moment time bounds when they exist.
8. Face membership follows I8B: owner-confirmed / trusted-provider / candidate remain distinct.
9. I10 must never imply a Person attended or spoke at an Occurrence without supporting evidence.
10. Fluent model text is not an Occurrence record.

## 8. Required Data / Service Concepts

### 8.1 Occurrence (Event or Trip)

Display label, kind (`event` | `trip`), optional time window(s), optional Place link(s), provenance, confirmation state.

### 8.2 Place (anchor, not Occurrence)

Existing first-class Place/location. May attach to evidence and to Occurrences. Used as a **strong** correlation signal (exact Place/GPS).

### 8.3 Membership

Occurrence id + evidence kind + **precise evidence reference** (§4.5) + join method + confidence + actor + status (`candidate` | `owner_confirmed` | `rejected` | `withdrawn`).

### 8.4 Ask retrieval

MBQL Person / Place / Event / Trip / time → **if an Occurrence exists, retrieve its membership**; optionally run discovery for additional candidates and disclose them as candidates. Independent modality retrieve remains a fallback with disclosure when no Occurrence exists.

### 8.5 Correction

Unlink member; change Occurrence dates/label; merge/split Occurrences only with owner action and preserved provenance (no silent merge of two Christmases).

## 9. EVS coverage (I10 homes)

Canonical homes from MBRM-001A Appendix A.1. I10 **bar** is join + retrieve + provenance, not narrative and not a new ingest product.

| EVS | Ask (short) | I10 bar |
|-----|-------------|---------|
| **EVS-047** (I8 parked joint) | Peggy and I around Christmas, emails **and** texts | Join to the same Event when supported; both modalities reachable |
| **EVS-004** | Grandpa's roll recipe (and why it mattered) | Recipe/doc retrieve + **linked** story/annotation if present; no invented “why” |
| **EVS-010** | What recipes did Peggy save? | Recipes/docs/email attachments MemoryBox already has; gap if incomplete |
| **EVS-149** | Letter Dad wrote when I graduated | Artifact + Person + graduation Event/time; uncertainty if several match |
| **EVS-157** | Dad's letters from 1968 | Person + date-window on artifacts; OCR dates stay confidence-tagged |
| **EVS-158** | Recipe cards that mention walnuts | Full-text on extracted recipe text already stored |
| **EVS-159** | Newspaper clipping about Dad's baseball team | Clipping + Person/activity; highlight supporting text, do not invent the team |
| **EVS-161** | Who wrote this letter / when? | Candidates + evidence; owner confirm; never silent fact |
| **EVS-147** | Mom's handwritten notes | Import/link with existing artifact path; uncertain extraction stays uncertain |
| **EVS-244** | How many recipes in MB or Paprika | Count ingested recipe records by source; disclose if Paprika is not connected |
| **EVS-152** | Show me everything I have about Grandpa's military service | **Architecture must support** Person + service context across sources. **Not** the first FlightSim ACCEPTED gate. |

**First FlightSim gate:** the inventory-selected Trip/Event (lock 3), spanning **at least two** operational modalities; **three** when available (photos + communications + video/spoken). Artifact EVSs earn in opportunistically.

## 10. Acceptance

### A. Definition / honesty

1. I10 definition founder-approved; Tom authorized runtime 2026-08-20.
2. I8B, I9, I8A, I4, I6 remain ACCEPTED and unreopened.
3. Prove command (when built) does not cartesian recognition or re-transcribe the archive.
4. Implementation start includes a short FlightSim inventory and records the chosen proof Occurrence (name, year/window, modalities present). Alaska/Christmas are not assumed.

### B. Join / membership

1. Two authentic items from different modalities that belong to the proof Trip/Event become durable members (candidate or confirmed per evidence strength and owner action).
2. A near-miss (same keyword, wrong year or Place) is **not** auto-confirmed; it may appear as a **candidate** with disclosure.
3. Opening a Spoken Moment member plays the source video at that moment’s start (not merely file start). Opening a face member uses the I8B range. Gallery **cards** may still follow I9 density (one file card) without destroying membership precision.

### C. Ask / retrieval

1. Ask the proof Occurrence by its real name/year → **membership set**, mixed modalities, not only one pile and not a fresh fuzzy OR.
2. Additional near items, if shown, are labeled **candidates**.
3. Person switch after a talking Ask does not leak the previous Person’s tapes into this Occurrence.
4. “Include texts in this trip” uses membership (or explicit eligible SMS for that window), not a dump of all texts.

### D. GRAPH-03

1. Owner unlinks a wrong email from the Trip; re-Ask does not silently restore it.
2. Date or Place correction on the Occurrence updates discovery; old assertion remains in history.

### E. Scale

Controlled FlightSim subset. Not “correlate the entire archive” as a prerequisite. EVS-152 does not block this gate.

## 11. Critical Success Factors

1. **Join is the product**, not a bigger OR-search.
2. **Retrieval uses durable membership**, then may offer candidates.
3. **Place stays an anchor**; Occurrence is Event or Trip.
4. **Spoken Moments stay time-addressable** in the membership SoT.
5. **Candidate vs confirmed** stays visible.
6. **Corrections stick.**
7. **Sources remain drillable.**
8. **I11 is not smuggled in.**
9. **I8B/I9/I8A locks hold.**
10. **MBQL stays one contract.**
11. **Weak evidence is disclosed, not narrated away.**
12. **The model never owner-confirms.**

## 12. Closed founder questions (v1.0 §12)

| # | Question | Decision |
|---|---------|----------|
| 1 | Proof occurrence name | Inventory at implementation start. Do not hard-code Alaska or Christmas. Two modalities minimum; three target. |
| 2 | Tables vs extend | One Occurrence model + one membership mechanism. Schema is engineering. No parallel graph. |
| 3 | Auto-propose | Deterministic evidence first. Model may propose candidates, I7A-traced, never auto-confirm. |
| 4 | EVS-152 | Architecture yes; first ACCEPTED gate no. |
| 5 | I8A cards | Optional/opportunistic. Not required. Do not reopen I8A chrome. |

## 13. Hold / build authorization

v1.1 is **approved to build** (2026-08-20). Runtime proceeds on a dedicated I10 branch. I8.5 and ACR-P2-001 remain off this path unless Tom reorders.
