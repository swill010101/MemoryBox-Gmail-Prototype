[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ExpectedReleaseSha,
    [Parameter(Mandatory=$true)][string]$ApprovalReference,
    [Parameter(Mandatory=$true)][string]$ExpectedPlanSha,
    [Parameter(Mandatory=$true)][string]$ToolRelease,
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
$modelSha = 'e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3'
$modelBytes = 101621760
$release = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$toolRoot = (Resolve-Path -LiteralPath $ToolRelease).Path
$model = Join-Path $toolRoot 'model\titanet-l.nemo'
$python = Join-Path $toolRoot '.titanet-venv\Scripts\python.exe'
$plan = Join-Path $release 'i13-reviewed-eugene-reprocessing-voice-pilot-plan.json'
$backupRoot = 'C:\MemoryBox-backups'
$container = 'memorybox-pg'
$mediaRoot = 'P:\Photos\Home Videos'

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
    Invoke-DbJson "SELECT json_build_object('migration',(SELECT max(version) FROM schema_migrations),'pilot_present',to_regclass('public.i13_voice_pilot_runs') IS NOT NULL,'active_voice_admissions',(SELECT count(*) FROM i13_processing_admissions WHERE plan_json->>'purpose'='voice_pilot' AND state IN ('registered','started')),'voice_admissions',(SELECT count(*) FROM i13_processing_admissions WHERE plan_json->>'purpose'='voice_pilot'),'voice_runs',(SELECT count(*) FROM i13_voice_pilot_runs),'voice_attempts',(SELECT count(*) FROM i13_voice_pilot_attempts),'voice_events',(SELECT count(*) FROM i13_voice_pilot_events),'voice_results',(SELECT count(*) FROM i13_voice_pilot_results),'recognition_queue',(SELECT count(*) FROM recognition_queue_items),'speech_queue',(SELECT count(*) FROM speech_queue_items),'words',(SELECT count(*) FROM speech_transcript_words),'versions',(SELECT count(*) FROM i13_transcript_versions),'annotations',(SELECT count(*) FROM i13_transcript_annotations),'tom_current',(SELECT stale FROM i13_voice_pilot_results WHERE admission_id='9e0a2605-8bfc-4ec7-aa6e-501f9bca7cea'::uuid),'n1_current',(SELECT stale FROM i13_voice_pilot_results WHERE admission_id='46cb1d21-b464-4bc4-bf7c-7d0de0202ca6'::uuid),'patio_current',(SELECT stale FROM i13_voice_pilot_results WHERE admission_id='f59050d5-cb4b-4ff7-beee-609b28f7af61'::uuid));"
}

