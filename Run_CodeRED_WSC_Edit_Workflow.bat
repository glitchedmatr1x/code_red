@echo off
setlocal
cd /d "%~dp0"
py -3 tools\codered_wsc_edit_workflow.py %*
if errorlevel 1 (
  python tools\codered_wsc_edit_workflow.py %*
)
