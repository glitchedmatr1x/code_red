@echo off
setlocal
set PYTHON_CMD=py -3
%PYTHON_CMD% --version >nul 2>nul
if errorlevel 1 set PYTHON_CMD=python
if "%~1"=="" goto usage
%PYTHON_CMD% tools\codered_content_rpf_deep_scan.py %*
if errorlevel 1 (
  echo.
  echo Code RED Content RPF Deep Scan failed.
  echo Check the JSON/CSV reports in your --out folder if any were written.
  pause
  exit /b 1
)
exit /b 0
:usage
echo Code RED Content RPF Deep Scanner
echo.
echo Example:
echo   set CODERED_RDR_EXE=D:\Games\Red Dead Redemption\rdr.exe
echo   Run_CodeRED_Content_RPF_DeepScan.bat scan --rpf content.rpf --out logs\content_rpf_deep_scan --export-candidates
echo.
pause
exit /b 2
