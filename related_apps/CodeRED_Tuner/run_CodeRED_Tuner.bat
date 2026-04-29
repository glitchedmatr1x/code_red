@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
call "%~dp0Install_CodeRED_Tuner_Dependencies.bat" --quiet
where pyw >nul 2>nul
if %ERRORLEVEL%==0 (
  start "Code RED Tuner" pyw -3 "%~dp0codered_tuner.py"
  exit /b 0
)
where pythonw >nul 2>nul
if %ERRORLEVEL%==0 (
  start "Code RED Tuner" pythonw "%~dp0codered_tuner.py"
  exit /b 0
)
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%~dp0codered_tuner.py"
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%~dp0codered_tuner.py"
  exit /b %ERRORLEVEL%
)
echo Python was not found. Install Python 3.10+ and run this file again.
pause
exit /b 1
