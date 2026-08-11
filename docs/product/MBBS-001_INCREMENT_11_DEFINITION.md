# MBBS-001 Increment 11 — Guided Capture (EF-11) — Final Definition

**Status:** **BUILD AUTHORIZED — READY FOR OWNER ACCEPTANCE**  
**Date:** 2026-08-11 (build authorized)  
**Roadmap placement:** **After Increment 10 Cross-provider Person (ACCEPTED)** · **Before Increment 12 (MV Export)**  
**Owner acceptance gate (locked):** On FlightSim, **without SQL/dev intervention**, Tom creates an outbound **Guided Capture campaign** for a **real recipient** (no MemoryBox account required), pastes/edits ≥3 questions, sets a **short practical cadence**, and starts. MemoryBox sends questions **on that cadence** (does **not** stall on unanswered priors). Recipient replies typed then voice; MB correlates; Tom sees **New responses**, reviews, sets **credibility**, marks reviewed; campaign **completes outbound** after the last active question is **sent** (or skipped); late replies still correlate.  
**Charter source:** [MBBS-001](MBBS-001_MEMORYBOX_BUILD_SPECIFICATION.md) § Increment 11  
**Governed by:** [MB_P1_ENGINEERING_RULES.md](../source/MB_P1_ENGINEERING_RULES.md) · [MB_LOCKED_DECISIONS_P1.md](../source/MB_LOCKED_DECISIONS_P1.md)  
**EVS catalog (authoritative):** [MBEVS-001_EVS_Catalog_v0.8.xlsx](../source/MBEVS-001_EVS_Catalog_v0.8.xlsx) (v0.8)  
**Depends on:** I5 Story · **I5A Journal + Capture/STT** · I2 email Evidence foundations · Ask (I4) · I6 Person (optional link only) · I9A owner Person (campaign owner)  
**Prior:** [MBBS-001_INCREMENT_10_ACCEPTANCE.md](MBBS-001_INCREMENT_10_ACCEPTANCE.md) — **ACCEPTED**  
**Acceptance:** [MBBS-001_INCREMENT_11_ACCEPTANCE.md](MBBS-001_INCREMENT_11_ACCEPTANCE.md) — **READY FOR OWNER ACCEPTANCE**  
**Next (after 11):** Increment 12 — MV Export  
**Authorization:** **Authorized** — Tom: *If there are no more questions or issues, you are approved to build i11* (2026-08-11).

**Product intent:** Owner-configured **outbound interview campaigns** to a specific respondent (family, friend, neighbor, coworker, or other memory-holder — including non-MB users). Email is the **required** real end-to-end channel for owner acceptance. In-app owner self-prompt is **not** required for I11-OWNER.

**Parked / OUT elsewhere:** Kinship [TASK-P1P2-002](MBBS_P1_P2_BACKLOG.md) · Universal lazy-teach [TASK-P1P2-001](MBBS_P1_P2_BACKLOG.md) · EVS-140 · I12 Export · see §11.

---

## 0. Locked decisions (final)

