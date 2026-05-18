@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PAUSE_ON_EXIT="
if "%~1"=="" (
    set "PAUSE_ON_EXIT=1"
    echo Code RED Vehicle Script Lab
    echo.
    echo No command was supplied, so this launcher is running a status check.
    echo.
    echo Common commands:
    echo   Run_CodeRED_Vehicle_Script_Lab.bat target-map --out logs\vehicle_script_lab\vehicle_activation_map.json
    echo   Run_CodeRED_Vehicle_Script_Lab.bat scan-rpf --archive game\content.rpf --out logs\vehicle_script_lab\content_scripts
    echo   Run_CodeRED_Vehicle_Script_Lab.bat scan-folder --input imports\scripts --out logs\vehicle_script_lab\scripts
    echo   Run_CodeRED_Vehicle_Script_Lab.bat compare --left imports\playercar.wsc --right imports\beat_crime_wagonthief.wsc --out logs\vehicle_script_lab\playercar_vs_wagonthief
    echo   Run_CodeRED_Vehicle_Script_Lab.bat make-asi-scaffold --out asi\CodeREDVehicleBridge
    echo.
)

if not exist "tools\codered_vehicle_script_lab.py" (
    echo ERROR: tools\codered_vehicle_script_lab.py was not found.
    echo Unzip this package into the Code RED root folder next to Code_RED.bat and main.py.
    set "RESULT=1"
    goto end
)

call :find_python
if errorlevel 1 (
    set "RESULT=1"
    goto end
)

if "%~1"=="" (
    call :run_lab status
) else (
    call :run_lab %*
)
set "RESULT=%ERRORLEVEL%"
goto end

:find_python
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 (
    set "PY_CMD=py -3"
    exit /b 0
)
python -c "import sys" >nul 2>nul
if not errorlevel 1 (
    set "PY_CMD=python"
    exit /b 0
)
python3 -c "import sys" >nul 2>nul
if not errorlevel 1 (
    set "PY_CMD=python3"
    exit /b 0
)
echo ERROR: No suitable Python runtime was found.
echo Install Python 3, or try: py -3 tools\codered_vehicle_script_lab.py status
exit /b 1

:run_lab
echo Using Python command: %PY_CMD%
echo.
%PY_CMD% tools\codered_vehicle_script_lab.py %*
exit /b %ERRORLEVEL%

:end
if not "%RESULT%"=="0" (
    echo.
    echo Code RED Vehicle Script Lab failed.
    echo Check logs\vehicle_script_lab\vehicle_script_lab_crash.log if it exists.
    echo.
)
if defined PAUSE_ON_EXIT (
    echo.
    pause
) else if not "%RESULT%"=="0" (
    pause
)
exit /b %RESULT%
