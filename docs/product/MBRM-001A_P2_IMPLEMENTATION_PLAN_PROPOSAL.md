# MBRM-001A — Proposed P2 Implementation Plan (Review Draft)

**Status:** Proposed for founder review · **Date:** 2026-08-12  
**Planning only — does not authorize build**  
**Locked inputs:** [MBPS-002](MBPS-002_P2_PRODUCT_SPECIFICATION.md) · [MBEVS-001 v1.0](MBEVS-001_EVS_CATALOG_v1.0.md) · DOCX masters in [`docs/source/`](../source/)  
**Relationship to prior draft:** Revises sequencing recommendations in [MBRM-001_P2_ROADMAP.md](MBRM-001_P2_ROADMAP.md). **Do not treat the earlier shell-first order as approved.**

## 0. Verdict on “start with Product Shell / High-Volume UX / Settings / Archive Health”

**Not the best first implementation increment** given the locked first proof point and capability dependencies.

| Prior draft order | Problem |
|-------------------|---------|
| P2-I1 Product Shell | Maturation without proving P2 archive-understanding thesis |
| then Archive Health / Timeline UX / Settings | Valuable, but not on the critical path for “Show me Peggy” |
| Identity sync & video moments later | Delays the preferred P2 proof |

**Better first authorized build:** a **Person-in-Media vertical** that completes “Show me Peggy” end-to-end (Immich→canonical Person → photos + appearance timeslots → jump-to-moment → correct → reusable evidence → retrieval update), with only **thin** open/detail/correct/return context UX.

Product shell, Archive Health, Settings, and high-volume timeline remain **P2 requirements** (MBPS-002) but are sequenced **after** the vertical proves the dependency chain—or as thin supporting slices only where the proof cannot proceed without them.

MBPS-002 §8 lists coherent shell as a **P2 completion** criterion, not as the mandated first build slice.

---

## 1. Locked planning decisions incorporated

| Decision | Roadmap implication |
|----------|---------------------|
| Family contribution in P2 = controlled **owner-run campaign** input | **P2-I14**; not general multi-user |
| Full multi-user accounts/roles/permissions/per-user context | **Late-P2 / P2.5 only** |
| Immich→MB Person sync **nightly by default** | **P2-I1** (and ongoing) |
| Owner **Sync / Poll now** | **P2-I1** UX control (People/Status/Settings-thin) |
| Newly named/changed Immich Person → auto create/map MB Person | **P2-I1** (P2-ID-02/03) |
| Newly known Person eligible for **video-recognition reprocess** on existing video | **P2-I1** acceptance (not deferred) |
| Confidence thresholds normally **system-managed** | No owner threshold dial in early Settings; progressive disclosure of uncertainty only |
| Owner trust rating of a contribution/Story is **owner-private** | **P2-I15**; family UX must not expose it |
| Family UX may show overall MB confidence/uncertainty + evidence | Allowed; distinct from private owner trust |
| EVS-254/255/256 later in P2 | **P2-I11-later** after core narrative |
| Formal Experience Flows only when multi-step reuse needs them | Formalize for Show-me-Peggy correct/return; Ask→Evidence→Correct; Recognize→Confirm→Reuse; defer others |
| First meaningful P2 proof = **“Show me Peggy.”** | **P2-I1** acceptance gate |

Ambiguities **not** silently resolved are listed in §11 and §12.D.

---

## 2. Major dependency chains (before sequencing)

### Chain A — Person-in-media (critical path for Show me Peggy)

```text
Immich named Person
  → nightly sync / Sync now
  → canonical MB Person (map or create; conflict → review)
  → face evidence (provider + owner confirm)
  → video recognition / reprocess on existing video
  → appearance timeslot (start/end, frame, confidence, method, correction state)
  → searchable moment
  → Ask “Show me Peggy” (photos + moments, not file-only)
  → open jumps to timeslot
  → owner corrects miss/wrong association
  → reusable identity evidence
  → relearning / subsequent retrieval reflects correction
  → provenance + system confidence preserved
  → return to original result context
```

### Chain B — Spoken moments (after face-moment vertical)

