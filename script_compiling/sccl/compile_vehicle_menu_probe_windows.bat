@echo off
setlocal

echo [CodeRED] Direct SC-CL vehicle menu compile probe...

set "SCCL_ROOT=%~dp0"
set "PROJECT=%SCCL_ROOT%projects\vehicle_menu_probe"
set "SRC=%PROJECT%\src\main.c"
set "INCLUDE=%PROJECT%\include"
set "OUT=%SCCL_ROOT%output\vehicle_menu_probe"

if not exist "%SRC%" (
  echo [CodeRED] Missing source: %SRC%
  exit /b 2
)

if not exist "%INCLUDE%\RDR\natives32.h" (
  echo [CodeRED] Missing include: %INCLUDE%\RDR\natives32.h
  exit /b 2
)

if "%SCCL_EXE%"=="" (
  set "SCCL_EXE=%SCCL_ROOT%output\SC-CL.exe"
)

if not exist "%SCCL_EXE%" (
  echo [CodeRED] SC-CL.exe not found.
  echo [CodeRED] Put SC-CL.exe at:
  echo   %SCCL_ROOT%output\SC-CL.exe
  echo.
  echo [CodeRED] Or set:
  echo   set SCCL_EXE=C:\path\to\SC-CL.exe
  exit /b 3
)

if not exist "%OUT%" mkdir "%OUT%"

echo [CodeRED] Compiler: %SCCL_EXE%
echo [CodeRED] Source:   %SRC%
echo [CodeRED] Include:  %INCLUDE%
echo [CodeRED] Output:   %OUT%

"%SCCL_EXE%" ^
  -target=RDR_#SC ^
  -platform=X360 ^
  -out-dir="%OUT%" ^
  -name=vehicle_menu_probe ^
  -extra-arg=-I"%INCLUDE%" ^
  "%SRC%"

set "EXITCODE=%ERRORLEVEL%"
echo [CodeRED] SC-CL exit: %EXITCODE%
exit /b %EXITCODE%