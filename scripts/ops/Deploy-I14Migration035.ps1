#Requires -Version 5.1
<#
.SYNOPSIS
  Bounded FlightSim apply of I14 migration 035 only. Does not change Git HEAD.
.DESCRIPTION
  Operator must already have checked out the founder-approved release SHA.
  Schema-review commit 4c13f70aae0d18f217eec4dcf43a98e6b964b14d must be an ancestor,
  and 035 SQL must match that commit's blob.
  Does not seed, backfill, ingest, merge evidence, run Peggy, change UI/Ask, or register tasks.
.PARAMETER ReleaseSha
  Full 40-character SHA of the already-checked-out release. Required.
.PARAMETER PreflightOnly
  Read-only git/ledger/health/counts checks. No backup, migrate, or restart.
.PARAMETER AllowOfflineOrigin
  Skip origin/codex/p2-i14-communications equality. Founder-authorized offline use only.
.PARAMETER Rollback
  Stop serve, save diagnostics, check out prior production SHA, reverse empty 035.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [Parameter(Mandatory = $true)]
  [string]$ReleaseSha,
  [switch]$PreflightOnly,
  [switch]$AllowOfflineOrigin,
  [switch]$Rollback,
  [string]$RepoRoot = '',
  [string]$HealthUrl = 'http://127.0.0.1:8790/health',
  [string]$PythonExe = ''
)

$ErrorActionPreference = 'Stop'
$RequiredPrior = '743c76712cb286ccdae3ad1108fb260dbd04770d'
$SchemaReviewSha = '4c13f70aae0d18f217eec4dcf43a98e6b964b14d'
$MigrationFile = '035_p2_i14_communications_lineage.sql'

if (-not $RepoRoot) {
  $RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot 'memorybox'))) {
  throw "STOP memorybox package not found under $RepoRoot"
}
Set-Location -LiteralPath $RepoRoot

function Import-DotEnvFile([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return }
  Get-Content -LiteralPath $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $idx = $line.IndexOf('=')
    if ($idx -lt 1) { return }
    $name = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    Set-Item -Path ("Env:$name") -Value $value
  }
}

function Import-FlightSimEnv {
  Import-DotEnvFile (Join-Path $RepoRoot 'config\memorybox_app.env')
  Import-DotEnvFile (Join-Path $RepoRoot 'config\video_worker.env')
  Import-DotEnvFile (Join-Path $RepoRoot 'config\memorybox_sources.env')
  if (-not $env:MEMORYBOX_DATABASE_URL) {
    $env:MEMORYBOX_DATABASE_URL = 'postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox'
  }
  if (-not $env:MEMORYBOX_P1_RUNTIME_HOST) { $env:MEMORYBOX_P1_RUNTIME_HOST = '1' }
}

function Resolve-MbPython {
  if ($PythonExe) { return $PythonExe }
  $venvPy = Join-Path $RepoRoot '.venv\Scripts\python.exe'
  if (Test-Path -LiteralPath $venvPy) { return $venvPy }
  throw "STOP MemoryBox venv Python not found: $venvPy"
}

function Invoke-Mb035 {
  param(
    [string]$Action,
    [string]$StdinJson = '',
    [string[]]$ArgList = @()
  )
  $py = Resolve-MbPython
  if ($StdinJson) {
    $StdinJson | & $py -m memorybox.ops.i14_migration_035 $Action @ArgList
  } else {
    & $py -m memorybox.ops.i14_migration_035 $Action @ArgList
  }
  if ($LASTEXITCODE -ne 0) { throw "STOP $Action failed" }
}

function Stop-MbServe {
  Get-NetTCPConnection -LocalPort 8790 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Seconds 2
}

function Start-MbServe {
  $py = Resolve-MbPython
  Start-Process -FilePath $py -ArgumentList @('-m', 'memorybox', 'serve') -WorkingDirectory $RepoRoot | Out-Null
}

function Get-UntrackedPaths {
  git -C $RepoRoot ls-files --others --exclude-standard
}

function Get-GitText {
  param([Parameter(Mandatory = $true)][string[]]$GitArgs)
  $raw = & git -C $RepoRoot @GitArgs
  if ($LASTEXITCODE -ne 0) { throw "STOP git $($GitArgs -join ' ') failed" }
  if ($null -eq $raw) { return '' }
  return (($raw | ForEach-Object { [string]$_ }) -join "`n").Trim()
}

function Assert-GitCleanTracked {
  $dirty = git -C $RepoRoot status --porcelain --untracked-files=no
  if ($dirty) { throw "STOP tracked files dirty:`n$dirty" }
}

function Save-RollbackDiagnostics([string]$DestDir) {
  New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
  git -C $RepoRoot rev-parse HEAD | Set-Content -Encoding ascii (Join-Path $DestDir 'head.txt')
  git -C $RepoRoot status --short | Set-Content -Encoding utf8 (Join-Path $DestDir 'git-status.txt')
  try {
    $h = Invoke-RestMethod $HealthUrl
    @{ ok = [bool]$h.ok; pending = @($h.migrations.pending); applied_n = @($h.migrations.applied).Count } |
      ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $DestDir 'health-sanitized.json')
  } catch {
    Set-Content -Encoding utf8 (Join-Path $DestDir 'health-sanitized.json') '{"ok":false,"error":"health_unavailable"}'
  }
}

