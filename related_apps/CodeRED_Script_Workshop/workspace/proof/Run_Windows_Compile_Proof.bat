@echo off
setlocal
cd /d "%~dp0\..\..\..\.."
echo Code RED Script Workshop Windows Compile Proof
py -3 related_apps\CodeRED_Script_Workshop\CodeRED_Script_Workshop.py scan --refresh
py -3 tools\codered_script_compile_validation.py
if errorlevel 1 exit /b 1
echo Review related_apps\CodeRED_Script_Workshop\workspace\recompile_queue before enabling real compiler output promotion.
endlocal
