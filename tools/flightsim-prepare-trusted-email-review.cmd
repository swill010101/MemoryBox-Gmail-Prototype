@echo off
REM FlightSim: prepare date-bounded trusted email conversations. No models.
cd /d C:\memorybox 2>nul
if not exist python.exe if not exist .git (
  cd /d C:\MemoryBox 2>nul
)
set MEMORYBOX_P1_RUNTIME_HOST=1
set MEMORYBOX_ALLOW_DEV_DEFAULTS=
if exist tools\export-memorybox-app-env.py (
  for /f "usebackq delims=" %%L in (`python tools\export-memorybox-app-env.py`) do %%L
)
if not defined MEMORYBOX_DATABASE_URL set MEMORYBOX_DATABASE_URL=postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox
echo Preparing trusted email review. No Gemma. No Sol. No Phase 3.
python -m memorybox prepare-trusted-email-review --person "Peggy George" --flightsim
echo.
echo STOP. Open the MODEL_PASTE.txt path printed above. Do not run Gemma yet.
exit /b %ERRORLEVEL%
