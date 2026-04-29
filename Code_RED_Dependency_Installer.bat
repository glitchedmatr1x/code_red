@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 Code_RED_Dependency_Installer.py
  pause
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python Code_RED_Dependency_Installer.py
  pause
  exit /b %ERRORLEVEL%
)
echo Python 3.10+ was not found on PATH.
echo Install Python, then run this file again.
pause
exit /b 1
