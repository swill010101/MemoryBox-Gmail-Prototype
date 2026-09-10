#Requires -Version 5.1
<#
.SYNOPSIS
  FlightSim consolidated deploy + engineering proof for I13 Interactive Learn worker.
.NOTES
  Run on FlightSim ONLY (C:\MemoryBox). Window stays open; logs under proof root.
  Proof/backup root: E:\MemoryBox-backups if E: exists, else C:\MemoryBox-backups.
  Example:
    git fetch origin codex/p2-i13-stage-a
    git show origin/codex/p2-i13-stage-a:docs/implementation/p2-i13-stage-a/flightsim-deploy-i13-interactive-learn.ps1 |
      Set-Content -Encoding utf8 docs\implementation\p2-i13-stage-a\flightsim-deploy-i13-interactive-learn.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File docs\implementation\p2-i13-stage-a\flightsim-deploy-i13-interactive-learn.ps1
#>
param(
  [switch]$ProofOnly,
  [switch]$SkipDeploy,
  [switch]$SkipRestart,
  [string]$ProofRootBase = ''
)

$ErrorActionPreference = 'Stop'
$Branch       = 'codex/p2-i13-stage-a'
$AdmissionId  = '9e1cb49b-ec9d-40cb-ac34-7b3968d5af2a'
$DbUrl        = 'postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox'
$RepoRoot     = 'C:\MemoryBox'
$DeployScriptRel = 'docs/implementation/p2-i13-stage-a/flightsim-deploy-i13-interactive-learn.ps1'
$PreDeploySha = $null
$BackupFile   = $null
$script:Failed = $false
$script:FailReason = ''

