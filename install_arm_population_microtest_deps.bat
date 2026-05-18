@echo off
setlocal
set PYTHON_CMD=py -3
%PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 set PYTHON_CMD=python
%PYTHON_CMD% -m pip install --upgrade cryptography zstandard
pause
