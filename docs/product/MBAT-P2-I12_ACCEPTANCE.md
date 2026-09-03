# MBAT-P2-I12 — Historian Collection Acceptance

**Increment:** P2-I12 Historian Collection & Campaigns V1  
**Status:** Planning **LOCKED** 2026-09-03 (founder cadence/assessment/opt-out/ack **2026-09-03**) · **BUILD NOT AUTHORIZED**  
**Prove (proposed):** `python -m memorybox prove-historian-capture` · `--flightsim` for live mailbox  
**Definition:** [MBBS-P2_INCREMENT_12_DEFINITION.md](MBBS-P2_INCREMENT_12_DEFINITION.md)  
**PRD:** [MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md](MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md)

---

## 1. Minimum acceptance intent (FlightSim, no SQL intervention)

Tom executes on FlightSim with real `memorybox@marvinbot.net` channel when live criteria apply. Harness slice tests may use fake adapter.

| # | Criterion |
|---|-----------|
| A-01 | Tom creates a real campaign for ≥1 canonical MB Person with ≥3 questions |
| A-02 | MemoryBox sends one question at a time through dedicated Capture email |
| A-03 | Real reply links to exact campaign, respondent, question snapshot, delivery, received time |
| A-04 | Original inbound text, attachments, metadata, provenance unchanged after receipt |
| A-05 | Tom creates/edits Review Draft without altering immutable source |
| A-06 | Tom records private qualitative assessment distinct from system confidence |
| A-07 | Tom explicitly retains, rejects, or promotes the response |
| A-08 | Promotion creates chosen first-class MB object with full source/draft/promotion chain |
| A-09 | Ask/narration retrieves promoted testimony with correct attribution and uncertainty |
| A-10 | Pause, resume, stop, completion, duplicate handling, unmatched-reply handling work |
| A-11 | PoC SQLite is not a second source of truth |
| A-12 | Existing MemoryBox functionality remains operational |
| A-13 | Unanswered lifecycle: sent → waiting → **one** reminder → waiting → no_response → next question per **question cadence** (follow-up interval separate) |
| A-14 | Respondent STOP opts out with logged provenance; no further sends to that respondent |
| A-15 | Thank-you acknowledgment after adjudication may confirm receipt only; never leaks assessment, rejection rationale, or draft/Story text |

---

## 2. Automated prove strategy

### 2.1 Command

```bash
python -m memorybox prove-historian-capture [--slice s1|s2|s3|s4|s5] [--flightsim]
```

### 2.2 Slice gates (align with MBRM-001B §8)

| Slice | Automated tests (representative) |
|-------|----------------------------------|
| **S1** | Campaign + multi-question; cadence config + follow-up interval stored separately; start/pause/resume/stop; fake send creates delivery + snapshot; **waiting → one reminder → no_response** harness (compressed timers); schema applies |
| **S2** | Fake inbound correlates by token; idempotent duplicate Message-ID; unmatched → quarantine; STOP → opt-out + send halt; raw uri + hash stored |
| **S3** | Review Draft versioning; source immutable; **four assessment labels** (separate from verdict); verdict retained/rejected/promotion_authorized |
| **S4** | Promote to Story; provenance chain; Ask attribution; **rejected** verdict excluded from affirmative Ask; thank-you sent with forbidden-content check |
| **S5** | Full harness A-01..A-12 mapping; `--flightsim` requires live creds (skip with clear message if absent) |

### 2.3 Regression suite

Keep green (non-exhaustive):

- `prove-i10a`, `prove-i10b`, `prove-i10c`, `prove-journal`  
- `prove-guided-capture` until deprecated (then alias)  
- `prove-i11` / `prove-i11a` smoke where applicable  

### 2.4 Prove output

JSON payload:

```json
{
  "ok": true,
  "slice": "s4",
  "criteria": { "C-01": true, "...": true },
  "flightsim": false,
  "email_provider": { "provider_key": "fake_historian_email", "live": false }
}
```

---

## 3. Detailed criteria IDs

| ID | Criterion | Maps to |
|----|-----------|---------|
| C-01 | Campaign CRUD + lifecycle states | A-01, A-10 |
| C-02 | Person-required respondent + confirmed email route | A-01 |
| C-03 | Question snapshot on send; later edit does not rewrite sent | A-02, A-03 |
| C-04 | One-at-a-time send per respondent | A-02 |
| C-05 | Inbound → Capture Item immutable | A-03, A-04 |
| C-06 | Attachment preservation + hash | A-04 |
| C-07 | Review Draft versions; source pane read-only | A-05 |
| C-08 | Owner assessment: High / Moderate / Low / Uncertain; private + history; **orthogonal to verdict** | A-06 |
| C-09 | Verdict: Keep in archive / Reject as evidence / Promote; required before promotion | A-07 |
| C-10 | Story promotion + provenance chain | A-08 |
| C-11 | Ask retrieval attribution + uncertainty | A-09 |
| C-12 | Pause/resume/stop/completed behavior | A-10 |
| C-13 | Duplicate inbound idempotent | A-10 |
| C-14 | Unmatched queue + resolution | A-10 |
| C-15 | No SQLite SoT | A-11 |
| C-16 | Regression: core MB proves pass | A-12 |
| C-17 | Follow-up interval separate from question cadence (daily/weekly/monthly/weekday/time) | A-13 |
| C-18 | Unanswered lifecycle: at most **one** reminder per delivery | A-13 |
| C-19 | After `no_response`, next question scheduled per question cadence only | A-13 |
| C-20 | STOP opt-out: audit row + `opted_out` respondent + cancelled pending sends | A-14 |
| C-21 | Thank-you after verdict: generic receipt only; automated leak guard | A-15 |

---

## 4. FlightSim live prove checklist (Tom)

When `--flightsim` authorized:

1. Confirm `memorybox@marvinbot.net` credentials configured (not in Git).  
2. Create campaign for a real MB Person (e.g. Peggy) with 3 questions.  
3. Start campaign; verify outbound in Sent.  
4. Reply from respondent email to each question (one at a time).  
5. Poll/tick ingest; verify Capture Items in inbox.  
6. Complete review → assessment → verdict → Story promotion.  
7. Ask: query that should cite promoted testimony; verify attribution.  
8. Test pause mid-campaign and unmatched reply (mis-subject).  
9. Leave one question unanswered through reminder → `no_response`; verify next question follows **cadence**, not follow-up interval.  
10. Reply `STOP` from respondent; verify opt-out audit and no further sends.  
11. Complete adjudication with thank-you enabled; verify ack body contains no assessment/verdict/draft/Story text.  

Record run id under `docs/test-output/historian-capture/` (implementation phase).

---

## 5. Open questions affecting acceptance

| # | Question | Default for prove design |
|---|----------|--------------------------|
| O3 | Story-only vs Story+Artifact in first acceptance | **Story-only** required; Artifact optional bonus |
| O7 | PoC data required? | **No** — fresh campaign only |
| O4 | Default follow-up interval | 72h before reminder; 72h after reminder before `no_response` (harness: 60s) |

---

## 6. Authorization boundary (this planning phase)

| Action | Done in planning commit? |
|--------|------------------------|
| Write acceptance doc | **Yes** |
| Implement `prove-historian-capture` | **No** |
| Run live email | **No** |
| FlightSim deploy | **No** |

---

**PLANNING LOCKED 2026-09-03. Await BUILD AUTHORIZATION.**
