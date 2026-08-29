@echo off
REM FlightSim: Phase 1 trusted-identity retrieve report. ASCII only.
REM Do not merge PR 74 or PR 76. Run from the repo root on this branch.
cd /d C:\memorybox 2>nul
if not exist python.exe if not exist .git (
  cd /d C:\MemoryBox 2>nul
)
echo.
echo === migrate ===
python -m memorybox migrate
echo.
echo === reclassify + report ===
python -m memorybox reclassify-trusted-identities --person "Peggy George"
echo.
echo === prove trusted identity ===
python -m memorybox prove-trusted-identity-retrieval --flightsim
echo.
echo If trusted peggo417 is missing, attest then re-run:
echo python -m memorybox attest-trusted-identity --person "Peggy George" --email peggo417@hotmail.com
echo python -m memorybox prove-trusted-identity-retrieval --flightsim
