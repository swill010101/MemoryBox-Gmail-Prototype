@echo off
REM FlightSim one-shot: address-centric email identity gate (Peggy / peggo417)
REM Stop after Gallery + Full-Evidence V2 — do NOT start historian summarization.
REM
REM Usage (from C:\memorybox or \\flightsim\memorybox):
REM   tools\flightsim-address-centric-gate.cmd
REM
REM Env: startmb loads config\memorybox_app.env only inside PowerShell. This
REM script calls tools\flightsim-address-centric-prove.ps1 so migrate/prove use
REM the same DATABASE_URL as serve (Takeout archive), not silent ALLOW_DEV defaults.
REM
setlocal
cd /d "%~dp0.."
set BRANCH=cursor/p2-i11a-address-centric-email-49da

echo ===== address-centric email gate (FlightSim) =====
echo branch: %BRANCH%
echo.

git fetch origin %BRANCH%
if errorlevel 1 goto :fail
git checkout -B %BRANCH% origin/%BRANCH%
if errorlevel 1 (
  echo.
  echo CHECKOUT FAILED — working tree may be dirty. Either commit/stash local
  echo changes on FlightSim, or run:
  echo   git status
  echo   git stash push -m address-centric-gate-temp
  echo then re-run this script.
  goto :fail
)
git pull --ff-only origin %BRANCH%
if errorlevel 1 goto :fail
git rev-parse --short HEAD
echo.

echo Restart MemoryBox services, then migrate + prove...
call ".\startmb.cmd" -Restart
if errorlevel 1 (
  echo WARNING: startmb -Restart returned %errorlevel% — continuing
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0flightsim-address-centric-prove.ps1"
set PROVE_EXIT=%errorlevel%

echo.
echo ===== paste the ADDRESS_CENTRIC_GATE block above into the agent chat =====
echo need: "ok": true  and  "flightsim": true
echo file: docs\test-output\historian-full-evidence\peggy-v2\ADDRESS_CENTRIC_GATE.json
echo if prove failed, also paste ADDRESS_CENTRIC_FAILURE_DIAG.json when present
echo STOP — do not run historian summarization / OBSERVATION_EXTRACT
echo.
exit /b %PROVE_EXIT%

:fail
echo FAILED — fix git/migrate errors above, then re-run.
exit /b 1
