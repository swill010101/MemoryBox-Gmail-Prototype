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
REM Auto-deliver: posts gate to PR #74 via gh when available, and always force-pushes
REM gate artifacts to cursor/flightsim-address-centric-result-49da for the cloud agent.
REM
setlocal
REM pushd maps UNC (\\flightsim\memorybox) to a drive letter; cd /d cannot.
pushd "%~dp0.."
if errorlevel 1 (
  echo ERROR: could not enter repo root from "%~dp0"
  echo Prefer a mapped path like C:\memorybox when running over UNC.
  goto :fail
)
set BRANCH=cursor/p2-i11a-address-centric-email-49da
set RESULT_BRANCH=cursor/flightsim-address-centric-result-49da

echo ===== address-centric email gate (FlightSim) =====
echo branch: %BRANCH%
echo cwd: %CD%
echo.

git fetch origin %BRANCH%
if errorlevel 1 goto :fail

REM Untracked gate artifacts from prior runs can block checkout; remove only those paths.
if exist "docs\test-output\historian-full-evidence\peggy-v2\ADDRESS_CENTRIC_GATE.json" (
  del /f /q "docs\test-output\historian-full-evidence\peggy-v2\ADDRESS_CENTRIC_GATE.json" 2>nul
)
if exist "docs\test-output\historian-full-evidence\peggy-v2\ADDRESS_CENTRIC_VERDICT.txt" (
  del /f /q "docs\test-output\historian-full-evidence\peggy-v2\ADDRESS_CENTRIC_VERDICT.txt" 2>nul
)
if exist "docs\test-output\historian-full-evidence\peggy-v2\ADDRESS_CENTRIC_FAILURE_DIAG.json" (
  del /f /q "docs\test-output\historian-full-evidence\peggy-v2\ADDRESS_CENTRIC_FAILURE_DIAG.json" 2>nul
)

REM Auto-stash tracked dirt so checkout succeeds. Do NOT use -u: keep
REM gitignored config\memorybox_app.env / immich.env on disk for startmb/prove.
set TRACKED_DIRTY=0
git diff --quiet
if errorlevel 1 set TRACKED_DIRTY=1
git diff --cached --quiet
if errorlevel 1 set TRACKED_DIRTY=1
if not "%TRACKED_DIRTY%"=="0" (
  echo ===== stashing tracked local changes (address-centric-gate-temp) =====
  git stash push -m "address-centric-gate-temp"
  if errorlevel 1 (
    echo WARNING: stash failed — trying checkout anyway
  ) else (
    echo Stashed. Restore later with: git stash list ^& git stash pop
  )
)

git checkout -B %BRANCH% origin/%BRANCH%
if errorlevel 1 (
  echo.
  echo CHECKOUT FAILED — working tree still blocked. Inspect:
  echo   git status
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

echo.
echo ===== ADDRESS_CENTRIC_GATE (paste into agent if auto-deliver fails) =====
if exist "%GATE_VERDICT%" (
  type "%GATE_VERDICT%"
  echo.
)
if exist "%GATE_JSON%" (
  echo ```json
  type "%GATE_JSON%"
  echo ```
) else (
  echo ERROR: gate JSON missing at %GATE_JSON%
)
if exist "%GATE_FAIL%" if not "%PROVE_EXIT%"=="0" (
  echo.
  echo === FAILURE_DIAG ===
  type "%GATE_FAIL%"
)
echo ===== end gate paste block =====
echo.

REM Always drop latest gate at repo root + Desktop for easy paste/upload.
if exist "%GATE_JSON%" (
  copy /Y "%GATE_JSON%" "ADDRESS_CENTRIC_GATE_LATEST.json" >nul
  if exist "%GATE_VERDICT%" copy /Y "%GATE_VERDICT%" "ADDRESS_CENTRIC_VERDICT_LATEST.txt" >nul
  if defined USERPROFILE (
    if exist "%USERPROFILE%\Desktop" (
      copy /Y "%GATE_JSON%" "%USERPROFILE%\Desktop\ADDRESS_CENTRIC_GATE.json" >nul 2>nul
      if exist "%GATE_VERDICT%" copy /Y "%GATE_VERDICT%" "%USERPROFILE%\Desktop\ADDRESS_CENTRIC_VERDICT.txt" >nul 2>nul
      echo Copied gate to Desktop and ADDRESS_CENTRIC_GATE_LATEST.json
    )
  )
  if exist "%GATE_VERDICT%" (
    echo Opening VERDICT in notepad for paste...
    start "" notepad.exe "%CD%\ADDRESS_CENTRIC_VERDICT_LATEST.txt"
  )
)

REM Auto-deliver to PR #74 when gh is authenticated — wakes the cloud agent.
where gh >nul 2>&1
if not errorlevel 1 (
  if exist "%GATE_JSON%" (
    echo ===== posting gate to PR #74 via gh =====
    (
      echo ## FlightSim ADDRESS_CENTRIC_GATE
      echo.
      echo Branch: `%BRANCH%`
      echo Host: `%COMPUTERNAME%`
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
    set GH_POSTED=0
    gh pr comment 74 --repo swill010101/MemoryBox-Gmail-Prototype --body-file "%TEMP%\mb_address_centric_gate_pr_comment.md"
    if not errorlevel 1 set GH_POSTED=1
    if "%GH_POSTED%"=="0" (
      echo WARNING: gh pr comment failed — trying issues API...
      gh api repos/swill010101/MemoryBox-Gmail-Prototype/issues/74/comments -F body=@"%TEMP%\mb_address_centric_gate_pr_comment.md"
      if not errorlevel 1 set GH_POSTED=1
    )
    if "%GH_POSTED%"=="1" (
      echo Posted to PR #74.
    ) else (
      echo WARNING: gh PR comment failed — results-branch push still attempted.
    )
  )
)

REM Always force-push gate artifacts to results branch (disposable delivery branch;
REM re-runs reset history from feature tip so non-FF push would otherwise fail).
if exist "%GATE_JSON%" (
  echo.
  echo ===== force-pushing gate to %RESULT_BRANCH% =====
  git fetch origin %RESULT_BRANCH% 2>nul
  git checkout -B %RESULT_BRANCH%
  if errorlevel 1 (
    echo WARNING: could not checkout results branch — paste gate manually from above.
  ) else (
    git add --force "%GATE_JSON%"
    if exist "%GATE_VERDICT%" git add --force "%GATE_VERDICT%"
    if exist "%GATE_FAIL%" git add --force "%GATE_FAIL%"
    git status --short
    git diff --cached --quiet
    if errorlevel 1 (
      git commit -m "flightsim: ADDRESS_CENTRIC_GATE from archive prove"
    ) else (
      echo No staged changes vs index — amending empty tip with --allow-empty so push refreshes.
      git commit --allow-empty -m "flightsim: ADDRESS_CENTRIC_GATE refresh"
    )
    git push -u origin %RESULT_BRANCH% --force
    if errorlevel 1 (
      echo WARNING: results-branch force-push failed — paste the gate manually from above.
    ) else (
      echo Pushed %RESULT_BRANCH% (force).
    )
    git checkout -B %BRANCH% origin/%BRANCH%
    if errorlevel 1 (
      echo WARNING: could not return to %BRANCH% — check git status on FlightSim.
    )
  )
)

echo.
echo need: "ok": true  and  "flightsim": true
echo file: %GATE_JSON%
echo STOP — do not run historian summarization / OBSERVATION_EXTRACT
echo.
popd
exit /b %PROVE_EXIT%

:fail
echo FAILED — fix git/migrate errors above, then re-run.
popd 2>nul
exit /b 1
