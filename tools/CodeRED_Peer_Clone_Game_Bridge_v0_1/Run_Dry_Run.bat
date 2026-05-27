@echo off
setlocal
cd /d "%~dp0"
py -3 CodeRED_Peer_Clone_Game_Bridge_DryRun.py --bridge bridge --runtime runtime
