@echo off
setlocal
cd /d "%~dp0"
echo [CodeRED] Stage 1/2: detecting SC-CL.exe...
call build_sccl_windows.bat
set BUILD_RC=%ERRORLEVEL%
echo [CodeRED] Detection exit: %BUILD_RC%
if %BUILD_RC% GEQ 3 exit /b %BUILD_RC%
echo [CodeRED] Stage 2/2: running timeout-safe compile probe...
call compile_vehicle_menu_probe_windows.bat
set COMPILE_RC=%ERRORLEVEL%
echo [CodeRED] Compile probe exit: %COMPILE_RC%
exit /b %COMPILE_RC%
