@echo off
setlocal
cd /d "%~dp0"
title Code RED WFT RSC5 Edit Bridge - Menu

echo Code RED WFT/RSC5 Edit Bridge
echo.
echo This launcher keeps the window open and writes errors to logs\wft_tool_last_run.log.
echo.

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 tools\codered_wft_rsc5_tool.py --menu
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        python tools\codered_wft_rsc5_tool.py --menu
    ) else (
        echo Python was not found. Install Python 3 and try again.
    )
)

echo.
echo Launcher finished.
pause
