# PRD — Address-centric communication identity (Peggy / peggo417)

**Branch:** `cursor/p2-i11a-address-centric-email-49da`  
**Stop:** Gallery + Full-Evidence V2 with Peggy emails via address identity. No historian summarization.

## Problem

Person-scoped email retrieve was chicken-and-egg: needing a Person email contact before finding mail. Archive shows one address with multiple display names:

- Structured: `Peg Legg <peggo417@hotmail.com>`
- Also observed: `Peggy George <peggo417@hotmail.com>` (confirm whether structured header vs quoted body)

Address is the stable identity; display names are observations.

## Success criteria

1. Probe reports every distinct **structured** From/To/CC(/BCC) display name for `peggo417@hotmail.com` with counts; separately counts **quoted-body** header-only hits.
2. Confirms whether structured headers contain both `Peggy George` and `Peg Legg` pairings.
3. Archive-wide `communication_identities` (or equivalent reuse) stores address → observed display names → optional resolved_person_id.
4. Person resolve: Person → trusted communication identities → all mail for those addresses — **without** requiring the Person to already have the email contact before discovery.
5. Once `peggo417` ↔ Peggy: Gallery + Full-Evidence V2 include Peg Legg–labeled messages; same path as Ask.
6. No Peggy-specific hardcode.

## In scope

- Migration + index/upsert for address-centric identity
- Inventory/probe CLI for an address
- Wire expand/retrieve to address-first discovery + closure
- Persist Peg Legg as **observed display name on the address** (Person alias only when appropriate / optional)
- Acceptance proves + FlightSim commands

## Out of scope

- Historian OBSERVATION_EXTRACT / chunk summarization / HO
- Silent body-name identity
- Shared-mailbox forced assignment

## Constraints

- Prefer structured participant headers; quoted RFC headers = lower confidence only
- Fail closed on multi-person address claims
- Reuse `person_contact_points` as confirmed Person attachment after resolve

## Build plan

1. Schema `communication_identities`
2. Scan/upsert from evidence `*_parsed` (+ optional quoted-body pass)
3. `inventory_email_address` / CLI
4. `resolve_addresses_for_person` → attach contacts + backfill
5. Wire `expand_emails_for_retrieve`
6. Prove + FlightSim V2

## Open questions

None blocking — Tom’s assignment is acceptance.
