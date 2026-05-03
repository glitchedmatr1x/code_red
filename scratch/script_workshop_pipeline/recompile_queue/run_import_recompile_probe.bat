@echo off
setlocal
echo Code RED Script Import/Recompile Probe
echo This helper does not overwrite archives. It validates source candidates only.
echo.
if not exist RECOMPILE_QUEUE.json (
  echo [ERROR] RECOMPILE_QUEUE.json missing. Re-run tools\codered_script_pipeline.py.
  exit /b 1
)
echo Review RECOMPILE_QUEUE.json and Script Compile Lab validation before adding compiler commands.
echo Proof output target: ..\..\logs\CodeRED_Script_Import_Recompile_Proof.txt
endlocal
