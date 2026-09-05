# Stage A deployment plan - Tom operates FlightSim

This is a step-by-step proposal, not deployment authorization. The agent performed no deployment, runtime migration, recognition, transcription, cleanup, quarantine, deletion, or corpus/archive processing. Review this commit first. **Do not run `startmb.ps1`, `startmb.cmd`, a legacy prove command, migration, Learn, or an archive pass as a shortcut through the gates below.** Existing startup scripts may migrate and start drains.

## Current position - founder reports, 2026-09-05

**Gate 2, step 15: founder review of the current locked Ask/Gallery corrections.** This status supersedes historical pending/start instructions below; do not repeat migration or backup work merely because the original procedure remains documented.

- Gate 1 preparation and exact 22-source membership review completed. Owner annotations/voice acceptance remain separate.
- Backup restored and compared; final maintenance backup retained; Tom reported migration 030 committed. No further migration is needed for Ask corrections.
- Locked app/worker deployment completed. Prior lock probes returned 403; Explore and Capture screens opened. This is not a full live I12 workflow re-prove.
- Tom reports current photo Gallery corrected; Tom/Eugene named queries and combined Christmas/Florida queries work. Tom subsequently reported the chip correction and other current checks working. After the curator correction deployment instructions for 6d1bf63678d79bd021bc4803eca09f0211a35ca1, Tom reported "passes" for the consecutive-Ask status check.
- Current Ask/Gallery correction checks pass by owner report. Next: step 15 founder review; the one-source [playable-copy pilot plan](PLAYABLE-COPY-PILOT-PLAN.md) is prepared. Tom supplied passing source/tool/destination preflight; the check-only-by-default single-source helper and 14 offline tests are prepared. Tom approved one staging/validation attempt with helper d3e7eff71c8a627bf1f712dfe5c99be493c38992; Tom supplied a successful staged validation report: full decode passed, original unchanged, 229,993,314-byte H.264 output. Tom reports all staged picture/audio/seeking checks passed. Tom approved publication of this one validated copy. Tom now reports all 15 Gallery entries for this source play successfully, with the playhead apparently continuing beyond the relevance stop time. The one-source playback result is recorded; Tom approved a read-only fragment lineage trace; [the exporter and offline findings](FRAGMENT-LINEAGE-ASSESSMENT.md) are prepared. FlightSim trace received: all 79 native half-second moments exactly reproduce the cadence/grouping defect, including observation links. The 15 displayed entries still need Gallery membership correlation. See the lineage assessment for findings and the bounded correction recommendation; no remediation has started. This report does not establish measured response-time recovery, full source playback, or full I13 acceptance.
- Gate 3 bounded processing has NOT started. Gate 4 archive acceptance/unlock/start has NOT started. Keep drains off and admission unset. Unplayable sources, fragment presentation and face/voice learning acceptance remain outstanding; no cleanup or conversion is authorized by this status update.

## Gate 1 - Review and prepare, without running the application

1. Review `FOUNDER-AUTHORIZATION.md`, `README.md`, the code diff, migration 030, runtime/source inventories, tests, and playback screenshot. Record the exact Stage A commit accepted by the founder. Do not use a moving branch tip as the deployment identity.
2. On FlightSim, identify the current service process/task names, working directories, Python environments, configured provider endpoints and source roots. Preserve the existing deployment and its environment. Keep passwords/tokens out of logs and Git. The dev machine is Toms-Desktop; target PostgreSQL is FlightSim. Source roots confirmed by SMB are `\\flightsim\photos\Home Videos` and `\\flightsim\photos\Videos`; the latter was empty. The dev machine's P: points at media-server, so do not infer a FlightSim drive from this machine.
3. Inspect Git and obtain the reviewed branch. These commands do not switch the existing deployment:

   ```powershell
   Set-Location C:\MemoryBox
   git status --short
   git branch --show-current
   git rev-parse HEAD
   git fetch origin codex/p2-i13-stage-a
   git show --stat <APPROVED_STAGE_A_SHA>
   ```

   If there is local work, preserve it. Do not reset, clean, overwrite, or copy private runtime files into the release checkout.
4. Create a new explicit release worktree from the approved SHA, only if the path is unused:

   ```powershell
   $i13Release = 'C:\MemoryBox-releases\p2-i13-stage-a'
   if (Test-Path -LiteralPath $i13Release) { throw 'Choose a new unused release path' }
   git worktree add --detach $i13Release <APPROVED_STAGE_A_SHA>
   Set-Location $i13Release
   git status --short
   git rev-parse HEAD
   ```

