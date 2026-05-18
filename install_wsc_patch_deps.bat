@echo off
setlocal
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  set PY=py -3
) else (
  set PY=python
)
%PY% -m pip install --upgrade cryptography zstandard
pause
