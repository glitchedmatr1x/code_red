@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a file onto this BAT to scan it.
  echo Example: drag medium_update_thread.wsc onto this file.
  pause
  exit /b 1
)
if not exist reports mkdir reports
set "OUT=reports\%~n1_scan"
echo Scanning: %~1
echo Report folder: %OUT%
py -3 codered_mod_workbench.py scan "%~1" --out "%OUT%"
echo.
echo Done. Opening summary if it exists...
if exist "%OUT%\summary.md" notepad "%OUT%\summary.md"
if exist "%OUT%" explorer "%OUT%"
pause
