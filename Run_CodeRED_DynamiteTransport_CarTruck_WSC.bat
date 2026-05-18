@echo off
setlocal
set PYTHON_CMD=py -3
where py >nul 2>nul
if errorlevel 1 set PYTHON_CMD=python
%PYTHON_CMD% tools\codered_dynamite_transport_cartruck_wsc.py %*
if errorlevel 1 (
  echo.
  echo Code RED Dynamite/Transport CarTruck WSC tool failed.
  pause
  exit /b 1
)
