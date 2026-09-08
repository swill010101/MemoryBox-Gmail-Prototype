[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ExpectedReleaseSha,
    [Parameter(Mandatory=$true)][string]$ToolRelease,
    [string]$AdmissionId = 'f9aa45bc-d5b1-4608-bca1-61cfe9993aeb',
    [string]$ExpectedPlanSha = '99b8a8e93f0bfc7addb1eea05ae0c6e9705de9d0085cecfb0999281df04c59fe'
)

$ErrorActionPreference = 'Stop'
$modelSha = 'e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3'
$modelBytes = 101621760
$release = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$toolRoot = (Resolve-Path -LiteralPath $ToolRelease).Path
$python = Join-Path $toolRoot '.titanet-venv\Scripts\python.exe'
$model = Join-Path $toolRoot 'model\titanet-l.nemo'
$mediaRoot = 'P:\Photos\Home Videos'

function Require-LastExit([string]$message, [object[]]$output) {
    if ($LASTEXITCODE -ne 0) {
        foreach ($line in $output) { if ($null -ne $line) { Write-Host $line } }
        throw $message
    }
}

Push-Location $release
try {
    if ((git rev-parse HEAD).Trim().ToLowerInvariant() -ne $ExpectedReleaseSha.ToLowerInvariant()) { throw 'Release SHA mismatch.' }
    if (git status --porcelain) { throw 'Release is not clean; preserve it and stop.' }
    if (-not $env:MEMORYBOX_DATABASE_URL) { throw 'MEMORYBOX_DATABASE_URL is absent; use the configured FlightSim shell.' }
    if (-not (Test-Path -LiteralPath $python)) { throw 'The verified TitaNet Python environment is unavailable.' }
    if (-not (Test-Path -LiteralPath $model)) { throw 'The verified local TitaNet model is unavailable.' }
    if ((Get-Item -LiteralPath $model).Length -ne $modelBytes) { throw 'TitaNet model byte count mismatch.' }
    if ((Get-FileHash -LiteralPath $model -Algorithm SHA256).Hash.ToLowerInvariant() -ne $modelSha) { throw 'TitaNet model hash mismatch.' }
    if (-not (Test-Path -LiteralPath $mediaRoot)) { throw 'Configured media root is unavailable.' }
    $ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if (-not $ffmpeg) { $ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue }
    if (-not $ffmpeg) { throw 'ffmpeg is unavailable.' }

    $env:MEMORYBOX_RECOGNITION_DRAIN = '0'
    $env:MEMORYBOX_SPEECH_DRAIN = '0'
    Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue
    $output = & $python -B -m memorybox.processing.voice_pilot_cli check --id $AdmissionId --expected-plan-sha $ExpectedPlanSha --media-root $mediaRoot --model $model --ffmpeg $ffmpeg.Source --allow-stopped 2>&1
    Require-LastExit 'Stopped Eugene Patio pilot diagnostic failed.' $output
    $result = (($output | Where-Object { $_ -and $_.Trim() }) -join "`n") | ConvertFrom-Json
    if (-not $result.read_only -or -not $result.files_verified -or $result.model_execution_verified) { throw 'Stopped Eugene Patio pilot diagnostic did not remain read-only.' }
    [pscustomobject]@{
        ok = $true
        mode = 'stopped_admission_read_only_check'
        release_sha = $ExpectedReleaseSha.ToLowerInvariant()
        admission_id = $AdmissionId
        plan_sha256 = $ExpectedPlanSha.ToLowerInvariant()
        files_verified = $result.files_verified
        model_execution_verified = $result.model_execution_verified
        database_writes = $false
        private_audio_processed = $false
        admission_created = $false
    } | ConvertTo-Json
}
finally {
    Pop-Location
}