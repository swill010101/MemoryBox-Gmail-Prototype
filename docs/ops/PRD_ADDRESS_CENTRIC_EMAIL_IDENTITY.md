# PRD — Address-centric communication identity (Peggy / peggo417)

**Branch:** `cursor/p2-i11a-stabilize-a3b9`  
**Stop:** Gallery + Full-Evidence V2 with Peggy emails via address identity. No historian summarization.

## Governing rule

> MemoryBox discovers communication identities from the archive first, resolves
> those identities to People second, and then uses the resolved identities to
> retrieve complete Person evidence.

```
1. DISCOVER  archive structured headers → communication_identities
             (address + observed display names; person optional)
2. RESOLVE   identities ↔ People (corroborate; fail closed if shared)
             → person_contact_points + resolved_person_id
3. RETRIEVE  Person → trusted identities → all mail for those addresses
```

Display names (`Peg Legg`, `Peggy George`) are observations on an address.
The address (`peggo417@hotmail.com`) is the stable communication identity.

## Problem

Person-scoped email retrieve was chicken-and-egg: needing a Person email contact before finding mail. Archive shows one address with multiple display names:

- Structured: `Peg Legg <peggo417@hotmail.com>`
- Also observed: `Peggy George <peggo417@hotmail.com>` (structured vs quoted-body — probe reports which)

## Success criteria

1. Probe reports every distinct **structured** From/To/CC(/BCC) display name for `peggo417@hotmail.com` with counts; separately counts **quoted-body** header-only hits.
2. Confirms whether structured headers contain both `Peggy George` and `Peg Legg` pairings.
3. Archive-wide `communication_identities` stores address → observed display names → optional resolved_person_id.
4. Discovery does **not** require the Person to already contain the email.
5. Once `peggo417` ↔ Peggy: Gallery + Full-Evidence V2 include Peg Legg–labeled messages; same path as Ask.
6. No Peggy-specific hardcode.
7. A Person's confirmed emails are **that Person's mailboxes**, not co-recipients on the same threads. Owner/noreply/marketplace addresses must not attach. Retrieve must not be "the whole mailbox."

## Out of scope

- Historian OBSERVATION_EXTRACT / chunk summarization / HO
- Silent body-name identity
- Shared-mailbox forced assignment

## Constraints

- Prefer structured participant headers; quoted RFC headers = lower confidence only
- Fail closed on multi-person address claims
- Reuse `person_contact_points` as confirmed Person attachment **after** resolve
