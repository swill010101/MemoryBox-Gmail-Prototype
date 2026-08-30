@echo off
REM FlightSim: Phase 1 product report first, then freeze + Gemma/Sol.
REM Do not merge PR 74 or PR 76. Stop on Phase 1 failure — do not widen matching.
cd /d C:\memorybox 2>nul
if not exist python.exe if not exist .git (
  cd /d C:\MemoryBox 2>nul
)
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
echo.
echo === migrate ===
python -m memorybox migrate
echo.
echo === Phase 1 prove (trusted retrieve + Gallery report) ===
python -m memorybox prove-trusted-identity-retrieval --flightsim
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
python tools\verify-trusted-identity-gate.py
if errorlevel 1 (
  echo PHASE 1 VERIFIER FAILED — do not run Gemma/Sol.
  exit /b 1
)
call :deliver_evidence "evidence(flightsim): trusted-identity Phase 1 gate"
echo.
echo === Phase 2 pipeline (freeze, Gemma, Sol) — stop before Phase 3 ===
python -m memorybox run-trusted-evidence-pipeline --person "Peggy George" --flightsim
if errorlevel 1 (
  echo TRUSTED EVIDENCE PIPELINE FAILED OR SKIPPED
  echo Paste the PHASE2_SUMMARY block printed above.
  echo If gemma error is ollama_model_missing: ollama pull gemma4:26b
  echo If sol error is cloud_sol_not_configured / no_sol_model: set MEMORYBOX_CLOUD_LLM_* in config\memorybox_app.env
  echo Phase 3 is not authorized. Do not run chunk compare or model-per-chunk.
  call :deliver_evidence "evidence(flightsim): pipeline stop (Phase 2 incomplete)"
  exit /b 1
)
python tools\verify-trusted-fev2-reports.py
if errorlevel 1 (
  echo TRUSTED FEV2 REPORTS FAILED
  call :deliver_evidence "evidence(flightsim): trusted FEV2 reports (verifier failed)"
  exit /b 1
)
call :deliver_evidence "evidence(flightsim): trusted FEV2 Gemma+Sol reports"
echo.
echo === Phase 3 chunk models (after Phase 2 verifier) ===
python -m memorybox run-trusted-fev2-chunked-models --from-dir docs\test-output\trusted-full-evidence-v2
if errorlevel 1 (
  echo PHASE 3 CHUNK MODELS FAILED
  echo Phase 2 reports above still stand. Re-run only chunk models, not Phase 1.
  echo python -m memorybox run-trusted-fev2-chunked-models --from-dir docs\test-output\trusted-full-evidence-v2
  exit /b 1
)
call :deliver_evidence "evidence(flightsim): trusted FEV2 + L1 chunk models"
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
  if exist "%EVIDENCE_DIR%\PHASE1_SUMMARY.txt" gh pr comment 77 --body-file "%EVIDENCE_DIR%\PHASE1_SUMMARY.txt"
  if exist "%EVIDENCE_DIR%\PHASE2_SUMMARY.txt" gh pr comment 77 --body-file "%EVIDENCE_DIR%\PHASE2_SUMMARY.txt"
  if exist "%EVIDENCE_DIR%\PHASE3_SUMMARY.txt" gh pr comment 77 --body-file "%EVIDENCE_DIR%\PHASE3_SUMMARY.txt"
)
goto :eof
