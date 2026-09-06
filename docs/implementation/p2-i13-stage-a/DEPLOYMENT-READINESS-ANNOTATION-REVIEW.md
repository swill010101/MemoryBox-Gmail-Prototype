# Annotation review deployment readiness ? 2026-09-06

## Authorization and boundary

Tom authorizes autonomous development, tests, clone migration rehearsal when applicable, commits and publication to codex/p2-i13-stage-a. Before FlightSim production changes, submit one consolidated report and request one approval for the complete deployment. After approval, carry out that plan without further approval requests unless plan, target or risk materially changes. Tom operates FlightSim; the agent has not established remote deployment access. Production commands below are prepared for Tom and are not yet executed.

## Exact release and target

- Repository: swill010101/MemoryBox-Gmail-Prototype; branch: codex/p2-i13-stage-a.
- Approved development commit, pushed: 7bc47b5911caeb8ca256dcc260f17943d2fb777a.
- Production target: FlightSim, new detached checkout C:\MemoryBox-releases\p2-i13-annotation-review-7bc47b5.
- Existing release/rollback target: C:\MemoryBox-releases\p2-i13-annotation-ui-2c2dd2d at 2c2dd2dcb62373acce3453555f1b7ea139ed79ce. Verify it before stopping services; stop if it differs.
- Runtime working directory stays C:\MemoryBox; app 127.0.0.1:8790, worker 127.0.0.1:8791.
- Source media, derivatives, Capture, runtime configuration, recognition/speech queues and processing locks remain unchanged by this code repair. No Learn, transcription, recognition, cleanup or corpus run.

## Change and verification

Saved entries identify speaker, source time range and text. Review assignment restores the form and highlights/scrolls to the exact assigned words without changing playback. Twenty synthetic Chromium checks pass, including reopen, review, form keys, save/error retention and layout reachability. JavaScript syntax and diff whitespace checks pass. Screenshot reviewed. API responses in the browser test are synthetic: live review of the stored Person/span remains pending. Prior UI repair passed 33 Stage A tests and three annotation contract tests; launcher reruns its offline suites before starting this release. Twelve opt-in database tests stay skipped on FlightSim.

## Migration and backup result

No migration or backend file differs from the previous release. Clone migration rehearsal for this UI-only release is not applicable; do not replay 031. Prior PostgreSQL 16 clone rehearsal of 031 passed snapshot/equality checks and rolled back. Tom reported live 031 committed at 2026-09-06 10:13:23.839021 UTC with 1,736 snapshots, 140,441 archived words and zero mismatches.

Previous verified-by-operator backup: C:\MemoryBox-backups\i13-final-pre031-1902478e2eeb4a319d9a6fd0f2d43eff\memorybox.dump; 424809224 bytes; SHA256 358B3E00FA8DAC13E4B601F39E0105DCA70544BA6E8FACC5C6361801853CAAC2. It predates 031 and later annotations. A fresh backup is therefore part of the approved deployment below. Verify local/container SHA256 equality and pg_restore archive readability; report its path, bytes and hash. This is not a full restore rehearsal of the new backup. No restoration is part of normal UI rollback.

## Downtime and deployment commands

Estimated downtime: 5?10 minutes for service shutdown, backup, checks and restart; actual time depends on FlightSim. Prepare the detached checkout before closing services. Use the configured FlightSim PowerShell session containing existing database/Qdrant settings; do not print credentials. Execute these blocks only after approval of this complete plan.

