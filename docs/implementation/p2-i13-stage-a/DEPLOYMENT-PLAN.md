# Stage A deployment plan - Tom operates FlightSim

This is a step-by-step proposal, not deployment authorization. The agent performed no deployment, runtime migration, recognition, transcription, cleanup, quarantine, deletion, or corpus/archive processing. Review this commit first. **Do not run `startmb.ps1`, `startmb.cmd`, a legacy prove command, migration, Learn, or an archive pass as a shortcut through the gates below.** Existing startup scripts may migrate and start drains.

## Gate 1 - Review and prepare, without running the application

1. Review `FOUNDER-AUTHORIZATION.md`, `README.md`, the code diff, migration 026, runtime/source inventories, tests, and playback screenshot. Record the exact Stage A commit accepted by the founder. Do not use a moving branch tip as the deployment identity.
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

5. Use FlightSim's existing compatible Python environment and the documented dependencies. Do not launch the monolith. In the new deployment terminal set both drains off and leave the admission ID unset:

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
7. Finalize the **exact** 22-source selection from the 48 candidates with Tom. A directory or first-N scan is not approval. Verify each stable provider/source ID, source hash, duration, modality coverage and owner-confirmed identity/time truth. Use an explicitly authored selection JSON with exact file paths and IDs, then read/hash only those selected files:

   ```powershell
   python -B docs/implementation/p2-i13-stage-a/inventory-selected-sources.py --selection <EXACT_22_SOURCE_SELECTION_JSON>
   ```

   This reads bytes for hashes and strips machine-specific paths from the manifest output. It performs no media decoding or models. Truth and coverage must be supplied by the owner, never filled from recognition guesses. A source's size/mtime must remain stable while hashed. Assemble the reviewed plan in the schema documented in `scope-plan-schema.md`. Run only the read-only preview:

   ```powershell
   python -B -m memorybox.processing preview --plan <REVIEWED_PLAN_JSON>
   ```

   Until membership/truth are complete, rejection is expected. Record plan digest, source count, Person count, maximum work items and worst-case attempts. **Stop for founder review of the exact manifest and budget.**

## Gate 2 - Separate approval to apply migration and deploy locked code

8. Obtain explicit approval to apply **026_p2_i13_scope_admission.sql** and deploy the reviewed code in locked mode. Stage A implementation authorization did not grant this approval.
9. Before switching service code, use the existing operator procedures to stop recognition/speech scheduling and old processing workers. Record the exact processes stopped and preserve current job records. Do not mark the 72 historical running rows failed/complete, reset the queue, or migrate/quarantine observations. The inventory status is not proof that any particular process is alive. Old binaries do not enforce I13 gates; leaving them running would bypass the new controls.
10. Take a consistent PostgreSQL backup using established FlightSim backup procedures (`pg_dump` or the existing backup mechanism), and verify restore to a separate disposable database. Preserve relevant service configuration and the old release path. No source media or derivative cleanup is needed. Keep backups outside Git. Schema migration 026 is additive: new admission/event/unit/attempt tables, nullable queue admission stamps, indexes, and immutable-plan trigger; it does not stamp or alter old queue rows.
11. Check `schema_migrations` directly in a read-only transaction. Do not use `memorybox.migrate.pending()` as a read-only probe: it runs schema bootstrap. Verify that **026 is the only unapplied migration** in this checkout. If other migrations are pending, stop and reconcile them with the founder; do not apply them incidentally.
12. Only after steps 8-11 pass, run the repository migrator in the reviewed release environment:

   ```powershell
   python -B -m memorybox migrate
   ```

   Expected output: only `026_p2_i13_scope_admission.sql`. Record the result and schema version. If it fails, stop; do not manually patch runtime tables or continue serving new processing code. This command is documented here for Tom's future approved deployment and was **not executed** by the agent.
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

16. Only after founder approves the exact 22-source plan, owner truth, work limits, migration, and a bounded run, register the immutable plan with a recorded review reference:

   ```powershell
   python -B -m memorybox.processing register --plan <REVIEWED_PLAN_JSON> --review-ref <FOUNDER_PLAN_APPROVAL_REFERENCE>
   ```

   Registration creates an audit record in state `registered`. It does not start workers or enqueue anything. Record its returned admission UUID and plan digest. Configure that same UUID in all relevant native service/CLI environments as `MEMORYBOX_I13_ADMISSION_ID`; a missing or mismatched UUID fails closed. Do not use a different manifest in the worker environment.
17. A separate deliberate bounded start decision changes state. This enables future admitted calls, so it must not be run as a smoke test:

   ```powershell
   python -B -m memorybox.processing start --id <BOUNDED_ADMISSION_UUID> --reference <FOUNDER_BOUNDED_START_REFERENCE>
   ```

   The command itself enqueues zero items and launches zero workers. Existing drains, if enabled later, may now consume stamped admitted work. Only enable the needed drains and explicitly enqueue the reviewed work after that separate authorization. Do not invoke `--full` for a bounded admission. The scoped face archive-pass now operates only on admitted People and sources, not an archive discovery sweep; speech limits reject truncation instead of silently choosing the first sources. Direct Learn is also scope-gated. Provider-wide seed/sync, old pending-crop teach, legacy recognition and old live prove commands remain disabled pending their own scoped designs.
18. Follow the later approved run/proof plan. Queue reasons cannot create multiple admitted units for the same modality/Person/source; processing attempts are atomically bounded at 1-3 per item. The reviewed plan caps whole-work cardinality with a hard ceiling of 10,000 items. Stops block new reservations/claims; work already executing is not forcibly interrupted or rolled back. A stopped admission cannot restart; a new reviewed admission is required. Do not bypass the cap or revive old queue rows to force progress.

## Gate 4 - Future archive acceptance, unlock, then separate start

19. Archive release is out of Stage A. After bounded acceptance, an archive plan must still contain explicit inventory membership, a reviewed workload budget and owner truth; it cannot use a wildcard. Register it as a separate `scope_kind=archive` plan. The bounded admission cannot be widened in place.
20. With separate founder acceptance and unlock references, an operator may **later** unlock it:

   ```powershell
   python -B -m memorybox.processing unlock --id <ARCHIVE_ADMISSION_UUID> --acceptance-ref <BOUNDED_ACCEPTANCE_REFERENCE> --reference <FOUNDER_ARCHIVE_UNLOCK_REFERENCE>
   ```

   This writes only unlock state/audit. It neither creates start state nor launches/enqueues work. A distinct `start --id ... --reference <FOUNDER_ARCHIVE_START_REFERENCE>` is required later. Do not run either action under this Stage A authorization.

## Rollback / hold

21. If locked deployment fails, keep drains disabled and the admission ID unset. Stop the new processing services using the established operator procedure. Restore service routing to the preserved prior release only after ensuring its old drains/scheduled archive passes will remain disabled; old code lacks I13 admission enforcement. Do not run `startmb` blindly on rollback.
22. Prefer leaving additive migration 026 and its audit/history in place; older code ignores these fields. Do not drop new tables/columns, erase admission history, delete generated files, reset queues, or restore an old database over newer data without a separate reviewed recovery decision. For an active later grant, `python -B -m memorybox.processing stop --id <UUID> --reference <STOP_DECISION>` closes new work admission; it is not a data rollback or forced cancellation of in-flight work.
23. Report exact release SHA, migration state, service environment/paths (without secrets), gate/admission IDs and digest, observed checks, failures and the next founder decision. Preserve I12 without redesign or migration of its records.
