# MBPRD-P2-I12 — Historian Collection & Campaigns V1

**Status:** PRD **LOCKED FOR PLANNING** 2026-09-03 · **BUILD AUTHORIZED S1–S5** 2026-09-03  
**Definition:** [MBBS-P2_INCREMENT_12_DEFINITION.md](MBBS-P2_INCREMENT_12_DEFINITION.md)  
**Roadmap:** [MBRM-001B](MBRM-001B_P2_HISTORIAN_COLLECTION_AND_CAMPAIGNS.md)  
**Domain:** [MBDC-P2-I12_DOMAIN_MODEL.md](MBDC-P2-I12_DOMAIN_MODEL.md)  
**Screens:** [MBSC-P2-I12_HISTORIAN_COLLECTION_SCREEN_CONTRACT.md](MBSC-P2-I12_HISTORIAN_COLLECTION_SCREEN_CONTRACT.md)  
**Acceptance:** [MBAT-P2-I12_ACCEPTANCE.md](MBAT-P2-I12_ACCEPTANCE.md)

---

## 1. Problem and outcome

### Problem

Family history often lives in the memories of living relatives. The owner needs a **controlled, provenance-preserving** way to ask known people specific questions, receive their replies exactly as sent, privately assess reliability, and **deliberately** fold accepted testimony into MemoryBox — without treating email as immediate truth or maintaining a separate capture application.

### Outcome (V1)

Tom can run an email-based historian campaign for canonical MB People, receive immutable inbound evidence, review and assess it in MemoryBox, and optionally promote accepted material into Stories (and optionally Artifacts/evidence) with full attribution — while Ask can cite promoted testimony with uncertainty and source separation.

### Success criteria

1. End-to-end campaign → send → reply → review → verdict → optional promotion on FlightSim without SQL intervention ([MBAT-P2-I12](MBAT-P2-I12_ACCEPTANCE.md)).  
2. Inbound source never rewritten after receipt.  
3. MemoryBox Postgres is the **sole authoritative** store (PoC SQLite not a second SoT).  
4. Existing MemoryBox functionality remains operational.

---

## 2. Scope and exclusions

See [definition §V1 scope](MBBS-P2_INCREMENT_12_DEFINITION.md).

---

## 3. Lifecycle and state machines

### 3.1 Campaign state machine

```text
draft ──start──► running ◄──resume── paused
  │                 │
  │                 ├──pause──► paused
  │                 ├──stop──► stopped (terminal for sends)
  │                 └──all questions sent & no pending──► completed
  │
  └──(edit questions/respondents while draft only)
```

| State | Sends allowed | Edits allowed |
|-------|---------------|---------------|
| `draft` | No | Campaign metadata, respondents, question order/text |
| `running` | Yes (scheduler) | Add questions only if not yet sent; no rewrite of sent snapshots |
| `paused` | No | Same as running except scheduler frozen |
| `stopped` | No | Read-only for outbound; inbound still accepted |
| `completed` | No | Read-only outbound; inbound still accepted |

`exhausted` may alias `completed` in UI copy; canonical status = `completed`.

### 3.2 Cadence vs response follow-up (founder lock)

Two **independent** timing controls:

| Control | Purpose | V1 configurability |
|---------|---------|-------------------|
| **Question cadence** | When the **next question** may be sent after the prior question cycle completes | Daily · weekly · monthly · weekday-specific · selected send time (campaign timezone) |
| **Response follow-up interval** | How long to wait for an answer **before** reminder and before declaring no-response | Configurable per campaign (separate from question cadence) |

`cadence_seconds` alone is **insufficient** — store structured `cadence_config_json` (pattern + weekdays + local send time) and `follow_up_interval_seconds` (or equivalent) as distinct fields.

### 3.3 Per-respondent unanswered-question lifecycle (founder lock)

Each **Delivery** (one question × one respondent) follows this **required V1** lifecycle when no Capture Item arrives:

```text
pending → sent → waiting
              → (follow_up_interval elapses, no reply)
              → reminder_sent  [exactly one friendly reminder — never more than one]
              → waiting
              → (follow_up_interval elapses again, no reply)
              → no_response / exhausted
              → schedule next question per question cadence
```

