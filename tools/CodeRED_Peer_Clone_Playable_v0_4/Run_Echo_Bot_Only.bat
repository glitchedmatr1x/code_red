@echo off
cd /d "%~dp0"
set /p HOST_IP=Relay Host IP: 
if "%HOST_IP%"=="" set HOST_IP=127.0.0.1
py -3 CodeRED_Peer_Clone_Playable.py bot --host "%HOST_IP%" --port 47666 --client-id bot_echo --name "Echo Bot" --actor ACTOR_mpplayer02 --color orange
pause
