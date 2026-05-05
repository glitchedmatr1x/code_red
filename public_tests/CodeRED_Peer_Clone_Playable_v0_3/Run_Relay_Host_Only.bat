@echo off
cd /d "%~dp0"
echo Keep this relay window open.
py -3 CodeRED_Peer_Clone_Playable.py host --bind 0.0.0.0 --port 47666
pause
