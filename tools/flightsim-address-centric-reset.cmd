@echo off
REM Recover FlightSim working tree onto the address-centric tip.
REM Use when a plain "git pull origin <branch>" left merge CONFLICT markers,
REM or checkout is blocked. Does NOT delete gitignored config\*.env.
REM
REM Usage (from C:\memorybox):
REM   tools\flightsim-address-centric-reset.cmd
REM then:
REM   tools\flightsim-address-centric-gate.cmd
REM
setlocal
set BRANCH=cursor/p2-i11a-address-centric-email-49da
set REPO_ROOT=%~dp0..

pushd "%REPO_ROOT%"
if errorlevel 1 (
  echo ERROR: could not enter repo root from "%REPO_ROOT%"
  exit /b 1
)

echo ===== address-centric reset (FlightSim) =====
echo target: origin/%BRANCH%
echo cwd: %CD%
echo.

if exist ".git\MERGE_HEAD" (
  echo aborting merge...
  git merge --abort
)
if exist ".git\REBASE_HEAD" (
  echo aborting rebase...
  git rebase --abort
)
if exist ".git\CHERRY_PICK_HEAD" (
  echo aborting cherry-pick...
  git cherry-pick --abort
)
if exist ".git\rebase-merge" git rebase --abort
if exist ".git\rebase-apply" git rebase --abort

git fetch origin %BRANCH%
if errorlevel 1 (
  echo ERROR: git fetch failed
  popd
  exit /b 1
)

git checkout -B %BRANCH% origin/%BRANCH%
if errorlevel 1 (
  echo ERROR: checkout failed — git status:
  git status
  popd
  exit /b 1
)

git reset --hard origin/%BRANCH%
if errorlevel 1 (
  echo ERROR: hard reset failed
  popd
  exit /b 1
)

REM Drop untracked CONFLICT leftovers in known ops docs only if present as ?? 
REM Do not git clean -fdx — preserves config\memorybox_app.env / immich.env.

echo.
echo Ready on %BRANCH% at:
git rev-parse --short HEAD
git status -sb
echo.
echo Next: tools\flightsim-address-centric-gate.cmd
echo DO NOT: git pull origin %BRANCH% into some other local branch
echo.
popd
exit /b 0