| Topic | Decision |
|-------|----------|
| Product slice | Guided Capture **campaigns**: ordered questions → time-driven outbound → correlated inbound responses → owner review |
| Respondent | External **contact** (name + email + optional `people.id` link). **No** auto-mint of canonical Person from campaign participation |
| Domain | Distinct **Campaign** · **Question** · **Outbound Delivery** · **Inbound Response**. Not flattened to email rows |
| **Cadence (P1 default)** | **Time-driven.** Start time + cadence; one question **per outbound message**; next send follows cadence **even if prior unanswered**. Responses may arrive before/between/after later questions |
| **Future option** | Schema/API may reserve `wait_for_response_before_next` — **not** P1 default |
| “One at a time” | Means **one question in each outbound delivery**, **not** “only one unanswered question may exist” |
| Outbound completion | Campaign **exhausts/completes sending** when all active questions are **sent** or **explicitly skipped/cancelled** — **not** when all are answered |
| Late replies | Allowed after outbound completion; must still correlate |
| Skip | Owner may skip **unsent** question: mark skipped (preserve history), advance to next active; do not rewrite sent/answered history via later edit/reorder |
| Response channels | Typed email; voice/audio attachment; other inbound only if trivial |
| STT | **Existing I5A Capture/STT only** — no GC-specific Whisper |
| Review UI | **Required** thin surface: new-response count, open/read/play, transcript correct without altering audio, mark reviewed, **credibility assessment** |
| Credibility | **IN I11** — response-specific owner assessment enum (see §6); separate from testimony; **no** Ask ranking change in I11 |
| Knowledge | **Guided Capture Response is already** searchable/citable MB testimony. Promotion to Story/Journal/fact is **optional** and semantic |
| Email | Reuse **most mature path**: Marvin Gmail send/poll + plus-address / Message-ID correlation **behind** a Capture-channel provider — **do not** invent a second email architecture. FlightSim requires **real** outbound + inbound. **Owner Gmail:** send as owner (Sent retained); replies to owner inbox; MB polls/correlates |
| In-app self-prompt | **Not** required for I11-OWNER; earn-in only if same domain model |
| Prove | `prove-guided-capture` (+ `--flightsim`) |

---

## 1. Why 11 exists

Prior increments give owner-initiated Story/Journal and archive email Evidence. Missing: **owner-run interview campaigns** to others, **time-driven** outbound cadence, **prompt↔response** correlation, **owner review + credibility**, and Ask use of **respondent testimony** without forcing Story curation.

---

## 2. EVS assignment (v0.8, under campaign model)

| EVS | Role in I11 |
|-----|-------------|
| **EVS-131** | **IN** — email question + reply (campaign primary) |
| **EVS-130 / 135** | **IN** — voice inbound; preserve audio; I5A STT |
| **EVS-137** | **IN** — Ask retrieves linked Guided Capture Response (owner or third-party wording: “what did they say…”) — intentional testimony, not invented synthesis |
| **EVS-138 / 139** | **PARTIAL** — campaign pending/skip/next-active semantics (not owner “unanswered inbox” as sole UX) |
| **EVS-132** | **OUT of owner gate** — email campaign is required channel; thin preference optional |
| **EVS-133 / 134** | **PARTIAL** — open questions + attachment preserve when present |
| **EVS-136 / 140** | **DEFERRED / OUT** |
| **EVS-012** | **DONE** prior |

---

## 3. Domain model

### 3.1 Entities (PostgreSQL SoT)

```
GuidedCaptureRespondentContact
  id
  display_name
  email
  people_id NULLABLE   -- optional explicit link only
  provenance

Campaign
  id, owner_person_id
  respondent_contact_id
  status: draft | running | paused | stopped | outbound_complete
  start_at, cadence_interval, timezone
  send_mode: time_driven (P1 default)
             [| wait_for_response_before_next reserved, unused in P1]
  created_at, updated_at, provenance

Question
  id, campaign_id
  body_text, sort_order
  status: active | skipped | cancelled | deleted_soft?
  -- skip preserves row + history; not silent delete of identity

OutboundDelivery
  id, campaign_id, question_id, respondent_contact_id
  channel: email
  scheduled_for, sent_at
  status: pending | sent | failed | cancelled
  outbound_message_id, correlation_token, thread keys
  preserved outbound Source/Evidence refs
  provenance

InboundResponse   -- FIRST-CLASS searchable/citable testimony
  id
  campaign_id, question_id, delivery_id NULLABLE (best-effort), respondent_contact_id
  channel: email_text | voice | …
  received_at
  review_status: new | reviewed
  credibility: not_rated | trust_strongly | generally_trust | uncertain | doubt | believe_incorrect
  credibility_set_at, credibility_set_by, credibility_history (versions)
  preserved inbound Source/Evidence / audio_uri (immutable)
  extracted_text (derived from email; original retained)
  transcript_text + transcript_versions (STT derived; audio immutable)
  optional_resulting_knowledge_refs[]  -- Story/Journal/… only if promoted
  provenance
```

**Status terminology:**

