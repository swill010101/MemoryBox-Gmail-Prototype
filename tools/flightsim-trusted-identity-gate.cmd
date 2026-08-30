@echo off
REM FlightSim: Phase 1 product report first, then freeze + Gemma/Sol.
REM Do not merge PR 74 or PR 76. Stop on Phase 1 failure — do not widen matching.
REM Self-sync onto origin tip like address-centric (no force-push, no merge).
setlocal
set BRANCH=cursor/p2-i11a-trusted-identity-retrieve-49da
set REPO_ROOT=%~dp0..
pushd "%REPO_ROOT%" 2>nul
if errorlevel 1 (
  cd /d C:\memorybox 2>nul
)
if not exist .git (
  cd /d C:\MemoryBox 2>nul
)
if exist ".git\MERGE_HEAD" git merge --abort
if exist ".git\REBASE_HEAD" git rebase --abort
if exist ".git\CHERRY_PICK_HEAD" git cherry-pick --abort
if exist ".git\rebase-merge" git rebase --abort
if exist ".git\rebase-apply" git rebase --abort
echo ===== sync origin/%BRANCH% =====
git fetch origin %BRANCH%
if errorlevel 1 (
  echo ERROR: git fetch failed — will not run Phase 2 on a stale tree.
  exit /b 1
)
git checkout -B %BRANCH% origin/%BRANCH%
if errorlevel 1 (
  echo ERROR: checkout %BRANCH% failed
  git status
  exit /b 1
)
git reset --hard origin/%BRANCH%
if errorlevel 1 (
  echo ERROR: hard reset failed
  exit /b 1
)
git rev-parse --short HEAD
echo.
REM Same as address-centric prove.ps1: P1=1 and no ALLOW_DEV so --flightsim
REM can stamp flightsim=true. Clearing ALLOW_DEV drops the :memory: Qdrant
REM default — set the startmb localhost URL when app.env did not export it.
set MEMORYBOX_P1_RUNTIME_HOST=1
set MEMORYBOX_ALLOW_DEV_DEFAULTS=
REM startmb loads app.env only in PowerShell. findstr leaves quotes/CR on keys.
if exist tools\export-memorybox-app-env.py (
  for /f "usebackq delims=" %%L in (`python tools\export-memorybox-app-env.py`) do %%L
)
if not defined MEMORYBOX_DATABASE_URL set MEMORYBOX_DATABASE_URL=postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox
if not defined MEMORYBOX_QDRANT_URL set MEMORYBOX_QDRANT_URL=http://127.0.0.1:6333
if not defined MEMORYBOX_OLLAMA_BASE_URL set MEMORYBOX_OLLAMA_BASE_URL=http://127.0.0.1:11434
echo hostname=%COMPUTERNAME%
echo MEMORYBOX_P1_RUNTIME_HOST=%MEMORYBOX_P1_RUNTIME_HOST%
echo ALLOW_DEV_DEFAULTS=%MEMORYBOX_ALLOW_DEV_DEFAULTS%
echo MEMORYBOX_QDRANT_URL=%MEMORYBOX_QDRANT_URL%
echo MEMORYBOX_OLLAMA_BASE_URL=%MEMORYBOX_OLLAMA_BASE_URL%
echo CLOUD_LLM_MODEL=%MEMORYBOX_CLOUD_LLM_MODEL%
if defined MEMORYBOX_CLOUD_LLM_BASE_URL (echo CLOUD_LLM_BASE_URL_SET=1) else (echo CLOUD_LLM_BASE_URL_SET=)
if defined MEMORYBOX_CLOUD_LLM_API_KEY (echo CLOUD_LLM_KEY_SET=1) else (echo CLOUD_LLM_KEY_SET=)
REM System32 powershell — PATH powershell.exe can be a WindowsApps stub (exit 0).
set PS_REAL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe
if not exist "%PS_REAL%" set PS_REAL=powershell.exe
set PROVE_PS1=%CD%\tools\flightsim-trusted-identity-prove.ps1
echo.
echo === migrate ===
"%PS_REAL%" -NoProfile -ExecutionPolicy Bypass -File "%PROVE_PS1%" -Step Migrate
call :deliver_evidence "evidence(flightsim): trusted-identity gate started"
echo.
echo === Phase 1 (reuse green FlightSim gate; otherwise prove) ===
REM verify-trusted-identity-gate.py via prove.ps1 — bare cmd python can be WindowsApps.
if exist docs\test-output\trusted-full-evidence-v2\TRUSTED_IDENTITY_GATE.json (
  "%PS_REAL%" -NoProfile -ExecutionPolicy Bypass -File "%PROVE_PS1%" -Step Phase1Verify
  if not errorlevel 1 (
    echo Phase 1 already PASS — skip archive prove so year-fair freeze / Gemma / Sol can start.
    goto phase2_freeze
  )
  echo Existing Phase 1 gate failed verifier — re-prove. Do not widen matching.
)
echo === Phase 1 prove (trusted retrieve + Gallery report) ===
"%PS_REAL%" -NoProfile -ExecutionPolicy Bypass -File "%PROVE_PS1%" -Step Phase1
if errorlevel 1 (
  echo.
  echo PHASE 1 FAILED — do not widen matching.
  echo If migrate/prove died on MEMORYBOX_QDRANT_URL, pull and re-run this gate.
  echo Do not re-attest for an env/Qdrant miss — product trust was already green.
  echo If peggo417 is on the profile but untrusted, re-add it on the People card
  echo or attest, then re-run prove only:
  echo python -m memorybox attest-trusted-identity --person "Peggy George" --email peggo417@hotmail.com
  echo python -m memorybox prove-trusted-identity-retrieval --flightsim
  exit /b 1
)
echo.
echo === Phase 1 FlightSim verifier (reject ALLOW_DEV / empty Gallery) ===
"%PS_REAL%" -NoProfile -ExecutionPolicy Bypass -File "%PROVE_PS1%" -Step Phase1Verify
if errorlevel 1 (
  echo PHASE 1 VERIFIER FAILED — do not run Gemma/Sol.
  exit /b 1
)
call :deliver_evidence "evidence(flightsim): trusted-identity Phase 1 gate"
:phase2_freeze
echo.
echo === Phase 2 preflight (Ollama Gemma + cloud Sol; commit even if missing) ===
"%PS_REAL%" -NoProfile -ExecutionPolicy Bypass -File "%PROVE_PS1%" -Step Preflight
call :deliver_evidence "evidence(flightsim): Phase 2 preflight"
echo.
echo === Phase 2 freeze (year-fair email + slim person; no calendar/story scan) ===
echo Commit before Gemma/Sol so a model timeout still leaves the fixture.
"%PS_REAL%" -NoProfile -ExecutionPolicy Bypass -File "%PROVE_PS1%" -Step Freeze
if errorlevel 1 (
  echo PHASE 2 FREEZE FAILED — do not run Gemma/Sol.
  echo If error is trusted_email_starved, paste the freeze JSON selected_email_count.
  exit /b 1
)
call :deliver_evidence "evidence(flightsim): trusted FEV2 freeze"
echo.
echo === Phase 2 pipeline (freeze, Gemma, Sol) ===
"%PS_REAL%" -NoProfile -ExecutionPolicy Bypass -File "%PROVE_PS1%" -Step Pipeline
if errorlevel 1 (
  echo TRUSTED EVIDENCE PIPELINE FAILED OR SKIPPED
  echo Paste the PHASE2_SUMMARY block printed above.
  echo If gemma error is ollama_model_missing: ollama pull gemma4:26b
  echo If sol error is cloud_sol_not_configured / no_sol_model: set MEMORYBOX_CLOUD_LLM_* in config\memorybox_app.env
  echo Phase 3 is not authorized. Do not run chunk compare or model-per-chunk.
  call :deliver_evidence "evidence(flightsim): pipeline stop (Phase 2 incomplete)"
  exit /b 1
)
"%PS_REAL%" -NoProfile -ExecutionPolicy Bypass -File "%PROVE_PS1%" -Step VerifyReports
if errorlevel 1 (
  echo TRUSTED FEV2 REPORTS FAILED
  call :deliver_evidence "evidence(flightsim): trusted FEV2 reports (verifier failed)"
  exit /b 1
)
call :deliver_evidence "evidence(flightsim): trusted FEV2 Gemma+Sol reports"
echo.
echo === Phase 2 complete. Phase 3 is not authorized. ===
echo Do not run chunk compare or model-per-chunk until Tom authorizes Phase 3.
echo Paste PHASE2_SUMMARY. Do not paste PHASE1_SUMMARY emails into cmd.
echo Cloud Sol needs MEMORYBOX_CLOUD_LLM_BASE_URL + MEMORYBOX_CLOUD_LLM_API_KEY + MEMORYBOX_CLOUD_LLM_MODEL
echo Reports: docs\test-output\trusted-full-evidence-v2\
goto :eof

