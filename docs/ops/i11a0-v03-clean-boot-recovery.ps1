# FlightSim only. After a normal reboot. One v0.3 27K Qwen B confirmation.
# Does not start Gemma, Words of Life, Docker Desktop, Cursor, or extra apps.
# Stops before inference if clean-boot gates fail. Does not retry on stop rules.
$ErrorActionPreference = "Stop"
if ($env:COMPUTERNAME -ne "FlightSim") {
    throw "this recovery script must run on FlightSim (got $($env:COMPUTERNAME))"
}
Set-Location C:\MemoryBox
if (-not (Test-Path "C:\MemoryBox")) { Set-Location "C:\memorybox" }

git fetch origin
git checkout cursor/p2-i11a0-offline-harness
git pull --ff-only origin cursor/p2-i11a0-offline-harness
$head = (git rev-parse HEAD).Trim()
$expected = "75f00afe6c5f11d98b5ac043339d5c5a41d0cbe3"
$okAncestor = $false
if ($head -eq $expected) { $okAncestor = $true }
else {
    git merge-base --is-ancestor $expected HEAD
    if ($LASTEXITCODE -eq 0) { $okAncestor = $true }
}
if (-not $okAncestor) {
    throw "HEAD $head is not $expected or a descendant; stop before inference"
}

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$diag = Join-Path (Get-Location) "docs\test-output\i11a0-benchmark\gate3-b-i14-narration-quality-v03-27k-confirm\diagnostics\clean-boot-$stamp"
New-Item -ItemType Directory -Force -Path $diag | Out-Null

function Save-Text($name, $text) { Set-Content -LiteralPath (Join-Path $diag $name) -Value $text -Encoding utf8 }

$llama = Get-Process llama-server -ErrorAction SilentlyContinue
if ($llama) {
    $llama | Format-List * | Out-String | Set-Content (Join-Path $diag "STOP-orphaned-llama-server.txt")
    throw "orphaned llama-server.exe present; stop before inference"
}

$env:MEMORYBOX_P1_RUNTIME_HOST = "1"
$ps = Invoke-RestMethod http://127.0.0.1:11434/api/ps
$ver = Invoke-RestMethod http://127.0.0.1:11434/api/version
$tags = Invoke-RestMethod http://127.0.0.1:11434/api/tags
$ps | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $diag "api_ps.json")
$ver | ConvertTo-Json | Set-Content (Join-Path $diag "api_version.json")
if ($ps.models -and $ps.models.Count -gt 0) {
    throw "a model is already loaded; stop before inference"
}

$os = Get-CimInstance Win32_OperatingSystem
$freeGb = [double]$os.FreePhysicalMemory / 1MB
$usedGb = ([double]$os.TotalVisibleMemorySize - [double]$os.FreePhysicalMemory) / 1MB
$totalGb = [double]$os.TotalVisibleMemorySize / 1MB
$smi = nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits
Save-Text "nvidia-smi.csv" $smi
$smiParts = ($smi -split ",") | ForEach-Object { $_.Trim() }
$gpuName = $smiParts[0]
$vramUsedGb = [double]$smiParts[2] / 1024.0
$digest = "304bf7349c71ad37a07eec8be67212b3f05b0f243f4a6f7c98e90dd2f3009f48"
$qwen = $tags.models | Where-Object { $_.name -eq "qwen3:14b-q8_0" } | Select-Object -First 1
$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match "ollama|llama-server|python" } |
    Select-Object Name, ProcessId, CommandLine, ExecutablePath, WorkingSetSize, PrivatePageCount, CreationDate
$procs | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $diag "processes.json") -Encoding utf8

$baseline = [ordered]@{
    hostname = $env:COMPUTERNAME
    ollama_version = $ver.version
    model_tag = "qwen3:14b-q8_0"
    model_digest = $qwen.digest
    ram_total_gb = $totalGb
    ram_used_gb = $usedGb
    ram_free_gb = $freeGb
    ram_commit_kb = $os.TotalVirtualMemorySize
    ram_free_virtual_kb = $os.FreeVirtualMemory
    page_file_size_kb = $os.SizeStoredInPagingFiles
    page_file_free_kb = $os.FreeSpaceInPagingFiles
    gpu_name = $gpuName
    vram_used_gb = $vramUsedGb
    gpu_util = $smiParts[3]
    git_branch = (git branch --show-current).Trim()
    git_commit = $head
    api_ps_models = $ps.models
}
$baseline | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $diag "baseline.json") -Encoding utf8

$problems = @()
if ($freeGb -lt 12) { $problems += "available_ram_below_12gb:$freeGb" }
if ($vramUsedGb -ge 3) { $problems += "idle_vram_not_below_3gb:$vramUsedGb" }
if ($gpuName -notmatch "4090") { $problems += "gpu_not_rtx_4090:$gpuName" }
if ($qwen.digest -ne $digest) { $problems += "digest_mismatch:$($qwen.digest)" }
if ($problems.Count -gt 0) {
    $problems | Set-Content (Join-Path $diag "STOP-gates.txt")
    throw ("clean-boot gates failed: " + ($problems -join "; "))
}

python -m memorybox prove-i11a0-benchmark
if ($LASTEXITCODE -ne 0) { throw "offline prove failed; inference not started" }

python -m memorybox i11a0-narration-quality-v03-confirm --confirm-benchmark --config docs/ops/i11a0.b.narration-quality-v03-27k.json --out docs/test-output/i11a0-benchmark/gate3-b-i14-narration-quality-v03-27k-confirm
$code = $LASTEXITCODE
Save-Text "confirm_exit_code.txt" "$code"
if ($code -ne 0) {
    Write-Warning "confirmation command exited $code (inspect run_record; do not retry here)"
}
