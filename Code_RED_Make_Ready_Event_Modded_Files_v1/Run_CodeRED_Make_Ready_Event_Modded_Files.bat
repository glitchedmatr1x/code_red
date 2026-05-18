@echo off
setlocal
cd /d "%~dp0"

if not defined CODERED_RDR_EXE (
  if exist "%CD%\..\rdr.exe" set "CODERED_RDR_EXE=%CD%\..\rdr.exe"
)
if not defined CODERED_RDR_EXE (
  if exist "%CD%\rdr.exe" set "CODERED_RDR_EXE=%CD%\rdr.exe"
)
if not defined CODERED_RDR_EXE (
  if exist "D:\Games\Red Dead Redemption\rdr.exe" set "CODERED_RDR_EXE=D:\Games\Red Dead Redemption\rdr.exe"
)

echo Using CODERED_RDR_EXE=%CODERED_RDR_EXE%
py -3 tools\codered_make_ready_event_mods.py
if errorlevel 1 (
  echo.
  echo Code RED ready modded file build failed.
  echo Check that clean WSC originals are in .\imports and CODERED_RDR_EXE points to rdr.exe.
  pause
  exit /b 1
)

echo.
echo Done. Ready files are in .\ready_modded_files
pause
