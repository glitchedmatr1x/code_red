@echo off
setlocal
cd /d "%~dp0..\.."
powershell -ExecutionPolicy Bypass -File related_apps\CodeRED_Peer_Clone_Game_Bridge_v0_1\build_peer_clone_game_bridge_windows.ps1