Rules:

1. **Never send more than one reminder** per question per respondent.  
2. If a Capture Item arrives during `waiting` (before or after reminder), transition to `answered` and **do not** send reminder or mark `no_response`.  
3. Late replies after `no_response` still create immutable Capture Items (linked to delivery); they do **not** rewind outbound cadence automatically.  
4. **Opted-out** respondents skip all future sends (§3.8).  
5. Campaign **pause** freezes timers; **resume** continues from frozen state.

### 3.4 Delivery state machine

```text
pending → sent → waiting ⇄ (one reminder) → waiting → no_response | exhausted
pending → failed → (owner retry) → pending
pending | waiting → cancelled (campaign stop / skip / opt-out)
waiting | reminder_sent → answered (Capture Item received)
```

Canonical terminal outcomes per delivery: `answered`, `no_response`, `exhausted`, `cancelled`, `failed`.

### 3.5 Capture Item

```text
received → (immutable; no state mutation of source fields)
         → linked Review Drafts
         → verdict applied
```

Holding states for unmatched inbound:

- `unmatched` — no correlation  
- `ambiguous` — multiple candidate deliveries  
- `resolved` — owner linked to delivery/campaign  

### 3.6 Review Draft

```text
draft_v1 → draft_v2 → … → current_proposed
```

Immutable link to `capture_item_id`. Only one `is_current` per Capture Item.

### 3.7 Owner assessment vs verdict (founder lock)

**Owner assessment** (private qualitative confidence) and **verdict** (disposition) are **separate** controls. Either may be set without the other, but promotion requires both assessment (recommended) and verdict.

#### Owner assessment (locked labels)

| UI label | Code | Notes |
|----------|------|-------|
| **High confidence** | `high_confidence` | Private to owner |
| **Moderate confidence** | `moderate_confidence` | |
| **Low confidence** | `low_confidence` | |
| **Uncertain** | `uncertain` | |

Not rated is a UI default before first save (`not_rated` internal only). Assessment is **never** sent to the contributor.

#### Verdict (locked labels)

| UI label | Code |
|----------|------|
| **Keep in archive** | `retained` |
| **Reject as evidence** | `rejected` |
| **Promote to MemoryBox** | `promotion_authorized` |

```text
none → retained | rejected | promotion_authorized
```

`promotion_authorized` does not itself create knowledge objects; owner completes promotion action separately (may be same UI step with confirmation). **Reject as evidence** blocks affirmative Ask/narration use regardless of assessment.

### 3.8 Respondent STOP / opt-out (founder lock)

Respondents may opt out via inbound **STOP** (subject/body keyword per adapter rules, case-insensitive).

| Behavior | Rule |
|----------|------|
| Detection | Inbound poll classifies STOP; creates audit row + Capture Item if needed |
| Provenance | Log `opted_out_at`, `opt_out_inbound_message_id`, matched keyword, respondent Person |
| Sends | **No further question or reminder** emails to that **campaign respondent** |
| Campaign | Other respondents continue unless they also opt out |
| Owner | HC-05 shows opted-out badge; owner may manually mark opt-out from UI with audit |

### 3.9 Thank-you acknowledgment (founder lock)

After owner records a **verdict**, MemoryBox may send an optional **thank-you** email to the respondent.

| Rule | Detail |
|------|--------|
| Default | **On** per campaign (`send_thank_you_ack` default true); owner may disable |
| Allowed content | Thank you; response received/preserved |
| **Forbidden** | Private owner assessment · rejection rationale · Review Draft edits · promoted Story wording |
| Timing | After verdict saved; one ack per Capture Item unless owner resends manually (out of V1) |
| Opt-out | Never send thank-you to opted-out respondents |

### 3.10 Promotion

```text
promotion_authorized → promoted (Story | Artifact | accepted_evidence)
```

Failure rolls back promotion row only; Capture Item and drafts remain.

---

## 4. Data contracts (summary)

Full schema: [MBDC-P2-I12_DOMAIN_MODEL.md](MBDC-P2-I12_DOMAIN_MODEL.md).

### 4.1 Correlation

