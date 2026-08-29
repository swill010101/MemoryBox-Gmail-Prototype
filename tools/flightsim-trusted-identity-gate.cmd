@echo off
REM FlightSim: Phase 1 trusted retrieve, then freeze FEV2, Gemma, Sol.
REM Do not merge PR 74 or PR 76. Stop on Phase 1 failure — do not widen matching.
cd /d C:\memorybox 2>nul
if not exist python.exe if not exist .git (
  cd /d C:\MemoryBox 2>nul
)
echo.
echo === migrate ===
python -m memorybox migrate
echo.
echo === trusted evidence pipeline (Phase 1 then 2) ===
python -m memorybox run-trusted-evidence-pipeline --person "Peggy George" --flightsim
echo.
echo If Phase 1 has no trusted peggo417, attest then re-run:
echo python -m memorybox attest-trusted-identity --person "Peggy George" --email peggo417@hotmail.com
echo python -m memorybox run-trusted-evidence-pipeline --person "Peggy George" --flightsim
echo.
echo Cloud Sol needs MEMORYBOX_CLOUD_LLM_BASE_URL + MEMORYBOX_CLOUD_LLM_API_KEY + MEMORYBOX_CLOUD_LLM_MODEL
echo Reports: docs\test-output\trusted-full-evidence-v2\PHASE1_*.json FEV2REPORT_*.json PIPELINE_*.json
