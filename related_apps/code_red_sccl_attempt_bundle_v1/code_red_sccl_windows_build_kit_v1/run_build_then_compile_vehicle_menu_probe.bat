@echo off
setlocal
cd /d "%~dp0"
call build_sccl_windows.bat
set BUILD_RC=%ERRORLEVEL%
if %BUILD_RC% GEQ 3 exit /b %BUILD_RC%
call compile_vehicle_menu_probe_windows.bat
exit /b %ERRORLEVEL%
