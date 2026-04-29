@echo off
cd /d "%~dp0"
if "%~1"=="" (
  python tools\codered_obj_viewer.py
) else (
  python tools\codered_obj_viewer.py %*
)