Import-FlightSimEnv
$Python = Resolve-MbPython

Write-Host '=== GIT / RELEASE ==='
$head = Get-GitText @('rev-parse', 'HEAD')
$branch = Get-GitText @('branch', '--show-current')
if (-not $branch) { $branch = '(detached)' }
Write-Host "HEAD=$head"
Write-Host "BRANCH=$branch"
Write-Host "RELEASE_SHA=$ReleaseSha"
git -C $RepoRoot status --short
Assert-GitCleanTracked
$untracked = @(Get-UntrackedPaths)
Write-Host 'UNTRACKED_FILES'
if ($untracked.Count -eq 0) { Write-Host '(none)' } else { $untracked | ForEach-Object { Write-Host $_ } }

$releaseArgs = @($ReleaseSha)
if ($AllowOfflineOrigin) { $releaseArgs += '--offline' }
$rel = Invoke-Mb035 -Action 'assert-release' -ArgList $releaseArgs
Write-Host $rel
Invoke-Mb035 'assert-ops-pack' | Out-Host

if ($Rollback) {
  if (-not $PSCmdlet.ShouldProcess($RepoRoot, 'Rollback empty 035 after saving diagnostics')) { return }
  Write-Host '=== ROLLBACK ==='
  Stop-MbServe
  $stamp = Get-Date -Format yyyyMMdd-HHmmss
  $rootBak = if (Test-Path 'E:\MemoryBox-backups') { 'E:\MemoryBox-backups' } else { 'C:\MemoryBox-backups' }
  $diag = Join-Path $rootBak "i14-035-rollback-diag-$stamp"
  Save-RollbackDiagnostics $diag
  $rbSql = Join-Path $diag 'rollback-empty-035.sql'
  & $Python -m memorybox.ops.i14_migration_035 print-rollback-sql | Set-Content -Encoding ascii $rbSql
  Write-Host "DIAGNOSTICS=$diag"
  git -C $RepoRoot checkout --detach $RequiredPrior
  if ((Get-GitText @('rev-parse', 'HEAD')) -ne $RequiredPrior) { throw 'STOP rollback HEAD mismatch' }
  git -C $RepoRoot cat-file -e "${RequiredPrior}:memorybox/migrations/$MigrationFile" 2>$null
  if ($LASTEXITCODE -eq 0) { throw 'STOP 035 unexpectedly present on prior SHA' }
  if (Test-Path -LiteralPath (Join-Path $RepoRoot "memorybox\migrations\$MigrationFile")) {
    throw 'STOP 035 still on disk after restoring prior SHA'
  }
  Get-Content -Raw -LiteralPath $rbSql | docker exec -i memorybox-pg psql -U memorybox -d memorybox -v ON_ERROR_STOP=1
  if ($LASTEXITCODE -ne 0) { throw 'STOP rollback SQL failed; if tables have rows use the verified dump' }
  Start-MbServe
  $deadline = (Get-Date).AddSeconds(60)
  $h = $null
  do {
    try {
      $h = Invoke-RestMethod $HealthUrl
      if ($h.ok -and -not @($h.migrations.pending).Count) { break }
    } catch { $h = $null }
    Start-Sleep -Seconds 1
  } while ((Get-Date) -lt $deadline)
  if (-not $h -or -not $h.ok) { throw 'STOP health not ok after rollback restart' }
  $mail = Invoke-RestMethod 'http://127.0.0.1:8790/historian-capture/email-status'
  if (-not $mail.ok -or $mail.provider_key -ne 'namecheap_privateemail_imap_smtp') {
    throw 'STOP historian-capture email-status failed after rollback'
  }
  $sched = Invoke-RestMethod 'http://127.0.0.1:8790/admin/api/scheduled-services'
  $hc = @($sched.services | Where-Object { $_.kind -eq 'recurring_service' -and $_.id -eq 'historian_capture_email' })
  if ($hc.Count -ne 1) { throw 'STOP expected one Historian Capture recurring service after rollback' }
  if ($hc[0].status -in @('Error', 'Disabled', 'Not configured')) {
    throw "STOP HC schedule status after rollback: $($hc[0].status)"
  }
  if ($hc[0].status -eq 'Delayed') { Write-Host 'HC_SCHEDULE_DELAYED=true' }
  git -C $RepoRoot status --short
  return
}

Write-Host '=== PREFLIGHT LEDGER ==='
$pre = Invoke-Mb035 'preflight-ledger'
Write-Host $pre
$health = Invoke-RestMethod $HealthUrl
$healthJson = $health | ConvertTo-Json -Depth 8 -Compress
$healthCheck = Invoke-Mb035 -Action 'assert-health-preflight' -StdinJson $healthJson
Write-Host $healthCheck
$preObj = $pre | ConvertFrom-Json
$script:BaselineCounts = $preObj.counts | ConvertTo-Json -Compress
Write-Host "BASELINE_COUNTS=$($script:BaselineCounts)"
Invoke-Mb035 'assert-ops-pack' | Out-Host

