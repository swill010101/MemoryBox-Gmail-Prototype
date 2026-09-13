# P2-I14 Phase B — schema decision (candidate 036)

**Status:** Product request + proposed SQL. **Not a migration file.** Not applied.  
**Date:** 2026-09-13  
**Branch:** `codex/p2-i14-communications`  
**Proposed SQL:** [036_p2_i14_prepared_communications.proposed.sql](036_p2_i14_prepared_communications.proposed.sql)  
**Depends on:** migration **035** (lineage tables exist, empty on FlightSim).  
**Gates complete:** Person Pilot 1 packet accepted; Person Pilot 2 (Sue) packet accepted 12/12.

This is the product request for **empty prepared-email tables only**. Show this PRD and get explicit sign-off before moving the SQL into `memorybox/migrations/` or running `migrate`.

## Problem being solved and why it matters now

Visual review proved the reconstruction rules on two Persons. Those rules still live only in preview code. There is no durable store for cleaned authored text, chronological ordinals, commercial class, or Evidence-ref linkage. Ask/Gallery cannot consume a published generation until that store exists.

It matters now because both Person pilots are accepted. The next honest step is an additive derived schema that can hold the same structure the packets already display — without loading family text yet.

## Success criteria

1. Proposed SQL creates five empty `comms_prepared_*` tables, additive only, with `evidence_id` `ON DELETE RESTRICT`.
2. `published` defaults to false. A CHECK forbids `published = true` unless `status = 'published'`.
3. Each evidence row appears at most once per generation (`UNIQUE (generation_id, evidence_id)`).
4. Display ordinals are unique per thread and are not a substitute for `sent_at`.
5. SQL is **not** registered under `memorybox/migrations/` until founder authorizes promotion.
6. Tests prove the SQL contract without using database `memorybox`.
7. No prepared rows, logical-source seeds, Gallery changes, or I11A runs.

## Scope

### In

- Email prepared generation / thread / message / participant / attachment tables.
- Integrity that encodes T-0001 / T-1265 locks (UTC `sent_at`, one evidence once, cleaned text column distinct from originals, commercial class, forward-omission reason, URL-stripped flag).
- Static tests; optional disposable-Postgres apply of 001 + 035 + proposed 036.

### Out

- Putting 036 into `memorybox/migrations/` or applying it on Desktop/FlightSim.
- Inserting reconstructed corpus rows (Peggy, Sue, or household).
- Calendar prepared events (RRULE / revision grain still unlocked).
- SMS prepared episodes.
- Seed of `household_email` / memberships / identity backfill.
- Ask/Gallery product changes.
- Changing 035 SQL bytes.
- Publishing a generation.

## Constraints

| Constraint | Detail |
| --- | --- |
| Immutable originals | `evidence` is never updated or deleted by 036. Prepared text is a derived copy. |
| Evidence FK | `ON DELETE RESTRICT`. No `SET NULL`. |
| Prefix | `comms_prepared_*` to match 035 `comms_*`. |
| Email only | `source_kind = 'email'`. |
| Logical source | `logical_source_id` nullable until production seed. |
| Rebuild | Child rows `ON DELETE CASCADE` from generation so a failed build can be dropped. Evidence is not cascaded. |
| Privacy | SQL comments and git tests contain no bodies, addresses, or tracking URLs. |
| Health | Until promotion, FlightSim `migrate` pending list must not include 036. |

## Timestamp and commercial rules (locked from pilots)

- Authoritative time: payload `sent_at` stored as `timestamptz` (UTC instant). Tie-break at load time is `evidence_id`. Display numbers assigned only after that sort.
- `commercial_class`: `not_commercial` / `commercial_retain` / `commercial_suppress` / `commercial_uncertain`.
- Thread `gallery_eligibility`: `show_by_default` / `suppress_default` / `hold_uncertain`.
- Prepared text must not store live tracking/account/unsubscribe/legal URLs; `urls_stripped` records that sanitization ran.
- Duplicate commercial/relay bodies already present in the same thread are not stored in `cleaned_authored_text` or `forward_block`; `forward_omitted` records the reason.
- Human wrapper text may be stored in `cleaned_authored_text`.

## Original vs forward (locked)

Preserve both immutable originals when an original commercial message and a human forward both exist. Do not collapse distinct human-authored messages. Duplicate detection at load time is normalized ≥80-character overlap with an earlier message in the same canonical thread — not subject equality.

## Open questions for Tom

| ID | Question | Recommendation |
| --- | --- | --- |
| Q-036-promote | Move proposed SQL into `memorybox/migrations/036_p2_i14_prepared_communications.sql` and allow a later empty-table apply? | Yes, after this PRD sign-off. Separate apply authorization, like 035. |
| Q-036-load | After empty tables exist, load Peggy + Sue (or full household email) prepared rows with `published = false`? | **Separate** authorization. Not this PRD. |
| Q-036-publish | Set `published = true` and show comms in Gallery? | **Separate** authorization after load validation. |
| Q-036-sms-cal | Include SMS/calendar tables now? | **No.** Calendar revision grain unlocked; SMS not in these packets. |

## Rollback (after a future apply)

1. `comms_prepared_attachments`
2. `comms_prepared_participants`
3. `comms_prepared_messages`
4. `comms_prepared_threads`
5. `comms_prepared_generations`

Never drop 001–035 or `evidence`.
