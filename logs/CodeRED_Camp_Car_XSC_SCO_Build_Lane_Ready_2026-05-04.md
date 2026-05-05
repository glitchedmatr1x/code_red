# Code RED Camp Car XSC/SCO Build Lane Ready — 2026-05-04

## Added

```text
script_compiling/sccl/compile_camp_car_probe_sco_windows.bat
script_compiling/sccl/compile_camp_car_probe_all_windows.bat
```

## Updated

```text
script_compiling/sccl/package_camp_car_compile_proof_windows.ps1
```

The packager now includes both outputs when present:

```text
artifact/camp_car_probe.xsc
artifact/camp_car_probe.sco
```

## Command order

Run from repo root:

```powershell
script_compiling\sccl\compile_camp_car_probe_all_windows.bat
powershell -ExecutionPolicy Bypass -File script_compiling\sccl\package_camp_car_compile_proof_windows.ps1
```

## Why

The camp-car proof already compiled as `.xsc`. Several extracted gringo/script examples use `.sco`, so this pass adds a controlled `RDR_SCO` build for the same source.

## Boundary

Proof outputs only.

No archive import.
No camp file replacement.
No game install.
