@echo off
setlocal

rem Code RED Repo Doctor launcher.
rem Audits generated clutter and active paths without deleting anything.

pushd "%~dp0"

if not exist "tools\codered_repo_doctor.py" (
  echo [ERROR] Missing tools\codered_repo_doctor.py
  pause
  exit /b 1
)

py -3 tools\codered_repo_doctor.py --project-root "%CD%"

echo.
echo Repo Doctor complete. Review logs\CodeRED_Repo_Doctor_Report.json.
pause
popd
endlocal
