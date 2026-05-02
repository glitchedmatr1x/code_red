@echo off
setlocal
cd /d "%~dp0"
echo Preparing Code RED Test Demo...
where pyw >nul 2>nul
if %ERRORLEVEL%==0 (
  start "" pyw -3 "%~dp0Launch_CodeRED_Tuner.pyw" --demo
  exit /b 0
)
where pythonw >nul 2>nul
if %ERRORLEVEL%==0 (
  start "" pythonw "%~dp0Launch_CodeRED_Tuner.pyw" --demo
  exit /b 0
)
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%~dp0Launch_CodeRED_Tuner.py" --demo
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%~dp0Launch_CodeRED_Tuner.py" --demo
  exit /b %ERRORLEVEL%
)
echo Python was not found. Install Python 3.10+ and run this file again.
pause
exit /b 1
