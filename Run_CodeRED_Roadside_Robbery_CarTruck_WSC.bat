@echo off
setlocal
set PY=py -3
echo Using Python command: %PY%
%PY% "%~dp0tools\codered_roadside_robbery_cartruck_wsc.py" %*
if errorlevel 1 (
  echo.
  echo Code RED Roadside Robbery CarTruck WSC patcher failed.
  pause
)
