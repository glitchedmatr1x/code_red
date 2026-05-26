@echo off
setlocal
cd /d "%~dp0\.."
py -3 tools\codered_actor_enum_workbench.py %*
if errorlevel 1 (
  echo.
  echo CodeRED actor enum workbench failed with exit code %errorlevel%.
  exit /b %errorlevel%
)
