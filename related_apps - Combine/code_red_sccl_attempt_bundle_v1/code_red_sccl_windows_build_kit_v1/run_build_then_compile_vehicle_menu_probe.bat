@echo off
setlocal
cd /d "%~dp0"
echo ==== Code RED build + compile vehicle menu probe ====
echo.
echo Optional usage:
echo   run_build_then_compile_vehicle_menu_probe.bat C:\full\path\to\SC-CL-master.zip
echo.
call build_sccl_windows.bat "%~1"
if errorlevel 1 (
  echo Build/detect failed. Check output\build_sccl_windows.log
  exit /b 1
)
call compile_vehicle_menu_probe_windows.bat "%~1"
if errorlevel 1 (
  echo Compile failed. Check output\compile_vehicle_menu_probe.log
  exit /b 1
)
echo Done. Check output\vehicle_menu_probe_build
exit /b 0
