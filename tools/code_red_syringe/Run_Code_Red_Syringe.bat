@echo off
setlocal
cd /d "%~dp0"
py -3 code_red_syringe.py --gui
if errorlevel 1 (
  echo.
  echo Python launcher failed. Trying python.exe...
  python code_red_syringe.py --gui
)
endlocal
