@echo off
py -3 -m pip install cryptography zstandard
if errorlevel 1 python -m pip install cryptography zstandard
pause
