@echo off
setlocal
cd /d "%~dp0..\.."
powershell -ExecutionPolicy Bypass -File tools\CodeRED_PeerCompanion\build_peer_companion_windows.ps1