function Resolve-ProofRootBase {
  param([string]$Override)
  if ($Override) { return $Override.TrimEnd('\') }
  foreach ($candidate in @('E:\MemoryBox-backups', 'C:\MemoryBox-backups', 'C:\MemoryBox\proof-output')) {
    $parent = Split-Path $candidate -Parent
    if (-not (Test-Path -LiteralPath $parent)) {
      try { New-Item -ItemType Directory -Force -Path $parent | Out-Null } catch { continue }
    }
    if (Test-Path -LiteralPath $parent) { return $candidate }
  }
  throw 'No writable proof root found (tried E:\MemoryBox-backups, C:\MemoryBox-backups, C:\MemoryBox\proof-output)'
}

$ProofRoot = Join-Path (Resolve-ProofRootBase -Override $ProofRootBase) "i13-interactive-learn-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
$LogFile   = Join-Path $ProofRoot 'deploy.log'

function Write-Log([string]$Message) {
  $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
  Write-Host $line
  Add-Content -LiteralPath $LogFile -Value $line -Encoding utf8
}

function Stop-Deploy([string]$Reason) {
  $script:Failed = $true
  $script:FailReason = $Reason
  Write-Log "STOP: $Reason"
  throw $Reason
}

function Invoke-Docker {
  param(
    [Parameter(Mandatory = $true)][string[]]$Args
  )
  Write-Log ("docker " + ($Args -join ' '))
  $out = & docker @Args 2>&1
  $code = $LASTEXITCODE
  if ($code -ne 0) {
    Stop-Deploy "docker failed ($code): docker $($Args -join ' ')`n$out"
  }
  return $out
}

function Invoke-Psql([string]$Sql) {
  return Invoke-Docker -Args @(
    'exec', 'memorybox-pg', 'psql', '-U', 'memorybox', '-d', 'memorybox', '-c', $Sql
  )
}

try {
  New-Item -ItemType Directory -Force -Path $ProofRoot | Out-Null
  Start-Transcript -LiteralPath (Join-Path $ProofRoot 'transcript.txt') -Force | Out-Null
  Write-Log "PROOF_ROOT=$ProofRoot"

  Set-Location $RepoRoot

  Write-Log 'Step 0: git preflight'
  $PreDeploySha = (git rev-parse HEAD).Trim()
  Write-Log "PRE_DEPLOY_SHA=$PreDeploySha"
  $PreDeploySha | Out-File -Encoding utf8 (Join-Path $ProofRoot 'PRE_DEPLOY_SHA.txt')
  # Bootstrap via `git checkout origin/... -- script` stages this file; unstage so preflight stays clean.
  git reset HEAD -- $DeployScriptRel 2>$null | Out-Null
  $Dirty = git status --porcelain | Where-Object { $_ -match '^[ MADRCU]' }
  $Dirty = @($Dirty | Where-Object { $_ -notmatch [regex]::Escape($DeployScriptRel) })
  if ($Dirty.Count -gt 0) {
    $Dirty | Out-File -Encoding utf8 (Join-Path $ProofRoot 'git_dirty_before.txt')
    Stop-Deploy @"
tracked FlightSim changes exist (see git_dirty_before.txt):
$($Dirty -join "`n")

Clean to PRE_DEPLOY_SHA, then re-run this script:
  cd C:\MemoryBox
  git reset --hard $PreDeploySha
  git status --short

If you need to keep staged WIP (e.g. marvin_capture), stash first:
  git stash push -u -m pre-i13-deploy-wip
"@
  }

  Write-Log 'Checking Docker'
  $names = Invoke-Docker -Args @('ps', '--format', '{{.Names}}')
  $nameList = @($names | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
  Write-Log ("docker ps: " + ($nameList -join ', '))
  if ($nameList -notcontains 'memorybox-pg') { Stop-Deploy 'memorybox-pg container not running' }

  $env:MEMORYBOX_DATABASE_URL = $DbUrl

  Write-Log 'Step 1: record pre-deploy DB state'
  $ownerLearnSql = @"
SELECT id::text, 'face' AS lane, video_external_id, video_provider_key, status, enqueue_reason
FROM recognition_queue_items
WHERE i13_admission_id = '$AdmissionId'::uuid AND enqueue_reason = 'owner_learn'
UNION ALL
SELECT id::text, 'voice', video_external_id, video_provider_key, status, enqueue_reason
FROM speech_queue_items
WHERE i13_admission_id = '$AdmissionId'::uuid AND enqueue_reason = 'owner_learn'
ORDER BY lane, video_external_id;
"@
  Invoke-Psql $ownerLearnSql | Out-File -Encoding utf8 (Join-Path $ProofRoot 'owner_learn_before.txt')

  Invoke-Psql "SELECT id::text, state, plan_json->>'scope_kind' AS scope_kind, interactive_learn_enabled FROM i13_processing_admissions WHERE id = '$AdmissionId'::uuid;" |
    Out-File -Encoding utf8 (Join-Path $ProofRoot 'admission_before.txt')

  Invoke-Psql "SELECT COUNT(*) AS archive_started_or_unlocked FROM i13_processing_admissions WHERE plan_json->>'scope_kind'='archive' AND state IN ('unlocked','started');" |
    Out-File -Encoding utf8 (Join-Path $ProofRoot 'archive_lock_before.txt')

  @{
    MEMORYBOX_RECOGNITION_DRAIN = $env:MEMORYBOX_RECOGNITION_DRAIN
    MEMORYBOX_SPEECH_DRAIN       = $env:MEMORYBOX_SPEECH_DRAIN
    MEMORYBOX_I13_ADMISSION_ID   = $env:MEMORYBOX_I13_ADMISSION_ID
  } | ConvertTo-Json | Out-File (Join-Path $ProofRoot 'drain_env_before.json')

  if ($ProofOnly) {
    Write-Log 'ProofOnly: stopping after pre-deploy capture'
  } else {
    Write-Log 'Step 2: PostgreSQL backup'
    $BackupFile = Join-Path $ProofRoot 'memorybox-pre-i13-interactive-learn.dump'
    Invoke-Docker -Args @('exec', 'memorybox-pg', 'pg_dump', '-U', 'memorybox', '-Fc', 'memorybox', '-f', '/tmp/pre-i13.dump') | Out-Null
    & docker cp memorybox-pg:/tmp/pre-i13.dump $BackupFile
    if ($LASTEXITCODE -ne 0) { Stop-Deploy 'docker cp backup failed' }
    Invoke-Docker -Args @('exec', 'memorybox-pg', 'rm', '-f', '/tmp/pre-i13.dump') | Out-Null
    $info = Get-Item -LiteralPath $BackupFile
    Write-Log "BACKUP_PATH=$($info.FullName) SIZE=$($info.Length) TIME=$($info.LastWriteTime)"
    if ($info.Length -lt 1000000) { Stop-Deploy "backup file too small: $($info.Length) bytes" }
    & docker cp $BackupFile memorybox-pg:/tmp/pre-i13-verify.dump
    if ($LASTEXITCODE -ne 0) { Stop-Deploy 'docker cp backup verify failed' }
    $verify = Invoke-Docker -Args @('exec', 'memorybox-pg', 'pg_restore', '-l', '/tmp/pre-i13-verify.dump')
    $verify | Select-Object -First 5 | Out-File (Join-Path $ProofRoot 'backup_verify.txt')
    Invoke-Docker -Args @('exec', 'memorybox-pg', 'rm', '-f', '/tmp/pre-i13-verify.dump') | Out-Null
    Write-Log 'backup verified via docker exec pg_restore -l'

    if (-not $SkipDeploy) {
      Write-Log 'Step 3: fetch and deploy exact commit'
      git fetch origin $Branch
      $ApprovedSha = (git rev-parse "origin/$Branch").Trim()
      Write-Log "APPROVED_SHA=$ApprovedSha"
      git checkout $Branch
      git merge --ff-only $ApprovedSha
      $Head = (git rev-parse HEAD).Trim()
      if ($Head -ne $ApprovedSha) { Stop-Deploy "HEAD=$Head expected $ApprovedSha" }
      Write-Log "FlightSim HEAD verified: $Head"
    }

    if (-not $SkipRestart) {
      Write-Log 'Step 4: restart serve with required env'
      $env:MEMORYBOX_I13_ADMISSION_ID  = $AdmissionId
      $env:MEMORYBOX_RECOGNITION_DRAIN = '0'
      $env:MEMORYBOX_SPEECH_DRAIN      = '0'
      $env:MEMORYBOX_DATABASE_URL      = $DbUrl
      & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot 'startmb.ps1') -Role serve -Restart
      Start-Sleep 20
    }

    Write-Log 'Step 5: engineering proof'
    $env:MEMORYBOX_I13_ADMISSION_ID  = $AdmissionId
    $env:MEMORYBOX_RECOGNITION_DRAIN = '0'
    $env:MEMORYBOX_SPEECH_DRAIN      = '0'
    $env:MEMORYBOX_DATABASE_URL      = $DbUrl

    $status = Invoke-RestMethod 'http://127.0.0.1:8790/admin/api/i13/status' -TimeoutSec 30
    $status | ConvertTo-Json -Depth 4 | Out-File (Join-Path $ProofRoot 'status_after.json')
    Write-Log "interactive_learn_worker_enabled=$($status.interactive_learn_worker_enabled)"

    1..12 | ForEach-Object {
      Start-Sleep 10
      $jobs = Invoke-RestMethod 'http://127.0.0.1:8790/admin/api/jobs' -TimeoutSec 30
      $all = @()
      if ($jobs.recognition) { $all += $jobs.recognition }
      if ($jobs.speech) { $all += $jobs.speech }
      $stranded = @($all | Where-Object { $_.enqueue_reason -eq 'owner_learn' -and $_.status -in @('queued','running') }).Count
      Write-Log "Poll $_ stranded owner_learn=$stranded"
      if ($stranded -eq 0) { break }
    }

    $jobsAfter = Invoke-RestMethod 'http://127.0.0.1:8790/admin/api/jobs' -TimeoutSec 30
    $jobsAfter | ConvertTo-Json -Depth 5 | Out-File (Join-Path $ProofRoot 'jobs_after.json')

    $ownerLearnAfterSql = @"
SELECT id::text, 'face' AS lane, video_external_id, status, enqueue_reason
FROM recognition_queue_items
WHERE i13_admission_id = '$AdmissionId'::uuid AND enqueue_reason = 'owner_learn'
UNION ALL
SELECT id::text, 'voice', video_external_id, status, enqueue_reason
FROM speech_queue_items
WHERE i13_admission_id = '$AdmissionId'::uuid AND enqueue_reason = 'owner_learn'
ORDER BY lane;
"@
    Invoke-Psql $ownerLearnAfterSql | Out-File -Encoding utf8 (Join-Path $ProofRoot 'owner_learn_after.txt')

    $env:MEMORYBOX_I13_LEARN_RECON_OUTPUT = Join-Path $ProofRoot 'learn-recon.json'
    $env:MEMORYBOX_I13_ADMISSION_ID = $AdmissionId
    $env:MEMORYBOX_RECOGNITION_DRAIN = '0'
    $env:MEMORYBOX_SPEECH_DRAIN = '0'
    & python -B (Join-Path $RepoRoot 'docs\implementation\p2-i13-stage-a\inspect-interactive-learn-reconciliation.py')
    Write-Log "INSPECTOR_EXIT=$LASTEXITCODE"
    if ($LASTEXITCODE -ne 0) { Stop-Deploy "reconciliation inspector failed with exit $LASTEXITCODE" }

    Write-Log 'DEPLOYMENT PROOF PASSED'
  }
} catch {
  if (-not $script:Failed) {
    Write-Log "ERROR: $($_.Exception.Message)"
    $script:FailReason = $_.Exception.Message
  }
  Write-Host ''
  Write-Host '=== DEPLOY FAILED ===' -ForegroundColor Red
  Write-Host $script:FailReason -ForegroundColor Red
  Write-Host "Log: $LogFile" -ForegroundColor Yellow
  Write-Host ''
  Write-Host 'Rollback (code only - does not reverse DB):' -ForegroundColor Cyan
  Write-Host '  cd C:\MemoryBox' -ForegroundColor Cyan
  if ($PreDeploySha) { Write-Host "  git checkout $PreDeploySha" -ForegroundColor Cyan }
  Write-Host '  then restart serve with pre-deploy env' -ForegroundColor Cyan
  if ($BackupFile) { Write-Host "DB backup: $BackupFile" -ForegroundColor Cyan }
} finally {
  try { Stop-Transcript | Out-Null } catch {}
  Write-Host ''
  Read-Host 'Press Enter to close this window'
}
