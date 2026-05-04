# Milestone — SC-CL Compile Lane Proven

Date: 2026-05-04

## Status

The Code RED SC-CL / script-compiling lane is now proven enough for controlled proof-script builds.

## Proven result

```text
SC-CL exit: 0
Artifact count: 1
script_compiling\sccl\output\vehicle_menu_probe\vehicle_menu_probe.xsc
length: 1462
sha1: F6BDB733B54EAAAE757984008A7804F489471A5D
```

## What was fixed

- SC-CL runtime/DLL staging now works.
- Fake/proof shim headers are detected and rejected.
- Real SC-CL headers are promoted into the active lane.
- The vehicle probe validates against the real `vector3` `CREATE_ACTOR_IN_LAYOUT` signature.
- The active compile batch produces a real `.xsc` artifact.
- Output path handling is now clean enough to produce the artifact in the expected folder.
- Stale duplicate output artifacts are cleaned before compile.

## Current active lane

```text
script_compiling/sccl/
  compile_vehicle_menu_probe_windows.bat
  promote_real_sccl_headers_windows.ps1
  stage_sccl_runtime_windows.ps1
  diagnose_sccl_runtime_windows.ps1
  sccl_lane_doctor_windows.ps1
  inspect_vehicle_menu_output_windows.ps1
  projects/vehicle_menu_probe/src/main.c
```

## Known harmless warning

SC-CL prints a compilation database warning:

```text
Could not auto-detect compilation database
Running without flags.
```

This is not blocking the current proof because compilation succeeds and outputs the expected `.xsc` artifact.

## Important boundary

Do not install/import this compiled script into the game yet.

This milestone proves the compile lane, not the archive install/import lane.

## Next safe pass

1. Package the compiled proof artifact with source/header/compiler metadata.
2. Add a repeatable proof-package script.
3. Decide where `.xsc` belongs only after archive import/override behavior is separately proven.
4. Keep the full Code RED runtime menu in the ScriptHook / AI Trainer lane until native signatures are proven one at a time.
