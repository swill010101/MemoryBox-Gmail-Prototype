# Marvin Capture - stop / start / restart (Windows PoC)
#
# Usage (from C:\memorybox):
#   .\scripts\deploy_marvin_capture.ps1              # restart (default)
#   .\scripts\deploy_marvin_capture.ps1 -Action status
#   .\scripts\deploy_marvin_capture.ps1 -Action stop
#   .\scripts\deploy_marvin_capture.ps1 -Action start
#   .\scripts\deploy_marvin_capture.ps1 -Action restart
#   .\scripts\deploy_marvin_capture.ps1 -Action restart -Pull:$false
#
# Default ports (PoC - vanity names later):
#   marvin-capture   8790
#   hvrt             8788   (stub only in this script)
#   ask              8787   (reserved)
#   mbd-demonstrator 8780   (reserved)

[CmdletBinding()]
param(
    [ValidateSet("status", "stop", "start", "restart")]
    [string]$Action = "restart",

    # Cursor-controlled: this deploy pulls the PR branch by default
    [bool]$Pull = $true,

    [string]$Branch = "cursor/marvin-capture-v01-3344",
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
    if (-not (Test-Path (Join-Path $RepoRoot "scripts\run_marvin_capture.py"))) {
        $RepoRoot = "C:\memorybox"
    }
}

$ServiceName = "marvin-capture"
$Port = 8790
$PidFile = Join-Path $RepoRoot "logs\$ServiceName.pid"
$LogFile = Join-Path $RepoRoot "logs\$ServiceName.out.log"
$ErrFile = Join-Path $RepoRoot "logs\$ServiceName.err.log"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$AppScript = Join-Path $RepoRoot "scripts\run_marvin_capture.py"

function Write-Info([string]$Msg) { Write-Host "[$ServiceName] $Msg" }

function Get-PortOwnerPid([int]$ListenPort) {
    $lines = netstat -ano | Select-String ":$ListenPort\s+.*LISTENING"
    $pids = @()
    foreach ($line in $lines) {
        if ($line -match "\s+(\d+)\s*$") {
            $pids += [int]$Matches[1]
        }
    }
    return ($pids | Select-Object -Unique)
}

function Get-TrackedPid {
    if (Test-Path $PidFile) {
        $raw = (Get-Content $PidFile -Raw).Trim()
        if ($raw -match "^\d+$") { return [int]$raw }
    }
    return $null
}

function Show-Status {
    $tracked = Get-TrackedPid
    $owners = @(Get-PortOwnerPid $Port)
    Write-Info "repo: $RepoRoot"
    Write-Info "port: $Port"
    Write-Info "pid file: $(if ($tracked) { $tracked } else { '(none)' })"
    if ($owners.Count -eq 0) {
        Write-Info "port $Port : free"
    } else {
        foreach ($procId in $owners) {
            try {
                $p = Get-Process -Id $procId -ErrorAction Stop
                Write-Info "port $Port held by PID $procId ($($p.ProcessName))"
            } catch {
                Write-Info "port $Port held by PID $procId (process gone?)"
            }
        }
    }
}

function Stop-ServiceInstance {
    $killed = @()
    $tracked = Get-TrackedPid
    if ($tracked) {
        try {
            Stop-Process -Id $tracked -Force -ErrorAction Stop
            $killed += $tracked
            Write-Info "stopped tracked PID $tracked"
        } catch {
            Write-Info "tracked PID $tracked not running"
        }
        Remove-Item $PidFile -ErrorAction SilentlyContinue
    }

    $owners = @(Get-PortOwnerPid $Port)
    foreach ($procId in $owners) {
        if ($killed -contains $procId) { continue }
        try {
            $p = Get-Process -Id $procId -ErrorAction Stop
            Write-Info "stopping port-$Port owner PID $procId ($($p.ProcessName))"
            Stop-Process -Id $procId -Force -ErrorAction Stop
            $killed += $procId
        } catch {
            Write-Info "could not stop PID $procId : $_"
        }
    }

    Start-Sleep -Seconds 1
    $left = @(Get-PortOwnerPid $Port)
    if ($left.Count -gt 0) {
        throw "port $Port still in use by PID(s): $($left -join ', ')"
    }
    Write-Info "port $Port is free"
}

