@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a WSC/RSC85 file onto this batch file.
  pause
  exit /b 1
)
if not exist patched mkdir patched
echo ============================================================
echo Code RED Sector Patch Examples
echo ============================================================
echo 1^) Enable all esc_villaWall04x child-sector entries
echo 2^) Rename beh_grave01x -^> dlc02x and make world/enabled
echo 3^) Rename beh_grave02x -^> dlc07x and make world/enabled
echo 4^) Rename beh_grave03x -^> dlc08x and make world/enabled
echo 0^) Cancel
echo.
set /p choice=Choose: 
if "%choice%"=="1" py -3 codered_mod_workbench.py sector-patch "%~1" --sector esc_villaWall04x --set-state enabled --all --out "patched\%~n1_villaWall04_enabled%~x1"
if "%choice%"=="2" py -3 codered_mod_workbench.py sector-patch "%~1" --sector beh_grave01x --replace-with dlc02x --set-type world --set-state enabled --all --out "patched\%~n1_behgrave01_to_dlc02_world%~x1"
if "%choice%"=="3" py -3 codered_mod_workbench.py sector-patch "%~1" --sector beh_grave02x --replace-with dlc07x --set-type world --set-state enabled --all --out "patched\%~n1_behgrave02_to_dlc07_world%~x1"
if "%choice%"=="4" py -3 codered_mod_workbench.py sector-patch "%~1" --sector beh_grave03x --replace-with dlc08x --set-type world --set-state enabled --all --out "patched\%~n1_behgrave03_to_dlc08_world%~x1"
echo.
echo Check the patched folder and manifest JSON.
pause
