# I14 Phase B — prepared communications data contract (proposal)

**Status:** Design proposal only. **Do not author a migration.**  
**Not 035.** Migration 035 stores lineage/identity tables, not threads or cleaned text.  
**Gate:** Person Pilot 1 representative packet **accepted** (2026-09-13). Person Pilot 2 (Sue) packet emitted for visual review. Distinct from I11A Peggy Narrative / Words of a Life.

Explore Person Ask (`Show me Peggy` / `Show me Sue`) later attaches **meaningful** prepared communication cards after photos without a Communications click. Canonical threads keep full conversational context. Narrative later uses **authenticated Pilot-authored** text only. A new Ask abandons unfinished background communications retrieval.

Suppression is **Gallery default retrieval only**. It never deletes or mutates immutable `evidence`.

## Proposed later schema (candidate 036, separately reviewed)

Names below are contractual, not SQL.

### `prepared_generations`

| Field | Intent |
| --- | --- |
| `id` | Generation identity |
| `algo_version` | Reconstruction + compaction + commercial classifier version |
| `logical_source_id` | Household stream (035 membership), when seeded |
| `published` | False until production-load authorization |

### `prepared_threads`

| Field | Intent |
| --- | --- |
| `id` | Stable thread id (`T-NNNN` class) |
| `generation_id` | Parent generation |
| `thread_key` | RFC/vendor cluster key (not subject-invented) |
| `earliest_at` / `latest_at` | Range with timezone provenance |
| `message_count` | Displayed messages |
| `evidence_count` | Source evidence rows |
| `duplicate_omitted_count` | Deliberate duplicates |
| `threading_confidence` | `vendor+rfc` / `rfc` / `vendor` / `mixed_unthreaded` |
| `identity_confidence` | `all_authenticated` / `unverified_present` / `mixed` |
| `gallery_eligibility` | `show_by_default` / `suppress_default` / `hold_uncertain` |
| `founder_review_state` | `unreviewed` / `accept_thread` / split/merge/incorrect_* / `needs_investigation` |
| `warnings` | Structured codes only |

### `prepared_messages`

| Field | Intent |
| --- | --- |
| `id` | Stable message id |
| `thread_id` | Parent thread |
| `ordinal` | Chronological order (1..n) |
| `evidence_id` | Immutable original (`ON DELETE RESTRICT`) |
| `evidence_ref` | Review pointer (`T-NNNN-M-NN`) |
| `sent_at` | Stored timestamptz |
| `subject` | As reconstructed |
| `cleaned_authored_text` | That message’s newly authored contribution only. Quoted reply history stays in immutable evidence and is reachable via `evidence_ref`. Forwards are stored separately, not treated as ordinary reply history. Signatures and list footers are a distinct pass. |
| `authorship` | `authenticated_focal` / `authenticated_other` / `unverified` |
| `voice_corpus` | True only if From address is confirmed unique focal contact |
| `commercial_class` | `retain` / `suppress` / `uncertain` / `not_commercial` |
| `direction` | sent_by_focal / sent_to_focal_other_author / no_focal / unresolved |

### `prepared_participants`

| Field | Intent |
| --- | --- |
| `message_id` | Parent message |
| `role` | `from` / `to` / `cc` / `bcc` |
| `display_name` | Label only |
| `address_normalized` | Authenticator |
| `identity_status` | `authenticated_focal` / `authenticated_other` / `unverified` |
| `person_id` | Set only when authenticated unique |

### `prepared_attachments`

| Field | Intent |
| --- | --- |
| `message_id` / `evidence_id` | Exact message + immutable original |
| `filename` / `mime_type` / `byte_size` | Metadata |
| `source_locator` | Pointer into archive; **do not copy bytes** |
| `gallery_action` | `view_image` (JPEG/PNG/GIF/WebP/…) / `open_pdf` / `open_document` / `record_only` |

Unsupported types remain visible as records. Gallery views supported images; PDFs/docs use open actions.

## Founder-review state

Per thread, same marks as the packet: Accept, Split here, Merge with another, Incorrect participant, Incorrect ordering, Quoted text removed incorrectly, Missing message, Needs investigation.

Person Pilot 1 Accept, then Sue (Pilot 2), then a **separate** production-load authorization remain mandatory.
