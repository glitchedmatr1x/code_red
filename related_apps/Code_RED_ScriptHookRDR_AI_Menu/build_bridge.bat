@echo off
setlocal

rem CodeRED ScriptHookRDR AI Menu build helper.
rem Run from the repository root in a Visual Studio Developer Command Prompt.

set OUTDIR=related_apps\Code_RED_ScriptHookRDR_AI_Menu\build
set SRC=related_apps\Code_RED_ScriptHookRDR_AI_Menu\CodeRED_AI_Menu.cpp
set OUT=%OUTDIR%\CodeRED_AI_Menu.asi

if not exist "%OUTDIR%" mkdir "%OUTDIR%"

where cl >nul 2>nul
if errorlevel 1 (
  echo [ERROR] cl.exe was not found.
  echo Open "x64 Native Tools Command Prompt for VS" or install Visual Studio Build Tools.
  exit /b 1
)

cl /std:c++17 /EHsc /LD /nologo "%SRC%" /Fe:"%OUT%" /link /OUT:"%OUT%"
if errorlevel 1 (
  echo [ERROR] Build failed.
  exit /b 1
)

echo.
echo Built: %OUT%
echo Copy CodeRED_AI_Menu.asi and CodeRED_AI_Menu.ini beside RDR.exe for testing.
endlocal
