@echo off
setlocal

rem Code RED AI Menu setup launcher.
rem Double-click this from the Code_RED repo root.
rem It prepares actor enum data and a safe inline roster, then opens the Build Assistant.

pushd "%~dp0"

if not exist "tools\codered_rebuild_actor_enum_map.py" (
  echo [ERROR] Missing tools\codered_rebuild_actor_enum_map.py
  pause
  exit /b 1
)

if not exist "tools\codered_build_assistant.py" (
  echo [ERROR] Missing tools\codered_build_assistant.py
  pause
  exit /b 1
)

echo ============================================================
echo Code RED AI Menu Setup
echo ============================================================

echo [1/4] Rebuilding actor enum map and safe inline roster...
py -3 tools\codered_rebuild_actor_enum_map.py --write-inline-roster --safe-roster-only --replace
if errorlevel 1 goto :error

echo [2/4] Validating roster against actor enum map...
py -3 tools\codered_actor_enum_tool.py validate
if errorlevel 1 goto :error

echo [3/4] Writing resolved safe roster proof...
py -3 tools\codered_actor_enum_tool.py safe-roster --replace
if errorlevel 1 goto :error

if exist "tools\codered_ai_menu_layout_patch.py" (
  echo [4/4] Applying compact menu layout patch if needed...
  py -3 tools\codered_ai_menu_layout_patch.py --replace
  if errorlevel 1 goto :error
) else (
  echo [4/4] Compact layout patcher not found. Skipping layout patch.
)

echo.
echo Setup complete. Opening Build Assistant...
py -3 tools\codered_build_assistant.py gui
popd
endlocal
exit /b 0

:error
echo.
echo [ERROR] Setup stopped. Check the output above and logs\CodeRED_Actor_Enum_Rebuild_Report.json.
popd
pause
exit /b 1
