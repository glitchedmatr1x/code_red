# Code RED SC-CL Proof Packager Ready — 2026-05-04

## Added

```text
script_compiling/sccl/package_vehicle_menu_compile_proof_windows.ps1
```

## Purpose

Package the proven SC-CL vehicle menu compile artifact without installing it into the game.

The packager collects:

```text
artifact/vehicle_menu_probe.xsc
source/main.c
headers/include/
reports/
COMPILE_PROOF_MANIFEST.json
README.md
```

It records SHA1 hashes for:

```text
vehicle_menu_probe.xsc
SC-CL.exe
main.c
active project headers
```

## Command

Run after a successful compile:

```powershell
powershell -ExecutionPolicy Bypass -File script_compiling\sccl\package_vehicle_menu_compile_proof_windows.ps1
```

## Boundary

Proof package only. Do not install/import this compiled script into the game yet.

The SC-CL compile lane is proven. The archive install/import lane remains separate and still needs proof.
