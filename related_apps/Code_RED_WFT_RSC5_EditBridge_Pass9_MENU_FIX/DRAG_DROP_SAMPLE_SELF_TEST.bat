@echo off
setlocal
cd /d "%~dp0"
title Code RED WFT Sample Self Test
(
    echo 7
    echo.
    echo 9
) | py -3 tools\codered_wft_rsc5_tool.py --menu
if %ERRORLEVEL% NEQ 0 (
    (
        echo 7
        echo.
        echo 9
    ) | python tools\codered_wft_rsc5_tool.py --menu
)
echo.
pause
