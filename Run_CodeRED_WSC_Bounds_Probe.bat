@echo off
setlocal
set PYTHON_EXE=py -3
%PYTHON_EXE% --version >nul 2>&1
if errorlevel 1 set PYTHON_EXE=python

echo Using Python command: %PYTHON_EXE%
%PYTHON_EXE% tools\codered_wsc_bounds_probe.py %*
if errorlevel 1 (
  echo.
  echo Code RED WSC Bounds Probe failed.
  pause
  exit /b 1
)
