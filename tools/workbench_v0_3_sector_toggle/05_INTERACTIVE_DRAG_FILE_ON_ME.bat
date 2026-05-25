@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a file onto this BAT for interactive string replacement.
  pause
  exit /b 1
)
if not exist patched mkdir patched
py -3 codered_mod_workbench.py interactive "%~1" --outdir patched
explorer patched
pause
