@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a WSC/binary file onto this BAT to replace an integer/enum.
  echo Use 03_FIND_INTEGER first unless you are sure.
  pause
  exit /b 1
)
if not exist patched mkdir patched
set /p OLD=Old value, example 1166: 
set /p NEW=New value, example 1193: 
set /p WIDTH=Byte width, usually 2 [2]: 
if "%WIDTH%"=="" set WIDTH=2
set /p ENDIAN=Endian little/big [little]: 
if "%ENDIAN%"=="" set ENDIAN=little
echo.
echo Type ALL to patch every match, or paste one decoded offset like 0x35D4A.
set /p TARGET=Target: 
set "OUT=patched\%~n1_int_%OLD%_to_%NEW%%~x1"
if /I "%TARGET%"=="ALL" (
  py -3 codered_mod_workbench.py replace-int "%~1" --old %OLD% --new %NEW% --width %WIDTH% --endian %ENDIAN% --all --out "%OUT%"
) else (
  py -3 codered_mod_workbench.py replace-int "%~1" --old %OLD% --new %NEW% --width %WIDTH% --endian %ENDIAN% --offset %TARGET% --out "%OUT%"
)
echo.
if exist "%OUT%" explorer patched
pause
