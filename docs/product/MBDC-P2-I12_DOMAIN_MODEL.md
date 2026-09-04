# MBDC-P2-I12 — Historian Collection Domain Model

**Status:** **ACCEPTED** 2026-09-04 (Tom: “i12 is accepted”) · Definition **LOCKED** 2026-09-03 · **BUILD AUTHORIZED S1–S5** 2026-09-03  
**PRD:** [MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md](MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md)  
**Definition:** [MBBS-P2_INCREMENT_12_DEFINITION.md](MBBS-P2_INCREMENT_12_DEFINITION.md)

---

## 1. Design principles

1. **MemoryBox Postgres is authoritative** — no parallel SQLite SoT.  
2. **Inbound is immutable** — derived text is additive; raw bytes and headers are sacred.  
3. **Sent questions are snapshotted** — campaign edits never rewrite history.  
4. **People are canonical** — every respondent resolves to `people.id` before send.  
5. **Owner assessment is private** — separate column/table from contributor text and system confidence.  
6. **Promotion is explicit** — junction records preserve capture → draft → promoted object chain.

### Naming note (migration from I11 `guided_capture`)

Existing tables (`guided_capture_*`) are a **partial predecessor**. Build may:

- **Rename/evolve** to `historian_capture_*` in a new migration, or  
- **Extend** `guided_capture_*` with additive columns and new tables for Capture Items / Review Drafts / Verdicts.

This document uses **`historian_capture_*`** as the target logical model. Physical table names are an implementation choice documented in the build PR.

---

## 2. Entity relationship overview

```text
historian_capture_campaigns
  ├── historian_capture_campaign_respondents (N per campaign)
  │     └── people (FK, required)
  │     └── contact_route (confirmed email)
  ├── historian_capture_questions (ordered)
  └── historian_capture_deliveries (per respondent × question send)
        └── question_snapshot (immutable at send)
        └── waiting / reminder / no_response lifecycle

historian_capture_items (immutable inbound)
  ├── historian_capture_attachments
  ├── historian_capture_review_drafts (versioned)
  ├── historian_capture_verdicts
  ├── historian_capture_owner_assessments (history)
  ├── historian_capture_promotions → stories | artifacts | evidence
  ├── historian_capture_respondent_opt_outs (audit)
  └── historian_capture_thank_you_acknowledgments
```

---

## 3. Tables and fields

### 3.1 `historian_capture_campaigns`

| Field | Type | Mutable | Notes |
|-------|------|---------|-------|
| `id` | UUID PK | No | |
| `owner_person_id` | UUID FK → `people` | No after create | Tom |
| `title` | TEXT | Yes (draft only) | |
| `status` | ENUM | Yes | `draft`, `running`, `paused`, `stopped`, `completed` |
| `cadence_config_json` | JSONB | Yes (draft/paused) | Pattern: `daily` \| `weekly` \| `monthly` \| `weekdays`; `weekdays`: [0–6]; `send_time_local`: `HH:MM` |
| `follow_up_interval_seconds` | INT | Yes (draft/paused) | Wait before reminder and before `no_response` (separate from question cadence) |
| `send_thank_you_ack` | BOOL | Yes (draft) | Default **true** |
| `timezone_name` | TEXT | Yes (draft) | For cadence send time |
| `provenance_json` | JSONB | Append | |
| `created_at` / `updated_at` | TIMESTAMPTZ | Auto | |

**Deprecated for V1:** `cadence_seconds` alone — retain only for harness backward compat if needed; logical cadence is `cadence_config_json`.

**Uniqueness:** none beyond PK.

### 3.2 `historian_capture_campaign_respondents`

