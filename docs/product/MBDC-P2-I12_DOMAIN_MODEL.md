# MBDC-P2-I12 — Historian Collection Domain Model

**Status:** Planning **LOCKED** 2026-09-03 · **BUILD NOT AUTHORIZED**  
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

historian_capture_items (immutable inbound)
  ├── historian_capture_attachments
  ├── historian_capture_review_drafts (versioned)
  ├── historian_capture_verdicts
  ├── historian_capture_owner_assessments (history)
  └── historian_capture_promotions → stories | artifacts | evidence
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
| `cadence_seconds` | INT | Yes (draft/paused) | Default 86400 |
| `send_mode` | ENUM | Yes (draft) | `time_driven`, `wait_for_response` (V1 may ship time_driven only) |
| `timezone_name` | TEXT | Yes (draft) | |
| `provenance_json` | JSONB | Append | |
| `created_at` / `updated_at` | TIMESTAMPTZ | Auto | |

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
| `status` | ENUM | Yes | `active`, `removed` |
| `progress_json` | JSONB | Yes | Per-question sent/answered summary |

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
| `scheduled_for` | TIMESTAMPTZ | Yes while pending | |
| `sent_at` | TIMESTAMPTZ | Set once | |
| `status` | ENUM | Yes | `pending`, `sent`, `failed`, `cancelled` |
| `correlation_token` | TEXT | No | **UNIQUE** |
| `question_snapshot_text` | TEXT | No after send | Exact text sent |
| `question_snapshot_hash` | TEXT | No after send | SHA-256 of snapshot |
| `outbound_message_id` | TEXT | Set on send | Provider transport id |
| `thread_id` | TEXT | Set on send | |
| `preserved_outbound_raw_uri` | TEXT | Set on send | |
| `fail_detail` | TEXT | Yes on failure | |
| `retry_count` | INT | Yes | |
| `provenance_json` | JSONB | Append | |

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
| `assessment_code` | ENUM | No | See PRD O1 |
| `note_private` | TEXT | No | |
| `set_by` | TEXT | No | |
| `set_at` | TIMESTAMPTZ | No | |
| `supersedes_assessment_id` | UUID NULL | No | |

**Not** on contributor-visible fields. History is append-only.

### 3.10 `historian_capture_promotions`

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

### 3.11 `historian_capture_unmatched_queue` (optional view or table)

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

- `deliveries (status, scheduled_for)` — scheduler  
- `deliveries (correlation_token)` — inbound match  
- `capture_items (inbound_message_id)` partial unique  
- `capture_items (match_status, received_at DESC)` — inbox/quarantine  
- `review_drafts (capture_item_id, version)`  
- `promotions (promoted_type, promoted_id)`  

---

**PLANNING LOCKED 2026-09-03.**
