@echo off
setlocal
cd /d "%~dp0"
set PY_CMD=py -3
%PY_CMD% --version >nul 2>&1
if errorlevel 1 set PY_CMD=python
%PY_CMD% tools\codered_navres_battleset_scan.py %*
if errorlevel 1 (
  echo.
  echo Code RED Navres BattleSet scanner failed.
  pause
  exit /b 1
)
endlocal
