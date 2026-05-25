@echo off
setlocal
set CODE_RED=D:\Games\Red Dead Redemption\Code_RED
set INSTALLER=%CODE_RED%\tools\codered_mp_freeroam_pass3_installer.py

echo Code RED MP Free Roam Pass 3 Installer
echo.
echo 1. Dry run only
echo 2. Build cloned content.rpf only
echo 3. Build and swap into game\content.rpf with backup
echo.
set /p CHOICE=Choose 1, 2, or 3: 

cd /d "%CODE_RED%"
set PYTHONPATH=.

if "%CHOICE%"=="1" (
  py -3 "%INSTALLER%" --dry-run
  goto END
)
if "%CHOICE%"=="2" (
  py -3 "%INSTALLER%"
  goto END
)
if "%CHOICE%"=="3" (
  echo.
  echo This will backup game\content.rpf and replace it with the built Pass 3 RPF if verification passes.
  set /p OK=Type YES to continue: 
  if /I "%OK%"=="YES" (
    py -3 "%INSTALLER%" --swap-in
  ) else (
    echo Cancelled.
  )
  goto END
)
echo Invalid choice.
:END
echo.
pause
