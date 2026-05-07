@echo off
setlocal
cd /d "%~dp0"
echo Code RED Peer Clone Sync - Player B Client
echo.
echo Enter Player A's LAN/VPN IP address.
echo Do NOT use 127.0.0.1 unless both clients are on this same PC.
echo.
set /p HOST_IP=Player A IP: 
if "%HOST_IP%"=="" set HOST_IP=127.0.0.1
py -3 CodeRED_Peer_Clone_Sync.py client --host "%HOST_IP%" --port 47666 --client-id player_b --name "Player B" --actor ACTOR_mpplayer01 --rate 15
pause