```text
Source audio/video
  → STT (time-aligned)
  → diarization
  → speaker identity ↔ MB Person
  → transcript passage
  → searchable spoken moment
  → Ask / play passage
  → correct speaker → reuse
```

### Chain C — Provider identity sync (shared foundation)

```text
Provider identity change (name/merge/split/correct)
  → detect on nightly or Sync now
  → reconcile to canonical MB Person
  → ambiguous → Review queue (no silent destructive merge)
  → trigger eligible reprocessing (video recognition, indexes)
```

### Chain D — Evidence → narrative

```text
Ingest (photo/video/comms/…)
  → correlation across sources
  → evidence-backed narrative/summary
  → drill-down to evidence
  → owner review before durable Story save
```

### Chain E — Archive gap → propagate

```text
Archive gap / Health queue item
  → Review & Learn task
  → owner correction
  → propagate to affected evidence/retrieval
  → preserve provenance of prior assertions
```

---

## 3. Increment kinds

| Kind | Meaning |
|------|---------|
| **F** | Foundational capability |
| **U** | Product / UX maturation |
| **A** | Archive-understanding expansion |
| **E** | Family-facing experience / proof |

Increments below list primary kinds; many are mixed.

---

## 4. Proposed increments

### P2-I1 — Show me Peggy (Person-in-Media Vertical) · **F+E** · **FIRST AUTHORIZED BUILD CANDIDATE**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Ask “Show me Peggy” returns Immich-backed canonical Person results including **photos and exact video appearance moments**; open jumps to timeslot; owner can correct; correction reuses; context returns |
| **MBPS** | P2-ID-01..04; P2-VID-01..04 (VID-05 earn-in); thin P2-UX-01 context continuity; P2-UX-04 progressive disclosure; Recognize→Confirm→Reuse + Ask→Evidence→Correct patterns |
| **Absorbs** | TASK-P1P2-001 **for Ask/Person-in-media path**; sync portion of continuous identity; reprocess eligibility |
| **EVSs covered (primary)** | See Appendix: ~20 active homes including EVS-009/191, EVS-011/193, EVS-024, EVS-037/246, EVS-058, EVS-100, EVS-228, EVS-250, related person/video retrieval needing moment completion. P1 EVS-014/028/032 remain **regression** but must **earn in** to moment-complete behavior under this increment’s acceptance |
| **Reusable capabilities** | Provider Person sync (nightly + Sync now); canonical map/create; face evidence records; video appearance timeslot index; Ask person retrieval; correction→relearn; result-context stack |
| **Prerequisites** | P1 baseline (Ask, People, Immich provider, HVRT/video path as available) |
| **Domain/services** | Person & Identity; Provider sync job; Video Intelligence / HVRT timeslots; Ask/Query Planner; Evidence/Provenance; thin Review correct |
| **UX / Experience Flows** | **Formalize:** Show-me-Peggy result→open moment→correct→return; Recognize→Confirm→Reuse. **Do not** require full product-shell redesign |
| **Acceptance scenarios** | (1) Peggy exists as MB Person solely because named in Immich—no redundant MB enrollment. (2) Sync now + nightly path both refresh provider people. (3) “Show me Peggy” returns photos **and** video moments. (4) Opening a video result jumps to Peggy appearance timeslot. (5) Owner corrects missed/wrong face↔Person. (6) Correction becomes reusable evidence. (7) Subsequent retrieval reflects correction where appropriate. (8) Provenance + system confidence preserved; no fake certainty. (9) Open/detail/correct/return restores prior result context |
| **OUT / deferred** | Full product shell; Archive Health redesign; Settings maturity; high-volume timeline chrome; SMS; kinship graph; STT/spoken moments; external history; multi-user; inventing unsupported Immich stats; owner-adjustable confidence dials |
| **Risks / unresolved** | Reprocess scope (all videos vs queue/budget)—**founder decision**. Whether “moments” for I1 are **face-appearance only** (recommended) vs also speech—**flagged**. HVRT readiness on FlightSim. Immich face-asset rights/API for evidence reuse. Duplicate EVS IDs in catalog (Appendix issues) |

