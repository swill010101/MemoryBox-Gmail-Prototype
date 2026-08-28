@echo off
REM FlightSim one-shot: address-centric email identity gate (Peggy / peggo417)
REM Stop after Gallery + Full-Evidence V2 — do NOT start historian summarization.
REM
REM Usage (from C:\memorybox or \\flightsim\memorybox):
REM   tools\flightsim-address-centric-gate.cmd
REM
setlocal
cd /d "%~dp0.."

echo ===== address-centric email gate (FlightSim) =====
echo branch: cursor/p2-i11a-address-centric-email-49da
echo.

git fetch origin
if errorlevel 1 goto :fail
git pull origin cursor/p2-i11a-address-centric-email-49da
if errorlevel 1 goto :fail

echo.
echo Restart MemoryBox services, then migrate + prove...
call ".\startmb.cmd" -Restart
if errorlevel 1 (
  echo WARNING: startmb -Restart returned %errorlevel% — continuing
)

python -m memorybox migrate
if errorlevel 1 goto :fail

python -m memorybox prove-address-centric-email-e2e --flightsim
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
