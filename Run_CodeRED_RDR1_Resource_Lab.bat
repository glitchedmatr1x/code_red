@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Code RED RDR1 Resource Lab launcher.
rem Double-click safe: when no arguments are supplied, run a visible status check and pause.

set "PAUSE_ON_EXIT="
if "%~1"=="" (
    set "PAUSE_ON_EXIT=1"
    echo Code RED RDR1 Resource Lab
    echo.
    echo No command was supplied, so this launcher is running a startup/status check.
    echo.
    echo Common commands after this window opens successfully:
    echo   Run_CodeRED_RDR1_Resource_Lab.bat analyze --input imports\commongringos.wgd --out logs\rdr1_resource_lab\commongringos
    echo   Run_CodeRED_RDR1_Resource_Lab.bat search-refs --input imports\commongringos.wgd --query revolver --out logs\rdr1_resource_lab\commongringos_search
    echo   Run_CodeRED_RDR1_Resource_Lab.bat override-string --input imports\commongringos.wgd --old OLD --new NEW --out patches\commongringos_mod.wgd --patch-root patches\wgd_override --internal-path commongringos.wgd
    echo   Run_CodeRED_RDR1_Resource_Lab.bat weapon-lasso-override --input imports\commongringos.wgd --out patches\commongringos_lasso_override.wgd --patch-root patches\wgd_lasso_override --internal-path commongringos.wgd
    echo   Run_CodeRED_RDR1_Resource_Lab.bat patch-archive --archive game\gringores.rpf --patch-root patches\wgd_override --out game\patched\gringores.rpf
    echo.
)

if not exist "tools\codered_rdr1_resource_lab.py" (
    echo ERROR: tools\codered_rdr1_resource_lab.py was not found.
    echo.
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
echo.
echo Install Python 3, or open PowerShell in this folder and try:
echo   py -3 tools\codered_rdr1_resource_lab.py status
echo.
exit /b 1

:run_lab
echo Using Python command: %PY_CMD%
echo.
%PY_CMD% tools\codered_rdr1_resource_lab.py %*
exit /b %ERRORLEVEL%

:end
if not "%RESULT%"=="0" (
    echo.
    echo Code RED RDR1 Resource Lab failed.
    echo Check logs\rdr1_resource_lab\rdr1_resource_lab_crash.log if it exists.
    echo.
)
if defined PAUSE_ON_EXIT (
    echo.
    pause
) else if not "%RESULT%"=="0" (
    pause
)
exit /b %RESULT%
