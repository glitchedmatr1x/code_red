@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 -m pip install --upgrade pip
  py -3 -m pip install -r requirements.txt
  pause
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  pause
  exit /b %ERRORLEVEL%
)
echo Python was not found.
pause
exit /b 1
