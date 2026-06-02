@echo off
setlocal
cd /d "%~dp0..\.."
py -3 tools\codered_sco_probe\codered_rpf_experiment.py ^
  --rpf "D:\Games\Red Dead Redemption\content.rpf" ^
  --entry "content/release64/init/rdr2init.wsc" ^
  --out build\codered_real_probe\rdr2init_wsc_nochange ^
  --find-entry-substring rdr2init
endlocal
