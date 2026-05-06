@echo off
setlocal
cd /d "%~dp0"
title Code RED Launcher

echo [Code RED] Starting from: %CD%

if exist "Code_RED.exe" (
  echo [Code RED] Launching Code_RED.exe
  start "" "Code_RED.exe"
  exit /b 0
)

if exist "Code RED.exe" (
  echo [Code RED] Launching Code RED.exe
  start "" "Code RED.exe"
  exit /b 0
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  if exist "run_workbench.py" (
    echo [Code RED] Launching run_workbench.py with py launcher
    py -3 run_workbench.py
    exit /b %ERRORLEVEL%
  )
  if exist "python_workbench.py" (
    echo [Code RED] run_workbench.py missing. Launching python_workbench.py with py launcher
    py -3 python_workbench.py
    exit /b %ERRORLEVEL%
  )
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  if exist "run_workbench.py" (
    echo [Code RED] Launching run_workbench.py with python
    python run_workbench.py
    exit /b %ERRORLEVEL%
  )
  if exist "python_workbench.py" (
    echo [Code RED] run_workbench.py missing. Launching python_workbench.py with python
    python python_workbench.py
    exit /b %ERRORLEVEL%
  )
)

echo [Code RED] Could not find a packaged EXE, run_workbench.py, or python_workbench.py.
echo [Code RED] Put this launcher in the same folder as Code RED's app files.
pause
exit /b 1
