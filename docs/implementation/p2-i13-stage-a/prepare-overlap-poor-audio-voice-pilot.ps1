[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedReleaseSha,
    [string]$ToolRelease,
    [switch]$WritePlan
)

$ErrorActionPreference = 'Stop'
$modelSha = 'e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3'
$modelBytes = 101621760
$release = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$selection = Join-Path $PSScriptRoot 'overlap-poor-audio-voice-pilot-proposal.json'
if ($ToolRelease) { $toolRoot = (Resolve-Path -LiteralPath $ToolRelease).Path } else { $toolRoot = $release }
$model = Join-Path $toolRoot 'model\titanet-l.nemo'
$python = Join-Path $toolRoot '.titanet-venv\Scripts\python.exe'
$writtenPlan = Join-Path $release 'i13-reviewed-overlap-poor-audio-voice-pilot-plan.json'
$tempPlan = $null

function Require-LastExit([string]$message, [object[]]$output) {
    if ($LASTEXITCODE -ne 0) {
        foreach ($line in $output) { if ($null -ne $line) { Write-Host $line } }
        throw $message
    }
}

function Get-UnexpectedReleaseChanges {
    @(git status --porcelain | Where-Object {
        $line = $_.Trim()
        if ($line -match '^\?\?\s+i13-reviewed-.+-voice-pilot-plan\.json$') { return $false }
        return $true
    })
}

Push-Location $release
try {
    if ((git rev-parse HEAD).Trim().ToLowerInvariant() -ne $ExpectedReleaseSha.ToLowerInvariant()) {
        throw 'Release SHA mismatch.'
    }
    if (-not (Test-Path -LiteralPath $selection)) { throw 'Overlap pilot selection is missing.' }
    if (-not $env:MEMORYBOX_DATABASE_URL) { throw 'MEMORYBOX_DATABASE_URL is absent; use the configured FlightSim shell.' }
    if (-not (Test-Path -LiteralPath $python)) { throw 'The isolated TitaNet Python environment is unavailable.' }
    if (-not (Test-Path -LiteralPath $model)) { throw 'The verified local TitaNet model is unavailable.' }
    if ((Get-Item -LiteralPath $model).Length -ne $modelBytes) { throw 'TitaNet model byte count mismatch.' }
    if ((Get-FileHash -LiteralPath $model -Algorithm SHA256).Hash.ToLowerInvariant() -ne $modelSha) {
        throw 'TitaNet model hash mismatch.'
    }

    $unexpectedChanges = @(Get-UnexpectedReleaseChanges)
    if ($unexpectedChanges.Count -ne 0) {
        throw ('Release has unexpected changes; preserve it and stop. Unexpected: ' + ($unexpectedChanges -join ' | '))
    }

    $preflight = & $python -B (Join-Path $PSScriptRoot 'prepare-overlap-poor-audio-voice-pilot.py') 2>&1
    Require-LastExit 'Overlap pilot preflight failed.' $preflight

    if ($WritePlan) {
        if (Test-Path -LiteralPath $writtenPlan) { throw 'Overlap pilot plan path already exists; preserve it and stop.' }
        $outputPlan = $writtenPlan
    }
    else {
        $tempPlan = Join-Path ([System.IO.Path]::GetTempPath()) ("mb-i13-overlap-pilot-plan-$([guid]::NewGuid().ToString('N')).json")
        $outputPlan = $tempPlan
    }

    $prepared = & $python -B -m memorybox.processing.voice_pilot_cli prepare `
        --selection $selection --model $model --revision 'nvidia/nemo/titanet_large:v1' `
        --output $outputPlan --match-threshold 0.45 --uncertain-threshold 0.30 2>&1
    Require-LastExit 'Overlap pilot plan preparation failed.' $prepared
    $preparedJson = (($prepared | Where-Object { $_ -and $_.Trim() }) -join "`n") | ConvertFrom-Json
    if (-not $preparedJson.plan_sha256) { throw 'Prepared plan digest is missing.' }

    $preview = & $python -B -m memorybox.processing.control preview --plan $outputPlan 2>&1
    Require-LastExit 'Overlap pilot plan preview failed.' $preview
    $previewJson = (($preview | Where-Object { $_ -and $_.Trim() }) -join "`n") | ConvertFrom-Json
    if ($previewJson.purpose -ne 'voice_pilot' -or $previewJson.work_items -ne 4 -or $previewJson.max_attempts -ne 4 -or $previewJson.audio_seconds -ne 32.38) {
        throw 'Overlap pilot preview did not preserve the fixed bounded scope.'
    }

    [pscustomobject]@{
        ok = $true
        mode = if ($WritePlan) { 'plan_written_no_admission' } else { 'check_only' }
        release_sha = $ExpectedReleaseSha.ToLowerInvariant()
        plan_sha256 = $preparedJson.plan_sha256
        work_items = $previewJson.work_items
        audio_seconds = $previewJson.audio_seconds
        private_audio_processed = $false
        database_writes = $false
        admission_created = $false
        plan_file = if ($WritePlan) { $writtenPlan } else { $null }
        tool_release = $toolRoot
    } | ConvertTo-Json
}
finally {
    if ($tempPlan -and (Test-Path -LiteralPath $tempPlan)) { Remove-Item -LiteralPath $tempPlan -Force }
    Pop-Location
}
