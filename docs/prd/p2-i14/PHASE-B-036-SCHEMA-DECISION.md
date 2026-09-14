# P2-I14 Phase B — schema decision (migration 036)

**Status:** SQL registered; contract checks 1–3 corrected. **Not applied.**  
**Date:** 2026-09-13  
**Branch:** `codex/p2-i14-communications`  
**File:** `memorybox/migrations/036_p2_i14_prepared_communications.sql`  
**Depends on:** migration **035** (unchanged).

## `scope_key`

**Exact value:** `household_email` only (`CHECK` + default).

It names the **source stream grain**, not a Person. Production has one prepared email generation per `comms_logical_sources` row whose `logical_key = household_email` and `source_kind = email`. Unique active generation is `(logical_source_id)` where `is_active`. There is no `person_id` on the generation table. A Person name or UUID cannot be stored as `scope_key`. Binding a calendar/SMS logical source raises `prepared_generation_must_use_household_email_source`.

Peggy and Sue were validation pilots. An email involving both exists **once**. `Show me Peggy` and `Show me Sue` reach it through `comms_prepared_participants.person_id`.

## Communication identity vs Person identity

| Id | Meaning |
| --- | --- |
| `canonical_record_id` | 035 communication identity → immutable `evidence`. Required on **every** message at activation. |
| `person_id` | Optional known MemoryBox participant. Unknown From/To/Cc stay `NULL`. Not required to prepare or publish. |

Activation treatment:

- Gallery-eligible, suppress-default, uncertain, and quality-flagged messages: all stored; all need `canonical_record_id`; Person Ask uses trusted participant links only.
- Voice: `voice_corpus` plus authenticated **From** `person_id` for any canonical MB Person in the household generation. To/Cc never qualifies authored voice. One generation; Ask/I11A select a Person by joining From `person_id`.
- Missing Person does not block publication.

## Activation

`comms_prepared_assert_generation_ready` runs **before** any supersede. Failure leaves the prior active generation unchanged.

## Participant and attachment rules

Exactly one From (unique index; missing From refused at activation). Unique `(message_id, role, lower(btrim(address)))`. Authenticated requires `person_id`; unverified forbids it. Attachments: `parent_evidence_id` = message original; `attachment_evidence_id` optional distinct row.

Prepared `cleaned_authored_text` / `forward_block` cannot contain `https?://`.


## Problem and success

Prepared email structure is proven on two Person packets but had no durable schema. 036 adds empty derived tables so a later, separately authorized apply can exist without loading family text.

Success: 035 then 036 apply on disposable PostgreSQL; evidence and 035 objects unchanged; uniqueness, participants, attachments, commercial/quality/voice, and atomic activation constraints hold; no seeds; no production DSN.

## Tables and constraints

| Object | Role | Integrity |
| --- | --- | --- |
| `comms_prepared_generations` | Immutable prepared build | `source_kind`/`scope_key` = email; starts `building` / unpublished / inactive; CHECK published+active only when `status = published` with logical source + checksum; unique active row per `(logical_source_id, scope_key)` |
| `comms_prepared_active_generations` | View | `is_active AND published AND status = published` only |
| `comms_prepared_threads` | Canonical thread | Unique `(generation_id, display_id)` and `(generation_id, thread_key)`; Gallery eligibility + suppression reason; founder-review state; provenance JSON |
| `comms_prepared_messages` | One evidence once per generation | `UNIQUE (generation_id, evidence_id)`; unique `(thread_id, ordinal)`; `evidence_id` and optional `canonical_record_id` `ON DELETE RESTRICT`; trigger requires `generation_id` to match the thread; `sent_at` timestamptz |
| `comms_prepared_participants` | From/To/Cc | Many people per message; authenticated rows require `person_id`; unverified forbids `person_id` |
| `comms_prepared_attachments` | Metadata only | Unique `(message_id, attachment_ordinal)`; `evidence_id` RESTRICT; disposition + `gallery_action` including `record_only` |
| `comms_prepared_activate_generation(uuid)` | Atomic publish | Validates, locks logical source, supersedes prior active, activates one generation |
| Guard triggers | No row-by-row publish | `published` / `is_active` / `status=published` only while the activate GUC is set |

No calendar/SMS tables. No `INSERT` seeds. 035 SQL bytes are not modified.

## Atomic publication

A generation is born unpublished and inactive. Load (later) writes child rows while `status` is `building` then `validated`. Gallery must read the active view, which is empty until activation.

`comms_prepared_activate_generation` runs in one transaction: prior active generation for that logical source/scope becomes `superseded` (unpublished, inactive); the new validated generation becomes the single `published` + `is_active` row. Failed generations stay unpublished. Direct `UPDATE`/`INSERT` of published/active flags raises `row_by_row_publication_forbidden`. Child tables have no publish flag.

## Pilot packet field → column mapping

| Packet / preview field | Schema |
| --- | --- |
| T-NNNN | `comms_prepared_threads.display_id` |
| MESSAGE n after UTC sort | `comms_prepared_messages.ordinal` (assigned after `sent_at`, tie-break `evidence_id`) |
| Evidence-ref T-NNNN-M-NN | `evidence_ref` |
| Immutable original | `evidence_id` → `evidence` (unchanged) |
| Cleaned authored text | `cleaned_authored_text` |
| Forward / relay / omitted duplicate | `forward_status`, `forward_omitted`, `forward_block` |
| Tracking URLs stripped | `urls_stripped` |
| Packet `commercial_retain` | `commercial_class = retain_life_evidence` |
| Packet `commercial_suppress` | `commercial_class = suppress_default` |
| Packet `commercial_uncertain` | `commercial_class = uncertain` |
| Packet `not_commercial` | `not_commercial` |
| Thread suppress-by-default | `gallery_eligibility = suppress_default` + `suppression_reason` |
| Voice corpus | `voice_corpus` (clean quote, resolved identity, authenticated From Person; schema token `authenticated_focal` means authenticated author, not one household focal) |
| Remaining quote risk | `quote_quality`, generated `quote_contamination_flagged` |
| From/To/Cc | `comms_prepared_participants.role` + `address_normalized` + `identity_confidence` + `person_id` |
| Attachment flags | `comms_prepared_attachments` metadata, not bytes |
| Accept / other marks | `founder_review_state` |
| 035 identity | optional `canonical_record_id` |

## Rollback

1. View `comms_prepared_active_generations`  
2. Function `comms_prepared_activate_generation`  
3. Trigger/function `comms_prepared_guard_activation`  
4. Trigger/function `comms_prepared_message_generation_guard`  
5. `comms_prepared_attachments`  
6. `comms_prepared_participants`  
7. `comms_prepared_messages`  
8. `comms_prepared_threads`  
9. `comms_prepared_generations`  

Never drop 001–035 or `evidence`.

## Out of this step

FlightSim apply, production `migrate`, prepared-row load, generation activation on production, Gallery, Ask, I11A, 035 changes, family seeds.
