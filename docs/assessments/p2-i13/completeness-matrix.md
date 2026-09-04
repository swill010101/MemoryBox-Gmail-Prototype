# Completeness matrix

Assessment at `12fe18305f81350f28f8bcc0851c8a1091103f91`. States follow PRD: Complete needs code plus proof; Partial identifies implemented and missing portions; Defective needs reproduction; Missing means no identified implementation in searched baseline; Unknown means evidence cannot decide. No whole FR is marked Complete without workflow proof. Future tests below were not executed unless explicitly noted. Paths are under `memorybox/` unless stated otherwise.

| FR | State | Area | Evidence and limitation | Change/dependency impact (proposal only) | Verification |
|---|---|---|---|---|---|
| I13-FR-001 | Partial | Inventory | Native migrations 008/011/012/013; schema-api-inventory.md; pipeline-inventory.md. Repository inventory complete; actual deployed native schema unresolved. | Reconcile authoritative runtime schema, consumers and files before any schema edit. | Read-only schema/lineage inventory; no current runtime acceptance. |
| I13-FR-002 | Partial | Root cause | archive_pass.py:enqueue_known_people_archive(full=True); founder clarification; actual planner requests 3 x 4 pairs in isolated check. Historical 155K operands/results unknown. | Prevent unbounded work admission; recover historical counts if available. Do not confuse processed work with invalid media. | Fan-out check passed; historical count reconciliation pending. |
| I13-FR-003 | Unknown | Remediation | No authoritative invalid-set inventory or backup/recovery proof. No remediation attempted. | Approve consistent backup/restore and mapping/quarantine plan after diagnosis. | Before/after counts and restore proof deferred. |
| I13-FR-004 | Partial | Idempotency | queue.py conflict key and native rebuild exist; process.py:upsert_appearance_moment is INSERT; observations.py cleanup lacks provider predicates. | Version natural keys, transactional concurrency/retry protection and source-safe supersession. | Static risks confirmed; repeated bounded and concurrent runs deferred. |
| I13-FR-005 | Defective | Playback | explore.js:bindAppearanceView; reproduced start=12, attempted=15, paused at 14. Historical ACR requires clamp. | After explicit supersession, keep source seek and permit playback past relevance interval. | Actual binder/media double; rendered source playback still pending. |
| I13-FR-006 | Partial | Navigation | explore.js:openModal/closeModal; gallery.scrollTop and modal sequence; shell context stack. | Preserve query/filter/range/sort/scroll through new moment navigation. | Existing p2_i4_acceptance.py inspected; rendered Prev/Next/return deferred. |
| I13-FR-007 | Partial | Transcript follow | explore.js:bindSpeechTranscript marks active word on timeupdate, without active-utterance follow/scroll arbitration. | Add follow with deliberate manual-scroll suspension/resume. | Rendered long-transcript scroll/follow test pending. |
| I13-FR-008 | Partial | Transcript seek | bindSpeechTranscript click sets player.currentTime from word data-start; binder can clamp outside current appearance. | Keep seeking and remove relevance clamp under I13; utterance/timestamp and keyboard interactions. | Source-time click/keyboard proof deferred. |
| I13-FR-009 | Partial | Voice sample | Explore transcript selection and arrow refinement; speech/learn.py; real WAV/ECAPA exemplar extraction. No overlay/quality-confirmation lifecycle. | Add owner overlay, quality guidance, pre-confirmation assignment and scoped async work. | Poor/clean audio and span-boundary UI proof pending. |
| I13-FR-010 | Partial | Face sample | Explore pause/box/crop/Person selection; recognition/learn.py; crops.py quality flags. | Reuse flow; persist full method/config/actor evidence and enforce scope. | Pure grouping checked; crop quality and rendered confirmation not rerun. |
| I13-FR-011 | Partial | Combined Learn | explore.js:submitExploreLearn calls speech and face APIs separately. Face-only/voice-only possible; partial success not fully adjudicated. | Keep independent evidence, explicit per-modality confirmation and partial-failure recovery. | Three modes plus second-call failure test pending. |
| I13-FR-012 | Partial | Background work | Learn calls synchronous current scans and queues others; drains/runs exist; no manifest gate. | Queue bounded current and other sources with immutable model/config; reject off-manifest before work. | Negative API/worker, retry and source-open tests deferred. |
| I13-FR-013 | Partial | Review | Review/Person/Explore expose identity and source moments; independent confidence inputs and unified suggestion review incomplete. | Review model with per-modality provenance and adjudication actions. | Source/time/modality/confidence drill-through test pending. |
| I13-FR-014 | Partial | Correction | Face owner_correct/withdraw primitives; speech correction API accepts withdraw only; assignments update in place. | Add immutable supersession and bounded dependent re-evaluation. | Old/new history and affected-scope proof deferred. |
| I13-FR-015 | Partial | Retirement | Face withdrawn filter and voice exemplar withdrawn column exist; no complete reason/reversal/stale-dependency lifecycle. | Reasoned reversible retirement, original-preservation copy, dependency lineage. | No-future-use/reversal/stale suggestion tests pending. |
| I13-FR-016 | Partial | Jobs | Native queues/runs and status APIs; legacy jobs exist; owner Jobs page/Pause protocol missing. | Persist scope/counts/actions and restart-safe Pause/Retry/View. | Reconcile stored writes, failures and UI counts after bounded run. |
| I13-FR-017 | Missing | Release lock | Archive-pass APIs and workers contain no I13 accepted-gate enforcement; full planner fan-out reproduced. | Gate API, enqueue, drain, retry, direct Learn, CLI and archive actions centrally. | Reject missing approval/off-manifest/archive work; not executed. |
| I13-FR-018 | Partial | Timeline | explore.js:computePrecision, timeline range/zoom/playhead handlers exist. | Preserve increasing precision and moment/source presentation. | Rendered resize/playhead/year-month-day regression pending. |
| I13-FR-019 | Partial | Retrieval | speech/retrieve.py phrase/Person/subject; speech/index.py vectors; appearance retrieval and Explore conversion. Production voice turn hook absent. | Reuse search paths; real voice matching, valid source/time, phrase boundaries and stale-index behavior. | All four query modes on owner truth deferred. |
| I13-FR-020 | Partial | Legacy presentation | Source-linked moment fields exist; Explore presents interval duration and clamps playback. | Represent observations as moments of one source; never new source videos. | No pseudo-videos proof pending; clamp reproduced. |
| I13-FR-021 | Partial | Fragment inventory | Checkpoint contains 3557 <=2s face rows; physical proxies/audio/crops exist. Full fragment/file lineage unknown. | Inventory authoritative records and individual derivative lineage without inferring source status. | Read-only checkpoint aggregates; WAL/live and physical-fragment inventory pending. |
| I13-FR-022 | Missing | Fragment migration | No I13 mapping/quarantine ledger or migration in baseline. | Plan source links, overlap reconciliation and consumer migration; quarantine uncertain rows. | Every old reference resolved once; separate authorization required. |
| I13-FR-023 | Unknown | Derivative deletion | No verified file-by-file generated-only classification or recovery proof. | No deletion now; prove backup, references and source preservation before eligibility. | Restore/source hash and migrated-reference proof deferred. |
| I13-FR-024 | Missing | Admin shell | shell.js FAMILY/SYSTEM lacks I13 Admin primary destination and owner enforcement for that area. | Shared owner-only Admin navigation plus service access policy. | All owner screens and unauthorized access checks pending. |
| I13-FR-025 | Partial | Admin destinations | Archive Health, Settings, People and accepted Historian Capture exist separately; no I13 landing/Jobs/Learned Evidence screens. | Reuse destinations and dark shell; implement missing pages; preserve I12 behavior. | Approved references inspected; live render not performed. |
| I13-FR-026 | Missing | Unlock separation | No accepted-gate/unlock lifecycle; archive-pass both requests work and starts drain. | Persist explicit founder acceptance/unlock and separate intentional start. | Unlock must not enqueue; start rejects locked state; deferred. |

