@echo off
setlocal
set PY=py -3
%PY% --version >nul 2>nul
if errorlevel 1 set PY=python
%PY% -m pip install --upgrade cryptography zstandard
pause
endlocal
