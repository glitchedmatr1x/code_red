@echo off
setlocal
cd /d "%~dp0"
python tools\codered_codex_bundle_import_cli.py %*
if errorlevel 1 pause
