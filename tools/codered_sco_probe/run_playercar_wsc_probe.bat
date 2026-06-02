@echo off
setlocal
cd /d "%~dp0..\.."
py -3 tools\codered_sco_probe\codered_rpf_experiment.py ^
  --rpf "D:\Games\Red Dead Redemption\content.rpf" ^
  --entry "content/scripting/gringo/SimpleGringo/playercar.wsc" ^
  --out build\codered_real_probe\playercar_wsc_nochange ^
  --find-entry-substring playercar ^
  --find-entry-substring player_car ^
  --find-entry-substring SimpleGringo ^
  --find-entry-substring gringo
endlocal
