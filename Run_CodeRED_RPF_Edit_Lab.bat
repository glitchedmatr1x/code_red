@echo off
setlocal
cd /d "%~dp0"
py -3 related_apps\rpf_edit_lab.py %*
if errorlevel 1 (
  python related_apps\rpf_edit_lab.py %*
)
