@echo off
setlocal

rem Code RED Build Assistant launcher.
rem Double-click this from the Code_RED repo root.

set SCRIPT=%~dp0tools\codered_build_assistant.py

if not exist "%SCRIPT%" (
  echo [ERROR] Missing %SCRIPT%
  pause
  exit /b 1
)

py -3 "%SCRIPT%" gui
if errorlevel 1 (
  echo.
  echo [ERROR] CodeRED Build Assistant exited with an error.
  pause
  exit /b 1
)

endlocal
