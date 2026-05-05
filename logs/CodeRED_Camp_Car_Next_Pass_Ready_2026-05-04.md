# Code RED Camp Car Next Pass Ready — 2026-05-04

## Added

```text
script_compiling/sccl/package_camp_car_compile_proof_windows.ps1
tools/codered_scan_camp_car_import_candidates.py
```

## Camp-car proof package command

Run after a successful camp-car compile:

```powershell
powershell -ExecutionPolicy Bypass -File script_compiling\sccl\package_camp_car_compile_proof_windows.ps1
```

This packages:

```text
artifact/camp_car_probe.xsc
source/main.c
headers/include/
reports/
COMPILE_PROOF_MANIFEST.json
README.md
```

Boundary: proof-only, not installed/imported.

## Read-only import candidate scan

Run from repo root:

```powershell
py -3 tools\codered_scan_camp_car_import_candidates.py --root .
```

Or scan a larger extracted workspace if needed:

```powershell
py -3 tools\codered_scan_camp_car_import_candidates.py --root "D:\Games\Red Dead Redemption\Code_RED"
```

Outputs:

```text
logs/camp_car_import_candidate_scan.json
logs/camp_car_import_candidate_scan.csv
logs/camp_car_import_candidate_scan.md
```

## What the scanner looks for

```text
camp/playerCamp/cam_playerCamp
vehicle/car/truck/wagon
WSI/WGD/gringo/Vehicle_Generator/car_gringo/PlayerCar
release64/scripting/.xsc/.wsc/.sco
```

## Boundary

The scanner is read-only. It does not modify archives or game files.

## Next safe objective

Use scanner results to pick candidate camp/placement/script paths before building any copied-archive import proof.
