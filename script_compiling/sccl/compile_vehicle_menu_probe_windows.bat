@echo off
setlocal EnableExtensions

echo [CodeRED] Direct SC-CL vehicle menu compile probe...

set "SCCL_ROOT=%~dp0"
set "REPO_ROOT=%SCCL_ROOT%..\..\"
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI\"
set "PROJECT=%SCCL_ROOT%projects\vehicle_menu_probe"
set "SRC=%PROJECT%\src\main.c"
set "INCLUDE=%PROJECT%\include"
set "OUT=%SCCL_ROOT%output\vehicle_menu_probe"

if not exist "%SRC%" (
  echo [CodeRED] Missing source: %SRC%
  exit /b 2
)

if not exist "%INCLUDE%\RDR\natives32.h" (
  echo [CodeRED] Missing include: %INCLUDE%\RDR\natives32.h
  exit /b 2
)

rem PowerShell environment variables should pass through, but if not, use common repo locations.
if "%SCCL_EXE%"=="" if exist "%SCCL_ROOT%output\SC-CL.exe" set "SCCL_EXE=%SCCL_ROOT%output\SC-CL.exe"
if "%SCCL_EXE%"=="" if exist "%REPO_ROOT%resources\SC-CL_DROP_HERE\SC-CL.exe" set "SCCL_EXE=%REPO_ROOT%resources\SC-CL_DROP_HERE\SC-CL.exe"
if "%SCCL_EXE%"=="" if exist "%REPO_ROOT%SC-CL-master\bin\SC-CL.exe" set "SCCL_EXE=%REPO_ROOT%SC-CL-master\bin\SC-CL.exe"
if "%SCCL_EXE%"=="" if exist "%REPO_ROOT%SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\SC-CL.exe" set "SCCL_EXE=%REPO_ROOT%SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\SC-CL.exe"
if "%SCCL_EXE%"=="" if exist "%SCCL_ROOT%obsolete\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe" set "SCCL_EXE=%SCCL_ROOT%obsolete\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe"

if not exist "%SCCL_EXE%" (
  echo [CodeRED] SC-CL.exe not found.
  echo [CodeRED] Checked:
  echo   %SCCL_ROOT%output\SC-CL.exe
  echo   %REPO_ROOT%resources\SC-CL_DROP_HERE\SC-CL.exe
  echo   %REPO_ROOT%SC-CL-master\bin\SC-CL.exe
  echo   %REPO_ROOT%SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\SC-CL.exe
  echo   %SCCL_ROOT%obsolete\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe
  echo.
  echo [CodeRED] Or set in PowerShell:
  echo   $env:SCCL_EXE="C:\path\to\SC-CL.exe"
  exit /b 3
)

if not exist "%OUT%" mkdir "%OUT%"

echo [CodeRED] Compiler: %SCCL_EXE%
echo [CodeRED] Source:   %SRC%
echo [CodeRED] Include:  %INCLUDE%
echo [CodeRED] Output:   %OUT%

"%SCCL_EXE%" ^
  -target=RDR_#SC ^
  -platform=X360 ^
  -out-dir="%OUT%" ^
  -name=vehicle_menu_probe ^
  -extra-arg=-I"%INCLUDE%" ^
  "%SRC%"

set "EXITCODE=%ERRORLEVEL%"
echo [CodeRED] SC-CL exit: %EXITCODE%
exit /b %EXITCODE%
