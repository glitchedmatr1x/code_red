@echo off
setlocal
cd /d "%~dp0"
if not exist output mkdir output
set LOG=output\build_sccl_windows.log
echo Code RED SC-CL Windows build helper > "%LOG%"
echo Started: %DATE% %TIME% >> "%LOG%"

if defined SCCL_EXE (
  if exist "%SCCL_EXE%" (
    echo SCCL_EXE=%SCCL_EXE% >> "%LOG%"
    echo SC-CL already available: %SCCL_EXE%
    exit /b 0
  )
)

for %%P in ("..\..\..\SC-CL.exe" ".\SC-CL.exe" "..\code_red_script_compile_lab_v1\SC-CL.exe" "..\..\..\resources\SC-CL-master\bin\SC-CL.exe" "..\..\..\resources\SC-CL-master\llvm-14.0.0.src\MinSizeRel\bin\SC-CL.exe") do (
  if exist %%~fP (
    echo Found SC-CL.exe at %%~fP >> "%LOG%"
    echo Found SC-CL.exe at %%~fP
    exit /b 0
  )
)

echo SC-CL.exe was not found. >> "%LOG%"
echo Place SC-CL.exe here or set SCCL_EXE before running compile_vehicle_menu_probe_windows.bat. >> "%LOG%"
echo [WARN] SC-CL.exe not found. This is a detection helper, not a source builder.
exit /b 2
