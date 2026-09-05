# FlightSim PostgreSQL backup and restore plan

Prepared 2026-09-05 for Tom. No backup/restore or runtime change was executed during preparation. Resolve client tools/version, protected backup storage and available PostgreSQL disk capacity before execution. This procedure uses native PostgreSQL clients; if only Docker clients exist, adapt after identifying the actual container. Do not guess a container or pipe binary dump bytes through PowerShell text redirection.

## Readiness and scope

1. Locate pg_dump, pg_restore, createdb and psql on FlightSim. Prefer clients matching the server major version. Verify the actual server version, database size, extensions and role's database-creation rights using the existing read-only connection.
2. Select a protected absolute backup directory outside Git (C:\MemoryBox-backups is a proposal, subject to capacity/access checks). Also allow space for a full test restore, indexes, WAL and headroom on PostgreSQL's data volume. A separate compatible test instance is preferable if already available; the commands below use a distinct test database on the existing instance and add load there.
3. Preserve current deployment SHA/paths, staged Capture code, configurations and external media through existing protected backup procedures. A database dump excludes external files and cluster-global roles/tablespaces. Same-instance restore relies on existing roles/extensions; this is not a complete host recovery test.
4. pg_dump provides a consistent snapshot during normal writes. For the final pre-migration rollback point, pause actual writers/schedulers through verified service procedures. Setting drains off in a new terminal does not stop old processes. Do not kill guessed processes, alter queue statuses or stop PostgreSQL. Coordinate I12 scheduling without changing its data/behavior. If initial rehearsal is online, take a fresh final backup after the later maintenance pause.

## Confirm connection - separate block

Enter the verified client-facing endpoint from deployment configuration, not the internal SQL container address. Passwords are entered locally at PostgreSQL prompts, never in chat or command arguments. Existing secured password-file authentication may be used instead.

```powershell
& {
    $script:i13PgHost = Read-Host 'Verified PostgreSQL client host'
    $script:i13PgPort = Read-Host 'Verified PostgreSQL port'
    $script:i13PgUser = Read-Host 'Existing backup/restore role'
    pg_dump --version
    if ($LASTEXITCODE -ne 0) { throw 'pg_dump unavailable.' }
    pg_restore --version
    if ($LASTEXITCODE -ne 0) { throw 'pg_restore unavailable.' }
    psql -X -W -h $i13PgHost -p $i13PgPort -U $i13PgUser -d memorybox -v ON_ERROR_STOP=1 -c 'SELECT current_database(), current_user, version();'
    if ($LASTEXITCODE -ne 0) { throw 'Identity check failed.' }
}
```

Stop and compare identity/version with readiness results before running the next block.

## Backup - after readiness review

