@echo off
cd /d "%~dp0"
set /p HOST_IP=Player A LAN/VPN IP: 
if "%HOST_IP%"=="" set HOST_IP=127.0.0.1
py -3 CodeRED_Peer_Clone_Playable.py play --host "%HOST_IP%" --port 47666 --client-id player_b --name "Player B" --actor ACTOR_mpplayer01 --color cyan
pause
