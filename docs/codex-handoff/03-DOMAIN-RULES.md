# Domain Rules (Historian Capture)

Authoritative sources: [MBDC-P2-I12](../product/MBDC-P2-I12_DOMAIN_MODEL.md), [MBPRD-P2-I12](../product/MBPRD-P2-I12_HISTORIAN_COLLECTION_CAMPAIGNS.md).

## Core principle

Inbound email replies are **external evidence**, not accepted knowledge. The owner reviews, assesses privately, and explicitly verdicts before anything enters Stories, Artifacts, or Ask.

## Lifecycle

```text
Campaign (draft → running → paused/stopped/completed)
  → Delivery per question (pending → waiting → answered | no_response | failed)
  → Capture Item (immutable inbound)
  → Review Draft(s) (versioned working copy)
  → Owner Assessment (private qualitative label)
  → Verdict (retained | rejected | promotion_authorized)
  → Optional Promotion → Story | Artifact
  → Optional Thank-you (generic only)
```

## Campaign states

| Status | Outbound | Inbound |
|--------|----------|---------|
| draft | No | N/A |
| running | Yes (scheduled) | Yes |
| paused | No | Yes (review continues) |
| stopped | No | Yes |
| completed | No | Yes |

## Cadence vs follow-up (separate)

- **Question cadence:** daily / weekly / monthly / weekday / time — when next question sends after previous cycle completes
- **Follow-up interval:** default **7 days** — when reminder fires if no reply; second interval → `no_response`

## Correlation (locked)

- Outbound subject: `[MB-HC-<token>] <campaign title>`
- Reply-To: `<transport>+hc-<token>@domain`
- Inbound matched on token in subject, To, Delivered-To, or X-Original-To

## Immutable source

- `historian_capture_items` store raw content hash, preserved URI, headers
- Review edits go to `historian_capture_review_drafts` only
- Download original: `GET /historian-capture/items/{id}/source` (plain text)

## Owner assessment (4 labels)

Separate from verdict and from system confidence. Never sent to contributor. Never auto-converted to numeric truth score.

## Verdicts

| Verdict | Effect |
|---------|--------|
| retained | Kept in archive; visible in Kept tab |
| rejected | Excluded from affirmative Ask |
| promotion_authorized | Eligible for Story/Artifact promotion |

## STOP / opt-out

Reply with STOP (first word) → respondent `opted_out`, pending deliveries cancelled, audit row written.

## Unmatched mail

No token or unknown token → quarantine (`match_status` unmatched/ambiguous); visible in Needs attention tab.

## People rules

- Every respondent must link to canonical MB Person (`people_id`)
- Email from Person profile contacts or manual entry at campaign create
- Person profile email edit UI is limited — HC reads first email contact from profile

## What HC is not

- Not automatic Story generation on receipt
- Not a second MarvinCapture app
- Not contributor accounts or multi-user editing
- Not using PoC SQLite as source of truth
