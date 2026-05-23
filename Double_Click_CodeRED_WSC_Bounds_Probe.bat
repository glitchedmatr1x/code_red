@echo off
cd /d "%~dp0"
echo Code RED WSC Bounds Probe
echo.
echo Examples:
echo   Run_CodeRED_WSC_Bounds_Probe.bat status
echo   Run_CodeRED_WSC_Bounds_Probe.bat scan --input imports\event_roadside_prisoners.wsc imports\event_roadside_ambush.wsc imports\beat_roadside_robbery.wsc --out logs\wsc_bounds_probe\roadside_scan
echo.
pause
