#Requires -Version 5.1
<#
.SYNOPSIS
  Bounded FlightSim deploy of I14 migration 035 only.
.DESCRIPTION
  Authorized SHA 4c13f70aae0d18f217eec4dcf43a98e6b964b14d.
  Does not seed, backfill, ingest, merge evidence, run Peggy, change UI/Ask, or register tasks.
.PARAMETER PreflightOnly
  Read-only git/ledger/health/counts checks. No fetch, backup, migrate, or restart.
.PARAMETER Rollback
  Reverse a verified empty 035 apply after restoring the prior Git SHA.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [switch]$PreflightOnly,
  [switch]$Rollback,
  [string]$RepoRoot = '',
  [string]$HealthUrl = 'http://127.0.0.1:8790/health',
  [string]$PythonExe = ''
)

$ErrorActionPreference = 'Stop'
$RequiredPrior = '743c76712cb286ccdae3ad1108fb260dbd04770d'
$RequiredSha = '4c13f70aae0d18f217eec4dcf43a98e6b964b14d'
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
  # Documented FlightSim serve interpreter is the repo venv, not PATH python / startmb -Role serve.
  Start-Process -FilePath $py -ArgumentList @('-m', 'memorybox', 'serve') -WorkingDirectory $RepoRoot | Out-Null
}

function Get-UntrackedPaths {
  git -C $RepoRoot ls-files --others --exclude-standard
}

function Test-UntrackedCollisions([string]$TargetSha, [switch]$RequireTarget) {
  $untracked = @(Get-UntrackedPaths)
  Write-Host 'UNTRACKED_FILES'
  if ($untracked.Count -eq 0) { Write-Host '(none)' } else { $untracked | ForEach-Object { Write-Host $_ } }
  git -C $RepoRoot cat-file -e "$TargetSha^{commit}" 2>$null
  if ($LASTEXITCODE -ne 0) {
    if ($RequireTarget) { throw "STOP target SHA $TargetSha is not present locally" }
    Write-Host 'TARGET_SHA_NOT_LOCAL: listed untracked files; incoming-tree collision check deferred until fetch'
    return
  }
  $incoming = @(git -C $RepoRoot ls-tree -r --name-only $TargetSha)
  $hits = @()
  foreach ($path in $untracked) {
    $norm = ($path -replace '\\', '/').TrimStart('./')
    if ($incoming -contains $norm) { $hits += $norm }
  }
  if ($hits.Count -gt 0) {
    throw ("STOP untracked files collide with checkout paths: " + ($hits -join ', '))
  }
}

function Assert-GitCleanTracked {
  $dirty = git -C $RepoRoot status --porcelain --untracked-files=no
  if ($dirty) { throw "STOP tracked files dirty:`n$dirty" }
}

function Test-AllowedStartHead([string]$Head) {
  if ($Head -eq $RequiredPrior -or $Head -eq $RequiredSha) { return }
  git -C $RepoRoot merge-base --is-ancestor $RequiredSha $Head
  if ($LASTEXITCODE -eq 0) { return }
  throw "STOP unexpected HEAD=$Head expected prior $RequiredPrior, target $RequiredSha, or a descendant of the target"
}

Import-FlightSimEnv
$Python = Resolve-MbPython

Write-Host '=== GIT ==='
$head = (git -C $RepoRoot rev-parse HEAD).Trim()
$branch = (git -C $RepoRoot branch --show-current).Trim()
Write-Host "HEAD=$head"
Write-Host "BRANCH=$branch"
git -C $RepoRoot status --short
Assert-GitCleanTracked
Test-UntrackedCollisions $RequiredSha
Test-AllowedStartHead $head

if ($Rollback) {
  if (-not $PSCmdlet.ShouldProcess($RepoRoot, 'Rollback empty 035 and restore prior SHA')) { return }
  Write-Host '=== ROLLBACK ==='
  Stop-MbServe
  git -C $RepoRoot checkout -B codex/p2-i13-stage-a $RequiredPrior
  if ((git -C $RepoRoot rev-parse HEAD).Trim() -ne $RequiredPrior) { throw 'STOP rollback HEAD mismatch' }
  if (Test-Path -LiteralPath (Join-Path $RepoRoot "memorybox\migrations\$MigrationFile")) {
    throw 'STOP 035 still on disk after restoring prior SHA'
  }
  Invoke-Mb035 'rollback-empty-035'
  Start-MbServe
  Invoke-Mb035 -Action 'poll-health' -ArgList @($HealthUrl) | Out-Host
  $mail = Invoke-RestMethod 'http://127.0.0.1:8790/historian-capture/email-status'
  ($mail | ConvertTo-Json -Compress | & $Python -m memorybox.ops.i14_migration_035 assert-email) | Out-Host
  $sched = Invoke-RestMethod 'http://127.0.0.1:8790/admin/api/scheduled-services'
  ($sched | ConvertTo-Json -Depth 8 -Compress | & $Python -m memorybox.ops.i14_migration_035 assert-scheduled) | Out-Host
  git -C $RepoRoot status --short
  return
}

Write-Host '=== PREFLIGHT LEDGER ==='
$pre = Invoke-Mb035 'preflight-ledger'
Write-Host $pre
$health = Invoke-RestMethod $HealthUrl
if (-not $health.ok) { throw 'STOP health not ok before deploy' }
$preObj = $pre | ConvertFrom-Json
$script:BaselineCounts = $preObj.counts | ConvertTo-Json -Compress
Write-Host "BASELINE_COUNTS=$($script:BaselineCounts)"

if ($PreflightOnly -or $WhatIfPreference) {
  Write-Host 'PREFLIGHT_ONLY: no fetch, backup, migrate, or restart'
  git -C $RepoRoot status --short
  return
}

if (-not $PSCmdlet.ShouldProcess($RepoRoot, 'Backup, checkout 4c13f70, apply 035, restart serve')) { return }

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

Write-Host '=== CHECKOUT ==='
git -C $RepoRoot fetch origin
$originSha = (git -C $RepoRoot rev-parse origin/codex/p2-i14-communications).Trim()
if ($originSha -ne $RequiredSha) { throw "STOP origin SHA $originSha" }
Test-UntrackedCollisions $RequiredSha -RequireTarget
git -C $RepoRoot checkout -B codex/p2-i14-communications $RequiredSha
if ((git -C $RepoRoot rev-parse HEAD).Trim() -ne $RequiredSha) { throw 'STOP HEAD mismatch after checkout' }
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "memorybox\migrations\$MigrationFile"))) {
  throw 'STOP 035 file missing after checkout'
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
Write-Host 'FINAL_GIT'
git -C $RepoRoot status --short
Write-Host "PRIOR_OR_START=$head DEPLOYED=$((git -C $RepoRoot rev-parse HEAD).Trim()) BACKUP=$($info.FullName) SIZE=$($info.Length)"
Write-Host 'Done. No seed/backfill/ingest/Peggy/UI/task work was performed.'
