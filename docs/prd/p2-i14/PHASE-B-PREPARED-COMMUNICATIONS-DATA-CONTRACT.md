# I14 Phase B — prepared communications data contract (proposal)

**Status:** Locked in migration **036**. Empty schema **applied** on FlightSim (2026-09-13). Prepared **rows** are not loaded.  
**Not 035.** Migration 035 stores lineage/identity tables, not threads or cleaned text.  
**Gate:** Person Pilot 1 and Person Pilot 2 packets **accepted** (2026-09-13). Distinct from I11A Peggy Narrative / Words of a Life. See [PHASE-B-036-SCHEMA-DECISION.md](PHASE-B-036-SCHEMA-DECISION.md).

Explore Person Ask (`Show me Peggy` / `Show me Sue`) later attaches **meaningful** prepared communication cards after photos without a Communications click. Canonical threads keep full conversational context. Narrative later uses **authenticated Pilot-authored** text only. A new Ask abandons unfinished background communications retrieval.

Suppression is **Gallery default retrieval only**. It never deletes or mutates immutable `evidence`.

## Schema (migration 036)

Physical names are `comms_prepared_*`. Intent below.

### `comms_prepared_generations`

| Field | Intent |
| --- | --- |
| `id` | Generation identity |
| `algo_version` | Reconstruction + compaction + commercial classifier version |
| `scope_key` | Locked `household_email`. Source stream grain, not a Person. |
| `published` / `is_active` | False until `comms_prepared_activate_generation`. Gallery reads the active view only. |

### `comms_prepared_threads`

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
| `suppression_reason` | Required when eligibility is `suppress_default` |
| `founder_review_state` | `unreviewed` / `accept_thread` / split/merge/incorrect_* / `needs_investigation` |
| `provenance` / `warnings` | Structured JSON only |

### `comms_prepared_messages`

| Field | Intent |
| --- | --- |
| `id` | Stable message id |
| `thread_id` / `generation_id` | Parent thread; must match thread generation |
| `ordinal` | Display order after `sent_at` + `evidence_id` sort |
| `evidence_id` | Immutable original (`ON DELETE RESTRICT`) |
| `canonical_record_id` | Optional 035 identity (`ON DELETE RESTRICT`) |
| `evidence_ref` | Review pointer (`T-NNNN-M-NN`, scaling via 037 to more digits when needed) |
| `sent_at` | Stored timestamptz |
| `subject` | As reconstructed |
| `cleaned_authored_text` | Newly authored contribution only. No tracking/login/unsubscribe/marketing link text. |
| `forward_status` / `forward_omitted` / `forward_block` | New forward vs relay vs omitted duplicate history |
| `urls_stripped` | Sanitization ran |
| `quote_quality` / `quote_contamination_flagged` | Remaining quote risk; distinguishable; not voice-eligible |
| `identity_quality` | resolved / unverified / uncertain |
| `authorship` | `authenticated_focal` / `authenticated_other` / `unverified` |
| `voice_corpus` | True only for authenticated focal + clean quote + resolved identity |
| `commercial_class` | `retain_life_evidence` / `suppress_default` / `uncertain` / `not_commercial` |
| `direction` | sent_by_focal / sent_to_focal_other_author / no_focal / unresolved |

### `comms_prepared_participants`

| Field | Intent |
| --- | --- |
| `message_id` | Parent message (many people, one message) |
| `role` | `from` / `to` / `cc` |
| `display_name` | Label only |
| `address_normalized` | Authenticator |
| `identity_confidence` | `authenticated_focal` / `authenticated_other` / `unverified` |
| `person_id` | Required when authenticated; forbidden when unverified |

### `comms_prepared_attachments`

| Field | Intent |
| --- | --- |
| `parent_evidence_id` | Immutable parent communication evidence (the message original) |
| `attachment_evidence_id` | Optional distinct evidence row; null when only `source_locator` is used |
| `attachment_ordinal` / `disposition` | Order and inline vs attachment |
| `filename` / `mime_type` / `byte_size` | Metadata |
| `source_locator` | Pointer into archive; **do not copy bytes** |
| `gallery_action` | `view_image` / `open_pdf` / `open_document` / `record_only` |

Unsupported or unsafe types remain visible as `record_only`. Gallery may later view supported images/documents; the archive stays authoritative.

## Founder-review state

Per thread, same marks as the packet: Accept, Split here, Merge with another, Incorrect participant, Incorrect ordering, Quoted text removed incorrectly, Missing message, Needs investigation.

Person Pilot 1 and Sue (Pilot 2) Accept are complete. Empty 036 is applied. **Loading** prepared rows, generation activation, and Gallery publication remain **separate** founder authorizations.
