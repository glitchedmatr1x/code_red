@echo off
setlocal
cd /d "%~dp0"

set PYTHON_CMD=
where py >nul 2>nul
if %errorlevel%==0 set PYTHON_CMD=py -3
if not defined PYTHON_CMD (
  where python >nul 2>nul
  if %errorlevel%==0 set PYTHON_CMD=python
)
if not defined PYTHON_CMD (
  echo No Python runtime found. Install Python 3 and try again.
  pause
  exit /b 1
)

echo Using Python command: %PYTHON_CMD%
%PYTHON_CMD% tools\codered_wagonthief_cartruck_wsc.py %*
if errorlevel 1 (
  echo.
  echo Code RED WagonThief CarTruck WSC patcher failed.
  echo Check the JSON report beside your requested output, if one was written.
  pause
  exit /b 1
)
endlocal