| Concept | Meaning |
|---------|---------|
| `running` | Cadence may schedule/send |
| `paused` | No new sends |
| `stopped` | Owner stopped; cancel pending; no future sends |
| `outbound_complete` | All **active** questions **sent** or **skipped/cancelled** — sending finished; **responses may still arrive** |
| Response `new` / `reviewed` | Owner review state — independent of campaign outbound status |
| Credibility | Independent owner assessment on each response |

### 3.2 Cadence rules (P1 default = time-driven)

1. Owner sets **start_at** and **cadence** (e.g. weekly / every N days; acceptance may use a short interval).  
2. On start: schedule Delivery for Question 1 at start (or immediate).  
3. After a delivery is **sent** (success), schedule the **next active** question’s delivery at `sent_at + cadence` (or next cadence tick) — **regardless of whether a response arrived**.  
4. Multiple unanswered questions may coexist; each was one outbound at its time.  
5. **Pause** holds pending schedules; **Resume** continues remaining active queue.  
6. **Stop** cancels pending; no further sends.  
7. **Skip** (unsent only): mark question `skipped`, preserve history, schedule/send next active per cadence rules.  
8. **Outbound complete** when no active unsent questions remain (all sent or skipped/cancelled).  
9. Failed send: visible `failed`; thin retry; do not pretend sent.  
10. Reserve `wait_for_response_before_next` for later — unused in P1.

**Example:** Q1 Wed → Q2 next Wed → Q3 next Wed, even if Q1/Q2 unanswered.

### 3.3 Email correlation (reuse Marvin path)

**Inspected:** Mature path is `application/marvin_capture/` — Gmail API send/poll, plus-address / Reply-To / Message-ID / thread correlation, raw mail preserve (`mail_store`, `gmail_client`, `plus_address`, `reply_extract`). MemoryBox PG today has **mbox ingest** (Evidence) but **no** separate outbound writer in `memorybox/providers`.

**Lock:** Implement Capture-channel **email adapter** that **reuses Marvin Gmail send/poll + correlation patterns** (extract behind provider interface into `memorybox/`). **Do not** invent a second parallel email stack. Preserve outbound/inbound originals; Guided Capture Delivery/Response hold product linkage. FlightSim owner gate = **real** Gmail (or same adapter) outbound + real inbound reply.

**Owner Gmail mailbox (locked):** Guided Capture **sends through the owner’s configured Gmail account** so the message **originates from the owner** and is **retained in the owner’s Gmail Sent** history. **Replies return to the owner’s normal Gmail inbox** (same account; plus-address / Reply-To / subject token are routing aids inside that inbox). MemoryBox **polls that inbox**, preserves raw mail, and **ingests/correlates** into Delivery/Response. There is **no** separate MemoryBox outbound mailbox and **no** send-as / relay that would leave Sent outside the owner’s Gmail.

Ambiguous correlation → disclose / owner resolve; never silent wrong attach. Duplicates → idempotent.

### 3.4 Respondent / Person boundary

- Campaign always uses **GuidedCaptureRespondentContact** (name + email).  
- **Do not** auto-create `people.id` because someone was emailed or replied.  
- Owner may **explicitly** link contact → existing Person, or **explicitly** create/link Person when appropriate.  
- Avoid polluting People graph with every campaign email address.

### 3.5 Domain gap (resolved for I11)

Prior Story/Journal/Evidence alone cannot be the capture SoT for third-party Q&A. **I11 requires first-class InboundResponse.** That record **is** valid MemoryBox knowledge for Ask. Optional promotion is separate (§8).

---

## 4. Typed and voice flows

### Typed email

Outbound Delivery preserved → inbound reply preserved → extract text for UI/search **without destroying** original → InboundResponse (`channel=email_text`, `review_status=new`) → bump New responses.

### Voice / audio

Preserve **immutable** audio → **I5A Capture/STT** → transcript derived with provenance → owner may correct transcript (**new version**; audio unchanged; correction ≠ rewriting spoken testimony) → review/credibility/reviewed.

### Other media

Only if trivial earn-in (e.g. preserve image attachment + link).

---