:deliver_evidence
REM Commit verifier artifacts on this branch (no force-push) so PR #77 can see them.
set "EVIDENCE_MSG=%~1"
set "EVIDENCE_DIR=docs\test-output\trusted-full-evidence-v2"
if not exist "%EVIDENCE_DIR%" goto :eof
if exist "%EVIDENCE_DIR%\TRUSTED_IDENTITY_GATE.json" git add -- "%EVIDENCE_DIR%\TRUSTED_IDENTITY_GATE.json"
if exist "%EVIDENCE_DIR%\PHASE1_prove.json" git add -- "%EVIDENCE_DIR%\PHASE1_prove.json"
if exist "%EVIDENCE_DIR%\PHASE1_SUMMARY.txt" git add -- "%EVIDENCE_DIR%\PHASE1_SUMMARY.txt"
if exist "%EVIDENCE_DIR%\PHASE2_GATE_STARTED.txt" git add -- "%EVIDENCE_DIR%\PHASE2_GATE_STARTED.txt"
if exist "%EVIDENCE_DIR%\PHASE2_PREFLIGHT.json" git add -- "%EVIDENCE_DIR%\PHASE2_PREFLIGHT.json"
if exist "%EVIDENCE_DIR%\PHASE2_SUMMARY.txt" git add -- "%EVIDENCE_DIR%\PHASE2_SUMMARY.txt"
if exist "%EVIDENCE_DIR%\PHASE3_SUMMARY.txt" git add -- "%EVIDENCE_DIR%\PHASE3_SUMMARY.txt"
for %%F in ("%EVIDENCE_DIR%\FEV2REPORT_*.json") do if exist "%%F" git add -- "%%F"
for %%F in ("%EVIDENCE_DIR%\PIPELINE_*.json") do if exist "%%F" git add -- "%%F"
for %%F in ("%EVIDENCE_DIR%\FEV2_*.json") do if exist "%%F" git add -- "%%F"
for %%F in ("%EVIDENCE_DIR%\FEV2CHUNK_*.json") do if exist "%%F" git add -- "%%F"
git diff --cached --quiet
if not errorlevel 1 goto :eof
git commit -m "%EVIDENCE_MSG%"
if errorlevel 1 goto :eof
for /f "delims=" %%B in ('git rev-parse --abbrev-ref HEAD') do set "EVIDENCE_BR=%%B"
git fetch origin "%EVIDENCE_BR%"
git pull --rebase origin "%EVIDENCE_BR%"
if errorlevel 1 (
  echo WARNING: rebase before evidence push failed. Do not force-push. Paste summaries on PR 77.
  goto :eof
)
set PUSH_TRY=1
set PUSH_SLEEP=4
:evidence_push_retry
git push -u origin "%EVIDENCE_BR%"
if not errorlevel 1 goto evidence_push_ok
if %PUSH_TRY% GEQ 5 (
  echo WARNING: evidence commit not pushed. Paste PHASE1_SUMMARY / PHASE2_SUMMARY on PR 77.
  goto :eof
)
echo evidence push retry %PUSH_TRY% in %PUSH_SLEEP%s
timeout /t %PUSH_SLEEP% /nobreak >nul
set /a PUSH_TRY+=1
set /a PUSH_SLEEP*=2
goto evidence_push_retry
:evidence_push_ok
where gh >nul 2>nul
if not errorlevel 1 (
  REM PHASE1_SUMMARY lists untrusted emails (ed.cox@...). Never body-file or
  REM call that file — cmd can treat ed. as a command. Comment Phase 2 only.
  if exist "%EVIDENCE_DIR%\PHASE2_SUMMARY.txt" gh pr comment 77 --body-file "%EVIDENCE_DIR%\PHASE2_SUMMARY.txt"
)
goto :eof
