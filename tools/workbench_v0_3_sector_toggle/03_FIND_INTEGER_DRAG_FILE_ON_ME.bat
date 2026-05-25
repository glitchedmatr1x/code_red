@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a WSC/binary file onto this BAT to find an integer/enum.
  pause
  exit /b 1
)
if not exist reports mkdir reports
set /p VALUE=Value to find, example 1166: 
if "%VALUE%"=="" exit /b 1
set /p WIDTH=Byte width, usually 2 for actor enums or 4 for big constants [2]: 
if "%WIDTH%"=="" set WIDTH=2
set /p ENDIAN=Endian little/big [little]: 
if "%ENDIAN%"=="" set ENDIAN=little
set "OUT=reports\%~n1_value_%VALUE%.csv"
py -3 codered_mod_workbench.py find-int "%~1" --value %VALUE% --width %WIDTH% --endian %ENDIAN% --out "%OUT%"
echo.
if exist "%OUT%" notepad "%OUT%"
pause
