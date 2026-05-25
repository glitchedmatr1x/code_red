@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a file onto this BAT, or run: interactive_replace.bat path\to\file.wsc
  pause
  exit /b 1
)
py -3 codered_mod_workbench.py interactive "%~1" --outdir "%~dpn1_patched"
pause