Prepare (does not start services):

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $i13Previous = 'C:\MemoryBox-releases\p2-i13-annotation-ui-2c2dd2d'
    $i13Release = 'C:\MemoryBox-releases\p2-i13-annotation-review-7bc47b5'
    $i13Sha = '7bc47b5911caeb8ca256dcc260f17943d2fb777a'
    $i13OldSha = git -C $i13Previous rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $i13OldSha -ne '2c2dd2dcb62373acce3453555f1b7ea139ed79ce') { throw 'Rollback release mismatch.' }
    $i13OldStatus = git -C $i13Previous status --porcelain
    if ($LASTEXITCODE -ne 0 -or $i13OldStatus) { throw 'Rollback release is not clean; preserve it.' }
    if (Test-Path -LiteralPath $i13Release) { throw 'New release path exists; stop.' }
    git -C $i13Previous fetch origin codex/p2-i13-stage-a
    if ($LASTEXITCODE -ne 0) { throw 'Fetch failed.' }
    git -C $i13Previous worktree add --detach $i13Release $i13Sha
    if ($LASTEXITCODE -ne 0) { throw 'Worktree creation failed.' }
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$i13Release\docs\implementation\p2-i13-stage-a\start-fragment-release.ps1" -ExpectedSha $i13Sha
    if ($LASTEXITCODE -ne 0) { throw 'Release checks failed.' }
}
```

Close only the existing app/worker consoles normally with Ctrl+C. Then fresh backup and start:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $i13Listeners = @(Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 8790,8791 })
    if ($i13Listeners.Count) { throw 'App/worker ports are still occupied.' }
    $i13Id = [guid]::NewGuid().ToString('N')
    $i13BackupDir = "C:\MemoryBox-backups\i13-pre-review-$i13Id"
    $i13ContainerDir = "/tmp/mb-i13-pre-review-$i13Id"
    if (Test-Path -LiteralPath $i13BackupDir) { throw 'Backup directory exists.' }
    New-Item -ItemType Directory -Path $i13BackupDir | Out-Null
    docker exec memorybox-pg mkdir $i13ContainerDir
    if ($LASTEXITCODE -ne 0) { throw 'Container backup directory creation failed.' }
    docker exec memorybox-pg pg_dump -U memorybox -d memorybox -Fc -f "$i13ContainerDir/memorybox.dump"
    if ($LASTEXITCODE -ne 0) { throw 'Backup failed.' }
    docker exec memorybox-pg pg_restore --list "$i13ContainerDir/memorybox.dump" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Backup archive inspection failed.' }
    $i13ContainerHashLine = docker exec memorybox-pg sha256sum "$i13ContainerDir/memorybox.dump"
    if ($LASTEXITCODE -ne 0) { throw 'Container hash failed.' }
    $i13ContainerHash = ($i13ContainerHashLine -split '\s+')[0]
    docker cp "memorybox-pg:$i13ContainerDir/memorybox.dump" "$i13BackupDir\memorybox.dump"
    if ($LASTEXITCODE -ne 0) { throw 'Backup copy failed.' }
    $i13Hash = (Get-FileHash -LiteralPath "$i13BackupDir\memorybox.dump" -Algorithm SHA256).Hash
    if ($i13Hash -ne $i13ContainerHash) { throw 'Backup hash mismatch.' }
    $i13Proof = [pscustomobject]@{
        BackupFile = "$i13BackupDir\memorybox.dump"
        Bytes = (Get-Item -LiteralPath "$i13BackupDir\memorybox.dump").Length
        SHA256 = $i13Hash
        ContainerDump = "$i13ContainerDir/memorybox.dump"
    }
    $i13Proof | ConvertTo-Json | Set-Content -LiteralPath "$i13BackupDir\backup-proof.json" -Encoding UTF8
    $i13Proof | Format-List
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\MemoryBox-releases\p2-i13-annotation-review-7bc47b5\docs\implementation\p2-i13-stage-a\start-fragment-release.ps1' -ExpectedSha '7bc47b5911caeb8ca256dcc260f17943d2fb777a' -Start
    if ($LASTEXITCODE -ne 0) { throw 'Launcher failed; inspect output and use rollback below if needed.' }
}
```

## Smoke checks and completion evidence

1. Both service consoles complete startup; release SHA is the pinned commit, drains both off, admission unset. Launcher success alone does not prove child services started.
2. Open http://127.0.0.1:8790, Ctrl+F5. Explore and Capture remain accessible; do not initiate Capture mail actions.
3. Ask show me Eugene Will. Open the same approved video, expand Annotate transcript. Verify the existing saved entry shows the intended Person, approximately 2:23 time range, and the assigned text.
4. Click Review assignment: exact words highlight and scroll into view; Person/correction fields populate; playback does not jump. Editing cursor keys must not navigate videos.
5. Save one intended owner correction if needed, observe confirmation, reopen and verify the same stored correction and history. This approval includes this owner annotation smoke test, not Learn. Do not create arbitrary truth just to test.
6. Confirm full transcript remains reachable and normal playback/Gallery return work. Report exact release SHA, backup proof, startup results, smoke results and any unresolved issue. Full voice recognition and full I13 acceptance remain separate.

## Rollback included in approval

If startup or smoke checks fail, close only the new app/worker consoles normally and preserve the failed output. Restart the verified previous locked release with the following command in the configured shell. Do not rerun migrations, remove overlays, restore a database, delete files or reset the original checkout. Both releases use the same 031 schema; annotations remain intact. Rollback restores the previous UI limitations.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\MemoryBox-releases\p2-i13-annotation-ui-2c2dd2d\docs\implementation\p2-i13-stage-a\start-fragment-release.ps1' -ExpectedSha '2c2dd2dcb62373acce3453555f1b7ea139ed79ce' -Start
```

If the prior release is not the expected rollback target, backup verification fails, another service owns the ports, or a new runtime/schema change is required, stop and report the material change. Do not kill unknown processes or improvise a database restore.


## Current status ? annotation review accepted by Tom

Tom reports "all works as designed and I now understand how multiple reviews can happen" and approves the deployed annotation review workflow. Record this as owner-reported live acceptance of code release 7bc47b5911caeb8ca256dcc260f17943d2fb777a on FlightSim, following the approved deployment plan. The accepted scope is saved-assignment discovery, reviewing multiple assignments, restored Person/text fields, exact-word highlighting and the corrected editing workflow. No independent runtime inspection was performed by the agent.

Migration 031 was already applied and was not part of this UI release. The complete deployment was approved before Tom's acceptance. The fresh backup output and exact startup/process evidence for this release have not been supplied in the conversation; do not infer those artifacts or independent queue-count verification from UI acceptance. The earlier supplied pre031 backup and migration results remain the recorded evidence.

Next: owner annotation and read-only coverage review for the exact 22-source manifest, distinguishing reviewed assignments from unreviewed evidence. Full face/voice recognition acceptance, off-camera speaker recognition, exemplar retirement/reprocessing proof and any separately bounded processing remain outstanding. Learn/drains/archive processing remain locked. This acceptance does not authorize an evidence or recognition run. No new deployment is needed for this documentation update.
