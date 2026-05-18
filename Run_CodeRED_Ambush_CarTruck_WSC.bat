@echo off
setlocal
cd /d "%~dp0"
set PYTHON_CMD=py -3
where py >nul 2>nul
if errorlevel 1 set PYTHON_CMD=python
%PYTHON_CMD% tools\codered_ambush_cartruck_wsc.py %*
if errorlevel 1 (
  echo.
  echo Code RED Roadside Ambush CarTruck WSC patcher failed.
  echo Check the JSON/CSV reports beside your output if any were written.
  pause
  exit /b 1
)
endlocal
