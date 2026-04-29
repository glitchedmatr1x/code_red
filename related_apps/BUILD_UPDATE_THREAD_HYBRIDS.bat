@echo off
setlocal
cd /d "%~dp0"
if exist content.rpf (
  py -3 build_update_thread_hybrids.py content.rpf
) else (
  echo Put this BAT, build_update_thread_hybrids.py, and content.rpf in the same folder,
  echo or drag content.rpf onto build_update_thread_hybrids.py.
  pause
)
pause