## Architectural, UX and non-functional requirements

| Requirement | State | Evidence / remaining proof |
|---|---|---|
| One immutable source, derived observations/moments with stable identity and valid times | Partial | Provider IDs and source URLs exist; owned-folder IDs depend on path and duration can be absent. Native schemas lack comprehensive duration/range/source referential checks. Full source-resolution proof pending. |
| No Immich correction/identity writeback | Partial | Inspected recognition/learning paths store MB evidence and use provider input; no I13 writeback introduced. Full deployed mutation audit not claimed. Preserve boundary in build. |
| Original video/audio/machine transcript preserved | Partial | Source media used for extraction; transcript replacement deletes words/turns. Overlay/version model required. Assessment changed no runtime data. |
| Learned evidence: Person/source/time/method/quality/actor/status/config/provenance | Partial | Face/voice evidence fields and run metadata exist; immutable full configuration and actor/lifecycle lineage incomplete. |
| Face and voice independent; off-camera recognition; corroboration transparent | Partial | Separate stores and deliberate face-ignore in native voice matcher. Real turn embeddings not implemented by production provider; corroboration policy absent. Fake proof is insufficient. |
| Versioned thresholds/grouping and resource limits | Partial | Face .38/.28, gap 8s, samples 80, voice .55/.40 and single-thread drains exist as constants/patterns. No unified persisted configuration, measured concurrency budget or accepted numerical policy. |
| Before-confirmation Assigned for learning copy | Missing | Current Learn flow does not provide the approved distinct assignment/quality-confirmation state. |
| Reasoned retirement and explicit original-preservation copy | Partial | Withdrawal primitives exist; full reviewed UI and reasoned reversal/dependency propagation absent. |
| Auditability and recoverability | Partial | Runs, evidence authority, withdrawals exist; additive supersession and cross-store restore proof missing. |
| Performance/asynchronous observability | Partial | Queues/drains/status exist; synchronous Learn and unmeasured latency; native voice may report no work. No runtime/GPU timing acceptance. |
| Owner privacy/access control | Unknown | Single-owner conventions and separate I12 contribution channel; I13 Admin policy not implemented or proven. Do not infer authorization enforcement from a label. |
| Accessibility | Partial | Existing buttons, Escape/nav and transcript tabindex/arrow handlers; mouse selection/crop workflow needs keyboard/focus/label/non-color proof against rendered screens. |
| All five approved screens | Partial | Existing Learn/People modal components; Admin landing/Jobs/Learned Evidence not implemented to reference. References inspected; no live screenshots or visual acceptance claimed. |
| Explicit versioned 22-source corpus and owner truth | Unknown | Not found; proposal intentionally empty, approved=false and processing_authorized=false. Directory has 19 files, not accepted membership. |
| I12 and later-increment boundaries | Complete | Assessment diff contains only this documentation/check packet. No I12 code, roadmap resequencing, communications aggregation or later learning changed. Verified by scoped Git diff. |