| Field | Type | Mutable | Notes |
|-------|------|---------|-------|
| `id` | UUID PK | No | |
| `campaign_id` | UUID FK | No | |
| `people_id` | UUID FK → `people` | No after confirm | **Required** |
| `display_name_snapshot` | TEXT | No after confirm | From Person at add time |
| `contact_route_kind` | TEXT | No after confirm | `email` in V1 |
| `contact_route_value` | TEXT | No after confirm | Confirmed address |
| `status` | ENUM | Yes | `active`, `removed`, `opted_out` |
| `opted_out_at` | TIMESTAMPTZ | Set once | When STOP processed or owner marks |
| `opt_out_inbound_message_id` | TEXT | Set once | Provenance |
| `opt_out_source` | ENUM | Set once | `respondent_stop`, `owner_manual` |
| `progress_json` | JSONB | Yes | Per-question sent/answered/no_response summary |

**Uniqueness:** `UNIQUE (campaign_id, people_id)` — one row per Person per campaign.

### 3.3 `historian_capture_questions`

| Field | Type | Mutable | Notes |
|-------|------|---------|-------|
| `id` | UUID PK | No | |
| `campaign_id` | UUID FK | No | |
| `body_text` | TEXT | Yes until first send | |
| `sort_order` | INT | Yes until first send | |
| `status` | ENUM | Yes | `active`, `skipped`, `cancelled` |
| `source` | TEXT | No | `owner_authored`, `starter_template` |

**Constraint:** no update to `body_text`/`sort_order` if any Delivery `sent` for this question.

### 3.4 `historian_capture_deliveries`

| Field | Type | Mutable | Notes |
|-------|------|---------|-------|
| `id` | UUID PK | No | |
| `campaign_id` | UUID FK | No | |
| `question_id` | UUID FK | No | |
| `campaign_respondent_id` | UUID FK | No | |
| `channel` | TEXT | No | `email` V1 |
| `scheduled_for` | TIMESTAMPTZ | Yes while pending | Next **question** send slot (cadence-driven) |
| `sent_at` | TIMESTAMPTZ | Set once | Initial question send |
| `status` | ENUM | Yes | See lifecycle below |
| `waiting_started_at` | TIMESTAMPTZ | Yes | Enter `waiting` after `sent` |
| `reminder_sent_at` | TIMESTAMPTZ | Set once | **At most one** reminder per delivery |
| `reminder_outbound_message_id` | TEXT | Set once | Reminder transport id |
| `no_response_at` | TIMESTAMPTZ | Set once | When declared `no_response` or `exhausted` |
| `follow_up_deadline_at` | TIMESTAMPTZ | Yes | Next timer fire (reminder or no_response) |
| `correlation_token` | TEXT | No | **UNIQUE** — same token for question + reminder thread |
| `question_snapshot_text` | TEXT | No after send | Exact text sent |
| `question_snapshot_hash` | TEXT | No after send | SHA-256 of snapshot |
| `outbound_message_id` | TEXT | Set on send | Provider transport id |
| `thread_id` | TEXT | Set on send | |
| `preserved_outbound_raw_uri` | TEXT | Set on send | |
| `fail_detail` | TEXT | Yes on failure | |
| `retry_count` | INT | Yes | |
| `provenance_json` | JSONB | Append | |

**Delivery `status` enum (V1):** `pending`, `sent`, `waiting`, `reminder_sent`, `answered`, `no_response`, `exhausted`, `failed`, `cancelled`.

**Lifecycle constraint:** `reminder_sent_at` IS NOT NULL implies at most one reminder; scheduler must not enqueue a second reminder for the same delivery.

**Uniqueness:** `UNIQUE (correlation_token)`; optional `UNIQUE (outbound_message_id)` where not null.

### 3.5 `historian_capture_items` (immutable inbound)

