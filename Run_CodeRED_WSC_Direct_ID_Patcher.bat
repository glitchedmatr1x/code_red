@echo off
setlocal
set PY=py -3
%PY% --version >nul 2>nul
if errorlevel 1 set PY=python
%PY% tools\codered_wsc_direct_id_patcher.py %*
if errorlevel 1 (
  echo.
  echo Code RED WSC Direct ID Patcher failed.
  pause
  exit /b 1
)
endlocal
