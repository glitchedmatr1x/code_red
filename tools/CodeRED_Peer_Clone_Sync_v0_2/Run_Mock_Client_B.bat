@echo off
rem Replace 127.0.0.1 with Player A host IP for LAN/VPN testing.
py -3 "%~dp0CodeRED_Peer_Clone_Sync.py" client --host 127.0.0.2 --port 47666 --client-id player_b --name "Player B" --actor ACTOR_mpplayer01 --rate 15
pause
