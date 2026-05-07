@echo off
py -3 "%~dp0CodeRED_Peer_Clone_Sync.py" client --host 127.0.0.1 --port 47666 --client-id player_a --name "Player A" --actor ACTOR_player_jack --rate 15
pause
