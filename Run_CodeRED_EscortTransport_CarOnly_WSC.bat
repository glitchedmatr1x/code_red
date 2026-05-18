@echo off
setlocal
set PYTHON_CMD=py -3
where py >nul 2>nul
if errorlevel 1 set PYTHON_CMD=python
%PYTHON_CMD% tools\codered_escort_transport_caronly_wsc.py %*
if errorlevel 1 (
  echo.
  echo Code RED Escort/Transport Car-Only WSC failed.
  echo Check the JSON/CSV reports beside your output if any were written.
  pause
)
endlocal
