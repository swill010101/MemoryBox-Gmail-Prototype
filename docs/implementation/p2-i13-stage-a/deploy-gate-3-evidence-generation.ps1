[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedReleaseSha,
    [Parameter(Mandatory = $true)][string]$ReviewReference,
    [Parameter(Mandatory = $true)][string]$StartReference,
    [Parameter(Mandatory = $true)][string]$ExpectedPlanSha,
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
$release = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$python = (Get-Command python -ErrorAction Stop).Source
$plan = Join-Path $release 'docs/implementation/p2-i13-stage-a/bounded-manifest-proposal.json'
$backupRoot = 'C:\MemoryBox-backups'
$container = 'memorybox-pg'

function Require-LastExit([string]$message, [object[]]$output) {
    if ($LASTEXITCODE -ne 0) {
        foreach ($line in $output) { if ($null -ne $line) { Write-Host $line } }
        throw $message
    }
}
function Invoke-DbJson([string]$query) {
    $out = docker exec $container psql -X -q -A -t -U memorybox -d memorybox -v ON_ERROR_STOP=1 -c $query
    Require-LastExit 'Database read failed.' $out
    return (($out | Where-Object { $_ -and $_.Trim() }) -join '') | ConvertFrom-Json
}
function Snapshot-Counts {
    Invoke-DbJson @"
SELECT json_build_object(
  'migration', (SELECT max(version) FROM schema_migrations),
  'active_evidence_admissions', (
    SELECT count(*) FROM i13_processing_admissions
    WHERE plan_json->>'purpose' = 'evidence_generation'
      AND state IN ('registered', 'started')
  ),
  'recognition_queue', (SELECT count(*) FROM recognition_queue_items),
  'speech_queue', (SELECT count(*) FROM speech_queue_items),
  'words', (SELECT count(*) FROM speech_transcript_words),
  'versions', (SELECT count(*) FROM i13_transcript_versions),
  'annotations', (SELECT count(*) FROM i13_transcript_annotations)
);
"@
}

Push-Location $release
try {
    if ((git rev-parse HEAD).Trim().ToLowerInvariant() -ne $ExpectedReleaseSha.ToLowerInvariant()) {
        throw 'Release SHA mismatch.'
    }
    if (-not $ReviewReference.Trim() -or -not $StartReference.Trim()) {
        throw 'Review and start references are required.'
    }
    if (-not $env:MEMORYBOX_DATABASE_URL) {
        throw 'MEMORYBOX_DATABASE_URL is absent; use the configured FlightSim shell.'
    }
    if (-not (Test-Path -LiteralPath $plan)) {
        throw 'Reviewed Gate 3 plan is missing.'
    }

    $env:MEMORYBOX_RECOGNITION_DRAIN = '0'
    $env:MEMORYBOX_SPEECH_DRAIN = '0'
    Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue

    $preflight = & $python -B (Join-Path $PSScriptRoot 'prepare-gate-3-evidence-generation.py') 2>&1
    Require-LastExit 'Gate 3 preflight failed.' $preflight

    $preview = & $python -B -m memorybox.processing preview --plan $plan 2>&1
    Require-LastExit 'Gate 3 plan preview failed.' $preview
    $previewJson = (($preview | Where-Object { $_ -and $_.Trim() }) -join "`n") | ConvertFrom-Json
    if ($previewJson.purpose -ne 'evidence_generation' -or $previewJson.work_items -ne 22) {
        throw 'Gate 3 preview did not preserve the fixed 22-source transcription scope.'
    }
    if ($previewJson.plan_sha256 -ne $ExpectedPlanSha.ToLowerInvariant()) {
        throw 'Gate 3 plan hash mismatch.'
    }

    if (-not $Execute) {
        [pscustomobject]@{
            ok = $true
            mode = 'check_only'
            release_sha = $ExpectedReleaseSha.ToLowerInvariant()
            plan_sha256 = $previewJson.plan_sha256
            work_items = $previewJson.work_items
            expected_runtime = 'noop_transcribe_for_existing_words'
            database_writes = $false
            admission_created = $false
        } | ConvertTo-Json
        exit 0
    }

    docker inspect $container | Out-Null
    Require-LastExit 'memorybox-pg container is unavailable.' @()

    $before = Snapshot-Counts
    if ($before.migration -lt '030') { throw 'Migration 030+ must be present.' }
    if ($before.active_evidence_admissions -ne 0) { throw 'An evidence_generation admission is already active.' }

    $token = [guid]::NewGuid().ToString('N')
    $backupDir = Join-Path $backupRoot "i13-final-pre-gate-3-evidence-$token"
    $remoteDir = "/tmp/mb-i13-final-pre-gate-3-evidence-$token"
    New-Item -ItemType Directory -Path $backupDir -ErrorAction Stop | Out-Null
    docker exec $container mkdir $remoteDir
    Require-LastExit 'Container backup directory creation failed.' @()
    docker exec -e 'PGOPTIONS=-c default_transaction_read_only=on' $container pg_dump -U memorybox -d memorybox --format=custom --lock-wait-timeout=5000 --file="$remoteDir/memorybox.dump"
    Require-LastExit 'Fresh backup failed.' @()
    docker exec $container pg_restore --list "$remoteDir/memorybox.dump" | Out-Null
    Require-LastExit 'Fresh backup archive inspection failed.' @()
    $containerHash = ((docker exec $container sha256sum "$remoteDir/memorybox.dump") -split '\s+')[0]
    Require-LastExit 'Container backup hash failed.' @()
    $backupFile = Join-Path $backupDir 'memorybox.dump'
    docker cp "${container}:$remoteDir/memorybox.dump" $backupFile
    Require-LastExit 'Backup copy failed.' @()
    $backupHash = (Get-FileHash -LiteralPath $backupFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($backupHash -ne $containerHash) { throw 'Fresh backup hash mismatch.' }
    [pscustomobject]@{
        backup_file = $backupFile
        bytes = (Get-Item -LiteralPath $backupFile).Length
        sha256 = $backupHash
        container_hash_matches = $true
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backupDir 'backup-proof.json') -Encoding UTF8

    $planSha = $previewJson.plan_sha256
    $registered = & $python -B -m memorybox.processing register --plan $plan --review-ref $ReviewReference 2>&1
    Require-LastExit 'Gate 3 admission registration failed.' $registered
    $admission = (($registered | Where-Object { $_ -and $_.Trim() }) -join "`n") | ConvertFrom-Json
    if (-not $admission.id) { throw 'Admission identifier missing.' }
    $admissionId = $admission.id

    try {
        & $python -B -m memorybox.processing start --id $admissionId --reference $StartReference 2>&1 | Out-Null
        Require-LastExit 'Gate 3 admission start failed.' @()

        $env:MEMORYBOX_I13_ADMISSION_ID = $admissionId
        $env:MEMORYBOX_SPEECH_DRAIN = '0'

        $enqueue = & $python -B (Join-Path $PSScriptRoot 'run-gate-3-evidence-generation.py') enqueue 2>&1
        Require-LastExit 'Gate 3 enqueue failed.' $enqueue
        $enqueueJson = (($enqueue | Where-Object { $_ -and $_.Trim() }) -join "`n") | ConvertFrom-Json
        if ($enqueueJson.enqueued_or_updated -ne 22) {
            throw 'Expected 22 admitted transcribe queue updates.'
        }

        $processed = @()
        for ($i = 0; $i -lt 3; $i++) {
            $batch = & $python -B (Join-Path $PSScriptRoot 'run-gate-3-evidence-generation.py') process 2>&1
            Require-LastExit 'Gate 3 process batch failed.' $batch
            $batchJson = (($batch | Where-Object { $_ -and $_.Trim() }) -join "`n") | ConvertFrom-Json
            $processed += $batchJson.results
            $queued = [int]($batchJson.queue.by_status.queued)
            if ($queued -eq 0) { break }
        }

        $status = & $python -B (Join-Path $PSScriptRoot 'run-gate-3-evidence-generation.py') status 2>&1
        Require-LastExit 'Gate 3 queue status read failed.' $status
        $statusJson = (($status | Where-Object { $_ -and $_.Trim() }) -join "`n") | ConvertFrom-Json
        if ([int]($statusJson.queue.by_status.queued) -gt 0) {
            throw 'Admitted transcription queue still has queued items.'
        }
    }
    finally {
        $env:MEMORYBOX_SPEECH_DRAIN = '0'
        Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue
        & $python -B -m memorybox.processing stop --id $admissionId --reference "Tom-stopped-gate-3-evidence-generation-2026-09-08" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Admission stop failed; preserve output and halt manual operations.' }
    }

    $after = Snapshot-Counts
    foreach ($field in 'recognition_queue', 'words', 'versions', 'annotations') {
        if ($before.$field -ne $after.$field) {
            throw "Unexpected legacy count change: $field"
        }
    }

    [pscustomobject]@{
        ok = $true
        release_sha = $ExpectedReleaseSha.ToLowerInvariant()
        admission_id = $admissionId
        plan_sha256 = $planSha
        review_reference = $ReviewReference
        start_reference = $StartReference
        backup_file = $backupFile
        backup_sha256 = $backupHash
        enqueued = $enqueueJson.enqueued_or_updated
        processed_batches = $processed.Count
        queue_final = $statusJson.queue
        legacy_counts_unchanged = $true
        automatic_retry = $false
    } | ConvertTo-Json -Depth 8
}
finally {
    $env:MEMORYBOX_RECOGNITION_DRAIN = '0'
    $env:MEMORYBOX_SPEECH_DRAIN = '0'
    Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue
    Pop-Location
}
