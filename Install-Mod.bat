@echo off
setlocal
set APP=%~dp0
set TOOL=%APP%CodeRED_RPF_Patcher_Lite.py

echo CodeRED RPF Patcher Lite
echo.
set /p MODDIR=Drag/type the mod folder path: 
set /p GAMEDIR=Game folder [%RDR_GAME_DIR%]: 
if "%GAMEDIR%"=="" set GAMEDIR=%RDR_GAME_DIR%

echo.
echo 1. Dry run only
echo 2. Build cloned RPFs only
echo 3. Install live with backups
set /p CHOICE=Choose 1, 2, or 3: 

if "%CHOICE%"=="1" py -3 "%TOOL%" --mod-dir "%MODDIR%" --game-dir "%GAMEDIR%" --dry-run
if "%CHOICE%"=="2" py -3 "%TOOL%" --mod-dir "%MODDIR%" --game-dir "%GAMEDIR%"
if "%CHOICE%"=="3" (
  echo This will replace live RPFs after verification and create backups.
  set /p OK=Type YES to continue: 
  if /I "%OK%"=="YES" py -3 "%TOOL%" --mod-dir "%MODDIR%" --game-dir "%GAMEDIR%" --swap-in
)
pause
