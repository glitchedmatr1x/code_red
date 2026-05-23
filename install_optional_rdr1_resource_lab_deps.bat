@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Installing optional Code RED RDR1 Resource Lab dependencies...
echo.
py -3 -m pip install -r requirements_CodeRED_RDR1_Resource_Lab.txt
if errorlevel 1 (
    echo.
    echo py -3 failed. Trying python...
    python -m pip install -r requirements_CodeRED_RDR1_Resource_Lab.txt
)
echo.
pause
