@echo off
setlocal
cd /d "%~dp0"
py -3 tools\codered_sccl_finalize_build.py --validate
if errorlevel 1 (
  echo.
  echo Code RED SC-CL finalizer needs attention. Review logs\CodeRED_SCCL_Finalize_Build_Report.md
  pause
  exit /b 1
)
echo.
echo Code RED SC-CL finalizer passed. Review logs\CodeRED_SCCL_Finalize_Build_Report.md
pause
endlocal
