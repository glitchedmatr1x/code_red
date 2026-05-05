@echo off
setlocal

rem Code RED Singleplayer Host launcher/install helper.
rem Run from anywhere after pulling Code_RED.

set REPO_ROOT=%~dp0..\..
pushd "%REPO_ROOT%" >nul

if "%~1"=="" (
  set GAME_ROOT=D:\Games\Red Dead Redemption
) else (
  set GAME_ROOT=%~1
)

echo # Code RED Singleplayer Host
echo Repo: %CD%
echo GameRoot: %GAME_ROOT%
echo.

echo [1/3] Building current ASI host...
powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_ScriptHookRDR_AI_Menu\build_ai_menu_asi_windows.ps1 -RepoRoot "."
if errorlevel 1 goto :fail

echo.
echo [2/3] Installing ASI host and data beside game executable...
powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_ScriptHookRDR_AI_Menu\install_ai_menu_asi_windows.ps1 -RepoRoot "." -GameRoot "%GAME_ROOT%"
if errorlevel 1 goto :fail

echo.
echo [3/3] Installing spawn-safe singleplayer data to avoid raw Car01/Truck01 crash path...
powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_ScriptHookRDR_AI_Menu\install_vehicle_first_menu_data_windows.ps1 -GameRoot "%GAME_ROOT%"
if errorlevel 1 goto :fail

echo.
echo Code RED Singleplayer Host is staged.
echo Launch the game, open menu with F8 or INSERT, and verify the footer is not / 413.
echo Safe expected roster: Roster 1-7 / 7.
echo.
popd >nul
exit /b 0

:fail
echo.
echo [ERROR] Singleplayer host setup failed. Check the messages above.
popd >nul
exit /b 1
