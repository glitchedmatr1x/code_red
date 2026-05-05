@echo off
setlocal
cd /d "%~dp0"

echo Code RED Faction Wars - Refresh Script Workshop + Scan
echo =======================================================
echo.

echo [1/2] Refreshing Script Workshop workspace...
py -3 related_apps\CodeRED_Script_Workshop\CodeRED_Script_Workshop.py scan --refresh
if errorlevel 1 (
  echo.
  echo [ERROR] Script Workshop refresh failed.
  exit /b 1
)

echo.
echo [2/2] Building Faction Wars target plan...
py -3 tools\codered_faction_wars_pipeline.py scan
if errorlevel 1 (
  echo.
  echo [ERROR] Faction Wars pipeline failed.
  exit /b 1
)

echo.
echo Done.
echo Review:
echo   research\faction_wars\FW_TARGET_PLAN.md
echo   logs\CodeRED_Faction_Wars_Pipeline_Report.md
echo   data\codered\faction_wars_targets.csv
echo.
endlocal