### P2-I2 — Product Shell & Context Maturation · **U**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Ask, Library/Timeline, People, Stories, Journal, Artifacts, Review, Settings, Archive Health feel like one product; context preserved across open→act→return |
| **MBPS** | P2-UX-01, P2-UX-04 |
| **EVSs** | Enabling; Sharing living-room style EVS-017/199/242 as presentation targets when shell exists |
| **Capabilities** | App shell navigation; shared context bus; progressive disclosure |
| **Prerequisites** | I1 (so shell wraps a real vertical, not empty chrome) |
| **Domain/services** | Experience Orchestrator / UX shell |
| **UX / Flows** | Shell IA; may formalize Explore→Open→Return |
| **Acceptance** | Owner no longer experiences P1 as disconnected tools; I1 flows still work inside shell |
| **OUT** | Full high-volume timeline engine (I4); multi-user |
| **Risks** | Over-scoping shell into Dashboard polish |

### P2-I3 — Archive Health & Provider Honesty · **U+A**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Owner sees coverage/gaps and a few high-leverage “Work on these now” items; Immich Photos inventory honest/real when accessible |
| **MBPS** | P2-AH-01..03; thin P2-SET-02 |
| **Absorbs** | **TASK-P1P2-004** |
| **EVSs** | EVS-216-class archive completeness; dating-gap teach queues (e.g. EVS-203) as Health entries |
| **Capabilities** | Status→Health; provider probes; gap→task handoff (Chain E start) |
| **Prerequisites** | I1 (recognition coverage metrics meaningful); I2 entry point |
| **Acceptance** | Photos totals available≠0 when Immich healthy+authorized; queues small and actionable |
| **OUT** | Universal health %; fake zeros; final Dashboard chrome |
| **Risks** | Immich API key scopes (known P1 residual) |

### P2-I4 — Timeline-first High-Volume Explore · **U**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Large photo/video sets navigable by timeline zoom/cluster/filter without provider-first UX |
| **MBPS** | P2-UX-02, P2-UX-03 |
| **EVSs** | Discovery/Photos/Places/Events P2 & P1–P2 explore-heavy set (Appendix) |
| **Prerequisites** | I2; moments from I1 improve video explore quality |
| **Acceptance** | Real archive-scale browse practical; return preserves filters/position |
| **OUT** | Confidence-first UI; spoken-moment engine (I9) |
| **Risks** | Scope creep into narrative |

### P2-I5 — Universal Person Surfaces · **F+U**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Every Person picker/associate surface uses Immich-named people via shared teach/map path—not Ask-only |
| **MBPS** | P2-ID-02/03 expansion; Import Don’t Replace |
| **Absorbs** | Remainder of **TASK-P1P2-001** |
| **EVSs** | Remaining People & Identity P2/P1–P2 not consumed by I1 |
| **Prerequisites** | I1 sync/map service |
| **Acceptance** | No surface requires MB-only pre-census when Immich has unique exact name |
| **OUT** | Bulk import choreography; flattening authority |
| **Risks** | Ambiguous same-name collisions UX consistency |

### P2-I6 — Kinship Inference · **A**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Minimal asserted facts yield disclosed derived kinship (cousins, gendered resolve where safe) |
| **MBPS** | P2-GRAPH-01 |
| **Absorbs** | **TASK-P1P2-002** |
| **EVSs** | Relationships taxonomy + grandkids-style retrieval |
| **Prerequisites** | I1/I5 Person stability |
| **Acceptance** | Inference disclosed; never overwrites SoT; ambiguity asked |
| **OUT** | Tree visualization; photo auto-genealogy |
| **Risks** | Over-inference |

### P2-I7 — SMS/Text Evidence · **A**

| Field | Content |
|-------|---------|
| **Primary user outcome** | SMS is first-class searchable evidence linked to People |
| **MBPS** | P2-COM-01 |
| **EVSs** | Text/SMS communications set |
| **Prerequisites** | I5 Person linking |
| **Acceptance** | Ingest, search, provenance, Person correlation |
| **OUT** | Multi-user messaging; carrier replacement |
| **Risks** | Source export quality / legal retention |

