@echo off
setlocal
set PYTHON_EXE=py -3
%PYTHON_EXE% --version >nul 2>&1
if errorlevel 1 set PYTHON_EXE=python
%PYTHON_EXE% -m pip install --upgrade cryptography zstandard
pause