5. Use FlightSim's existing compatible Python environment and the documented dependencies. Node.js on PATH is required by the playback regression test (`node --version`); reopen the terminal after installation. This is a test prerequisite, not an application startup step. Do not launch the monolith. In the new deployment terminal set both drains off and leave the admission ID unset:

   ```powershell
   $env:MEMORYBOX_RECOGNITION_DRAIN = '0'
   $env:MEMORYBOX_SPEECH_DRAIN = '0'
   Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue
   $env:PYTHONDONTWRITEBYTECODE = '1'
   python -B -m unittest discover -s tests -p test_i13_stage_a.py -v
   ```

   Expected: all Stage A offline tests pass. These use synthetic plans and database doubles, not the FlightSim database. Optional rendered proof: `python -B tests/browser_i13_playback.py` requires Chrome and Python `websockets`; it records a synthetic canvas video in browser memory. It never reads family media or starts the app. Output is under `docs/implementation/p2-i13-stage-a`; do not add rerun outputs to Git automatically.
6. Load the established deployment environment securely into this terminal (not `startmb.ps1`); preserve the two explicit drain-off values after loading it. Run the read-only inventory using the existing `MEMORYBOX_DATABASE_URL`:

   ```powershell
   python -B docs/implementation/p2-i13-stage-a/inventory-runtime.py
   ```

   Expected: `read_only=on`, `isolation=repeatable read`, timestamped aggregates. Compare counts by status/provider/reason to `runtime-inventory.json`; normal external activity may change counts. Do not repair discrepancies during this step.
7. Tom confirmed the exact 22-source membership on 2026-09-05. The versioned proposal now records that decision separately from owner truth. Verify the existing IDs/hashes/durations read-only if files have changed; do not select the first 22 files or substitute another directory. Do not ask Tom to prepare timestamp/name worksheets. Owner annotations are intended to be made in MB by selecting timestamp-backed transcript words or face evidence and assigning a Person.

   Preview the corrected evidence-generation proposal, without registering or starting anything:

   ```powershell
   python -B -m memorybox.processing preview --plan docs/implementation/p2-i13-stage-a/bounded-manifest-proposal.json
   ```

   Expected: purpose `evidence_generation`, 22 sources, zero Person targets, 22 transcription items, at most 44 attempts with the proposed two-attempt limit. Empty owner truth/coverage is valid at this phase. This does not authorize learning, face/voice matching, archive processing, or any runtime write. The proposed 1,000-item ceiling still needs review; it does not schedule 1,000 items.

   Review the corrected code and this evidence budget before migration or processing approval. The annotation-only UI/overlay workflow is not complete in Stage A: existing Learn also creates exemplars and triggers recognition. Do not use it as an annotation-only shortcut. See ANNOTATION-WORKFLOW.md. Later acceptance/learning needs owner-confirmed truth/coverage exported from MB and a new reviewed plan, not mutation of this admission.

## Gate 2 - Separate approval to apply migration and deploy locked code

8. Obtain explicit approval to apply **030_p2_i13_scope_admission.sql** and deploy the reviewed code in locked mode. Stage A implementation authorization did not grant this approval.
9. Before switching service code, use the existing operator procedures to stop recognition/speech scheduling and old processing workers. Record the exact processes stopped and preserve current job records. Do not mark the 72 historical running rows failed/complete, reset the queue, or migrate/quarantine observations. The inventory status is not proof that any particular process is alive. Old binaries do not enforce I13 gates; leaving them running would bypass the new controls.
10. Take a consistent PostgreSQL backup using established FlightSim backup procedures (`pg_dump` or the existing backup mechanism), and verify restore to a separate disposable database. Preserve relevant service configuration and the old release path. No source media or derivative cleanup is needed. Keep backups outside Git. Schema migration 030 is additive: new admission/event/unit/attempt tables, nullable queue admission stamps, indexes, and immutable-plan trigger; it does not stamp or alter old queue rows.
11. Check `schema_migrations` directly in a read-only transaction. Do not use `memorybox.migrate.pending()` as a read-only probe: it runs schema bootstrap. Verify that **030 is the only unapplied migration** in this checkout. If other migrations are pending, stop and reconcile them with the founder; do not apply them incidentally.
12. Only after steps 8-11 pass, run the repository migrator in the reviewed release environment:

   ```powershell
   python -B -m memorybox migrate
   ```

   Expected output: only `030_p2_i13_scope_admission.sql`. Record the result and schema version. If it fails, stop; do not manually patch runtime tables or continue serving new processing code. This command is documented here for Tom's future approved deployment and was **not executed** by the agent.
