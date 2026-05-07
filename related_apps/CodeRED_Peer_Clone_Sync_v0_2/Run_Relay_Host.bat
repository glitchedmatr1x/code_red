@echo off
setlocal
cd /d "%~dp0"
echo Code RED Peer Clone Sync Relay Host
echo Default port: 47666/tcp
echo Keep this window open during the test.
echo.
py -3 CodeRED_Peer_Clone_Sync.py host --bind 0.0.0.0 --port 47666
pause
