@echo off
setlocal
cd /d "%~dp0"
if not exist output mkdir output
set LOG=output\compile_vehicle_menu_probe.log
set LAB=..\code_red_script_compile_lab_v1
set SRC=%LAB%\src\main.c
set OUTDIR=output\vehicle_menu_probe_build
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

echo Code RED vehicle menu probe compile helper > "%LOG%"
echo Started: %DATE% %TIME% >> "%LOG%"

if not exist "%SRC%" (
  echo [ERROR] Missing source: %SRC% >> "%LOG%"
  echo [ERROR] Missing source: %SRC%
  exit /b 1
)

if defined SCCL_EXE (
  if exist "%SCCL_EXE%" goto :compile
)

for %%P in ("..\..\..\SC-CL.exe" ".\SC-CL.exe" "%LAB%\SC-CL.exe" "..\..\..\resources\SC-CL-master\bin\SC-CL.exe" "..\..\..\resources\SC-CL-master\llvm-14.0.0.src\MinSizeRel\bin\SC-CL.exe") do (
  if exist %%~fP (
    set SCCL_EXE=%%~fP
    goto :compile
  )
)

echo [ERROR] SC-CL.exe not found. Set SCCL_EXE or place SC-CL.exe in the build kit folder. >> "%LOG%"
echo [ERROR] SC-CL.exe not found.
exit /b 2

:compile
echo Using SC-CL: %SCCL_EXE% >> "%LOG%"
echo Source: %SRC% >> "%LOG%"
echo Output dir: %OUTDIR% >> "%LOG%"
"%SCCL_EXE%" "%SRC%" -o "%OUTDIR%\vehicle_menu_probe" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [ERROR] SC-CL compile failed. Review %LOG%
  exit /b 1
)

echo Compile helper completed. Review %OUTDIR% and %LOG%.
exit /b 0
