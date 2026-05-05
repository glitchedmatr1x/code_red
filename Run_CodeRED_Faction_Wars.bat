@echo off
setlocal
cd /d "%~dp0"
echo Code RED Faction Wars Pipeline
echo.
py -3 tools\codered_faction_wars_pipeline.py scan
if errorlevel 1 (
  echo.
  echo [ERROR] Faction Wars pipeline failed.
  exit /b 1
)
echo.
echo Reports written under logs, data\codered, and research\faction_wars.
endlocal