## 5. Owner response review UI (required, thin — no polish)

**Surface:** thin Guided Capture review UI.

| Capability | Required |
|------------|----------|
| **New responses** count/indicator | Yes |
| List: who, campaign, question, typed/voice, received at, STT status, review status, credibility | Yes |
| Open / read typed / play audio / view transcript | Yes |
| Correct transcript without altering audio | Yes |
| See question + respondent + provenance | Yes |
| Mark reviewed | Yes |
| **Credibility assessment** | Yes — §6 |

---

## 6. Owner credibility assessment (IN I11)

On each response, owner sets one of:

- **Not rated** (default)  
- **Trust strongly**  
- **Generally trust**  
- **Uncertain**  
- **Doubt**  
- **Believe incorrect**  

**Storage:** response-specific; owner identity; assessment; timestamp; version history where appropriate; **separate** from respondent testimony.

**Must not:** rewrite respondent words; change authorship; delete disputed testimony; promote opinion into factual evidence.

**I11 Ask:** may **display** credibility when citing a response; **does not** need ranking/boost/suppress logic yet. Later Trust / Family Contribution may use it.

---

## 7. Visibility — “something entered MemoryBox”

Minimum: New-response count/status; received timestamp; campaign + respondent; reviewed/unreviewed; credibility if set.  

**Out:** push, SMS alerts, mobile notification infra, P2 Status Wall.

---

## 8. Resulting knowledge semantics

**Layers stay distinct:**

1. Transport evidence (outbound/inbound mail, audio bytes)  
2. **InboundResponse** — respondent testimony (**already** searchable/citable)  
3. Optional promoted domain object  

**Ask example:** “What did Rick say about Peggy's Christmas parties?” may retrieve Rick’s Guided Capture Response with respondent, prompting question, campaign, received time, channel, credibility if available, original/source provenance — **without** requiring Story promotion.

**Optional promotion (semantic only):**

| Character | Optional landing |
|-----------|------------------|
| Strong narrative recollection | Story (`narrator_person_id` only if Person explicitly linked/created; Ask must disclose contributor) |
| Owner-as-respondent journal-style | Journal |
| Explicit profile/factual claim | Fact/assertion workflow with honest provenance |

**Forbidden:** Force every response into Story; trap response as email-only Evidence; require curation before Ask can cite the Response.

---

## 9. Standard question set (thin)

Small starter seed (e.g. from `config/mem_questions.json` / Marvin bank) + owner paste/custom; basic edit/reorder/delete of **unsent** items; categories may include childhood, parents/grandparents, school, work, marriage/family, holidays/traditions, favorite things, life lessons, tell me about a Person.  

**Do not** build a questionnaire CMS.

Editing/reordering must **not** rewrite already-sent or already-answered question history.

---

## 10. Failure handling

| Failure | Behavior |
|---------|----------|
| Outbound fail | Delivery `failed`; visible; cadence does not treat as sent |
| Uncorrelated inbound | Quarantine / disclose for owner match |
| Duplicate inbound | Idempotent |
| STT fail | Audio preserved; transcript failed; owner reviews audio |
| Stop / outbound_complete | No further sends; late responses still accepted |
| Mail/provider down | Visible degrade |

---

## 11. Out of I11

Multi-user accounts/permissions · P2.5 family-role model · voice login · SMS Guided Capture · push/mobile notifications · full questionnaire CMS · advanced credibility/ranking engine · collaborative Story editing · full family contribution portal · P2 Dashboard/Status Wall · EVS-140 AI prompt generation · kinship inference · universal lazy-teach · Immich write-back · I12 Export · UX polish · requiring in-app self-prompt for owner acceptance · auto-creating People from campaign emails · P1 `wait_for_response_before_next` as default

---

## 12. Success criteria