Push-Location $release
try {
    if ((git rev-parse HEAD).Trim().ToLowerInvariant() -ne $ExpectedReleaseSha.ToLowerInvariant()) { throw 'Release SHA mismatch.' }
    $expectedPlanRelative = 'i13-reviewed-eugene-reprocessing-voice-pilot-plan.json'
    $unexpectedChanges = @(git status --porcelain | Where-Object { $_ -ne "?? $expectedPlanRelative" })
    if ($unexpectedChanges.Count -ne 0) { throw 'Release has unexpected changes; preserve it and stop.' }
    if (-not $ApprovalReference.Trim()) { throw 'Approval reference is required.' }
    if (-not $env:MEMORYBOX_DATABASE_URL) { throw 'MEMORYBOX_DATABASE_URL is absent; use the configured FlightSim shell.' }
    if (-not (Test-Path -LiteralPath $python)) { throw 'The verified TitaNet Python environment is unavailable.' }
    if (-not (Test-Path -LiteralPath $model)) { throw 'The verified local TitaNet model is unavailable.' }
    if ((Get-Item -LiteralPath $model).Length -ne $modelBytes) { throw 'TitaNet model byte count mismatch.' }
    if ((Get-FileHash -LiteralPath $model -Algorithm SHA256).Hash.ToLowerInvariant() -ne $modelSha) { throw 'TitaNet model hash mismatch.' }
    if (-not (Test-Path -LiteralPath $plan)) { throw 'Reviewed Eugene reprocessing pilot plan is missing.' }
    $preflight = & $python -B (Join-Path $PSScriptRoot 'prepare-eugene-reprocessing-voice-pilot.py') 2>&1
    Require-LastExit 'Eugene reprocessing pilot preflight failed.' $preflight
    $preview = & $python -B -m memorybox.processing.control preview --plan $plan
    Require-LastExit 'Eugene reprocessing pilot plan preview failed.' $preview
    $previewJson = (($preview | Where-Object { $_ -and $_.Trim() }) -join "`n") | ConvertFrom-Json
    if ($previewJson.purpose -ne 'voice_pilot' -or $previewJson.work_items -ne 4 -or $previewJson.max_attempts -ne 4 -or $previewJson.audio_seconds -ne 39.52) { throw 'Eugene reprocessing pilot preview did not preserve the fixed scope.' }
    if ($previewJson.plan_sha256 -ne $ExpectedPlanSha.ToLowerInvariant()) { throw 'Reviewed Eugene reprocessing pilot plan hash mismatch.' }
    if (-not $Execute) {
        [pscustomobject]@{ ok=$true; mode='check_only'; release_sha=$ExpectedReleaseSha.ToLowerInvariant(); plan_sha256=$previewJson.plan_sha256; migration='032_p2_i13_voice_pilot.sql already present'; private_audio_processed=$false; database_writes=$false; admission_created=$false } | ConvertTo-Json
        exit 0
    }
    if (-not (Test-Path -LiteralPath $mediaRoot)) { throw 'Configured media root is unavailable.' }
    docker inspect $container | Out-Null
    Require-LastExit 'memorybox-pg container is unavailable.' @()
    $ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if (-not $ffmpeg) { $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue }
    if (-not $ffmpeg) { throw 'ffmpeg is unavailable.' }
    $before = Snapshot-Counts
    if ($before.migration -ne '032' -or -not $before.pilot_present) { throw 'Migration 032 and pilot tables must already be present.' }
    if ($before.active_voice_admissions -ne 0) { throw 'An existing voice admission is active; preserve it and stop.' }
    if ($before.tom_current -or $before.n1_current -or $before.patio_current) { throw 'Current Tom, N1, or Patio pilot results must remain current before this lifecycle run.' }
    $token = [guid]::NewGuid().ToString('N')
    $backupDir = Join-Path $backupRoot "i13-final-pre-eugene-reprocessing-$token"
    $remoteDir = "/tmp/mb-i13-final-pre-eugene-reprocessing-$token"
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
    [pscustomobject]@{ backup_file=$backupFile; bytes=(Get-Item -LiteralPath $backupFile).Length; sha256=$backupHash; container_hash_matches=$true } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backupDir 'backup-proof.json') -Encoding UTF8

    $planSha = $previewJson.plan_sha256
    $registered = & $python -B -m memorybox.processing.control register --plan $plan --review-ref $ApprovalReference
    Require-LastExit 'Eugene reprocessing pilot admission registration failed.' $registered
    $admission = (($registered | Where-Object { $_ -and $_.Trim() }) -join "`n") | ConvertFrom-Json
    if (-not $admission.id) { throw 'Admission identifier missing.' }
    $admissionId = $admission.id
    try {
        & $python -B -m memorybox.processing.control start --id $admissionId --reference $ApprovalReference | Out-Null
        Require-LastExit 'Eugene reprocessing pilot admission start failed.' @()
        $run = & $python -B -m memorybox.processing.voice_pilot_cli run --id $admissionId --expected-plan-sha $planSha --media-root $mediaRoot --model $model --ffmpeg $ffmpeg.Source 2>&1
        Require-LastExit 'Eugene reprocessing pilot run failed; no automatic retry.' $run
        $runResult = (($run | Where-Object { $_ -and $_.Trim() }) -join "`n") | ConvertFrom-Json
    }
    finally {
        & $python -B -m memorybox.processing.control stop --id $admissionId --reference $ApprovalReference | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Admission stop failed; preserve output and stop manual operations.' }
    }
    $after = Snapshot-Counts
    foreach ($field in 'recognition_queue','speech_queue','words','versions','annotations') {
        if ($before.$field -ne $after.$field) { throw "Unexpected legacy count change: $field" }
    }
    if ($after.voice_admissions -ne ($before.voice_admissions + 1) -or $after.voice_runs -ne ($before.voice_runs + 1) -or $after.voice_attempts -ne ($before.voice_attempts + 4) -or $after.voice_events -lt ($before.voice_events + 2) -or $after.voice_results -ne ($before.voice_results + 1)) { throw 'Final Eugene reprocessing pilot verification failed.' }
    [pscustomobject]@{ ok=$true; release_sha=$ExpectedReleaseSha.ToLowerInvariant(); admission_id=$admissionId; plan_sha256=$planSha; backup_file=$backupFile; backup_sha256=$backupHash; results=$runResult.results; legacy_counts_unchanged=$true; tom_result_current=$true; n1_result_current=$true; patio_result_current=$true; private_audio_processed=$true; automatic_retry=$false } | ConvertTo-Json -Depth 8
}
finally {
    Pop-Location
}
