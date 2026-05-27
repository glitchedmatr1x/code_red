@echo off
setlocal
where py >nul 2>&1 && py -3 "%~dp0Code_RED_Dependency_Installer.py"
if errorlevel 1 where python >nul 2>&1 && python "%~dp0Code_RED_Dependency_Installer.py"
if errorlevel 1 echo Python 3.11+ was not found on PATH.
endlocal
