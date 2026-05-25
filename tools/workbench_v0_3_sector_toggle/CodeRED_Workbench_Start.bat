@echo off
setlocal
cd /d "%~dp0"
title Code RED Mod Workbench v0.3

echo ============================================================
echo   Code RED Mod Workbench v0.3
echo ============================================================
echo.
echo This menu does NOT patch your original file.
echo It saves copies in .\patched or reports in .\reports.
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" was not found.
  echo Install Python 3, then run this again.
  echo.
  pause
  exit /b 1
)

echo Checking required Python packages...
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Requirement install failed. You can still try the menu,
  echo but WSC/RSC85 decoding may not work without cryptography and zstandard.
  echo.
  pause
)

echo.
py -3 simple_menu.py

echo.
echo Menu closed.
pause
