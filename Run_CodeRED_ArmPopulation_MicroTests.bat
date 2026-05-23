@echo off
setlocal
cd /d "%~dp0"
set PYTHON_CMD=py -3
%PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 set PYTHON_CMD=python
%PYTHON_CMD% tools\codered_arm_population_microtests.py %*
if errorlevel 1 (
  echo.
  echo Code RED Arm Population Micro Tests failed.
  pause
  exit /b 1
)
