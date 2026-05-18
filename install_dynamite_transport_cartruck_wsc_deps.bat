@echo off
setlocal
set PYTHON_CMD=py -3
where py >nul 2>nul
if errorlevel 1 set PYTHON_CMD=python
%PYTHON_CMD% -m pip install --upgrade cryptography zstandard
pause
