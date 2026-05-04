# Code RED SC-CL Lane

This is the active SC-CL compile lane. It is for **small, verified SC-CL proof scripts**, not the full Code RED trainer/menu.

## Current active project

```text
script_compiling/sccl/projects/vehicle_menu_probe/
```

## Correct order

Run these from the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File script_compiling\sccl\sccl_lane_doctor_windows.ps1
powershell -ExecutionPolicy Bypass -File script_compiling\sccl\promote_real_sccl_headers_windows.ps1
py -3 script_compiling\sccl\projects\vehicle_menu_probe\scripts\validate_vehicle_menu_probe.py
powershell -ExecutionPolicy Bypass -File script_compiling\sccl\stage_sccl_runtime_windows.ps1
script_compiling\sccl\compile_vehicle_menu_probe_windows.bat
```

## Layout

```text
script_compiling/sccl/
  compile_vehicle_menu_probe_windows.bat    direct compile command
  promote_real_sccl_headers_windows.ps1     replaces fake proof headers with real SC-CL headers
  stage_sccl_runtime_windows.ps1            stages SC-CL.exe and nearby DLL/runtime files
  sccl_lane_doctor_windows.ps1              read-only health report
  include/                                  active shared headers
  output/                                   local staged compiler/output; not source of truth
  projects/vehicle_menu_probe/              active proof source
  obsolete/                                 preserved old compile attempts
```

## Header rule

Do not compile with proof shim headers.

Bad marker:

```text
Minimal Code RED proof natives
```

Good marker:

```text
This file is part of SC-CL's include library
```

The real `CREATE_ACTOR_IN_LAYOUT` signature uses:

```c
CREATE_ACTOR_IN_LAYOUT(Layout Layout, const char* ActorName, eActor ActorID, vector3 Position, vector3 Rotation)
```

The active vehicle probe should use `vector3` position/rotation arguments, not loose float coordinates.

## Compiler runtime rule

If compile exits:

```text
-1073741515
```

that is Windows `0xC0000135`: SC-CL.exe was found, but a required DLL/runtime could not be loaded.

Try:

```powershell
powershell -ExecutionPolicy Bypass -File script_compiling\sccl\stage_sccl_runtime_windows.ps1
```

If it still fails, install/repair Microsoft Visual C++ Redistributable 2015-2022 x64 or stage the missing LLVM/Clang runtime DLLs beside `SC-CL.exe`.

## Policy

- Preserve old compile attempts under `obsolete/`.
- Do not delete proof/source material.
- Do not build the full Code RED menu through SC-CL until native signatures are verified one at a time.
- Use ScriptHook / AI Trainer for the real runtime Code RED menu.
