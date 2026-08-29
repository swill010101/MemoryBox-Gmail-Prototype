@echo off
REM Double-click or run from \\flightsim\memorybox
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0startmb.ps1" %*