if ($PreflightOnly -or $WhatIfPreference) {
  Write-Host 'PREFLIGHT_ONLY: no backup, migrate, or restart; Git HEAD unchanged'
  git -C $RepoRoot status --short
  Write-Host "HEAD_UNCHANGED=$(Get-GitText @('rev-parse', 'HEAD'))"
  return
}

if (-not $PSCmdlet.ShouldProcess($RepoRoot, 'Backup and apply 035 without changing Git HEAD')) { return }

Write-Host '=== BACKUP ==='
$stamp = Get-Date -Format yyyyMMdd-HHmmss
$rootBak = if (Test-Path 'E:\MemoryBox-backups') { 'E:\MemoryBox-backups' } else { 'C:\MemoryBox-backups' }
$bak = Join-Path $rootBak "pre-i14-035-$stamp"
New-Item -ItemType Directory -Force -Path $bak | Out-Null
$dump = Join-Path $bak 'memorybox.dump'
docker exec memorybox-pg pg_dump -U memorybox -Fc memorybox -f /tmp/pre-i14-035.dump
if ($LASTEXITCODE -ne 0) { throw 'STOP pg_dump failed' }
docker cp memorybox-pg:/tmp/pre-i14-035.dump $dump
if ($LASTEXITCODE -ne 0) { throw 'STOP docker cp backup failed' }
docker exec memorybox-pg rm -f /tmp/pre-i14-035.dump | Out-Null
$info = Get-Item -LiteralPath $dump
if ($info.Length -lt 1) { throw 'STOP dump empty' }
docker cp $dump memorybox-pg:/tmp/pre-i14-035-verify.dump
if ($LASTEXITCODE -ne 0) { throw 'STOP docker cp verify failed' }
docker exec memorybox-pg pg_restore -l /tmp/pre-i14-035-verify.dump | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'STOP pg_restore -l failed' }
docker exec memorybox-pg rm -f /tmp/pre-i14-035-verify.dump | Out-Null
Write-Host "BACKUP_PATH=$($info.FullName)"
Write-Host "BACKUP_SIZE=$($info.Length)"

if ((Get-GitText @('rev-parse', 'HEAD')) -ne $ReleaseSha.ToLower()) {
  throw 'STOP Git HEAD changed unexpectedly before migrate'
}

Write-Host '=== PENDING ==='
$pend = Invoke-Mb035 'pending'
Write-Host $pend

Write-Host '=== MIGRATE ==='
$mig = & $Python -m memorybox migrate
Write-Host $mig
$migObj = $mig | ConvertFrom-Json
$applied = @($migObj.applied)
if ($applied.Count -ne 1 -or $applied[0] -ne '035_p2_i14_communications_lineage.sql') {
  throw "STOP unexpected migrate output: $mig"
}

Write-Host '=== VERIFY SCHEMA ==='
$verify = ($script:BaselineCounts | & $Python -m memorybox.ops.i14_migration_035 verify-schema)
if ($LASTEXITCODE -ne 0) { throw 'STOP schema verification failed' }
Write-Host $verify
Invoke-Mb035 'assert-ops-pack' | Out-Host
if ((Get-GitText @('rev-parse', 'HEAD')) -ne $ReleaseSha.ToLower()) {
  throw 'STOP Git HEAD changed during apply'
}

Write-Host '=== RESTART SERVE ==='
Stop-MbServe
Start-MbServe
$poll = Invoke-Mb035 -Action 'poll-health' -ArgList @($HealthUrl)
Write-Host $poll
$mail = Invoke-RestMethod 'http://127.0.0.1:8790/historian-capture/email-status'
$emailJson = $mail | ConvertTo-Json -Compress
$emailCheck = $emailJson | & $Python -m memorybox.ops.i14_migration_035 assert-email
if ($LASTEXITCODE -ne 0) { throw 'STOP historian-capture email-status failed' }
Write-Host $emailCheck
$sched = Invoke-RestMethod 'http://127.0.0.1:8790/admin/api/scheduled-services'
$schedCheck = ($sched | ConvertTo-Json -Depth 8 -Compress | & $Python -m memorybox.ops.i14_migration_035 assert-scheduled)
if ($LASTEXITCODE -ne 0) { throw 'STOP scheduled-services assertion failed' }
Write-Host $schedCheck
Invoke-Mb035 'assert-ops-pack' | Out-Host
Write-Host 'FINAL_GIT'
git -C $RepoRoot status --short
Write-Host "RELEASE_HEAD=$(Get-GitText @('rev-parse', 'HEAD')) BACKUP=$($info.FullName) SIZE=$($info.Length)"
Write-Host 'Done. No seed/backfill/ingest/Peggy/UI/task work was performed. Git HEAD was not changed by this script.'