### P2-I8 — Richer Email · **A**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Threads, participants, attachments, richer correlation beyond P1 phrase retrieval |
| **MBPS** | P2-COM-02/03 |
| **EVSs** | Email-heavy communications / mixed email+text summaries |
| **Prerequisites** | I7 patterns helpful; I5 |
| **Acceptance** | Coverage gaps disclosed; originals preserved |
| **OUT** | Email client replacement |
| **Risks** | Attachment/artifact boundary with I10 |

### P2-I9 — Spoken Moments (STT / Speaker) · **F+A**

| Field | Content |
|-------|---------|
| **Primary user outcome** | “Hear/find X talking about Y” returns authentic passages, not only files |
| **MBPS** | P2-AUD-01..04; Chain B |
| **EVSs** | Audio & Voice + spoken-in-video summaries / voice identify |
| **Prerequisites** | I1 Person + timeslot substrate; ideally I4 explore |
| **Acceptance** | Time-aligned transcript; speaker↔Person with correction/reuse; authentic voice only |
| **OUT** | Synthetic speech; playlist≠listening confusion without disclosure |
| **Risks** | Diarization quality; compute cost |

### P2-I10 — Cross-Source Correlation · **A**

| Field | Content |
|-------|---------|
| **Primary user outcome** | People/Places/Events/Trips/Stories/artifacts correlate across modalities when evidence supports |
| **MBPS** | P2-GRAPH-02/03 |
| **EVSs** | Artifacts/Recipes and mixed-correlation asks |
| **Prerequisites** | I7–I9 as available; I6 helpful |
| **Acceptance** | Corrections propagate safely; provenance retained |
| **OUT** | Forced manual link graphs |
| **Risks** | Weak-evidence over-linking |

### P2-I11 — Evidence-Backed Narrative & Summaries · **E+A**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Multi-source narratives/summaries with drill-down; review before durable save |
| **MBPS** | P2-NAR-01..03 |
| **EVSs** | Stories & Narrative P2/P1–P2 (family-only; not 254–256) |
| **Prerequisites** | I10 |
| **Acceptance** | Facts vs inference vs gaps visible; AI narrative not auto-authoritative |
| **OUT** | External history (I11-later); synthetic media |
| **Risks** | Fluent-but-false tone |

### P2-I11-later — External Historical Context · **E**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Dated media can show cited U.S./world context distinguishable from family evidence |
| **MBPS** | P2-NAR-04 |
| **EVSs** | **EVS-254, 255, 256 only** |
| **Prerequisites** | I11 |
| **Acceptance** | Citations; no implied family impact without family evidence |
| **OUT** | Merging external facts into authentic evidence |
| **Risks** | Source quality; date precision |

### P2-I12 — Dynamic Views · **U**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Save intent; Live / Curated / Frozen modes |
| **MBPS** | P2-VIEW-01..03 |
| **EVSs** | Enabling for explore/narrative reopen |
| **Prerequisites** | I4 + I11 |
| **Acceptance** | Owner chooses live vs frozen deliberately |
| **OUT** | Multi-user share packages |
| **Risks** | Intent schema churn |

### P2-I13 — Settings & Processing Controls · **U**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Operate providers/processing/archive locations without dumping ops into explore |
| **MBPS** | P2-SET-01/02 |
| **EVSs** | Enabling |
| **Prerequisites** | I3; processing realities from I1/I9 |
| **Acceptance** | Sync now visible; provider health actionable; **confidence thresholds remain system-managed** unless founder later revisits |
| **OUT** | Early multi-user admin; exposing private owner trust ratings |
| **Risks** | Pressure to add threshold sliders contrary to locked decision |

### P2-I14 — Owner-run Capture Campaigns · **E**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Gap-driven, owner-controlled campaign capture; family input only via owner-run channels |
| **MBPS** | P2-CAP-01..03 thin |
| **EVSs** | Guided/Journal capture P2 + family contribution **owner-mediated** scenarios |
| **Prerequisites** | I3 gaps; I11 useful prompts |
| **Acceptance** | Campaign provenance; review before durable save; **not** general multi-user |
| **OUT** | Independent relative accounts |
| **Risks** | Confusing “contribution” with multi-user |

