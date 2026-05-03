@echo off
setlocal
cd /d "%~dp0\..\.."
py -3 related_apps\CodeRED_Script_Workshop\CodeRED_Script_Workshop.py gui
if errorlevel 1 pause
endlocal
