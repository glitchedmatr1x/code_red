@echo off
setlocal EnableExtensions

echo [CodeRED] Exporting experimental camp car WSC candidate from XSC...

set "ROOT=%~dp0..\..\"
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

py -3 "%ROOT%\tools\codered_xsc_to_wsc_candidate.py" ^
  --input "%ROOT%\script_compiling\sccl\output\camp_car_probe\camp_car_probe.xsc" ^
  --output "%ROOT%\script_compiling\sccl\output\camp_car_probe_wsc\camp_car_probe.wsc" ^
  --report "%ROOT%\script_compiling\sccl\output\camp_car_probe_wsc\camp_car_probe_wsc_candidate_report.json"

set "EXITCODE=%ERRORLEVEL%"
echo [CodeRED] WSC candidate export exit: %EXITCODE%
exit /b %EXITCODE%
