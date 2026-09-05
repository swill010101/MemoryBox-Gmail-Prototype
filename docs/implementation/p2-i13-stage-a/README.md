# P2-I13 Stage A - founder review packet

Base: accepted assessment `bc2b967274d51ffce356a12895df2cd8f77d73b0`.
Branch: `codex/p2-i13-stage-a`. Worktree: `C:/MemoryBox-worktrees/p2-i13-assessment`.
Founder authorization and confirmed playback/transcript/retirement decisions are recorded in [FOUNDER-AUTHORIZATION.md](FOUNDER-AUTHORIZATION.md).

**Stage A code is submitted for review; processing remains locked. Migration 026 is authored and unapplied. Tom confirmed the exact 22-source membership. Owner truth will be created through MB annotation, not manual prerequisite worksheets. The transcription-only evidence proposal requires separate processing review/start; membership approval does not authorize processing.**

## Changed

- Added centralized immutable-plan admission with provider/source/Person/modality checks and whole-plan cardinality preview. Missing plan, unstarted state, missing migration/store, off-manifest source, wrong Person, duplicate membership, incomplete owner truth for acceptance/learning, invalid supplied intervals, or oversized workload fails closed.
- Added reviewed plan registration, separate archive acceptance/unlock, separate processing start, stop, and audit events through operator CLI. No browser endpoint can grant itself processing authority. Unlock and start commands enqueue zero items and launch zero workers; start enables later admitted work.
- Stamped newly admitted/requeued work; pre-existing NULL-stamped queue rows are excluded from claims. Queue admission rechecks persisted state in the write transaction. One reason per logical admitted unit prevents reason-based multiplication; atomic attempt reservations cap retries across entry points. No old runtime row was stamped, reset, quarantined or deleted.
- Replaced full-inventory/People discovery during native archive passes with explicit reviewed plan membership. `--full` requires an archive admission. Learn follows only approved sources. API/CLI/queue/retry/drain/native processing paths enforce the same policy. Unmapped legacy and provider-wide seed/sync mutation paths are blocked rather than treated as approved scope.
- Removed forced stop-at-end and replay reset while retaining source seek. Gallery open/close context functions are unchanged. Source-open no longer automatically queues transcription or displays a fictitious newly started job.
- Added offline tests and a rendered Chromium synthetic-source proof. No family media was decoded or played during implementation; source headers and bytes were read only for inventory/hash verification.
- Preserved I12 files and migrations; transcript overlays and retirement cascade are recorded decisions for later stages, not implemented here.

## Authoritative runtime and causal reconciliation

Tom confirmed that FlightSim hosts deployment, media, models, PostgreSQL and other runtime services; Toms-Desktop is development. [runtime-inventory.json](runtime-inventory.json) is a single FlightSim PostgreSQL `REPEATABLE READ READ ONLY` snapshot at its recorded transaction timestamp.

- Recognition queue: **155,854** rows; **124,485 completed**, **31,297 excluded**, **72 running**, **0 queued** in that snapshot.
- Immich exemplar-change: **117,780 = 60 People x 1,963 source videos**, comprising 117,723 completed and 57 running rows. This directly reconciles the largest Cartesian workload block with the founder's reported all-known-People reconciliation. Other providers/reasons account for the remaining 38,074 rows; see grouped evidence.
- Recognition runs: **123,873**; face observations: **8,894**; face appearance moments: **3,599**. These are different units from queue work and source media.
- Native voice exemplars: **0** in this snapshot. No inference about future voice accuracy is made.
- Coarse duplicate appearance excess: **10**, excluding version/model/box distinctions; not a deletion set. Zero negative/reversed appearance ranges by the recorded check does not prove all intervals fit source durations.

Running is a persisted status, not proof of a live process. The operator must inspect service state before deployment; this task did not stop or repair old workers/rows.

## Source and manifest evidence

The initially interpreted nested share paths were incorrect/unavailable. Corrected paths are accessible under the dev Windows account, so **no share permission change is needed**:

- `\\flightsim\photos\Home Videos`: 48 video files, 34 top-level and 14 in subfolders.
- `\\flightsim\photos\Videos`: empty.

[source-candidates.json](source-candidates.json) records exact candidate IDs, relative paths, sizes and durations. All **48** canonical IDs matched native recognition history. Durations were read from container headers without decoding. File size/mtime remained stable across the metadata observation; this is not a filesystem snapshot atomic with the earlier database transaction.

[bounded-manifest-proposal.json](bounded-manifest-proposal.json) proposes exactly 22 named sources from FlightSim, with full read-only source hashes and durations. Tom confirmed this exact membership on 2026-09-05. It does not substitute the desktop's 19 files or claim directory membership is authorization. The selection deliberately spans longer home movies/recorded sessions and shorter clips; it has **no inferred Person identities, appearance/speech intervals, no-match labels or coverage assertions**. Owner truth remains empty and `owner_confirmed=false`. The corrected `evidence_generation` phase permits preview/registration of this membership-confirmed, transcription-only plan before owner truth exists; registration still requires a review reference and no work is admitted until separately started. Acceptance/learning retains truth and coverage requirements. The 1,000-item proposal budget and two-attempt budget are recommendations for review, not accepted processing limits.

## Proof

See [test-proof.json](test-proof.json), [browser-playback-proof.json](browser-playback-proof.json), and [browser-playback-proof.png](browser-playback-proof.png).

The rendered browser proof uses the actual changed binder and a synthetic source recorded entirely in browser memory: seek 0.5s, relevance end 1s, observed playback beyond 2.5s without forced pause. This supports actual media-element behavior; it is not live Gallery/Immich or corpus acceptance. Unit tests compare Gallery open/close code against the accepted baseline, exercise HTTP middleware without monolith startup, check CLI denial before provider imports, reject off-manifest work before queue writes, leave old rows unclaimable, and verify separate unlock/start with database doubles.

No production model, recognition/transcription job, corpus run, migration, cleanup, deletion, quarantine, provider mutation, or deployment was executed. Real PostgreSQL DDL/row-lock concurrency and full rendered Gallery/provider regression remain future gated verification. The old assessment proof remains historical and is not a Stage A test harness.

## Review and deployment

Follow the [23-step deployment plan](DEPLOYMENT-PLAN.md), [scope plan contract](scope-plan-schema.md), and read-only inventory/export recipes. Tom performs all deployments on FlightSim. The plan has separate gates for code review, migration/locked deployment, bounded start, archive acceptance/unlock, and archive start.

Before advancing: review the corrected Stage A code and transcription evidence budget; authorize migration/locked deployment separately. Do not bypass source gates to make legacy workflows run. Full evidence lifecycle repair, real voice matching, fragment remediation and later Admin screens remain out of Stage A.

## 2026-09-05 correction

See [ANNOTATION-WORKFLOW.md](ANNOTATION-WORKFLOW.md). Tom confirmed membership and rejected manual owner-truth preparation as the bootstrap requirement. The corrected admission separates evidence generation from acceptance/learning. FlightSim passed the original 22 tests after Node installation and returned a read-only repeatable-read inventory at 2026-09-05 10:18:58 UTC with the same reported table counts. These are operator-reported checks of 686a11a, not validation of this correction on FlightSim. Current offline regression results are in test-proof.json.

The correction at `1ecad04e8bf8f798181bbce4447b4941d1df8947` is founder-approved. Full I13 acceptance remains pending, including the explicit [voice acceptance checklist](ACCEPTANCE-CHECKLIST.md). Next: prepare the corrected FlightSim worktree and run its 26 offline tests plus read-only preview.
