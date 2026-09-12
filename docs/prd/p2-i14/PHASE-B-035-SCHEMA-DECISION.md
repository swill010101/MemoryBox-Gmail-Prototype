# P2-I14 Phase B — schema decision (migration 035)

**Status:** Revised for founder schema review. **Not applied** to Desktop or FlightSim.  
**Date:** 2026-09-11  
**Branch:** `codex/p2-i14-communications`  
**Base:** `db2cc463143941e24f2bc1bb5401d1cc2fe895dd`  
**File:** `memorybox/migrations/035_p2_i14_communications_lineage.sql`

## Founder locks

- Next number is **035**. FlightSim **001–034** applied; **025–029 remain**.
- Do not replay, renumber, retire, or modify 025–029.
- Never apply `025_historian_capture_i12.sql` as version 025.
- Reuse `person_contact_points.retrieval_trust` and `communication_rfc_ids`. Do not duplicate them.
- Four layers: logical source, extract instance, immutable record, prepared generation (generation store deferred).
- **Duplicate-count audit** of live evidence (`QueryCanceled` on FlightSim) does **not** block this additive schema. It **does** block: backfilling mappings; choosing a canonical evidence row among duplicates; merging or deleting evidence; adding uniqueness on existing `evidence`; claiming the archive is duplicate-free.
- Prepared-calendar RRULE expansion and occurrence grain remain **open**. 035 does not expand RRULEs.

## `evidence_id` is mandatory

A committed mapping must reference a real `evidence(id)`:

`evidence_id UUID NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT` plus `UNIQUE(evidence_id)`.

No repository constraint makes that impossible: `evidence` exists from 001; 035 is additive and does not rewrite `evidence`. Unmapped historical rows simply have no 035 row until a later, separately authorized backfill (blocked until duplicate audit).

Later ingest (not 035) must use one transaction: compute/check aliases → insert evidence → insert canonical row + aliases → commit.

## Tables and relationships

| Table | Role | Integrity |
| --- | --- | --- |
| `comms_logical_sources` | Production stream | `UNIQUE (source_kind, logical_key)` |
| `comms_source_memberships` | Landing file → one stream | PK `source_id` FK `sources(id) ON DELETE RESTRICT`; `logical_source_id` FK `comms_logical_sources(id) ON DELETE RESTRICT`; `UNIQUE (source_id, logical_source_id)` as extract FK target |
| `comms_extract_instances` | One full extract | Composite FK `(source_id, logical_source_id)` → memberships `ON DELETE RESTRICT`; non-unique `source_id` index; `UNIQUE (logical_source_id, fingerprint)`; `UNIQUE (logical_source_id, id)`. Same `sources.id` may have successive fingerprints **only** under its one membership. |
| `comms_source_checkpoint` | Progress per logical source | PK `logical_source_id`; composite FK `(logical_source_id, current_extract_instance_id)` → extract `(logical_source_id, id) ON DELETE RESTRICT` |
| `comms_record_identities` | Canonical record | `evidence_id NOT NULL` FK RESTRICT + `UNIQUE(evidence_id)`; first extract same-lineage composite FK |
| `comms_record_identity_aliases` | RFC / vendor / hash keys | `UNIQUE (logical_source_id, identity_method, record_key)`; FK `(canonical_record_id, logical_source_id)` so an alias cannot leave its canonical/lineage |

`landing_alias` + `landing_basename` only. Exact URI stays on `sources`. Admin/status must not expose absolute paths.

No production `logical_key` seeds.

## Identifiers

One canonical row; many aliases. An email can store RFC, Gmail/vendor, and full-message SHA-256 together. A later export that only has the hash still resolves to the same canonical row if that alias exists. RFC values are produced from existing `communication_rfc_ids` at ingest time, not from a second RFC table.

Same `(method, key)` may exist under a **different** `logical_source_id`.

## How 026–029 are reused

- `retrieval_trust`: publish a Person link only when `trusted`.
- `communication_rfc_ids`: `role=own` to create/resolve `email_rfc_message_id` aliases; `in_reply_to` / `references` for threads. 035 does not CREATE those objects.

## Tests

- `tests/test_p2_i14_lineage_schema.py` — ordering, SQL clauses, key helpers. In-memory store **removed**.
- `tests/test_p2_i14_lineage_pg.py` — disposable Postgres only (never `memorybox`): focused 001+035 (successive fingerprints on one `sources.id`, membership exclusivity, checkpoint `ON DELETE RESTRICT`); ephemeral full-chain apply of **repository** files 001–034 in numeric order, then 035. That chain uses this clone’s `025_historian_capture_i12.sql` and has no 026–029 files; it does **not** reproduce FlightSim’s trusted-retrieval 025–029 ledger. `DROP DATABASE ... WITH (FORCE)`. Passing these tests is **not** authorization to apply 035 on Desktop or FlightSim.

## Rollback

1. `comms_record_identity_aliases`
2. `comms_record_identities`
3. `comms_source_checkpoint`
4. `comms_extract_instances`
5. `comms_source_memberships`
6. `comms_logical_sources`

## Unresolved

- Production `logical_key` strings (configuration later).
- Live duplicate `content_hash` **count**.
- Recurring calendar prepared-row grain (Q2).
- Optional later read of `communication_rfc_ids` during ingest (not in 035).
