@echo off
setlocal
set PYEXE=py -3
where py >nul 2>nul
if errorlevel 1 set PYEXE=python
%PYEXE% -m pip install --upgrade cryptography zstandard
pause
endlocal
