@echo off
setlocal
cd /d "%~dp0"
echo Code RED Xbox ISO / XDVDFS Tool
if "%~1"=="" (
  echo Usage examples:
  echo   Run_XISO_Tool.bat index "D:\Games\RDR_DISC2.iso"
  echo   Run_XISO_Tool.bat extract "D:\Games\RDR_DISC2.iso" layer_0.rpf extracted_iso_files
  echo   Run_XISO_Tool.bat plan-replace "D:\Games\RDR_DISC2.iso" layer_0.rpf "D:\CodeRED\work\layer_0_modded.rpf"
  echo   Run_XISO_Tool.bat replace-copy-safe "D:\Games\RDR_DISC2.iso" layer_0.rpf "D:\CodeRED\work\layer_0_modded.rpf" "D:\Games\RDR_DISC2_CodeRED.iso"
  echo   Run_XISO_Tool.bat export-overlay "D:\Games\RDR_DISC2.iso" layer_0.rpf "D:\CodeRED\work\layer_0_modded.rpf" "D:\CodeRED\xenia_overlay"
  echo   Run_XISO_Tool.bat nested-find "D:\Games\RDR_DISC2.iso" layer_0.rpf "OLD_TEXT"
  echo   Run_XISO_Tool.bat nested-patch-copy "D:\Games\RDR_DISC2.iso" layer_0.rpf "OLD_TEXT" "NEW_TEXT" "D:\Games\RDR_DISC2_CodeRED.iso"
  echo.
  python tools\codered_xiso_tool.py --help
  exit /b 0
)
if /I "%~1"=="index" (
  python tools\codered_xiso_tool.py index "%~2" --out reports\xiso
  exit /b %ERRORLEVEL%
)
if /I "%~1"=="extract" (
  python tools\codered_xiso_tool.py extract "%~2" --path "%~3" --out "%~4"
  exit /b %ERRORLEVEL%
)
if /I "%~1"=="plan-replace" (
  python tools\codered_xiso_tool.py plan-replace "%~2" --path "%~3" --replacement "%~4" --out reports\xiso_replace_plan.json
  exit /b %ERRORLEVEL%
)
if /I "%~1"=="replace-copy-safe" (
  python tools\codered_xiso_tool.py replace-copy-safe "%~2" --path "%~3" --replacement "%~4" --output-iso "%~5" --report reports\xiso_replace_safe_report.json
  exit /b %ERRORLEVEL%
)
if /I "%~1"=="export-overlay" (
  python tools\codered_xiso_tool.py export-overlay "%~2" --path "%~3" --replacement "%~4" --out "%~5"
  exit /b %ERRORLEVEL%
)
if /I "%~1"=="nested-find" (
  python tools\codered_xiso_tool.py nested-find "%~2" --path "%~3" --needle "%~4" --out reports\xiso_nested_find.json
  exit /b %ERRORLEVEL%
)
if /I "%~1"=="nested-patch-copy" (
  python tools\codered_xiso_tool.py nested-patch-copy "%~2" --path "%~3" --old "%~4" --new "%~5" --output-iso "%~6" --report reports\xiso_nested_patch_copy_report.json
  exit /b %ERRORLEVEL%
)
python tools\codered_xiso_tool.py %*