## Acceptance gates (PRD section 8 / definition section 8)

| Gate | State | Reason |
|---|---|---|
| Integrity | Partial | Queue dedupe/grouping exist; equivalent rerun/source resolution proof missing. |
| Playback | Defective | Actual binder forced end pause reproduced; historical conflict recorded. |
| Transcript | Partial | Word highlight/seek present; follow/overlay/original preservation incomplete. |
| Face | Partial | Learning/withdrawal/grouping code exists; bounded accuracy/lifecycle proof absent. |
| Voice | Partial | Exemplar extraction exists; real native turn matching gap; off-camera proof absent. |
| Corroboration | Missing | No transparent combined confidence policy/lifecycle. |
| Retrieval | Partial | Four query pathways partly implemented; bounded relevant source/time results not proven. |
| Legacy Fragment Reconciliation | Unknown | Checkpoint short rows identified; authoritative row/file ledger incomplete. |
| Jobs | Partial | Queues/status exist; persisted approved scope, actions and owner display not complete. |
| Regression | Unknown | Code paths inspected; live rendered workflow not run because of write side effects. |
| Safety | Missing | Pre-acceptance archive rejection gate absent. No processing attempted in assessment. |
| Proof | Partial | Assessment evidence and isolated checks provided; bounded-run, performance, recovery and rendered screenshots deferred. |

No gate is accepted and no archive unlock is requested. Assessment completeness is distinct from product acceptance. See implementation-plan.md for every pending proof and founder decision.
