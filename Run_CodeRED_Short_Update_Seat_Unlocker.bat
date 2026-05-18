@echo off
setlocal
set PYEXE=py -3
where py >nul 2>nul
if errorlevel 1 set PYEXE=python
%PYEXE% tools\codered_short_update_seat_unlock.py %*
if errorlevel 1 (
  echo.
  echo Code RED Short Update Seat Unlocker failed.
  echo Check the JSON/CSV reports beside your output if any were written.
  pause
  exit /b 1
)
endlocal
