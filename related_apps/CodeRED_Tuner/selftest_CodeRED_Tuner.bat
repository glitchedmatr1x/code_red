@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 codered_tuner.py --selftest
  pause
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python codered_tuner.py --selftest
  pause
  exit /b %ERRORLEVEL%
)
echo Python was not found. Install Python 3.10+ and run this file again.
pause
exit /b 1
