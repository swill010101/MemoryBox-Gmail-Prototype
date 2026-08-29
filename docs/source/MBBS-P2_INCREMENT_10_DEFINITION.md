# P2-I10 Cross-Source Correlation — definition

**Status:** **ACCEPTED** 2026-08-21 (Tom: “i10 has been accepted”) · **BUILD AUTHORIZED** 2026-08-20 (Tom: “I10 is approved to build”; earlier “MB P2 Build from 9 on”) · v1.0  
**Authority:** this file. Readable pointer: [docs/product/MBBS-P2_INCREMENT_10_DEFINITION.md](../product/MBBS-P2_INCREMENT_10_DEFINITION.md)  
**Thin PRD:** [docs/product/MBPRD-P2-I10_CROSS_SOURCE.md](../product/MBPRD-P2-I10_CROSS_SOURCE.md)

**Sequence:** I1–I8A **ACCEPTED**. I8B runtime in flight (do not reopen). I9 Spoken Moments **BUILD AUTHORIZED** (this branch includes I9). **I10 ACCEPTED** 2026-08-21. Face-SoT (**I8.5**) later. **I11 narrative generation is OUT.**

## 0. Product intent

> **People, Places, Events/Trips, and themes must retrieve across photos, video, spoken passages, email, SMS, calendar, Stories, Journal, and Artifacts when the evidence supports a connection. Coverage gaps are disclosed. Owner corrections stick. MemoryBox does not invent a story.**

I9 made spoken passages first-class evidence. I8/I8A made communications livable. I4 mixed the Gallery. Those sources still answer mostly as **separate retrieve paths**. I10 is the **glue**: one Ask such as “Show me everything I have about Grandpa’s military service” returns a **mixed evidence pack** with per-source counts, provenance, and honest missing-source disclosure.

I10 is **correlation**, not narration. “Tell me the story of our Florida trip” remains **I11**.

## 1. Why now

I9 is authorized and on this tree. GRAPH-02/03 are the next locked capability after spoken moments. Tom authorized continuing P2 **from 9 on**. I10 is the next named increment in [MBRM-001A](../product/MBRM-001A_P2_IMPLEMENTATION_PLAN_PROPOSAL.md).

## 2. Founder locks (2026-08-20)

1. **Evidence first.** A correlated pack is cited items, not a generated paragraph treated as fact.
2. **Unknown stays unknown.** Candidate links are labeled candidate. Owner confirm outranks system. Rejected links are not silently restored from the same evidence.
3. **No cartesian.** Do not join every Person to every file. Correlation is Ask/theme/event/place constrained.
4. **I8A Q3 unchanged for ordinary Show-me.** Email/SMS/Calendar stay visually off a broad Gallery unless the owner asked for **everything about** / Show everything / Communications/Calendar presentation. Everything-about is an explicit all-source Ask.
5. **I9 spoken is one source among many** on everything-about. Do not collapse the pack to video-only because transcripts exist.
6. **Date conflicts are shown, not elected.** Two dates for the same event stay both visible (EVS-167 intent).
7. **Originals untouched.** Correlation links are derived assertions, not edits to mail/photos/video files.
8. **I11 / I12 / I8.5 / Place GIS / OCR engines / Paprika** are OUT.

## 3. IN

- Durable **Place** and **correlatable Event** (event | trip | theme) records.
- **Correlation links** from evidence/photo/video/artifact/story/journal/spoken_moment/person → place/event/person, with `candidate | confirmed | rejected | superseded`, authority, observed_date, provenance.
- Ask compile: **everything about / everything I have about / what do I have about** → `want_cross_source`, theme slot, all eligible modalities on, I8A presentation on for comms/calendar.
- Retrieve pack + **coverage** `{photos, video, spoken, email, sms, calendar, story, journal, artifact, missing[]}`.
- Owner **confirm / reject** a link; reject survives re-index of the same evidence (GRAPH-03).
- Date-conflict disclosure when linked items disagree on date.
- `python -m memorybox prove-p2-i10`.
- Explore curator **coverage strip** on cross-source asks (counts + gaps). No new app.

## 4. OUT

- Evidence-backed **narrative generation** and owner-review Story save (**I11**).
- External U.S./world history (**I12**).
- Face evidence ownership / Immich decoupling (**I8.5**).
- Durable Place GIS, map-as-destination, visual-setting inference as confirmed Place.
- OCR / handwriting engines; Paprika recipe connector (EVS-244).
- Forced KnowledgeLinks busywork; silent merge of conflicting dates.
- Reopening I4/I5/I7/I8/I8A/I9 except where I10 must union their retrieve.

## 5. Acceptance (harness + FlightSim)

### Harness (`prove-p2-i10`)

1. Compile “Show me everything I have about Grandpa’s military service” → cross-source, theme contains military, not video-only.
2. Pack includes at least two source kinds (e.g. email + artifact) for the same Person/theme.
3. Coverage lists present sources and **missing** sources with 0.
4. Rejected link is absent from the pack; the row still exists with status=rejected.
5. Two linked dates for one event are both disclosed; neither is silently dropped.
6. Residual chat / curator text is not stored as Evidence.

### FlightSim owner pass

**ACCEPTED** 2026-08-21 (Tom: “i10 has been accepted”). Mixed evidence pack, coverage + gaps, unlink sticks, no generated Story. Do not reopen I10 for I11 narrative.

## 6. EVS / MBPS trace (primary)

- **MBPS:** P2-GRAPH-02, P2-GRAPH-03 (correlation-ready COM-02 already shipped in I8).
- **Capability:** CAP-P2-012.
- **EVS homes:** EVS-152 (everything about Grandpa’s military service); EVS-004/010 recipe *find* only (not Paprika inventory); EVS-147/149/157–159 artifact retrieve earn-in; EVS-167 conflict dates (thin); EVS-161 confirm-don’t-store-as-fact.
- Narrative EVS-181/182/211–213/235 stay **I11**.