| Field | Type | Mutable | Notes |
|-------|------|---------|-------|
| `id` | UUID PK | No | |
| `campaign_id` | UUID FK NULL | No | Null if unmatched until resolved |
| `question_id` | UUID FK NULL | No | |
| `delivery_id` | UUID FK NULL | No | |
| `campaign_respondent_id` | UUID FK NULL | No | |
| `channel` | ENUM | No | `email_text` V1 |
| `received_at` | TIMESTAMPTZ | No | |
| `inbound_message_id` | TEXT | No | **UNIQUE** when present |
| `from_address` | TEXT | No | |
| `subject` | TEXT | No | |
| `preserved_raw_uri` | TEXT | No | Authoritative .eml |
| `content_hash` | TEXT | No | SHA-256 of raw |
| `header_json` | JSONB | No | Transport headers |
| `extracted_text` | TEXT | No | Derived; not authoritative over raw |
| `match_status` | ENUM | Yes | `matched`, `unmatched`, `ambiguous`, `resolved` |
| `provenance_json` | JSONB | Append | |

**Immutability:** no UPDATE to `preserved_raw_uri`, `content_hash`, `extracted_text`, `header_json`, `inbound_message_id` after insert.

### 3.6 `historian_capture_attachments`

| Field | Type | Mutable | Notes |
|-------|------|---------|-------|
| `id` | UUID PK | No | |
| `capture_item_id` | UUID FK | No | |
| `filename` | TEXT | No | |
| `mime_type` | TEXT | No | |
| `storage_uri` | TEXT | No | |
| `sha256` | TEXT | No | |
| `size_bytes` | BIGINT | No | |

### 3.7 `historian_capture_review_drafts`

| Field | Type | Mutable | Notes |
|-------|------|---------|-------|
| `id` | UUID PK | No | |
| `capture_item_id` | UUID FK | No | |
| `version` | INT | No | Monotonic per item |
| `is_current` | BOOL | Yes | Only one true per item |
| `body_text` | TEXT | Yes while current | Owner-edited working text |
| `notes_private` | TEXT | Yes while current | Owner context |
| `proposed_links_json` | JSONB | Yes while current | People, places, Stories |
| `created_by` | TEXT | No | `owner` |
| `created_at` | TIMESTAMPTZ | No | |
| `supersedes_draft_id` | UUID NULL | No | Prior version |

**Uniqueness:** `UNIQUE (capture_item_id, version)`.

### 3.8 `historian_capture_verdicts`

| Field | Type | Mutable | Notes |
|-------|------|---------|-------|
| `id` | UUID PK | No | |
| `capture_item_id` | UUID FK | No | |
| `review_draft_id` | UUID FK | No | Draft verdict applies to |
| `verdict` | ENUM | Yes | `retained`, `rejected`, `promotion_authorized` |
| `decided_by` | TEXT | No | `owner` |
| `decided_at` | TIMESTAMPTZ | No | |
| `supersedes_verdict_id` | UUID NULL | No | Reversible verdicts |

Latest verdict wins for Ask eligibility rules.

### 3.9 `historian_capture_owner_assessments`

| Field | Type | Mutable | Notes |
|-------|------|---------|-------|
| `id` | UUID PK | No | |
| `capture_item_id` | UUID FK | No | |
| `assessment_code` | ENUM | No | `high_confidence`, `moderate_confidence`, `low_confidence`, `uncertain` (plus internal `not_rated` before first save) |
| `note_private` | TEXT | No | |
| `set_by` | TEXT | No | |
| `set_at` | TIMESTAMPTZ | No | |
| `supersedes_assessment_id` | UUID NULL | No | |

**Not** on contributor-visible fields. History is append-only.

**Not** on contributor-visible fields. History is append-only. **Orthogonal to verdict** — store separately.

### 3.10 `historian_capture_respondent_opt_outs` (audit)

Append-only log when respondent STOP detected or owner marks opt-out.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `campaign_respondent_id` | UUID FK | |
| `capture_item_id` | UUID FK NULL | Inbound STOP message if preserved |
| `keyword_matched` | TEXT | e.g. `STOP` |
| `recorded_at` | TIMESTAMPTZ | |
| `source` | ENUM | `respondent_stop`, `owner_manual` |
| `provenance_json` | JSONB | Raw headers snippet, actor |

