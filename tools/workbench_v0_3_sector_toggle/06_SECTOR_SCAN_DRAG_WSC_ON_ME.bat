@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a WSC/RSC85 file onto this batch file.
  pause
  exit /b 1
)
if not exist reports mkdir reports
py -3 codered_mod_workbench.py sector-scan "%~1" --out "reports\%~n1_sector_scan"
echo.
echo Report folder: reports\%~n1_sector_scan
pause