function Update-Repo {
    if (-not $Pull) {
        Write-Info "skip git pull"
        return
    }
    Push-Location $RepoRoot
    try {
        Write-Info "git fetch / checkout $Branch / pull"
        git fetch origin $Branch
        git checkout $Branch
        git pull origin $Branch
    } finally {
        Pop-Location
    }
}

function Start-ServiceInstance {
    if (-not (Test-Path $Python)) {
        throw "venv python not found: $Python  (create with: python -m venv .venv)"
    }
    if (-not (Test-Path $AppScript)) {
        throw "missing $AppScript - are you on branch $Branch?"
    }

    $logsDir = Join-Path $RepoRoot "logs"
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

    $owners = @(Get-PortOwnerPid $Port)
    if ($owners.Count -gt 0) {
        Write-Info "port $Port still busy (PID $($owners -join ', ')) - forcing stop"
        foreach ($procId in $owners) {
            try {
                Stop-Process -Id $procId -Force -ErrorAction Stop
                Write-Info "force-stopped PID $procId"
            } catch {
                Write-Info "could not force-stop PID $procId : $_"
            }
        }
        Start-Sleep -Seconds 2
        $left = @(Get-PortOwnerPid $Port)
        if ($left.Count -gt 0) {
            throw "port $Port busy (PID $($left -join ', ')). Run -Action stop, then: taskkill /PID THE_PID /F"
        }
    }

    Write-Info "starting: $Python $AppScript --poll"
    $proc = Start-Process -FilePath $Python `
        -ArgumentList @($AppScript, "--poll") `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $LogFile `
        -RedirectStandardError $ErrFile `
        -PassThru `
        -WindowStyle Hidden

    $proc.Id | Set-Content -Path $PidFile -Encoding ascii

    $listenPid = $null
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Seconds 1
        if ($proc.HasExited) { break }
        $owners = @(Get-PortOwnerPid $Port)
        if ($owners.Count -gt 0) {
            $listenPid = $owners[0]
            break
        }
    }

    if ($proc.HasExited) {
        Write-Info "process exited early - last err log:"
        if (Test-Path $ErrFile) { Get-Content $ErrFile -Tail 40 }
        throw "marvin-capture failed to stay up (exit $($proc.ExitCode))"
    }

    if (-not $listenPid) {
        Write-Info "WARNING: process PID $($proc.Id) running but port $Port not listening yet"
        Write-Info "check logs: $LogFile / $ErrFile"
    } else {
        # Prefer the listener PID (uvicorn child may differ from Start-Process id)
        $listenPid | Set-Content -Path $PidFile -Encoding ascii
        $owners = @(Get-PortOwnerPid $Port)
        $strangers = @($owners | Where-Object { $_ -ne $listenPid -and $_ -ne $proc.Id })
        if ($strangers.Count -gt 0) {
            Write-Info "ERROR: extra process(es) on port $Port : $($strangers -join ', ')"
            Write-Info "killing start PID $($proc.Id) and refusing UP (old server still serving)"
            try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
            throw "port $Port contested by PID(s) $($strangers -join ', '). Kill them, then restart."
        }
        if ($listenPid -ne $proc.Id) {
            Write-Info "note: Start-Process PID $($proc.Id); listener PID $listenPid (pid file updated)"
        }
        Write-Info "UP - PID $listenPid listening on http://127.0.0.1:$Port/"
    }
    Write-Info "logs: $LogFile"
}

Write-Info "action=$Action pull=$Pull"
Show-Status

switch ($Action) {
    "status" { }
    "stop" { Stop-ServiceInstance; Show-Status }
    "start" {
        Update-Repo
        Start-ServiceInstance
        Show-Status
    }
    "restart" {
        Stop-ServiceInstance
        Update-Repo
        Start-ServiceInstance
        Show-Status
    }
}
