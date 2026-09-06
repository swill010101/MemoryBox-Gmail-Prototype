[CmdletBinding()]
param(
    [switch]$Execute,
    [Parameter(Mandatory=$true)][string]$ExpectedReleaseSha,
    [string]$ApprovalReference
)

$ErrorActionPreference = 'Stop'
$expectedSha = $ExpectedReleaseSha.ToLowerInvariant()
$modelSha = 'e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3'
$modelBytes = 101621760
$modelUrl = 'https://api.ngc.nvidia.com/v2/models/nvidia/nemo/titanet_large/versions/v1/files/titanet-l.nemo?redirect=true'
$release = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$model = Join-Path $release 'model\titanet-l.nemo'
$venv = Join-Path $release '.titanet-venv'
$python = Join-Path $venv 'Scripts\python.exe'
$selection = Join-Path $PSScriptRoot 'bounded-voice-pilot-proposal.json'
$plan = Join-Path $release 'i13-reviewed-voice-pilot-plan.json'
$backupRoot = 'C:\MemoryBox-backups'
$container = 'memorybox-pg'
$mediaRoot = 'P:\Photos\Home Videos'

function Require-LastExit([string]$Message) {
    if ($LASTEXITCODE -ne 0) { throw $Message }
}
function Invoke-DbJson([string]$Query) {
    $out = docker exec $container psql -X -q -A -t -U memorybox -d memorybox -v ON_ERROR_STOP=1 -c $Query
    Require-LastExit 'Database read failed.'
    return (($out | Where-Object { $_ -and $_.Trim() }) -join '') | ConvertFrom-Json
}
function Snapshot-Counts {
    return Invoke-DbJson "SELECT json_build_object('migration',(SELECT max(version) FROM schema_migrations),'pilot_present',to_regclass('public.i13_voice_pilot_runs') IS NOT NULL,'recognition_queue',(SELECT count(*) FROM recognition_queue_items),'speech_queue',(SELECT count(*) FROM speech_queue_items),'words',(SELECT count(*) FROM speech_transcript_words),'versions',(SELECT count(*) FROM i13_transcript_versions),'annotations',(SELECT count(*) FROM i13_transcript_annotations));"
}