### P2-I15 — Trust Consistency & Private Owner Trust · **F**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Consistent correct/merge/split/supersede across objects; owner-private trust ratings never leak into family-facing UX |
| **MBPS** | P2-TRUST-01..04 + locked private-trust decision |
| **EVSs** | Trust & Corrections remaining set; handwriting attribution |
| **Prerequisites** | Earns in from I1; formalize after major surfaces exist |
| **Acceptance** | Family UX shows MB uncertainty/evidence only; owner-private trust hidden; authentic vs generated boundary held |
| **OUT** | Synthetic media features |
| **Risks** | Dual “confidence” concepts colliding in UX copy |

### P2-I16 — Portability & Import-back · **A**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Stronger export/retrieve; import format-1 MB package without inventing Immich library restore |
| **MBPS** | Ownership; EVS-020 family |
| **Absorbs** | **TASK-P1P2-003** |
| **EVSs** | EVS-020; note EVS-202 duplicate/phase conflict (§11) |
| **Prerequisites** | Mature domain objects (after I11+) |
| **Acceptance** | Round-trip MB-owned knowledge/versions/GC context/MB originals |
| **OUT** | Full Immich/HVRT binary library restore |
| **Risks** | Format evolution |

### Late-P2 / P2.5 — Multi-user + Tone Dial · **E**

| Field | Content |
|-------|---------|
| **Primary user outcome** | Shared archive with accounts; relative “my father”; tone/warm path |
| **MBPS** | P2-MU-*; EVS-019/201 |
| **Prerequisites** | Primary owner P2 mature |
| **OUT as early P2** | Do not pull forward to unblock I1–I16 |
| **Risks** | Premature architecture |

---

## 5. Why this sequence (dependency + user value)

1. **Prove Chain A first** — locked proof point; unblocks credibility of P2.  
2. **Wrap with shell** — maturation after vertical exists.  
3. **Health / explore** — scale and honesty once person-moments exist.  
4. **Universal Person + kinship** — widen identity.  
5. **Comms → spoken → correlate → narrative** — archive understanding expansion.  
6. **Views / Settings / campaigns / trust / portability** — product completion.  
7. **External history late; multi-user/tone last.**

P3 synthetic EVS-253/257–260 stay **out**.

---

## 6. Finish block (required)

### A. Proposed P2 increment sequence

```text
P2-I1  Show me Peggy (Person-in-Media Vertical)     ← first authorized build candidate
P2-I2  Product Shell & Context Maturation
P2-I3  Archive Health & Provider Honesty (+004)
P2-I4  Timeline-first High-Volume Explore
P2-I5  Universal Person Surfaces (rest of +001)
P2-I6  Kinship Inference (+002)
P2-I7  SMS/Text Evidence
P2-I8  Richer Email
P2-I9  Spoken Moments (STT/Speaker)
P2-I10 Cross-Source Correlation
P2-I11 Narrative & Summaries
P2-I11-later External Historical Context (254–256)
P2-I12 Dynamic Views
P2-I13 Settings & Processing Controls
P2-I14 Owner-run Capture Campaigns
P2-I15 Trust Consistency & Private Owner Trust
P2-I16 Portability & Import-back (+003)
Late   Multi-user + Tone Dial
```

### B. EVS-to-increment traceability summary

- **Active P2-relevant EVSs:** 138 (89 P2 + 48 P1–P2 + 1 P2–P3).  
- **All have a primary home** in Appendix A (duplicates noted, not deleted/renumbered).  
- **P1-only (115):** regression pool; several (e.g. EVS-014 teach-in-video, person photo/video basics) **must earn moment-complete behavior** under I1 acceptance without re-phasing them.  
- **P3 synthetic / deferred invite:** out of P2 build.  
- Detailed map: **Appendix A**.

### C. Top dependency chains

Documented in §2: **A Person-in-media**, **B Spoken**, **C Provider sync**, **D Narrative**, **E Gap→propagate**. I1 executes A+C; I9 executes B; I10–I11 execute D; I3+I15 strengthen E.

### D. Open planning questions requiring founder decision