- Outbound subject includes `[MB-HC-<token>]` (proposed; aligns with existing `[MB-GC-…]` harness pattern)  
- `historian_capture_deliveries.correlation_token` UNIQUE  
- Optional `Reply-To` on dedicated mailbox — **not** required to use plus-address routing in V1  
- Inbound match order: transport `Message-ID` dedupe → correlation token → thread/In-Reply-To (secondary) → quarantine  

### 4.2 Question snapshot

On send, persist `question_snapshot_text` (+ optional `question_snapshot_hash`) on Delivery. Campaign question row may later change; snapshot is what was sent.

### 4.3 Immutability rules

| Entity | Immutable after create |
|--------|------------------------|
| Capture Item `raw_*`, `inbound_message_id`, `received_at`, hashes | Yes |
| Capture Attachment bytes | Yes |
| Delivery `question_snapshot_*`, `sent_at`, outbound ids | Yes after `sent` |
| Review Draft prior versions | Yes |
| Owner assessment history entries | Append-only |
| Promoted object content | Governed by target type (Story revisions); link to capture provenance immutable |

### 4.4 Owner assessment contract

```json
{
  "assessment_code": "moderate_confidence",
  "note_private": "optional owner note",
  "set_by": "owner",
  "set_at": "ISO-8601",
  "supersedes": "prior assessment id or null"
}
```

Allowed `assessment_code` values: `not_rated` (internal pre-save only), `high_confidence`, `moderate_confidence`, `low_confidence`, `uncertain`.

Not exposed to contributor or thank-you email. Narration may reference assessment category with uncertainty framing.

### 4.5 Thank-you acknowledgment contract

```json
{
  "capture_item_id": "uuid",
  "verdict_id": "uuid",
  "sent_at": "ISO-8601",
  "outbound_message_id": "provider-id",
  "body_snapshot": "exact sent text",
  "preserved_outbound_raw_uri": "file://..."
}
```

Body template is system-controlled; must pass automated forbidden-content checks (no assessment, verdict rationale, or draft/Story text).

---

## 5. Provenance and immutability

- Every Capture Item stores `preserved_raw_uri`, `content_hash`, `header_json`, `provenance_json`  
- Attachments stored with `storage_uri`, `mime_type`, `sha256`  
- Promotion records: `capture_item_id`, `review_draft_id`, `promoted_type`, `promoted_id`, `promoted_at`, `promoted_by`  
- Ask citation shape: respondent name, campaign/question context, owner assessment, “human testimony” flag, link to immutable source  

---

## 6. Promotion behavior

| Target | When | Rules |
|--------|------|-------|
| **Story** | Owner selects Story promotion | New Story or append to existing; narrator = respondent Person; owner = editor/creator; body from current Review Draft |
| **Artifact** | Owner selects Artifact promotion | When reply references or attaches object-worthy content; representation + optional transcript |
| **Accepted evidence** | Owner selects evidence promotion | When testimony should inform correlation without full Story shape |

**V1 minimum:** Story promotion required for acceptance. Artifact/evidence promotion = **open question** (§12).

No auto-promotion on inbound. Verdict `rejected` blocks affirmative evidence use in Ask/narration (assessment alone does not).

---

## 7. Security and privacy

- Single owner; no contributor login  
- Credentials for `memorybox@marvinbot.net` and Gmail integration: env/files outside Git  
- Private owner assessment never in outbound email (including thank-you acknowledgments)  
- Raw mail storage path not web-public  
- FlightSim prove uses real mailbox only when explicitly configured; harness uses fake adapter  
- No silent person creation from inbound From: address — reconcile in UI  

---

## 8. Failure and recovery

| Failure | Behavior |
|---------|----------|
| Outbound send failure | Delivery `failed` + `fail_detail`; owner retry |
| Inbound poll failure | Log; Archive Health / owner notification (hook); no data loss |
| Unmatched reply | Quarantine queue; owner manual link or dismiss |
| Duplicate Message-ID | Idempotent skip; no second Capture Item |
| Promotion failure | Transaction rollback on promotion row; capture/draft intact |
| Scheduler crash | Pending deliveries remain; tick resumes; waiting timers recover from stored deadlines |
| Duplicate reminder attempt | Block second reminder; log provenance |
| STOP received | Opt-out respondent; cancel pending/waiting deliveries for that respondent |
| Thank-you template leak | Block send; surface error to owner |
| Migration replay | Idempotent on transport ids ([MBMP-P2-I12](MBMP-P2-I12_MIGRATION_REPLAY.md)) |

