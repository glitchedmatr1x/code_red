@echo off
setlocal
cd /d "%~dp0"
py -3 CodeRED_Peer_Clone_Sync.py selftest
if errorlevel 1 (
  echo.
  echo [FAIL] Selftest failed. Check Python install and output above.
) else (
  echo.
  echo [OK] Selftest passed.
)
pause
