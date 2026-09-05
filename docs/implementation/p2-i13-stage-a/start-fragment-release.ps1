# Run from the exact reviewed release on FlightSim. Check-only unless -Start is supplied.
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedSha,
    [switch]$Start
)
$ErrorActionPreference = 'Stop'
$i13Release = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
$i13Python = 'C:\Users\tomwi\AppData\Local\Programs\Python\Python312\python.exe'
if (-not (Test-Path -LiteralPath $i13Python)) { throw 'Expected Python 3.12 executable missing.' }
if (-not $env:MEMORYBOX_DATABASE_URL -or -not $env:MEMORYBOX_QDRANT_URL) {
    throw 'Run in the configured FlightSim shell; database/Qdrant settings are missing. Do not paste credentials.'
}
$i13Head = git -C $i13Release rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $i13Head -ne $ExpectedSha) { throw 'Release commit mismatch.' }
$i13Status = git -C $i13Release status --porcelain
if ($LASTEXITCODE -ne 0 -or $i13Status) { throw 'Release worktree must be clean; preserve existing work.' }
Set-Location -LiteralPath $i13Release
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:MEMORYBOX_RECOGNITION_DRAIN = '0'
$env:MEMORYBOX_SPEECH_DRAIN = '0'
Remove-Item Env:MEMORYBOX_I13_ADMISSION_ID -ErrorAction SilentlyContinue
foreach ($i13Suite in @('test_i13_fragment_correction.py','test_i13_stage_a.py','test_i13_fragment_trace.py','test_i13_ask_context.py')) {
    & $i13Python -B -m unittest discover -s tests -p $i13Suite -v
    if ($LASTEXITCODE -ne 0) { throw "Tests failed: $i13Suite" }
}
$i13Args = @(
    '-B', (Join-Path $PSScriptRoot 'launch-locked.py'),
    '--runtime-root', 'C:\MemoryBox',
    '--expected-sha', $ExpectedSha,
    '--media-root', 'P:\Photos\Home Videos',
    '--derived-dir', 'C:\Users\tomwi\AppData\Local\Temp\memorybox_video_derived'
)
& $i13Python @i13Args
if ($LASTEXITCODE -ne 0) { throw 'Locked launcher check failed.' }
if (-not $Start) { Write-Host 'Checks passed. No service started. After review, rerun with -Start.'; return }
$i13Listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in @(8790,8791) })
if ($i13Listeners.Count) { throw 'Ports 8790/8791 must be clear. Close the existing app/worker consoles normally first.' }
function ConvertTo-I13Literal([string]$Value) { return "'" + $Value.Replace("'", "''") + "'" }
foreach ($i13Role in @('worker','app')) {
    $i13ChildArgs = $i13Args + @('--start','--role',$i13Role,'--deployment-reference',"Tom-reviewed-fragment-correction-$ExpectedSha")
    $i13Command = '& ' + (ConvertTo-I13Literal $i13Python) + ' ' + (($i13ChildArgs | ForEach-Object { ConvertTo-I13Literal $_ }) -join ' ')
    $i13Encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($i13Command))
    # Interactive consoles let Tom inspect startup and stop these services with Ctrl+C.
    Start-Process -FilePath 'powershell.exe' -WindowStyle Normal -WorkingDirectory $i13Release -ArgumentList @('-NoProfile','-NoExit','-EncodedCommand',$i13Encoded)
}
Write-Host 'App and worker launch requested. Verify both consoles and http://127.0.0.1:8790. Drains stay off.'