1. **Duplicate EVS block EVS-001..020 ≡ EVS-183..202** (exact scenario text). Which ID is canonical for acceptance tracing? (Do not renumber here—decision needed.)  
2. **EVS-020 (P2) vs EVS-202 (P2–P3)** same export scenario, **conflicting phase**—which phase governs?  
3. **I1 moment definition:** face-appearance timeslots only (recommended for “Show me Peggy”) or must v1 include speech passages?  
4. **Video reprocess scope** when a Person becomes newly known: whole library, recent N years, owner-selected, or budgeted queue?  
5. **Immich face assets** as reusable MB recognition evidence in I1: required vs post-I1 hardening?  
6. **FlightSim HVRT** readiness bar for I1 acceptance if timeslot worker degraded—fail closed vs partial disclosure?  
7. Should **TASK-004** Immich Photos inventory remain I3, or be a tiny ops patch parallel to I1 without expanding I1 scope?  
8. Confirm **confidence** stays system-managed for all of P2 unless revisited (locks out threshold sliders in I13).

### E. Recommended first authorized build increment & acceptance gate

**Recommend: P2-I1 — Show me Peggy (Person-in-Media Vertical).**

**Acceptance gate (FlightSim / real-family where practical):**

1. Peggy (or designated Immich-named person) is a canonical MB Person **without** redundant MB enrollment.  
2. Nightly sync configuration exists; **Sync / Poll now** refreshes provider people.  
3. Ask “Show me \<Person\>” returns **photos + video appearance moments**.  
4. Opening a video result **jumps to the appearance timeslot**.  
5. Owner **corrects** a miss/wrong association; correction stored as reusable evidence with provenance.  
6. A later Ask reflects the correction where appropriate.  
7. System confidence/uncertainty disclosed appropriately; **no** owner-private trust UI in this slice.  
8. Open → detail/correct → **return** restores the prior result context.  
9. Newly mapped Person is **eligible** for video-recognition processing against existing video (queue may still be running, but eligibility and kickoff are real—not documentation-only).

**Still required before code:** founder approval of this plan, then a written **P2-I1 definition** for review, then explicit build authorization.

---

## 7. Catalog issues for review (no renumber/delete)

| Issue | Detail | Impact |
|-------|--------|--------|
| **Exact duplicates** | EVS-001..020 duplicated as EVS-183..202 | Double-counts; ambiguous acceptance IDs |
| **Phase conflict** | EVS-020 P2 vs EVS-202 P2–P3 (same export text) | Portability sequencing ambiguity |
| **Tone dial duplicate** | EVS-019 ≡ EVS-201 | Late-P2 tracing noise |
| **Sharing duplicate** | EVS-017 ≡ EVS-199 | Shell/TV experience tracing noise |
| **Near-duplicates** | e.g. EVS-037 ~ EVS-246 (“Dad laughing”); EVS-233 ~ EVS-234 (spoken summarize; 234 is P1) | Overlapping acceptance |
| **Taxonomy under-represents video** | Few phase=P2 rows in Video taxonomy, but many People scenarios need timeslots | I1 must pull cross-taxonomy EVSs |
| **Dependency gap** | Catalog does not explicitly state “reprocess existing video when Person newly known” | Locked planning decision supplies it—must appear in I1 definition |
| **Ambiguity** | “Show me Peggy” not a numbered EVS; nearest are person photo/video + teach loops | Proof point is founder-specified composite acceptance, mapped onto EVS homes |

---

## Appendix A — Active P2 / P1–P2 / P2–P3 primary homes

*Primary home only. Exact duplicates keep their EVS numbers and inherit the lower-number sibling’s home.*

