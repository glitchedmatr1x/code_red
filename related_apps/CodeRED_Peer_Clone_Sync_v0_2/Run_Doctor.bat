@echo off
setlocal
cd /d "%~dp0"
py -3 CodeRED_Peer_Clone_Sync.py doctor
pause
