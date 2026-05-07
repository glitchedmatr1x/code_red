@echo off
setlocal
set "PATCH=%~dp0Code_RED"
set "TARGET=%~dp0"
if exist "%TARGET%main.py" goto found
if exist "%TARGET%Code_RED\main.py" (
  set "TARGET=%TARGET%Code_RED\"
  goto found
)
echo Put this patch folder beside your Code_RED folder, or copy the included Code_RED folder over your existing Code_RED folder.
echo No files outside the listed updated files are removed.
pause
exit /b 1
:found
echo Applying Code RED tuner/test demo patch to:
echo %TARGET%
xcopy "%PATCH%\*" "%TARGET%" /E /Y /I
if errorlevel 1 (
  echo Patch copy reported an error.
  pause
  exit /b 1
)
echo Patch applied. Use Run_Code_RED.bat, then Open Tuner or Test Demo.
pause
exit /b 0
