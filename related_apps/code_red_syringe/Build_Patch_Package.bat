@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a changed-files ZIP or folder onto this BAT, or run:
  echo py -3 code_red_syringe.py --replacements YOUR_CHANGED_FILES.zip --rpf YOUR_TARGET.rpf
  pause
  exit /b 1
)
py -3 code_red_syringe.py --replacements "%~1"
pause
