@echo off
setlocal
cd /d "%~dp0"
set PYTHON_CMD=py -3
%PYTHON_CMD% --version >nul 2>nul
if errorlevel 1 set PYTHON_CMD=python

echo Using Python command: %PYTHON_CMD%
%PYTHON_CMD% tools\codered_wsc_vehicle_replacer.py %*
if errorlevel 1 (
  echo.
  echo Code RED WSC Vehicle Replacer failed.
  echo If dependencies are missing, run install_wsc_vehicle_replacer_deps.bat.
  pause
  exit /b 1
)
