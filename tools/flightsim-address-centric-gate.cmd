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
REM Auto-deliver: posts gate to PR #74 via gh when available, and always pushes
REM gate artifacts to cursor/flightsim-address-centric-result-49da for the cloud agent.
REM
setlocal
cd /d "%~dp0.."
set BRANCH=cursor/p2-i11a-address-centric-email-49da
set RESULT_BRANCH=cursor/flightsim-address-centric-result-49da

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

set GATE_JSON=docs\test-output\historian-full-evidence\peggy-v2\ADDRESS_CENTRIC_GATE.json
set GATE_VERDICT=docs\test-output\historian-full-evidence\peggy-v2\ADDRESS_CENTRIC_VERDICT.txt
set GATE_FAIL=docs\test-output\historian-full-evidence\peggy-v2\ADDRESS_CENTRIC_FAILURE_DIAG.json

REM Auto-deliver to PR #74 when gh is authenticated — wakes the cloud agent.
where gh >nul 2>&1
if not errorlevel 1 (
  if exist "%GATE_JSON%" (
    echo.
    echo ===== posting gate to PR #74 via gh =====
    set COMMENT_FILE=%TEMP%\mb_address_centric_gate_pr_comment.md
    (
      echo ## FlightSim ADDRESS_CENTRIC_GATE
      echo.
      echo Branch: `%BRANCH%`
      echo.
      if exist "%GATE_VERDICT%" type "%GATE_VERDICT%"
      echo.
      echo ```json
      type "%GATE_JSON%"
      echo ```
      if exist "%GATE_FAIL%" if not "%PROVE_EXIT%"=="0" (
        echo.
        echo ### FAILURE_DIAG
        echo.
        echo ```json
        type "%GATE_FAIL%"
        echo ```
      )
    ) > "%TEMP%\mb_address_centric_gate_pr_comment.md"
    gh pr comment 74 --repo swill010101/MemoryBox-Gmail-Prototype --body-file "%TEMP%\mb_address_centric_gate_pr_comment.md"
    if errorlevel 1 (
      echo WARNING: gh pr comment failed — results-branch push still attempted.
    ) else (
      echo Posted to PR #74.
    )
  )
)

REM Always push gate artifacts to results branch (cloud agent fetches this).
if exist "%GATE_JSON%" (
  echo.
  echo ===== pushing gate to %RESULT_BRANCH% =====
  git fetch origin %RESULT_BRANCH% 2>nul
  git checkout -B %RESULT_BRANCH%
  if errorlevel 1 (
    echo WARNING: could not checkout results branch — paste gate manually.
  ) else (
    git add --force "%GATE_JSON%"
    if exist "%GATE_VERDICT%" git add --force "%GATE_VERDICT%"
    if exist "%GATE_FAIL%" git add --force "%GATE_FAIL%"
    git status --short
    git commit -m "flightsim: ADDRESS_CENTRIC_GATE from archive prove"
    git push -u origin %RESULT_BRANCH%
    if errorlevel 1 (
      echo WARNING: results-branch push failed — paste the gate manually.
    ) else (
      echo Pushed %RESULT_BRANCH%.
    )
    git checkout -B %BRANCH% origin/%BRANCH%
  )
)

echo.
echo ===== paste the ADDRESS_CENTRIC_GATE block above into the agent chat =====
echo need: "ok": true  and  "flightsim": true
echo file: %GATE_JSON%
echo verdict: %GATE_VERDICT%
if exist "%GATE_VERDICT%" (
  echo.
  type "%GATE_VERDICT%"
)
echo if prove failed, also paste ADDRESS_CENTRIC_FAILURE_DIAG.json when present
echo STOP — do not run historian summarization / OBSERVATION_EXTRACT
echo.
exit /b %PROVE_EXIT%

:fail
echo FAILED — fix git/migrate errors above, then re-run.
exit /b 1
