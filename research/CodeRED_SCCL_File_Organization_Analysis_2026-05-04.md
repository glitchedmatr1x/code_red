# Code RED SC-CL File Organization Analysis — 2026-05-04

## Scope

Focused only on the SC-CL / script-compiling lane.

## Findings

### 1. Active headers were still proof shims

The active lane had headers containing:

```text
Minimal Code RED proof natives
source-proof shims
```

Those headers can pass symbol-name checks but are not valid as real SC-CL compile headers.

### 2. Real headers exist elsewhere in repo

A real SC-CL header source exists under:

```text
SC-CL-master/bin/include/RDR/natives32.h
```

It contains the real SC-CL include-library marker and real native declarations.

### 3. Source still had a bad CREATE_ACTOR_IN_LAYOUT shape

The active vehicle probe source still used the old loose-float actor creation style. Real SC-CL expects:

```c
CREATE_ACTOR_IN_LAYOUT(Layout Layout, const char* ActorName, eActor ActorID, vector3 Position, vector3 Rotation)
```

The source was updated to use `vector3 spawnPos` and `vector3 spawnRot`.

### 4. Validator was too weak

The validator checked that names existed, but it did not reject fake/proof shim headers. It now checks for:

- real-looking SC-CL header markers
- fake shim markers
- vector3 create-actor signature
- source vector3 usage
- real 8-argument `_PRINT_SUBTITLE` call shape

### 5. Compiler runtime is still the current external blocker

Exit `-1073741515` means `0xC0000135`, a missing DLL/runtime after SC-CL.exe is found.

## Files changed

```text
script_compiling/sccl/projects/vehicle_menu_probe/src/main.c
script_compiling/sccl/projects/vehicle_menu_probe/scripts/validate_vehicle_menu_probe.py
script_compiling/sccl/promote_real_sccl_headers_windows.ps1
script_compiling/sccl/sccl_lane_doctor_windows.ps1
script_compiling/sccl/README.md
```

## New command order

```powershell
powershell -ExecutionPolicy Bypass -File script_compiling\sccl\sccl_lane_doctor_windows.ps1
powershell -ExecutionPolicy Bypass -File script_compiling\sccl\promote_real_sccl_headers_windows.ps1
py -3 script_compiling\sccl\projects\vehicle_menu_probe\scripts\validate_vehicle_menu_probe.py
powershell -ExecutionPolicy Bypass -File script_compiling\sccl\stage_sccl_runtime_windows.ps1
script_compiling\sccl\compile_vehicle_menu_probe_windows.bat
```

## Policy

Do not delete proof/source material. Preserve obsolete attempts under `script_compiling/sccl/obsolete/`, but keep the active lane strict and real-header based.
