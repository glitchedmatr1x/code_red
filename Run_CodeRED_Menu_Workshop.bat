@echo off
setlocal
cd /d "%~dp0"
py -3 tools\codered_menu_workshop.py --project data\codered\menu_specs\mp_spawn_menu.json --validate --emit-runtime --package %*
if errorlevel 1 (
  python tools\codered_menu_workshop.py --project data\codered\menu_specs\mp_spawn_menu.json --validate --emit-runtime --package %*
)
