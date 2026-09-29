# Read-only FlightSim host capture. Does not rewrite confirmation run directories.
# Run on FlightSim only. Does not call generate, Gemma, or Words of Life.
$ErrorActionPreference = "Continue"
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$repo = "C:\MemoryBox"
if (-not (Test-Path $repo)) { $repo = "C:\memorybox" }
Set-Location $repo
$out = Join-Path $repo "docs\test-output\i11a0-benchmark\gate3-b-i14-narration-quality-v03-27k-confirm\diagnostics\pre-reboot-onbox-$stamp"
New-Item -ItemType Directory -Force -Path $out | Out-Null

function Write-Json($name, $obj) {
    $obj | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $out $name) -Encoding utf8
}

$names = @("ollama.exe", "ollama app.exe", "llama-server.exe", "python.exe", "pythonw.exe")
$procs = Get-CimInstance Win32_Process | Where-Object {
    $n = $_.Name
    $names -contains $n -or ($n -and $n.ToLower() -match "ollama|llama-server|python")
}
$rows = foreach ($p in $procs) {
    $gp = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
    [pscustomobject]@{
        Name = $p.Name
        PID = $p.ProcessId
        ParentPID = $p.ParentProcessId
        CommandLine = $p.CommandLine
        ExecutablePath = $p.ExecutablePath
        CreationDate = $p.CreationDate
        KernelModeTime = $p.KernelModeTime
        UserModeTime = $p.UserModeTime
        WorkingSet = $p.WorkingSetSize
        PrivatePageCount = $p.PrivatePageCount
        PeakWorkingSet = $gp.PeakWorkingSet64
        CPUSeconds = $gp.CPU
    }
}
Write-Json "processes.json" $rows
Get-NetTCPConnection -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in 11434, 55964, 62518 -or $_.OwningProcess -in ($rows.PID) } |
    Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, State, OwningProcess |
    ConvertTo-Json | Set-Content (Join-Path $out "tcp.json") -Encoding utf8

$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
Write-Json "memory.json" @{
    hostname = $env:COMPUTERNAME
    TotalVisibleMemorySizeKB = $os.TotalVisibleMemorySize
    FreePhysicalMemoryKB = $os.FreePhysicalMemory
    TotalVirtualMemorySizeKB = $os.TotalVirtualMemorySize
    FreeVirtualMemoryKB = $os.FreeVirtualMemory
    SizeStoredInPagingFilesKB = $os.SizeStoredInPagingFiles
    FreeSpaceInPagingFilesKB = $os.FreeSpaceInPagingFiles
    CommitLimitBytes = $cs.TotalPhysicalMemory
}
try {
    $commit = Get-Counter '\Memory\Committed Bytes','\Memory\Commit Limit','\Paging File(_Total)\% Usage' -ErrorAction Stop
    Write-Json "commit_counters.json" ($commit.CounterSamples | ForEach-Object { @{ Path = $_.Path; CookedValue = $_.CookedValue } })
} catch { $_ | Out-File (Join-Path $out "commit_counters.error.txt") }

try {
    nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu,driver_version --format=csv | Out-File (Join-Path $out "nvidia-smi.csv") -Encoding utf8
    nvidia-smi | Out-File (Join-Path $out "nvidia-smi.txt") -Encoding utf8
} catch { $_ | Out-File (Join-Path $out "nvidia-smi.error.txt") }

try {
    Invoke-RestMethod http://127.0.0.1:11434/api/ps | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $out "api_ps.json") -Encoding utf8
    Invoke-RestMethod http://127.0.0.1:11434/api/version | ConvertTo-Json | Set-Content (Join-Path $out "api_version.json") -Encoding utf8
} catch { $_ | Out-File (Join-Path $out "api.error.txt") }

$start = Get-Date "2026-09-29 06:00"
$end = Get-Date "2026-09-29 10:00"
$filters = @(
    @{ log = "System"; file = "system_events.json" },
    @{ log = "Application"; file = "application_events.json" }
)
foreach ($f in $filters) {
    try {
        $ev = Get-WinEvent -FilterHashtable @{ LogName = $f.log; StartTime = $start; EndTime = $end } -ErrorAction SilentlyContinue |
            Where-Object {
                $_.ProviderName -match "Display|nvlddmkm|NVIDIA|Resource-Exhaustion|Application Hang|Application Error|Windows Error Reporting|Timeout|Ollama" -or
                $_.Id -in 26, 1001, 1000, 1026, 41, 7000, 7001, 7009, 7011 -or
                $_.Message -match "hang|crash|timeout|exhaust|nvlddmkm|Display driver"
            } |
            Select-Object TimeCreated, Id, ProviderName, LevelDisplayName, Message
        Write-Json $f.file $ev
    } catch { $_ | Out-File (Join-Path $out "$($f.file).error.txt") }
}
try {
    Get-WinEvent -FilterHashtable @{ LogName = "Microsoft-Windows-Resource-Exhaustion-Detector/Operational"; StartTime = $start } -ErrorAction SilentlyContinue |
        Select-Object TimeCreated, Id, Message |
        ConvertTo-Json | Set-Content (Join-Path $out "resource_exhaustion.json") -Encoding utf8
} catch { $_ | Out-File (Join-Path $out "resource_exhaustion.error.txt") }

"hostname=$env:COMPUTERNAME captured_utc=$stamp" | Set-Content (Join-Path $out "README.txt")
Write-Output $out
