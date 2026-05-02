@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
call "%~dp0Install_CodeRED_Tuner_Dependencies.bat" --quiet
if errorlevel 1 (
  echo Dependency check/install failed. See logs\dependency_check_latest.txt.
  pause
  exit /b 1
)
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%~dp0code_red_arcade.py" --settings "%~dp0runtime\arcade_settings.json" --renderer panda
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%~dp0code_red_arcade.py" --settings "%~dp0runtime\arcade_settings.json" --renderer panda
  exit /b %ERRORLEVEL%
)
echo Python was not found. Install Python 3.10+ and run this file again.
pause
exit /b 1