Run as one block. The destination must be outside all original/worktree/release checkouts, with reviewed access and capacity. No existing backup is overwritten.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $backupRoot = Read-Host 'Reviewed absolute protected backup root outside Git'
    if (-not [IO.Path]::IsPathRooted($backupRoot)) { throw 'Absolute path required.' }
    $script:i13BackupDir = Join-Path $backupRoot ('i13-pre030-' + [guid]::NewGuid().ToString('N'))
    if (Test-Path -LiteralPath $i13BackupDir) { throw 'Backup directory exists.' }
    New-Item -ItemType Directory -Path $i13BackupDir | Out-Null
    $script:i13Dump = Join-Path $i13BackupDir 'memorybox.dump'
    pg_dump -W -h $i13PgHost -p $i13PgPort -U $i13PgUser -d memorybox --format=custom --lock-wait-timeout=30s --file=$i13Dump
    if ($LASTEXITCODE -ne 0) { throw 'Dump failed; retain partial output, do not restore it.' }
    if ((Get-Item -LiteralPath $i13Dump).Length -eq 0) { throw 'Empty dump.' }
    pg_restore --list $i13Dump | Out-File -LiteralPath (Join-Path $i13BackupDir 'archive-list.txt') -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw 'Archive inspection failed.' }
    Get-FileHash -LiteralPath $i13Dump -Algorithm SHA256 |
        Format-List | Out-File -LiteralPath (Join-Path $i13BackupDir 'sha256.txt') -Encoding utf8
    Write-Output "Backup directory: $i13BackupDir"
}
```

Review all warnings. This full dump has no table filters. Archive listing/checksum does not prove restoration. Keep dump and private outputs outside Git.

## Restore - new test database only

Run in the same terminal after backup review. Database creation fails if the new name exists; no existing database is reused or replaced. Missing roles/extensions/permissions or locale errors require investigation, not permission relaxation or ownership suppression.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    if (-not $i13Dump -or -not (Test-Path -LiteralPath $i13Dump)) { throw 'Verified dump unavailable.' }
    $script:i13RestoreDb = 'mb_i13_restore_' + [guid]::NewGuid().ToString('N')
    if ($i13RestoreDb -notmatch '^mb_i13_restore_[a-f0-9]{32}$') { throw 'Invalid test target.' }
    createdb -W -h $i13PgHost -p $i13PgPort -U $i13PgUser --maintenance-db=memorybox --template=template0 $i13RestoreDb
    if ($LASTEXITCODE -ne 0) { throw 'Test database creation failed.' }
    pg_restore -W -h $i13PgHost -p $i13PgPort -U $i13PgUser --dbname=$i13RestoreDb --single-transaction --exit-on-error $i13Dump
    if ($LASTEXITCODE -ne 0) { throw 'Restore failed; retain test database and output for review.' }
    Write-Output "Restored database: $i13RestoreDb"
}
```

No --clean, --create, dropdb or ownership/ACL suppression is used. Retain the test database until a later explicit cleanup decision. Do not apply migration 030 or start MB against this database.

## Verify restored state

```powershell
& {
    if ($i13RestoreDb -notmatch '^mb_i13_restore_[a-f0-9]{32}$') { throw 'Invalid test target.' }
    psql -X -W -h $i13PgHost -p $i13PgPort -U $i13PgUser -d $i13RestoreDb -v ON_ERROR_STOP=1 -c "BEGIN READ ONLY; SELECT current_database(); SELECT version,filename FROM schema_migrations ORDER BY version; SELECT count(*) AS recognition_queue_rows FROM recognition_queue_items; SELECT count(*) AS speech_queue_rows FROM speech_queue_items; SELECT count(*) AS capture_campaigns FROM historian_capture_campaigns; SELECT count(*) AS capture_items FROM historian_capture_items; SELECT count(*) AS transcript_words FROM speech_transcript_words; SELECT to_regclass('public.i13_processing_admissions') AS i13_before_migration; COMMIT;"
    if ($LASTEXITCODE -ne 0) { throw 'Restore verification query failed.' }
}
```

Require the generated test database name, successful restore exit status, ledger 001-029 with the reported filenames, and absent I13 admissions. Compare counts to a contemporaneous source inventory. Historical counts (recognition queue 155854, speech queue 2011, transcript words 140441) are reference values, not guaranteed future counts. Online snapshot differences may be legitimate; unexplained quiescent differences require investigation.

Also compare restored I12 columns/constraints, extensions and queue indexes with source preflight metadata. The supplied query is a smoke check, not an exhaustive database comparison. Record locally: source/version, dump start/end, hash/size, tool versions, test database name, command return codes, warnings, writer pause status and schema/count comparisons. Never point MB at the test DB for this check: it could start jobs or Capture sends.

## Stop for review

Return noncredential verification results. Keep backup and test database. A successful independent restore verifies this database recovery artifact; it does not prove live I12 dependency availability, media recovery, voice recognition or host recovery. Final maintenance backup, migration 030 and locked deployment remain separate review gates. No recognition/transcription, archive processing or live-database rollback is authorized by preparation of this plan.

## Sources

[PostgreSQL pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html) documents consistent single-database exports and custom archives. [PostgreSQL pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html) documents explicit destinations and single-transaction/error handling. Match actual installed versions before execution.
