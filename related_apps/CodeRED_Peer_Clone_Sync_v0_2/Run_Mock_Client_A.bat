@echo off
setlocal
cd /d "%~dp0"
echo Player A mock client connecting to local relay...
echo Run this on the same PC as Run_Relay_Host.bat.
echo.
py -3 CodeRED_Peer_Clone_Sync.py client --host 127.0.0.1 --port 47666 --client-id player_a --name "Player A" --actor ACTOR_player_jack --rate 15
pause
