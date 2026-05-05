@echo off
setlocal
cd /d "%~dp0"

echo Code RED Faction Wars - Refresh + Broad Scan + Actionable Shortlist
echo =====================================================================
echo.

echo [1/3] Refreshing Script Workshop workspace...
py -3 related_apps\CodeRED_Script_Workshop\CodeRED_Script_Workshop.py scan --refresh
if errorlevel 1 (
  echo.
  echo [ERROR] Script Workshop refresh failed.
  exit /b 1
)

echo.
echo [2/3] Building broad Faction Wars target plan...
py -3 tools\codered_faction_wars_pipeline.py scan
if errorlevel 1 (
  echo.
  echo [ERROR] Faction Wars pipeline failed.
  exit /b 1
)

echo.
echo [3/3] Filtering actionable Faction Wars targets...
py -3 tools\codered_faction_wars_actionable_targets.py --limit 30
if errorlevel 1 (
  echo.
  echo [ERROR] Faction Wars actionable target filter failed.
  exit /b 1
)

echo.
echo Done.
echo Review first:
echo   research\faction_wars\FW_ACTIONABLE_TARGETS.md
echo Then review broad context:
echo   research\faction_wars\FW_TARGET_PLAN.md
echo   logs\CodeRED_Faction_Wars_Pipeline_Report.md
echo   data\codered\faction_wars_targets.csv
echo.
endlocal
