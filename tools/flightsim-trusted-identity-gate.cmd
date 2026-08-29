@echo off
REM FlightSim: Phase 1 product report first, then freeze + Gemma/Sol.
REM Do not merge PR 74 or PR 76. Stop on Phase 1 failure — do not widen matching.
cd /d C:\memorybox 2>nul
if not exist python.exe if not exist .git (
  cd /d C:\MemoryBox 2>nul
)
echo.
echo === migrate ===
python -m memorybox migrate
echo.
echo === Phase 1 prove (trusted retrieve + Gallery report) ===
python -m memorybox prove-trusted-identity-retrieval --flightsim
if errorlevel 1 (
  echo.
  echo PHASE 1 FAILED — do not widen matching.
  echo If peggo417 is on the profile but untrusted:
  echo python -m memorybox attest-trusted-identity --person "Peggy George" --email peggo417@hotmail.com
  echo Then re-run this script.
  exit /b 1
)
echo.
echo === Phase 2/3 pipeline (single-pass freeze, Gemma, Sol) ===
python -m memorybox run-trusted-evidence-pipeline --person "Peggy George" --flightsim
echo.
echo Cloud Sol needs MEMORYBOX_CLOUD_LLM_BASE_URL + MEMORYBOX_CLOUD_LLM_API_KEY + MEMORYBOX_CLOUD_LLM_MODEL
echo Reports: docs\test-output\trusted-full-evidence-v2\
