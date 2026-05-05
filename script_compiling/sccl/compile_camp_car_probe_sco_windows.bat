@echo off
setlocal EnableExtensions

echo [CodeRED] Direct SC-CL camp car probe SCO compile...

set "SCCL_ROOT=%~dp0"
set "REPO_ROOT=%SCCL_ROOT%..\..\"
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI\"
set "PROJECT=%SCCL_ROOT%projects\camp_car_probe"
set "SRC=%PROJECT%\src\main.c"
set "INCLUDE=%PROJECT%\include"
set "LANE_INCLUDE=%SCCL_ROOT%include"
set "OUT_ROOT=%SCCL_ROOT%output"
set "OUT=%OUT_ROOT%\camp_car_probe_sco"
set "OUT_ARG=%OUT%\\"
set "HEADER=%INCLUDE%\RDR\natives32.h"
set "PROMOTE=%SCCL_ROOT%promote_real_sccl_headers_windows.ps1"
set "INSPECT=%SCCL_ROOT%inspect_camp_car_output_windows.ps1"
set "VALIDATE=%PROJECT%\scripts\validate_camp_car_probe.py"

if not exist "%SRC%" (
  echo [CodeRED] Missing source: %SRC%
  exit /b 2
)

if not exist "%HEADER%" (
  echo [CodeRED] Project include missing. Copying active lane include into camp car project...
  if not exist "%LANE_INCLUDE%\RDR\natives32.h" (
    echo [CodeRED] Active lane include missing. Promoting real SC-CL headers...
    powershell -ExecutionPolicy Bypass -File "%PROMOTE%" -RepoRoot "%REPO_ROOT%"
  )
  if exist "%INCLUDE%" rmdir /s /q "%INCLUDE%"
  mkdir "%INCLUDE%"
  xcopy "%LANE_INCLUDE%\*" "%INCLUDE%\" /E /I /Y >nul
)

if not exist "%HEADER%" (
  echo [CodeRED] Missing include after repair: %HEADER%
  exit /b 2
)

findstr /i /c:"Minimal Code RED proof natives" /c:"source-proof shims" "%HEADER%" >nul 2>nul
if not errorlevel 1 (
  echo [CodeRED] Fake/proof shim header detected: %HEADER%
  echo [CodeRED] Promoting real SC-CL headers and refreshing project include...
  powershell -ExecutionPolicy Bypass -File "%PROMOTE%" -RepoRoot "%REPO_ROOT%"
  if exist "%INCLUDE%" rmdir /s /q "%INCLUDE%"
  mkdir "%INCLUDE%"
  xcopy "%LANE_INCLUDE%\*" "%INCLUDE%\" /E /I /Y >nul
)

findstr /i /c:"Minimal Code RED proof natives" /c:"source-proof shims" "%HEADER%" >nul 2>nul
if not errorlevel 1 (
  echo [CodeRED] Project header is still fake after promotion. Stopping.
  exit /b 4
)

if exist "%VALIDATE%" (
  echo [CodeRED] Validating camp car probe after include repair...
  py -3 "%VALIDATE%"
  if errorlevel 1 (
    echo [CodeRED] Camp car probe validation failed after include repair. Stopping before SCO compile.
    exit /b 5
  )
)

if "%SCCL_EXE%"=="" if exist "%SCCL_ROOT%output\SC-CL.exe" set "SCCL_EXE=%SCCL_ROOT%output\SC-CL.exe"
if "%SCCL_EXE%"=="" if exist "%REPO_ROOT%SC-CL-master\bin\SC-CL.exe" set "SCCL_EXE=%REPO_ROOT%SC-CL-master\bin\SC-CL.exe"
if "%SCCL_EXE%"=="" if exist "%SCCL_ROOT%obsolete\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe" set "SCCL_EXE=%SCCL_ROOT%obsolete\code_red_sccl_attempt_bundle_v1\code_red_sccl_windows_build_kit_v1\SC-CL.exe"

if not exist "%SCCL_EXE%" (
  echo [CodeRED] SC-CL.exe not found. Run:
  echo   powershell -ExecutionPolicy Bypass -File script_compiling\sccl\stage_sccl_runtime_windows.ps1
  exit /b 3
)

if not exist "%OUT%" mkdir "%OUT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item -LiteralPath '%OUT_ROOT%\camp_car_probecamp_car_probe.sco','%OUT%\camp_car_probe.sco' -Force -ErrorAction SilentlyContinue"

echo [CodeRED] Compiler: %SCCL_EXE%
echo [CodeRED] Source:   %SRC%
echo [CodeRED] Include:  %INCLUDE%
echo [CodeRED] Output:   %OUT_ARG%

"%SCCL_EXE%" ^
  -target=RDR_SCO ^
  -platform=X360 ^
  -out-dir="%OUT_ARG%" ^
  -name=camp_car_probe ^
  -extra-arg=-I"%INCLUDE%" ^
  "%SRC%"

set "EXITCODE=%ERRORLEVEL%"
echo [CodeRED] SC-CL SCO exit: %EXITCODE%

if exist "%INSPECT%" (
  echo [CodeRED] Inspecting camp car probe outputs...
  powershell -ExecutionPolicy Bypass -File "%INSPECT%" -RepoRoot "%REPO_ROOT%"
)

exit /b %EXITCODE%