13. Point the service launch configuration at the new release, preserve all existing runtime/source/provider locations, and retain:

   ```powershell
   $env:MEMORYBOX_RECOGNITION_DRAIN = '0'
   $env:MEMORYBOX_SPEECH_DRAIN = '0'
   Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue
   ```

   Start the monolith and source playback worker through the established service mechanism, not an old checkout. Do not start the legacy HVRT learning/process service for work. Its unmapped mutation paths are intentionally blocked; it is not a fallback engine. Keep the old release for rollback.
14. Verify **locked-mode** behavior: existing Gallery/Person/source playback and I12 Historian Capture screens load; no processing starts on opening a video; scope-sensitive POSTs reject with no admission. Read-only GET status/history remains available. Check query, filters, timeline, sort, scroll, Prev/Next and Gallery return. Playback should seek to evidence start and continue naturally. Use an already browser-playable source/proxy: legacy proxy generation can create derived files and is not part of this proof. Verify old queue rows are still unstamped, not newly claimed by the I13 workers. No live end-to-end processing acceptance is claimed by the offline tests.
15. Capture screenshots and aggregate health/count evidence. Review with Tom. **Stop here.** Locked-code deployment does not authorize a manifest start, any bounded run, or archive recognition.

## Gate 3 - Future bounded processing authorization (not part of Stage A)

16. Only after founder approves the membership-confirmed transcription evidence plan, work limits, migration, and a bounded evidence run, register the immutable plan with a recorded review reference:

   ```powershell
   python -B -m memorybox.processing register --plan <REVIEWED_PLAN_JSON> --review-ref <FOUNDER_PLAN_APPROVAL_REFERENCE>
   ```

   Registration creates an audit record in state `registered`. It does not start workers or enqueue anything. Record its returned admission UUID and plan digest. Configure that same UUID in all relevant native service/CLI environments as `MEMORYBOX_I13_ADMISSION_ID`; a missing or mismatched UUID fails closed. Do not use a different manifest in the worker environment.
17. A separate deliberate bounded start decision changes state. This enables future admitted calls, so it must not be run as a smoke test:

   ```powershell
   python -B -m memorybox.processing start --id <BOUNDED_ADMISSION_UUID> --reference <FOUNDER_BOUNDED_START_REFERENCE>
   ```

   The command itself enqueues zero items and launches zero workers. Existing drains, if enabled later, may now consume stamped admitted work. For the evidence-generation phase, only the speech transcription lane is eligible. Only enable its drain and explicitly enqueue the reviewed transcription work after that separate authorization. Do not invoke `--full` for a bounded admission. The scoped face archive-pass now operates only on admitted People and sources, not an archive discovery sweep; speech limits reject truncation instead of silently choosing the first sources. Direct Learn requires face/voice admission and is denied by this transcription-only evidence grant. Owner annotations must not be silently turned into exemplars or follow-on recognition; their separate workflow requires later implementation/review. Provider-wide seed/sync, old pending-crop teach, legacy recognition and old live prove commands remain disabled pending their own scoped designs.
18. Follow the later approved run/proof plan. Queue reasons cannot create multiple admitted units for the same modality/Person/source; processing attempts are atomically bounded at 1-3 per item. The reviewed plan caps whole-work cardinality with a hard ceiling of 10,000 items. Stops block new reservations/claims; work already executing is not forcibly interrupted or rolled back. A stopped admission cannot restart; a new reviewed admission is required. Do not bypass the cap or revive old queue rows to force progress.

## Gate 4 - Future archive acceptance, unlock, then separate start

19. Archive release is out of Stage A. After owner annotations are captured in MB and bounded acceptance is separately completed, an archive plan must still contain explicit inventory membership, a reviewed workload budget and owner truth; it cannot use a wildcard. Register it as a separate `scope_kind=archive` plan. The bounded admission cannot be widened in place.
20. With separate founder acceptance and unlock references, an operator may **later** unlock it:

   ```powershell
   python -B -m memorybox.processing unlock --id <ARCHIVE_ADMISSION_UUID> --acceptance-ref <BOUNDED_ACCEPTANCE_REFERENCE> --reference <FOUNDER_ARCHIVE_UNLOCK_REFERENCE>
   ```

   This writes only unlock state/audit. It neither creates start state nor launches/enqueues work. A distinct `start --id ... --reference <FOUNDER_ARCHIVE_START_REFERENCE>` is required later. Do not run either action under this Stage A authorization.

## Rollback / hold

