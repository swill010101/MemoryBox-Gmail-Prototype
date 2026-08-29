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
if exist config\memorybox_app.env (
  if not defined MEMORYBOX_DATABASE_URL for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /b "MEMORYBOX_DATABASE_URL=" config\memorybox_app.env`) do set "MEMORYBOX_DATABASE_URL=%%B"
  if not defined MEMORYBOX_QDRANT_URL for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /b "MEMORYBOX_QDRANT_URL=" config\memorybox_app.env`) do set "MEMORYBOX_QDRANT_URL=%%B"
)
if not defined MEMORYBOX_DATABASE_URL set MEMORYBOX_DATABASE_URL=postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox
if not defined MEMORYBOX_QDRANT_URL set MEMORYBOX_QDRANT_URL=http://127.0.0.1:6333
echo hostname=%COMPUTERNAME%
echo MEMORYBOX_P1_RUNTIME_HOST=%MEMORYBOX_P1_RUNTIME_HOST%
echo ALLOW_DEV_DEFAULTS=%MEMORYBOX_ALLOW_DEV_DEFAULTS%
echo MEMORYBOX_QDRANT_URL=%MEMORYBOX_QDRANT_URL%
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
echo.
echo === Phase 2/3 pipeline (single-pass freeze, Gemma, Sol) ===
python -m memorybox run-trusted-evidence-pipeline --person "Peggy George" --flightsim
echo.
echo Cloud Sol needs MEMORYBOX_CLOUD_LLM_BASE_URL + MEMORYBOX_CLOUD_LLM_API_KEY + MEMORYBOX_CLOUD_LLM_MODEL
echo Reports: docs\test-output\trusted-full-evidence-v2\
