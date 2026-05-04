@echo off
setlocal EnableExtensions

echo [CodeRED] Direct SC-CL vehicle menu compile probe...

set "SCCL_ROOT=%~dp0"
set "REPO_ROOT=%SCCL_ROOT%..\..\"
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI\"
set "PROJECT=%SCCL_ROOT%projects\vehicle_menu_probe"
set "SRC=%PROJECT%\src\main.c"
set "INCLUDE=%PROJECT%\include"
set "OUT_ROOT=%SCCL_ROOT%output"
set "OUT=%OUT_ROOT%\vehicle_menu_probe"
set "OUT_ARG=%OUT%\"
set "HEADER=%INCLUDE%\RDR\natives32.h"
set "PROMOTE=%SCCL_ROOT%promote_real_sccl_headers_windows.ps1"
set "INSPECT=%SCCL_ROOT%inspect_vehicle_menu_output_windows.ps1"

if not exist "%SRC%" (
  echo [CodeRED] Missing source: %SRC%
  exit /b 2
)

if not exist "%HEADER%" (
  echo [CodeRED] Missing include: %HEADER%
  if exist "%PROMOTE%" (
    echo [CodeRED] Attempting real-header promotion...
    powershell -ExecutionPolicy Bypass -File "%PROMOTE%" -RepoRoot "%REPO_ROOT%"
  )
)

if not exist "%HEADER%" (
  echo [CodeRED] Missing include after promotion attempt: %HEADER%
  exit /b 2
)

findstr /i /c:"Minimal Code RED proof natives" /c:"source-proof shims" "%HEADER%" >nul 2>nul
if not errorlevel 1 (
  echo [CodeRED] Fake/proof shim header detected: %HEADER%
  if exist "%PROMOTE%" (
    echo [CodeRED] Promoting real SC-CL headers before compile...
    powershell -ExecutionPolicy Bypass -File "%PROMOTE%" -RepoRoot "%REPO_ROOT%"
  ) else (
    echo [CodeRED] Missing promotion script: %PROMOTE%
    exit /b 4
  )
)

findstr /i /c:"Minimal Code RED proof natives" /c:"source-proof shims" "%HEADER%" >nul 2>nul
if not errorlevel 1 (
  echo [CodeRED] Project header is still fake after promotion. Stopping.
  echo [CodeRED] Header: %HEADER%
  exit /b 4
)

rem Prefer complete bin folders over drop-only EXE folders. The drop folder may contain SC-CL.exe without required DLLs.
if "%SCCL_EXE%"=="" if exist "%SCCL_ROOT%output\SC-CL.exe" set "SCCL_EXE=%SCCL_ROOT%output\SC-CL.exe"
if "%SCCL_EXE%"=="" if exist "%REPO_ROOT%SC-CL-master\bin\SC-CL.exe" set "SCCL_EXE=%REPO_ROOT%SC-CL-master\bin\SC-CL.exe"
if "%SCCL_EXE%"=="" if exist "%REPO_ROOT%SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\SC-CL.exe" set "SCCL_EXE=%REPO_ROOT%SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\SC-CL.exe"
if "%SCCL_EXE%"=="" if exist "%SCCL_ROOT%obsolete\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe" set "SCCL_EXE=%SCCL_ROOT%obsolete\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe"
if "%SCCL_EXE%"=="" if exist "%REPO_ROOT%resources\SC-CL_DROP_HERE\SC-CL.exe" set "SCCL_EXE=%REPO_ROOT%resources\SC-CL_DROP_HERE\SC-CL.exe"

if not exist "%SCCL_EXE%" (
  echo [CodeRED] SC-CL.exe not found.
  echo [CodeRED] Checked:
  echo   %SCCL_ROOT%output\SC-CL.exe
  echo   %REPO_ROOT%SC-CL-master\bin\SC-CL.exe
  echo   %REPO_ROOT%SC-CL-master\llvm-14.0.0.src\tools\clang\tools\extra\SC-CL\bin\SC-CL.exe
  echo   %SCCL_ROOT%obsolete\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe
  echo   %REPO_ROOT%resources\SC-CL_DROP_HERE\SC-CL.exe
  echo.
  echo [CodeRED] Try staging runtime files:
  echo   powershell -ExecutionPolicy Bypass -File script_compiling\sccl\stage_sccl_runtime_windows.ps1
  echo.
  echo [CodeRED] Or set in PowerShell:
  echo   $env:SCCL_EXE="C:\path\to\SC-CL.exe"
  exit /b 3
)

if not exist "%OUT%" mkdir "%OUT%"

echo [CodeRED] Compiler: %SCCL_EXE%
echo [CodeRED] Source:   %SRC%
echo [CodeRED] Include:  %INCLUDE%
echo [CodeRED] Output:   %OUT_ARG%

"%SCCL_EXE%" ^
  -target=RDR_#SC ^
  -platform=X360 ^
  -out-dir="%OUT_ARG%" ^
  -name=vehicle_menu_probe ^
  -extra-arg=-I"%INCLUDE%" ^
  "%SRC%"

set "EXITCODE=%ERRORLEVEL%"
echo [CodeRED] SC-CL exit: %EXITCODE%

if "%EXITCODE%"=="-1073741515" (
  echo [CodeRED] Windows status 0xC0000135: SC-CL.exe launched but a required DLL was missing.
  echo [CodeRED] Run:
  echo   powershell -ExecutionPolicy Bypass -File script_compiling\sccl\stage_sccl_runtime_windows.ps1
  echo [CodeRED] If that still fails, install/repair Microsoft Visual C++ Redistributable 2015-2022 x64.
)

if exist "%INSPECT%" (
  echo [CodeRED] Inspecting compile outputs...
  powershell -ExecutionPolicy Bypass -File "%INSPECT%" -RepoRoot "%REPO_ROOT%"
)

exit /b %EXITCODE%