21. If locked deployment fails, keep drains disabled and the admission ID unset. Stop the new processing services using the established operator procedure. Restore service routing to the preserved prior release only after ensuring its old drains/scheduled archive passes will remain disabled; old code lacks I13 admission enforcement. Do not run `startmb` blindly on rollback.
22. Prefer leaving additive migration 030 and its audit/history in place; older code ignores these fields. Do not drop new tables/columns, erase admission history, delete generated files, reset queues, or restore an old database over newer data without a separate reviewed recovery decision. For an active later grant, `python -B -m memorybox.processing stop --id <UUID> --reference <STOP_DECISION>` closes new work admission; it is not a data rollback or forced cancellation of in-flight work.
23. Report exact release SHA, migration state, service environment/paths (without secrets), gate/admission IDs and digest, observed checks, failures and the next founder decision. Preserve I12 without redesign or migration of its records.

## Updating the prepared FlightSim checkout for this correction

The already prepared release at 686a11a remains preserved. After founder review of the correction commit, fetch the branch and create a new unused detached worktree at the exact corrected SHA (for example `C:\MemoryBox-releases\p2-i13-stage-a-correction`). Do not repeat `worktree add` against the existing directory or assume a branch fetch updates a detached checkout. Run the corrected offline tests there; expected count is 26. Preserve FlightSim's staged `application/marvin_capture` dependency and current service paths; resolve that existing live I12 dependency before any deployment switch. No service switch is authorized by these preparation instructions.

## Current next step after correction approval

Tom approved correction `1ecad04e8bf8f798181bbce4447b4941d1df8947`. Prepare that exact commit in the new correction worktree described above; rerun the 26 offline tests and Step 7 preview. Review ACCEPTANCE-CHECKLIST.md: actual bounded voice recognition, including off-camera speech, remains required for full I13 acceptance. A transcription-only bootstrap is not voice acceptance. Complete the migration backup/pending-schema and live I12 dependency checks before requesting the separate migration/locked-deployment decision.

## Migration collision correction - 2026-09-05

This section supersedes the earlier next-step commit reference for deployment. Do not deploy 686a11a or 1ecad04: their I13 migration number 026 collides with FlightSim history. The review correction renames only the unapplied I13 migration to 030, with identical SQL bytes. Review and prepare the correction commit in a new unused worktree, then run 27 offline tests and the unchanged evidence preview.

Before any migration approval, run `python -B docs/implementation/p2-i13-stage-a/preflight-migrations.py` using FlightSim's existing database environment. This does not import the app or migrator and issues only read-only metadata queries. Expected pending list is only 030_p2_i13_scope_admission.sql, with historical filename differences at 009 and 025 reported explicitly. A new collision at 030, missing local migration files, or any additional pending migration blocks this deployment procedure. Do not edit schema_migrations or replay 009/025 to hide differences.

Tom's read-only output confirms AI trace and all 12 expected I12 tables exist; it does not prove their columns/constraints or live I12 workflow. Preserve existing I12 schema and code. Review the metadata exported by preflight, verify backups/restore and the staged live Capture dependency, and obtain migration/locked-deployment approval before proceeding. The migrator remains number-based; this correction does not claim a general migration identity redesign. See MIGRATION-RECONCILIATION.md.

## Backup/restore preparation

Follow [BACKUP-RESTORE-PLAN.md](BACKUP-RESTORE-PLAN.md), starting with client/storage readiness. Restore verification uses a new test database and stops before migration.

## Existing startmb launch arrangement

See [LOCKED-LAUNCH-PLAN.md](LOCKED-LAUNCH-PLAN.md). The native serve command auto-migrates and performs trace cleanup/bootstrap; do not use it as a read-only or migration-free preflight. Resolve effective source/derived/config paths through preflight-launch.py before completing a separate locked launcher. The original launcher and I12 files remain untouched.

The prepared launch-locked.py now supplies the separate launcher with check-only default; see LOCKED-LAUNCH-PLAN.md. Source/derived directories were confirmed by Tom. Run its check before any migration or service-start decision. Tests now include three offline launcher boundary checks (30 total).

## Playback availability correction

See [PLAYBACK-CORRECTION.md](PLAYBACK-CORRECTION.md). Video open now checks existing playable copies without conversion; missing copies show explicit feedback. Apply this code correction to both app and worker in locked mode, with no new migration or media generation. Offline test count is 33.

## Ask context and Person-result correction

See [ASK-CONTEXT-CORRECTION.md](ASK-CONTEXT-CORRECTION.md) for the new `clear all` command, fresh named-person searches, evidence membership guards, test commands and locked deployment verification. No migration or processing is required.