| EVS | Phase | Taxonomy | Primary increment | Notes |
|---|---|---|---|---|
| EVS-002 | P1–P2 | Events & Timeline | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-004 | P1–P2 | Recipes | P2-I10 Cross-Source Correlation |  |
| EVS-008 | P1–P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-009 | P1–P2 | Photos | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-010 | P1–P2 | Recipes | P2-I10 Cross-Source Correlation |  |
| EVS-011 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-017 | P2 | Sharing | P2-I2 Product Shell & Context Maturation |  |
| EVS-019 | P2 | Trust & Evidence | Late-P2/P2.5 Multi-user + Tone |  |
| EVS-020 | P2 | Ownership & Portability | P2-I16 Portability & Import-back |  |
| EVS-024 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-026 | P1–P2 | People & Identity | P2-I9 Spoken Moments (STT/Speaker) |  |
| EVS-027 | P2 | People & Identity | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-029 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-030 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-033 | P1–P2 | People & Identity | P2-I9 Spoken Moments (STT/Speaker) |  |
| EVS-034 | P1–P2 | People & Identity | P2-I5 Universal Person Surfaces |  |
| EVS-035 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-037 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-038 | P2 | People & Identity | P2-I5 Universal Person Surfaces |  |
| EVS-039 | P2 | People & Identity | P2-I5 Universal Person Surfaces |  |
| EVS-040 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-042 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-043 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-045 | P2 | People & Identity | P2-I6 Kinship Inference |  |
| EVS-047 | P1–P2 | Communications | P2-I8 Richer Email |  |
| EVS-055 | P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-058 | P2 | Video | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-064 | P2 | Audio & Voice | P2-I9 Spoken Moments (STT/Speaker) |  |
| EVS-065 | P1–P2 | Communications | P2-I7 SMS/Text Evidence |  |
| EVS-069 | P2 | Relationships | P2-I6 Kinship Inference |  |
| EVS-070 | P2 | Communications | P2-I8 Richer Email |  |
| EVS-071 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-079 | P2 | Corrections & Learning | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-081 | P2 | Photos | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-082 | P2 | Photos | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-083 | P2 | Relationships | P2-I6 Kinship Inference |  |
| EVS-084 | P2 | Relationships | P2-I6 Kinship Inference |  |
| EVS-085 | P1–P2 | Events & Timeline | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-086 | P1–P2 | Events & Timeline | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-087 | P1–P2 | Relationships | P2-I6 Kinship Inference |  |
| EVS-088 | P1–P2 | Relationships | P2-I6 Kinship Inference |  |
| EVS-089 | P1–P2 | Relationships | P2-I6 Kinship Inference |  |
| EVS-090 | P1–P2 | Places | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-091 | P2 | Corrections & Learning | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-092 | P2 | Corrections & Learning | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-093 | P2 | Corrections & Learning | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-094 | P2 | Corrections & Learning | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-095 | P2 | Photos | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-096 | P2 | Corrections & Learning | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-097 | P2 | Corrections & Learning | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-098 | P2 | Corrections & Learning | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-100 | P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-103 | P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-105 | P1–P2 | Places | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-106 | P1–P2 | Communications | P2-I7 SMS/Text Evidence |  |
| EVS-107 | P1–P2 | Communications | P2-I8 Richer Email |  |
| EVS-108 | P1–P2 | Communications | P2-I8 Richer Email |  |
| EVS-109 | P2 | Photos | P2-I11 Narrative & Summaries |  |
| EVS-110 | P1–P2 | Events & Timeline | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-111 | P1–P2 | Events & Timeline | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-114 | P2 | Corrections & Learning | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-116 | P2 | Places | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-118 | P1–P2 | Communications | P2-I7 SMS/Text Evidence |  |
| EVS-119 | P2 | Places | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-123 | P2 | Audio & Voice | P2-I9 Spoken Moments (STT/Speaker) |  |
| EVS-124 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-126 | P2 | Places | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-127 | P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-128 | P2 | Places | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-129 | P1–P2 | Family Contribution | P2-I14 Owner-run Capture Campaigns |  |
| EVS-136 | P1–P2 | Guided & Journal Capture | P2-I14 Owner-run Capture Campaigns |  |
| EVS-140 | P2 | Guided & Journal Capture | P2-I14 Owner-run Capture Campaigns |  |
| EVS-147 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |  |
| EVS-149 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |  |
| EVS-152 | P2 | Artifacts | P2-I10 Cross-Source Correlation |  |
| EVS-157 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |  |
| EVS-158 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |  |
| EVS-159 | P1–P2 | Artifacts | P2-I10 Cross-Source Correlation |  |
| EVS-161 | P2 | Artifacts | P2-I10 Cross-Source Correlation |  |
| EVS-167 | P1–P2 | Trust & Evidence | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-168 | P2 | Trust & Evidence | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-170 | P1–P2 | Trust & Evidence | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-171 | P2 | Trust & Evidence | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-181 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-182 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-184 | P1–P2 | Events & Timeline | P2-I4 Timeline-first High-Volume Explore | Exact duplicate of EVS-002; same home |
| EVS-186 | P1–P2 | Recipes | P2-I10 Cross-Source Correlation | Exact duplicate of EVS-004; same home |
| EVS-190 | P1–P2 | Stories & Narrative | P2-I11 Narrative & Summaries | Exact duplicate of EVS-008; same home |
| EVS-191 | P1–P2 | Photos | P2-I1 Show me Peggy (Person-in-Media Vertical) | Exact duplicate of EVS-009; same home |
| EVS-192 | P1–P2 | Recipes | P2-I10 Cross-Source Correlation | Exact duplicate of EVS-010; same home |
| EVS-193 | P1–P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) | Exact duplicate of EVS-011; same home |
| EVS-199 | P2 | Sharing | P2-I2 Product Shell & Context Maturation | Exact duplicate of EVS-017; same home |
| EVS-201 | P2 | Trust & Evidence | Late-P2/P2.5 Multi-user + Tone | Exact duplicate of EVS-019; same home |
| EVS-202 | P2–P3 | Ownership & Portability | P2-I16 Portability & Import-back | Exact duplicate of EVS-020; same home |
| EVS-203 | P2 | Corrections & Learning | P2-I3 Archive Health & Provider Honesty |  |
| EVS-204 | P2 | Relationships | P2-I6 Kinship Inference |  |
| EVS-205 | P2 | Relationships | P2-I6 Kinship Inference |  |
| EVS-206 | P2 | Relationships | P2-I6 Kinship Inference |  |
| EVS-207 | P2 | Relationships | P2-I6 Kinship Inference |  |
| EVS-208 | P2 | Relationships | P2-I6 Kinship Inference |  |
| EVS-209 | P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-210 | P2 | Relationships | P2-I6 Kinship Inference |  |
| EVS-211 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-212 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-213 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-214 | P2 | Corrections & Learning | P2-I15 Trust Consistency & Private Owner Trust |  |
| EVS-216 | P2 | Trust & Evidence | P2-I3 Archive Health & Provider Honesty |  |
| EVS-217 | P2 | Ownership & Portability | P2-I16 Portability & Import-back |  |
| EVS-220 | P2 | Communications | P2-I7 SMS/Text Evidence |  |
| EVS-221 | P2 | Communications | P2-I7 SMS/Text Evidence |  |
| EVS-222 | P2 | Communications | P2-I7 SMS/Text Evidence |  |
| EVS-223 | P2 | Communications | P2-I7 SMS/Text Evidence |  |
| EVS-224 | P2 | Communications | P2-I7 SMS/Text Evidence |  |
| EVS-226 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-227 | P2 | Discovery | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-228 | P2 | People & Identity | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-229 | P2 | Photos | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-230 | P2 | People & Identity | P2-I5 Universal Person Surfaces |  |
| EVS-232 | P2 | Audio & Voice | P2-I9 Spoken Moments (STT/Speaker) |  |
| EVS-233 | P2 | Audio & Voice | P2-I9 Spoken Moments (STT/Speaker) |  |
| EVS-235 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-236 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-237 | P2 | Video | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-238 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-239 | P2 | Family Contribution | P2-I14 Owner-run Capture Campaigns |  |
| EVS-241 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-242 | P2 | Sharing | P2-I2 Product Shell & Context Maturation |  |
| EVS-243 | P2 | Audio & Voice | P2-I9 Spoken Moments (STT/Speaker) |  |
| EVS-244 | P2 | Recipes | P2-I10 Cross-Source Correlation |  |
| EVS-246 | P1–P2 | Video | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-247 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-248 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-249 | P2 | Discovery | P2-I4 Timeline-first High-Volume Explore |  |
| EVS-250 | P2 | Corrections & Learning | P2-I1 Show me Peggy (Person-in-Media Vertical) |  |
| EVS-251 | P2 | Stories & Narrative | P2-I11 Narrative & Summaries |  |
| EVS-254 | P2 | Discovery | P2-I11-later External Historical Context |  |
| EVS-255 | P2 | Discovery | P2-I11-later External Historical Context |  |
| EVS-256 | P2 | Stories & Narrative | P2-I11-later External Historical Context |  |
