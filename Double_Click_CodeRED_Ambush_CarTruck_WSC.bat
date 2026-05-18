@echo off
setlocal
cd /d "%~dp0"
set PYTHON_CMD=py -3
where py >nul 2>nul
if errorlevel 1 set PYTHON_CMD=python
%PYTHON_CMD% tools\codered_ambush_cartruck_wsc.py status
pause
endlocal