Setting opt-out updates `campaign_respondents.status = opted_out` and cancels pending/waiting deliveries for that respondent.

### 3.11 `historian_capture_thank_you_acknowledgments`

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID PK | |
| `capture_item_id` | UUID FK | |
| `verdict_id` | UUID FK | Sent after this verdict |
| `campaign_respondent_id` | UUID FK | Must not be `opted_out` |
| `sent_at` | TIMESTAMPTZ | |
| `outbound_message_id` | TEXT | |
| `body_snapshot` | TEXT | Exact sent text (audit) |
| `preserved_outbound_raw_uri` | TEXT | |
| `skipped_reason` | TEXT NULL | e.g. `opted_out`, `disabled`, `forbidden_content` |

**Forbidden in `body_snapshot`:** assessment codes/labels, rejection rationale, Review Draft text, promoted Story text.

### 3.12 `historian_capture_promotions`

| Field | Type | Mutable | Notes |
|-------|------|---------|-------|
| `id` | UUID PK | No | |
| `capture_item_id` | UUID FK | No | |
| `review_draft_id` | UUID FK | No | |
| `verdict_id` | UUID FK | No | |
| `promoted_type` | ENUM | No | `story`, `artifact`, `accepted_evidence` |
| `promoted_id` | UUID | No | Target row id |
| `promoted_at` | TIMESTAMPTZ | No | |
| `promoted_by` | TEXT | No | |
| `provenance_json` | JSONB | No | Full chain |

**Uniqueness:** allow multiple promotions only if founder later authorizes split promotions; V1 default **one primary promotion per Capture Item**.

### 3.13 `historian_capture_unmatched_queue` (optional view or table)

May be implemented as `capture_items WHERE match_status IN ('unmatched','ambiguous')` plus resolution audit log.

| Field | Notes |
|-------|-------|
| `resolution_action` | `link_delivery`, `dismiss`, `create_ad_hoc` |
| `resolved_by` / `resolved_at` | Owner audit |

---

## 4. Identifiers and idempotency

| Key | Scope | Rule |
|-----|-------|------|
| `correlation_token` | Global | Unique; hex token in subject |
| `inbound_message_id` | Global | Unique; duplicate poll → skip |
| `outbound_message_id` | Provider | Unique when present |
| `content_hash` | Per item | Detect byte-identical re-upload (warn, don't duplicate) |

---

## 5. Mapping from I11 `guided_capture_*` (current repo)

| Current | Target | Action |
|---------|--------|--------|
| `guided_capture_contacts` | `campaign_respondents` + `people` | **Replace** — require Person FK; drop free-floating contact as authority |
| `guided_capture_campaigns` | `historian_capture_campaigns` | **Adapt** — multi-respondent |
| `guided_capture_questions` | `historian_capture_questions` | **Retain** shape |
| `guided_capture_deliveries` | `historian_capture_deliveries` | **Extend** — add `question_snapshot_*`, per-respondent FK |
| `guided_capture_responses` | Split → `capture_items` + `review_drafts` + `verdicts` + `assessments` | **Replace** semantics |
| `credibility` on response | `owner_assessments` history | **Move** |
| `review_status` | `verdict` + inbox UI state | **Replace** |
| `resulting_knowledge_json` | `promotions` | **Replace** |

---

## 6. Indexes (minimum)

- `deliveries (status, follow_up_deadline_at)` — waiting/reminder scheduler  
- `deliveries (status, scheduled_for)` — question cadence scheduler  
- `deliveries (correlation_token)` — inbound match  
- `capture_items (inbound_message_id)` partial unique  
- `capture_items (match_status, received_at DESC)` — inbox/quarantine  
- `review_drafts (capture_item_id, version)`  
- `promotions (promoted_type, promoted_id)`  

---

**PLANNING LOCKED 2026-09-03.**
