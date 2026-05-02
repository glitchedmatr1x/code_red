@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_sccl_windows.ps1" -ScclPath "%~1"
exit /b %ERRORLEVEL%
