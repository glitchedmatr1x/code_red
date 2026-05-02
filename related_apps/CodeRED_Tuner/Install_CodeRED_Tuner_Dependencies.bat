@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set QUIET=0
if "%~1"=="--quiet" set QUIET=1
set PYTHON_CMD=
where py >nul 2>nul
if %ERRORLEVEL%==0 set PYTHON_CMD=py -3
if "%PYTHON_CMD%"=="" (
  where python >nul 2>nul
  if %ERRORLEVEL%==0 set PYTHON_CMD=python
)
if "%PYTHON_CMD%"=="" (
  echo Python was not found. Install Python 3.10+ and run this file again.
  if "%QUIET%"=="0" pause
  exit /b 1
)
%PYTHON_CMD% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
  echo Tkinter is missing from this Python install. Reinstall Python and enable tcl/tk.
)
%PYTHON_CMD% -c "import importlib.util, sys; missing=[m for m in ('pygame','panda3d','cryptography') if importlib.util.find_spec(m) is None]; print('missing=' + ','.join(missing)); sys.exit(1 if missing else 0)" > logs\dependency_check_latest.txt 2>&1
if errorlevel 1 (
  echo Installing missing Code RED dependencies...
  %PYTHON_CMD% -m pip install -r requirements.txt
) else (
  echo Code RED dependencies already available.
)
if "%QUIET%"=="0" pause
exit /b 0