| ID | Criterion | Proof |
|----|-----------|-------|
| **I11-A** | Campaign + questions + paste/edit; contact respondent without auto Person | Harness + FS |
| **I11-B** | Time-driven cadence; unanswered prior does **not** stall next send | Harness |
| **I11-C** | Skip unsent; pause/resume/stop; outbound_complete ≠ all answered | Harness |
| **I11-D** | Typed reply correlates; New response; originals preserved | Harness + FS |
| **I11-E** | Voice: audio preserved; I5A STT; transcript correctable | Harness + FS |
| **I11-F** | Review UI + credibility enum + mark reviewed | Harness + FS |
| **I11-G** | Testimony non-overwrite; credibility separate | Harness |
| **I11-H** | Response citable in Ask without Story promotion | Harness |
| **I11-I** | Late response after outbound_complete; duplicates; ambiguous correlation; send/STT failure | Harness |
| **I11-J** | I1–I10 proves runnable | Prior |
| **I11-OWNER** | §13 real email loop | Tom |
| **I11-K** | Docs; OUT list not claimed | Docs |

---

## 13. FlightSim owner gate (cadence-driven)

1. Tom creates campaign for **real recipient** (name + email; no MB account).  
2. Pastes/edits **≥3** questions.  
3. Sets a **short practical acceptance-test cadence**.  
4. **Question 1** sends.  
5. Recipient sends **typed** reply.  
6. MB correlates; **New Response** visible.  
7. Tom reviews and sets a **credibility** assessment.  
8. **Next scheduled question sends according to cadence** — **not** because Tom marked the first response reviewed.  
9. Recipient sends **voice/audio** reply.  
10. Original audio preserved; **I5A STT** used.  
11. Tom plays audio, reviews/corrects transcript if needed, rates credibility, marks reviewed.  
12. **Final question** sends according to cadence.  
13. Campaign **outbound_complete** after final active question is **sent** (answers not required for completion).  
14. Late responses remain accepted/correlated afterward.

**In-app self-prompt not required** for this gate.

---

## 14. Synthetic harness (`prove-guided-capture`)

Must prove: time-driven cadence with unanswered prior **not** stalling; skip advances; pause/resume; stop; send failure; late response after `outbound_complete`; duplicates; ambiguous correlation; STT failure; testimony non-overwrite; credibility storage separate; Ask cite Response without promotion; `--flightsim` owner checks.

---

## 15. Architecture sketch (non-binding)

```
Owner ──► Campaign + Questions + RespondentContact (PG)
              │
              ▼
         Scheduler (time-driven cadence / pause / stop / skip)
              │
              ▼
         OutboundDelivery ──► Email adapter (Marvin Gmail lineage)
              │
              ▼
         Inbound mail/audio ──► preserve Evidence/Source
              │
              ▼
         InboundResponse (citable SoT) ──► I5A STT if voice
              │
              ▼
         Review UI (new count, credibility, reviewed)
              │
              ├── Ask cites Response directly
              └── optional semantic promotion (Story/…)
```

---

## 16. Build plan (only after authorize)

1. Migrations for Contact, Campaign, Question, Delivery, Response (+ transcript/credibility versions).  
2. Time-driven scheduler + skip/pause/stop/outbound_complete.  
3. Email adapter reusing Marvin Gmail send/poll/correlation.  
4. Voice → I5A STT.  
5. Thin review UI + new count + credibility.  
6. Ask retrieve Guided Capture Responses.  
7. Optional promotion hooks (not required for cite).  
8. `prove-guided-capture` + FlightSim owner gate.  
9. **Stop** — do not start I12.

---

## 17. Residual notes (non-blocking)

1. Exact cadence units / acceptance-test interval — choose at build (portable).  
2. Soft-delete vs `cancelled` naming for questions — smallest clean at build.  
3. Whether Ask citation UI is thin list vs full card — functional only.

No remaining product blockers for **final review sign-off** of this definition.

---

## 18. Authorization gate

**Status: BUILD AUTHORIZED — shipped for owner acceptance.**

Authorized by Tom (2026-08-11): *If there are no more questions or issues, you are approved to build i11*.

---

## 19. Stop line

After I11 acceptance: **Increment 12** (MV Export) only with new authorization.

---

*End of MBBS-001 Increment 11 — Guided Capture (EF-11) — Final Definition. BUILD AUTHORIZED.*
