@echo off
setlocal
cd /d "%~dp0"
set PYTHON_CMD=py -3
%PYTHON_CMD% --version >nul 2>nul
if errorlevel 1 set PYTHON_CMD=python
%PYTHON_CMD% -m pip install --upgrade cryptography zstandard
pause
