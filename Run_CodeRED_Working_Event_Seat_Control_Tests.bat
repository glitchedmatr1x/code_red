@echo off
setlocal
set PY=py -3
%PY% --version >nul 2>&1
if errorlevel 1 set PY=python
if "%1"=="" goto report
if /I "%1"=="report" goto report
echo Usage:
echo   Run_CodeRED_Working_Event_Seat_Control_Tests.bat report
exit /b 2
:report
%PY% tools\codered_working_event_control_test_matrix.py report --input-dir imports --out logs\working_event_seat_control_tests
exit /b %ERRORLEVEL%
