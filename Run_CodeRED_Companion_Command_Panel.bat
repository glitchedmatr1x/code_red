@echo off
setlocal
cd /d "%~dp0"
py -3 tools\codered_companion_command_panel.py
if errorlevel 1 (
  echo.
  echo Code RED Companion Command Panel exited with an error.
  pause
)
