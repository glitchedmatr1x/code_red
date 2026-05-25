@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a file or zip onto this BAT, or run: scan_file.bat path\to\file.wsc
  pause
  exit /b 1
)
py -3 codered_mod_workbench.py scan "%~1" --out "%~dpn1_scan"
pause
