@echo off
REM FlightSim: sync this branch, then prepare trusted email conversations.
REM No models. Never open an editor for a git commit message.
cd /d C:\memorybox 2>nul
if not exist .git (
  cd /d C:\MemoryBox 2>nul
)
set BRANCH=cursor/p2-i11a-trusted-identity-retrieve-49da
set GIT_MERGE_AUTOEDIT=no
set GIT_EDITOR=true
set GIT_SEQUENCE_EDITOR=true
echo ===== sync origin/%BRANCH% (preset commit message, no editor) =====
for /f %%B in ('git rev-parse --abbrev-ref HEAD') do set CUR_BR=%%B
if /I not "%CUR_BR%"=="%BRANCH%" (
  echo ERROR: checked out %CUR_BR% — expected %BRANCH%.
  echo Will not finish a merge or prepare on the wrong branch.
  git status
  exit /b 1
)
if exist ".git\MERGE_HEAD" (
  echo ERROR: in-progress merge on this tree. Will not commit --continue or prepare. Resolve or abort locally.
  git status
  exit /b 1
)
git fetch origin %BRANCH%
if errorlevel 1 (
  echo ERROR: git fetch failed — will not prepare on a stale tree.
  exit /b 1
)
git -c core.editor=true pull --rebase --no-edit origin %BRANCH%
if errorlevel 1 (
  echo ERROR: rebase not clean. Aborting rebase. Will not fall back to merge. Do not run Gemma.
  if exist ".git\REBASE_HEAD" git rebase --abort
  if exist ".git\rebase-merge" git rebase --abort
  if exist ".git\rebase-apply" git rebase --abort
  git status
  exit /b 1
)
git rev-parse HEAD
set MEMORYBOX_P1_RUNTIME_HOST=1
set MEMORYBOX_ALLOW_DEV_DEFAULTS=
if exist tools\export-memorybox-app-env.py (
  for /f "usebackq delims=" %%L in (`python tools\export-memorybox-app-env.py`) do %%L
)
if not defined MEMORYBOX_DATABASE_URL set MEMORYBOX_DATABASE_URL=postgresql://memorybox:memorybox@127.0.0.1:5432/memorybox
echo Preparing trusted email review. No Gemma. No Sol. No Phase 3.
python -m memorybox prepare-trusted-email-review --person "Peggy George" --flightsim
echo.
echo STOP. Open the MODEL_PASTE.txt path printed above. Do not git-add it. Do not run Gemma yet.
exit /b %ERRORLEVEL%
