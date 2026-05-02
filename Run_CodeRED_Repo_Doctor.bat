@echo off
setlocal

rem Code RED Repo Doctor launcher.
rem Audits active paths and generated clutter without deleting anything.

pushd "%~dp0"

if not exist "tools\codered_repo_doctor.py" (
  echo [ERROR] Missing tools\codered_repo_doctor.py
  pause
  popd
  exit /b 1
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 tools\codered_repo_doctor.py --project-root "%CD%"
  set EXITCODE=%ERRORLEVEL%
  echo.
  echo Repo Doctor complete. Review logs\CodeRED_Repo_Doctor_Report.json.
  pause
  popd
  exit /b %EXITCODE%
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python tools\codered_repo_doctor.py --project-root "%CD%"
  set EXITCODE=%ERRORLEVEL%
  echo.
  echo Repo Doctor complete. Review logs\CodeRED_Repo_Doctor_Report.json.
  pause
  popd
  exit /b %EXITCODE%
)

echo Python was not found. Install Python 3.10+ and run this file again.
pause
popd
exit /b 1
