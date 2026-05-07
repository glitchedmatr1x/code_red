@echo off
setlocal
cd /d "%~dp0"
py -3 tools\codered_decompile_recompile_hub.py %*
if errorlevel 1 (
  python tools\codered_decompile_recompile_hub.py %*
)