Push-Location $release
try {
    if ((git rev-parse HEAD) -ne $expectedSha) { throw 'Release SHA mismatch.' }
    if (git status --porcelain) { throw 'Release is not clean; preserve it and stop.' }
    if (-not (Test-Path -LiteralPath $selection)) { throw 'Reviewed pilot selection is missing.' }
    if (-not $Execute) {
        [pscustomobject]@{ ok=$true; mode='check_only'; release_sha=$expectedSha; migration='032_p2_i13_voice_pilot.sql'; private_audio_processed=$false; instructions='Review the production-readiness report, then rerun with -Execute and a specific approval reference.' } | ConvertTo-Json
        exit 0
    }
    if (-not $ApprovalReference.Trim()) { throw 'ApprovalReference is required with -Execute.' }
    if (-not (Test-Path -LiteralPath $mediaRoot)) { throw 'Configured media root is unavailable.' }
    if (-not $env:MEMORYBOX_DATABASE_URL) { throw 'MEMORYBOX_DATABASE_URL is absent; use the configured FlightSim shell.' }
    docker inspect $container | Out-Null
    Require-LastExit 'memorybox-pg container is unavailable.'
    $ffmpegCmd = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if (-not $ffmpegCmd) { $ffmpegCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue }
    if (-not $ffmpegCmd) { throw 'ffmpeg is unavailable.' }

    if (-not (Test-Path -LiteralPath $python)) {
        $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($pyLauncher) {
            & $pyLauncher.Source -3.12 -m venv $venv
        }
        else {
            $python312 = 'C:\Users\tomwi\AppData\Local\Programs\Python\Python312\python.exe'
            if (-not (Test-Path -LiteralPath $python312)) { throw 'Python 3.12 is unavailable.' }
            & $python312 -m venv $venv
        }
        Require-LastExit 'Python 3.12 virtual environment creation failed.'
    }
    & $python -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot 'titanet-requirements.in')
    Require-LastExit 'Pinned TitaNet dependency installation failed.'
    New-Item -ItemType Directory -Path (Split-Path -Parent $model) -Force | Out-Null
    if (Test-Path -LiteralPath $model) {
        $existingHash = (Get-FileHash -LiteralPath $model -Algorithm SHA256).Hash.ToLowerInvariant()
        if ((Get-Item -LiteralPath $model).Length -ne $modelBytes -or $existingHash -ne $modelSha) {
            $rejected = "$model.rejected-$([guid]::NewGuid().ToString('N'))"
            Move-Item -LiteralPath $model -Destination $rejected
            Write-Output "Preserved invalid model response: $rejected"
        }
    }
    if (-not (Test-Path -LiteralPath $model)) {
        $download = "$model.partial-$([guid]::NewGuid().ToString('N'))"
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $modelUrl -OutFile $download
            if ((Get-Item -LiteralPath $download).Length -ne $modelBytes) { throw 'TitaNet model byte count mismatch.' }
            if ((Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash.ToLowerInvariant() -ne $modelSha) { throw 'TitaNet model hash mismatch.' }
            Move-Item -LiteralPath $download -Destination $model
        }
        catch {
            if (Test-Path -LiteralPath $download) {
                $rejected = "$download.rejected"
                Move-Item -LiteralPath $download -Destination $rejected
                Write-Output "Preserved failed model download: $rejected"
            }
            throw
        }
    }
    & $python -B -m memorybox.processing.titanet_smoke --model $model --sha256 $modelSha
    Require-LastExit 'Synthetic-only model smoke failed.'

    $before = Snapshot-Counts
    if ($before.migration -ne '031' -or $before.pilot_present) { throw 'Live schema is not the reviewed migration-031 state.' }
    $token = [guid]::NewGuid().ToString('N')
    $backupDir = Join-Path $backupRoot "i13-final-pre032-$token"
    $remoteDir = "/tmp/mb-i13-final-pre032-$token"
    New-Item -ItemType Directory -Path $backupDir -ErrorAction Stop | Out-Null
    docker exec $container mkdir $remoteDir
    Require-LastExit 'Container backup directory creation failed.'
    docker exec -e 'PGOPTIONS=-c default_transaction_read_only=on' $container pg_dump -U memorybox -d memorybox --format=custom --lock-wait-timeout=5000 --file="$remoteDir/memorybox.dump"
    Require-LastExit 'Fresh backup failed.'
    docker exec $container pg_restore --list "$remoteDir/memorybox.dump" | Out-Null
    Require-LastExit 'Fresh backup archive inspection failed.'
    $containerHash = ((docker exec $container sha256sum "$remoteDir/memorybox.dump") -split '\s+')[0]
    Require-LastExit 'Container backup hash failed.'
    $backupFile = Join-Path $backupDir 'memorybox.dump'
    docker cp "${container}:$remoteDir/memorybox.dump" $backupFile
    Require-LastExit 'Backup copy failed.'
    $backupHash = (Get-FileHash -LiteralPath $backupFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($backupHash -ne $containerHash) { throw 'Fresh backup hash mismatch.' }
    [pscustomobject]@{ backup_file=$backupFile; bytes=(Get-Item -LiteralPath $backupFile).Length; sha256=$backupHash; container_hash_matches=$true } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backupDir 'backup-proof.json') -Encoding UTF8

    $migration = Get-Content -LiteralPath (Join-Path $release 'memorybox\migrations\032_p2_i13_voice_pilot.sql') -Raw
    $migrationSql = "BEGIN; SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='120s'; DO `$`$ BEGIN IF (SELECT max(version) FROM schema_migrations) <> '031' OR to_regclass('public.i13_voice_pilot_runs') IS NOT NULL THEN RAISE EXCEPTION 'unexpected live schema'; END IF; END `$`$;`n" + $migration + "`nINSERT INTO schema_migrations(version,filename) VALUES('032','032_p2_i13_voice_pilot.sql'); COMMIT;`n"
    $migrationFile = Join-Path $backupDir 'apply-032.sql'
    Set-Content -LiteralPath $migrationFile -Value $migrationSql -Encoding UTF8
    Get-Content -LiteralPath $migrationFile -Raw | docker exec -i $container psql -X -q -U memorybox -d memorybox -v ON_ERROR_STOP=1
    Require-LastExit 'Migration 032 failed; do not retry automatically.'
    $afterMigration = Snapshot-Counts
    if ($afterMigration.migration -ne '032' -or -not $afterMigration.pilot_present) { throw 'Migration verification failed.' }
    foreach ($field in 'recognition_queue','speech_queue','words','versions','annotations') {
        if ($before.$field -ne $afterMigration.$field) { throw "Unexpected legacy count change: $field" }
    }

    if (Test-Path -LiteralPath $plan) { throw 'Pilot plan path already exists; stop without changing the reviewed plan.' }
    $prepared = & $python -B -m memorybox.processing.voice_pilot_cli prepare --selection $selection --model $model --revision 'nvidia/nemo/titanet_large:v1' --output $plan --match-threshold 0.45 --uncertain-threshold 0.30
    Require-LastExit 'Pilot plan preparation failed.'
    $planSha = (($prepared -join "`n") | ConvertFrom-Json).plan_sha256
    if (-not $planSha) { throw 'Pilot plan digest is missing.' }
    $register = & $python -B -m memorybox.processing.control register --plan $plan --review-ref $ApprovalReference
    Require-LastExit 'Admission registration failed.'
    $admission = ($register -join "`n") | ConvertFrom-Json
    if (-not $admission.id) { throw 'Admission identifier missing.' }
    $admissionId = $admission.id
    try {
        & $python -B -m memorybox.processing.control start --id $admissionId --reference $ApprovalReference
        Require-LastExit 'Admission start failed.'
        & $python -B -m memorybox.processing.voice_pilot_cli run --id $admissionId --expected-plan-sha $planSha --media-root $mediaRoot --model $model --ffmpeg $ffmpegCmd.Source
        Require-LastExit 'Pilot run failed; no automatic retry.'
    }
    finally {
        & $python -B -m memorybox.processing.control stop --id $admissionId --reference $ApprovalReference
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Admission stop failed; preserve output and stop manual operations.' }
    }
    $final = Invoke-DbJson "SELECT json_build_object('runs',(SELECT count(*) FROM i13_voice_pilot_runs),'attempts',(SELECT count(*) FROM i13_voice_pilot_attempts),'events',(SELECT count(*) FROM i13_voice_pilot_events),'results',(SELECT count(*) FROM i13_voice_pilot_results),'legacy_counts_unchanged',((SELECT count(*) FROM recognition_queue_items)=$($before.recognition_queue) AND (SELECT count(*) FROM speech_queue_items)=$($before.speech_queue) AND (SELECT count(*) FROM speech_transcript_words)=$($before.words) AND (SELECT count(*) FROM i13_transcript_versions)=$($before.versions) AND (SELECT count(*) FROM i13_transcript_annotations)=$($before.annotations)));"
    if ($final.runs -ne 1 -or $final.attempts -ne 4 -or $final.events -lt 2 -or -not $final.legacy_counts_unchanged) { throw 'Final pilot verification failed.' }
    [pscustomobject]@{ ok=$true; release_sha=$expectedSha; admission_id=$admissionId; backup_file=$backupFile; backup_sha256=$backupHash; final=$final; private_audio_processed=$true; automatic_retry=$false } | ConvertTo-Json -Depth 5
}
finally {
    Pop-Location
}
