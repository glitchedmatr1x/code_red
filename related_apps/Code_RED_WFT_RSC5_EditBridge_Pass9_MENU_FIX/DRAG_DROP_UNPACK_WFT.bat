@echo off
setlocal
cd /d "%~dp0"
title Code RED WFT Unpack
if "%~1"=="" (
    echo Drag a .wft file onto this .bat to unpack it.
    echo.
    pause
    exit /b 1
)
set OUTDIR=exports\%~n1_unpacked
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 tools\codered_wft_rsc5_tool.py unpack --wft "%~1" --out-dir "%OUTDIR%"
) else (
    python tools\codered_wft_rsc5_tool.py unpack --wft "%~1" --out-dir "%OUTDIR%"
)
echo.
pause
