@echo off
setlocal
cd /d "%~dp0"
set PYTHON_CMD=
where py >nul 2>nul && set PYTHON_CMD=py -3
if "%PYTHON_CMD%"=="" where python >nul 2>nul && set PYTHON_CMD=python
if "%PYTHON_CMD%"=="" where python3 >nul 2>nul && set PYTHON_CMD=python3
if "%PYTHON_CMD%"=="" (
  echo ERROR: Python was not found. Install Python or run from an environment with py/python.
  pause
  exit /b 1
)
echo Using Python command: %PYTHON_CMD%
%PYTHON_CMD% tools\codered_car1194_wagonthief_wsc.py %*
if errorlevel 1 (
  echo.
  echo Code RED Car1194 WagonThief WSC failed.
  echo Check logs\car1194_wagonthief_wsc\crash.log if it exists.
  pause
  exit /b 1
)
endlocal
