@echo off
setlocal

rem CodeRED DualGunLab build helper.
rem Run from the repository root in a Visual Studio x64 Native Tools Command Prompt.

set OUTDIR=related_apps\Code_RED_ScriptHookRDR_DualGunLab\build
set SRC=related_apps\Code_RED_ScriptHookRDR_DualGunLab\CodeRED_DualGunLab.cpp
set OUT=%OUTDIR%\CodeRED_DualGunLab.asi
set OBJ=%OUTDIR%\CodeRED_DualGunLab.obj
set PDB=%OUTDIR%\CodeRED_DualGunLab.pdb
set IMPLIB=%OUTDIR%\CodeRED_DualGunLab.lib

if not exist "%OUTDIR%" mkdir "%OUTDIR%"

where cl >nul 2>nul
if errorlevel 1 (
  echo [ERROR] cl.exe was not found.
  echo Open "x64 Native Tools Command Prompt for VS" or install Visual Studio Build Tools.
  exit /b 1
)

cl /std:c++17 /EHsc /LD /nologo "%SRC%" /Fo"%OBJ%" /Fd"%PDB%" /Fe"%OUT%" /link /OUT:"%OUT%" /IMPLIB:"%IMPLIB%"
if errorlevel 1 (
  echo [ERROR] Build failed.
  exit /b 1
)

echo.
echo Built: %OUT%
echo Copy CodeRED_DualGunLab.asi and CodeRED_DualGunLab.ini beside RDR.exe for testing.
endlocal
