# Code RED Camp Car Workbench Run — 2026-05-04

## Command

```powershell
py -3 tools\codered_camp_car_workbench.py --root "C:\Users\glitc\OneDrive\Desktop\CodeRED_RPF_Extracts"
```

## Result

```text
Candidates: 300
JSON: logs\camp_car_workbench.json
CSV: logs\camp_car_workbench.csv
MD: logs\camp_car_workbench.md
```

## Key ranked groups

```text
playercamp_hosts: 5
  score=89 content/release64/scripting/gringo/commonscripts/playercamp01_gringo.wsc
  score=41 content/release64/scripting/gringo/commonscripts/playercamp02_gringo.wsc
  score=41 content/release64/scripting/gringo/commonscripts/playercamp03_gringo.wsc

vehicle_script_leads: 5
  score=66 content/release64/scripting/gringo/commonscripts/vehicle_generator.wsc
  score=59 content/release64/scripting/gringo/commonscripts/car_gringo.wsc
  score=59 content/release64/scripting/gringo/commonscripts/playercar.wsc

descriptor_hosts: 40
placement_dictionary_leads: 13
dlc_zombie_examples: 40
```

## Interpretation

The normal-game camp/vehicle gringo lead set is now clear:

```text
playercamp01_gringo.wsc
vehicle_generator.wsc
car_gringo.wsc
playercar.wsc
gen_vehicle_brain.wsc
```

The workbench did not prove an archive/import path yet. It proved that Code RED can rank and inspect the extracted RPF workspace from a Desktop folder without putting extracted game data into GitHub.

## Boundary

No archives or game files were modified.

Do not replace playercamp scripts directly yet.
Do not bulk patch WSI/WGD/refgroup files.
Do not install camp_car_probe.xsc until import/override behavior is proven.

## Next safe step

Build the SC-CL `RDR_SCO` output path for `camp_car_probe`, because several gringo/script examples use `.sco` slots while the current camp-car proof is `.xsc` only.

Then package both outputs and decide whether the import proof should test `.xsc`, `.sco`, or both in a copied archive only.