---

## 9. Integration summary

See [MBAS-P2-I12_INTEGRATION_MAP.md](MBAS-P2-I12_INTEGRATION_MAP.md).

---

## 10. PoC reuse summary

See [MBAS-P2-I12_POC_REUSE_MATRIX.md](MBAS-P2-I12_POC_REUSE_MATRIX.md).

---

## 11. Migration summary

See [MBMP-P2-I12_MIGRATION_REPLAY.md](MBMP-P2-I12_MIGRATION_REPLAY.md).

---

## 12. Founder decisions locked (2026-09-03)

| Topic | Decision |
|-------|----------|
| Question cadence vs follow-up | **Separate** controls; see §3.2–3.3 |
| Unanswered lifecycle | `sent → waiting → one reminder → waiting → no_response/exhausted → next question` |
| Reminder cap | **One** friendly reminder per question — never more |
| Cadence patterns | Daily · weekly · monthly · weekday-specific · selected send time |
| Owner assessment | **High confidence** · **Moderate confidence** · **Low confidence** · **Uncertain** (separate from verdict) |
| Verdict | **Keep in archive** · **Reject as evidence** · **Promote to MemoryBox** |
| STOP / opt-out | Logged provenance; no further sends to that respondent |
| Thank-you ack | Optional/default on after adjudication; never leak assessment, rejection rationale, or draft/Story text |

## 13. Open questions for Tom

**Founder decisions locked 2026-09-03 (BUILD AUTHORIZED S1–S4):**

| # | Decision |
|---|----------|
| O3 | Story promotion **required** in S4; Artifact promotion **deferred** to S5 |
| O4 | Default follow-up interval **72 hours** (reminder after first 72h; no-response after second 72h) |
| O5 | Partial/multi-question replies = **one immutable Capture Item**; owner may split Review Drafts manually |
| O6 | Unmatched inbound surfaces in **Capture Review inbox / Needs Attention** first; Archive Health secondary |
| O7 | MarvinCapture PoC data **not required** for V1 acceptance — fresh MB-native campaigns |
| O8 | Family communications ingestion **separate**; I12 uses dedicated Historian Capture mailbox path only |

## 14. Build authorization gate

S1–S4 **BUILD AUTHORIZED** 2026-09-03 on branch `cursor/p2-i12-s1-s4-implementation-7f27`.

S5 **BUILD AUTHORIZED** 2026-09-03 — live Historian Capture Gmail adapter (`memorybox@marvinbot.net`), Artifact promotion, Archive Health unmatched integration, staged `--flightsim` prove (Stage 1 connection → Stage 2 single round-trip → Stage 3 acceptance campaign). MarvinCapture SQLite replay remains optional/deferred.

FlightSim prove:

```bash
export MEMORYBOX_P1_RUNTIME_HOST=1
export MEMORYBOX_HC_GMAIL_CREDENTIALS=config/historian_capture_gmail_credentials.json
export MEMORYBOX_HC_GMAIL_TOKEN=config/historian_capture_gmail_token.json
export MEMORYBOX_HC_USER_EMAIL=memorybox@marvinbot.net
# Stage 1 only:
python3 -m memorybox prove-historian-capture --flightsim --slice s5
# Stage 2 (after Stage 1 passes):
export MEMORYBOX_HC_FLIGHTSIM_STAGE=2
export MEMORYBOX_HC_FLIGHTSIM_RECIPIENT=tom@example.com
python3 -m memorybox prove-historian-capture --flightsim --slice s5
# Stage 3 (after Stage 2 passes):
export MEMORYBOX_HC_FLIGHTSIM_STAGE=3
python3 -m memorybox prove-historian-capture --flightsim --slice s5
```

---

**PLANNING LOCKED 2026-09-03 · S5 BUILD AUTHORIZED 2026-09-03.**
