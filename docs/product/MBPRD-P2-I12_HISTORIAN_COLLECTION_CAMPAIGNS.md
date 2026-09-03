# MBPRD-P2-I12 — Historian Collection & Campaigns V1

**Status:** PRD **LOCKED FOR PLANNING** 2026-09-03 · **BUILD NOT AUTHORIZED**  
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

### 3.2 Per-respondent question cycle

Each **Campaign Respondent** tracks independent progress:

```text
for each active question in sort_order:
  schedule Delivery (pending)
    → send (sent | failed)
    → await Capture Item (optional; late replies OK)
    → advance to next question on cadence policy
```

V1 default cadence: **time-driven** (existing `guided_capture` pattern) — one question per interval per respondent unless founder selects wait-for-response mode (open question).

### 3.3 Delivery state machine

```text
pending → sent
pending → failed → (owner retry) → pending
pending → cancelled (campaign stop/skip)
```

### 3.4 Capture Item

```text
received → (immutable; no state mutation of source fields)
         → linked Review Drafts
         → verdict applied
```

Holding states for unmatched inbound:

- `unmatched` — no correlation  
- `ambiguous` — multiple candidate deliveries  
- `resolved` — owner linked to delivery/campaign  

### 3.5 Review Draft

```text
draft_v1 → draft_v2 → … → current_proposed
```

Immutable link to `capture_item_id`. Only one `is_current` per Capture Item.

### 3.6 Verdict

```text
none → retained | rejected | promotion_authorized
```

`promotion_authorized` does not itself create knowledge objects; owner completes promotion action separately (may be same UI step with confirmation).

### 3.7 Promotion

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
  "assessment_code": "generally_trust",
  "note_private": "optional owner note",
  "set_by": "owner",
  "set_at": "ISO-8601",
  "supersedes": "prior assessment id or null"
}
```

Not exposed to contributor. Narration may reference assessment category with uncertainty framing.

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

No auto-promotion on inbound. `believe_incorrect` blocks affirmative evidence use in Ask/narration.

---

## 7. Security and privacy

- Single owner; no contributor login  
- Credentials for `memorybox@marvinbot.net` and Gmail integration: env/files outside Git  
- Private owner assessment never in outbound email  
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
| Scheduler crash | Pending deliveries remain; tick resumes |
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

## 12. Open questions for Tom

| # | Question | Recommendation | Tradeoff |
|---|----------|----------------|----------|
| O1 | **Final V1 assessment labels** | Adopt existing `guided_capture` six-value set: `not_rated`, `trust_strongly`, `generally_trust`, `uncertain`, `doubt`, `believe_incorrect` | Familiar from I11 partial build; rename to “owner assessment” in UI |
| O2 | **Final verdict labels** | UI: **Keep in archive** · **Reject as evidence** · **Promote to MemoryBox** (confirm subtype) | Clear verbs; map to `retained` / `rejected` / `promotion_authorized` |
| O3 | **Promotion scope in first build slice** | **Story only** in S4; Artifact/evidence in S5 if needed | Faster acceptance; Artifact path needs I10B wiring |
| O4 | **Default cadence and resend policy** | 24h cadence (configurable); failed send manual retry only; no auto-resend of same question | Simple; avoids spam |
| O5 | **Partial / multi-question replies** | Single Capture Item; owner may split into multiple Review Drafts manually in V1 | Auto-split is V2 |
| O6 | **Unmatched failure surfacing** | Review inbox badge + Archive Health row “Capture unmatched (N)” | Needs I2 hook — can ship inbox-only in S2 |
| O7 | **PoC data required for V1 acceptance?** | **No** — acceptance uses fresh FlightSim campaign; PoC replay optional | Replay proves migration only |
| O8 | **Optimized communications ingestion placement** | Ingestion/backfill stays with P2-I6 decision ([2026-09-03 comms ADR](../decisions/2026-09-03-comms-preparation-and-unified-gallery.md)); I12 uses **Capture mailbox path** only, not family mbox rewrite | Avoid blocking I12 on Gallery/comms backfill |

---

## 13. Build authorization gate

This PRD does **not** authorize implementation. Required before build:

1. Tom sign-off on open questions (or defaults accepted).  
2. Explicit **BUILD AUTHORIZED** message for P2-I12 (whole or per slice).  
3. FlightSim credential readiness for `memorybox@marvinbot.net` (when live prove required).

---

**PLANNING LOCKED 2026-09-03.**
