@echo off
setlocal
set REPO_ROOT=%~dp0..\..
pushd "%REPO_ROOT%" >nul
powershell -ExecutionPolicy Bypass -File related_apps\Code_RED_Runtime_Probe\build_runtime_probe_asi_windows.ps1 -RepoRoot "."
set EXITCODE=%ERRORLEVEL%
popd >nul
if not "%EXITCODE%"=="0" exit /b %EXITCODE%
echo Built: related_apps\Code_RED_Runtime_Probe\build\CodeRED_Runtime_Probe.asi
endlocal
