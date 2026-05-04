@echo off
setlocal
cd /d "%~dp0\..\..\.."
echo [CodeRED] Running timeout-safe SC-CL vehicle menu compile probe...
py -3 tools\codered_sccl_safe_compile_probe.py --timeout 90
set RC=%ERRORLEVEL%
echo [CodeRED] Safe compile probe exit: %RC%
echo [CodeRED] Report: logs\CodeRED_SCCL_Safe_Compile_Probe_Report.md
echo [CodeRED] Output: logs\CodeRED_SCCL_Safe_Compile_Probe_Output.txt
exit /b %RC%
