@echo off
setlocal EnableExtensions

echo [CodeRED] Building camp car probe XSC + SCO proofs...

set "SCCL_ROOT=%~dp0"
set "COMPILE_XSC=%SCCL_ROOT%compile_camp_car_probe_windows.bat"
set "COMPILE_SCO=%SCCL_ROOT%compile_camp_car_probe_sco_windows.bat"

if not exist "%COMPILE_XSC%" (
  echo [CodeRED] Missing XSC compile batch: %COMPILE_XSC%
  exit /b 2
)
if not exist "%COMPILE_SCO%" (
  echo [CodeRED] Missing SCO compile batch: %COMPILE_SCO%
  exit /b 2
)

call "%COMPILE_XSC%"
set "XSC_EXIT=%ERRORLEVEL%"
if not "%XSC_EXIT%"=="0" (
  echo [CodeRED] XSC compile failed: %XSC_EXIT%
  exit /b %XSC_EXIT%
)

call "%COMPILE_SCO%"
set "SCO_EXIT=%ERRORLEVEL%"
if not "%SCO_EXIT%"=="0" (
  echo [CodeRED] SCO compile failed: %SCO_EXIT%
  exit /b %SCO_EXIT%
)

echo [CodeRED] Camp car probe XSC + SCO compile complete.
exit /b 0
