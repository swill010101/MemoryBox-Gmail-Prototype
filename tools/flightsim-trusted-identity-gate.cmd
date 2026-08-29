@echo off
REM FlightSim: Phase 1 product report first, then freeze + Gemma/Sol.
REM Do not merge PR 74 or PR 76. Stop on Phase 1 failure — do not widen matching.
cd /d C:\memorybox 2>nul
if not exist python.exe if not exist .git (
  cd /d C:\MemoryBox 2>nul
)
REM Same as address-centric prove.ps1: P1=1 and no ALLOW_DEV so --flightsim
REM can stamp flightsim=true. Product retrieve can be green while the
REM verifier rejects an ALLOW_DEV leftover from app.env / desktop session.
set MEMORYBOX_P1_RUNTIME_HOST=1
set MEMORYBOX_ALLOW_DEV_DEFAULTS=
if not defined MEMORYBOX_DATABASE_URL set MEMORYBOX_DATABASE_URL=postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox
echo hostname=%COMPUTERNAME%
echo MEMORYBOX_P1_RUNTIME_HOST=%MEMORYBOX_P1_RUNTIME_HOST%
echo ALLOW_DEV_DEFAULTS=%MEMORYBOX_ALLOW_DEV_DEFAULTS%
echo.
echo === migrate ===
python -m memorybox migrate
echo.
echo === Phase 1 prove (trusted retrieve + Gallery report) ===
python -m memorybox prove-trusted-identity-retrieval --flightsim
if errorlevel 1 (
  echo.
  echo PHASE 1 FAILED — do not widen matching.
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
