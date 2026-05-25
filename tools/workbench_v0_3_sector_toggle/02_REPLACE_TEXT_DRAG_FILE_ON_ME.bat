@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a file onto this BAT to replace text/string candidates.
  echo WSC rule: replacement must be same length or shorter.
  pause
  exit /b 1
)
if not exist patched mkdir patched
set /p FIND=Text to find: 
if "%FIND%"=="" exit /b 1
set /p REPL=Replace with: 
set "OUT=patched\%~n1_patched%~x1"
echo.
echo Input:  %~1
echo Output: %OUT%
echo Find:   %FIND%
echo Replace:%REPL%
echo.
py -3 codered_mod_workbench.py replace "%~1" --find "%FIND%" --replace "%REPL%" --out "%OUT%"
echo.
if exist "%OUT%" (
  echo Patched copy saved: %OUT%
  explorer patched
) else (
  echo No output was created. Check the message above.
)
pause
